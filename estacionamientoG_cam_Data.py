#!/usr/bin/env python3

################################################################################
# SPDX-FileCopyrightText: Copyright (c) 2019-2021 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
################################################################################

import sys
sys.path.append('../')
import gi
import configparser
gi.require_version('Gst', '1.0')
from gi.repository import GObject, Gst
from gi.repository import GLib
from ctypes import *
import time
import sys
import math
import platform
from common.is_aarch_64 import is_aarch64
from common.bus_call import bus_call
from common.FPS import GETFPS

import pyds

# Mqtt
import paho.mqtt.client as mqtt
broker_ip = "10.244.140.146"  # IP DE LA PI
topic = "deepstream/car_count"

client = mqtt.Client()
client.connect(broker_ip, 1883)

fps_streams={}

MAX_DISPLAY_LEN=64
PGIE_CLASS_ID_VEHICLE = 0
MUXER_OUTPUT_WIDTH=640
MUXER_OUTPUT_HEIGHT=480
MUXER_BATCH_TIMEOUT_USEC=4000000
GST_CAPS_FEATURES_NVMM="memory:NVMM"
OSD_PROCESS_MODE= 0
OSD_DISPLAY_TEXT= 1
pgie_classes_str= ["Vehicle"]

line_count = {
    "Entry": 0,
    "Exit": 0
}

# tiler_sink_pad_buffer_probe  will extract metadata received on OSD sink pad
# and update params for drawing rectangle, object information etc.
def tiler_src_pad_buffer_probe(pad,info,u_data):
    frame_number=0
    num_rects=0
    gst_buffer = info.get_buffer()
    if not gst_buffer:
        print("Unable to get GstBuffer ")
        return Gst.PadProbeReturn.OK

    # Retrieve batch metadata from the gst_buffer
    # Note that pyds.gst_buffer_get_nvds_batch_meta() expects the
    # C address of gst_buffer as input, which is obtained with hash(gst_buffer)
    batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
    l_frame = batch_meta.frame_meta_list
    frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
    frame_number=frame_meta.frame_num
    l_obj=frame_meta.obj_meta_list
    num_rects = frame_meta.num_obj_meta
    obj_counter = {
    PGIE_CLASS_ID_VEHICLE:0}
    while l_obj is not None:
        try: 
            # Casting l_obj.data to pyds.NvDsObjectMeta
            obj_meta=pyds.NvDsObjectMeta.cast(l_obj.data)
        except StopIteration:
            break
        obj_counter[obj_meta.class_id] += 1
        l_user_meta = obj_meta.obj_user_meta_list
        while l_user_meta:
            try:
                user_meta = pyds.NvDsUserMeta.cast(l_user_meta.data)
                if user_meta.base_meta.meta_type == pyds.nvds_get_user_meta_type("NVIDIA.DSANALYTICSOBJ.USER_META"):
                    user_meta_data = pyds.NvDsAnalyticsObjInfo.cast(user_meta.user_meta_data)
                    if user_meta_data.lcStatus:
                        for line_name in user_meta_data.lcStatus:
                            client.publish(topic, line_name)
                            line_count[line_name] += 1
                            total_space = line_count["Entry"] - line_count["Exit"]
                            print(f"Hay {total_space} espacios ocupados")

            except StopIteration:
                break
            try:
                l_user_meta = l_user_meta.next
            except StopIteration:
                break
        try: 
                l_obj=l_obj.next
        except StopIteration:
                break
    #print("Frame Number=", frame_number, "Number of Objects=",num_rects,"Vehicle_count=",obj_counter[PGIE_CLASS_ID_VEHICLE])

    #-- Probe user meta (analytics) -------------

    # Get frame rate through this probe
    fps_streams["stream0"].get_fps()

    return Gst.PadProbeReturn.OK


def main(args):
    number_sources=1
    # Standard GStreamer initialization
    GObject.threads_init()
    Gst.init(None)

    # Create gstreamer elements */
    # Create Pipeline element that will form a connection of other elements
    print("Creating Pipeline \n ")
    pipeline = Gst.Pipeline()

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")
    
    

    # -------------------- PLUGIN INITIALIZATION --------------------

    # ---------- [source] ----------
    print("Creating Source \n ")
    source = Gst.ElementFactory.make("v4l2src", "usb-cam-source")
    if not source:
        sys.stderr.write(" Unable to create Source \n")

    #---------- [v4l2src] ----------

    caps_v4l2src = Gst.ElementFactory.make("capsfilter", "v4l2src_caps")
    if not caps_v4l2src:
        sys.stderr.write(" Unable to create v4l2src capsfilter \n")

    #---------- [vidconvsrc] ----------

    vidconvsrc = Gst.ElementFactory.make("videoconvert", "convertor_src1")
    if not vidconvsrc:
        sys.stderr.write(" Unable to create videoconvert \n")

    #---------- [nvvidconvsrc] ----------
        # nvvideoconvert to convert incoming raw buffers to NVMM Mem (NvBufSurface API)
    nvvidconvsrc = Gst.ElementFactory.make("nvvideoconvert", "convertor_src2")
    if not nvvidconvsrc:
        sys.stderr.write(" Unable to create Nvvideoconvert \n")

    #---------- [caps_vidconvsrc] ----------

    caps_vidconvsrc = Gst.ElementFactory.make("capsfilter", "nvmm_caps")
    if not caps_vidconvsrc:
        sys.stderr.write(" Unable to create capsfilter \n")

    # ---------- [streammux] ----------

    print("Creating streamux \n ")
    # Create nvstreammux instance to form batches from one or more sources.
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    if not streammux:
        sys.stderr.write(" Unable to create NvStreamMux \n")

    


    # ---------- [queues] ----------
    
    queue1=Gst.ElementFactory.make("queue","queue1")
    queue2=Gst.ElementFactory.make("queue","queue2")
    queue3=Gst.ElementFactory.make("queue","queue3")
    queue4=Gst.ElementFactory.make("queue","queue4")
    queue5=Gst.ElementFactory.make("queue","queue5")
    pipeline.add(queue1)
    pipeline.add(queue2)
    pipeline.add(queue3)
    pipeline.add(queue4)
    pipeline.add(queue5)

    # ---------- [PGIE] ----------

    print("Creating Pgie \n ")
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    if not pgie:
        sys.stderr.write(" Unable to create pgie \n")

    #---------- [video converter] ----------

    print("Creating nvvidconv \n ")
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    if not nvvidconv:
        sys.stderr.write(" Unable to create nvvidconv \n")

    #---------- [sinkpad] ----------
    sinkpad = streammux.get_request_pad("sink_0")
    if not sinkpad:
        sys.stderr.write(" Unable to get the sink pad of streammux \n")

    # ----------- [srcpad] ----------

    srcpad = caps_vidconvsrc.get_static_pad("src")
    if not srcpad:
        sys.stderr.write(" Unable to get source pad of caps_vidconvsrc \n")

     #---------- [OSD] ----------
    print("Creating nvosd \n ")
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")
    if not nvosd:
        sys.stderr.write(" Unable to create nvosd \n")
    

    #---------- [transform] ----------

    if(is_aarch64()):
        print("Creating transform \n ")
        transform=Gst.ElementFactory.make("nvegltransform", "nvegl-transform")
        if not transform:
            sys.stderr.write(" Unable to create transform \n")

    #---------- [sink] ----------

    print("Creating EGLSink \n")
    sink = Gst.ElementFactory.make("nveglglessink", "nvvideo-renderer")
    if not sink:
        sys.stderr.write(" Unable to create egl sink \n")


    #---------- [tracker] ----------
    print("Creating tracker \n")
    nvtracker = Gst.ElementFactory.make("nvtracker", "tracker")
    if not nvtracker:
        sys.stderr.write(" Unable to create tracker \n")

    #---------- [nvds-analytics] ----------
    print("Creating nvdsanalytics \n")
    nvdsanalytics = Gst.ElementFactory.make("nvdsanalytics", "analytics")
    if not nvdsanalytics:
        sys.stderr.write(" Unable to create nvdsanalytics \n")

    # -------------------- PLUGIN PROPERTIES --------------------
    
    # ---------- [caps_v4l2src] ----------
    caps_v4l2src.set_property('caps', Gst.Caps.from_string("video/x-raw, framerate=30/1"))

    #---------- [caps_vidconvsrc] ----------

    caps_vidconvsrc.set_property('caps', Gst.Caps.from_string("video/x-raw(memory:NVMM)"))

    #---------- [source] ----------
    source.set_property('device', args[1])

    # ---------- [streammux] ----------
    streammux.set_property('width', 640)
    streammux.set_property('height', 480)
    streammux.set_property('batch-size', 1)
    streammux.set_property('batched-push-timeout', 4000000)

    # ---------- [PGIE] ----------

    pgie.set_property('config-file-path', "/opt/nvidia/deepstream/deepstream-6.0/deepstream_python_apps/apps/ParkSight/config_infer_primary.txt")
    pgie_batch_size=pgie.get_property("batch-size")
    if(pgie_batch_size != number_sources):
        print("WARNING: Overriding infer-config batch-size",pgie_batch_size," with number of sources ", number_sources," \n")
        pgie.set_property("batch-size",number_sources)

    #---------- [OSD] ----------

    nvosd.set_property('process-mode',OSD_PROCESS_MODE)
    nvosd.set_property('display-text',OSD_DISPLAY_TEXT)
    
    #---------- [sink] ----------

    sink.set_property("qos",1)
    sink.set_property("sync", False)

    #---------- [tracker] ----------

    nvtracker.set_property("tracker-width", 640)
    nvtracker.set_property("tracker-height", 480)
    nvtracker.set_property("ll-lib-file", "/opt/nvidia/deepstream/deepstream-6.0/lib/libnvds_nvmultiobjecttracker.so" )
    nvtracker.set_property("ll-config-file", "config_tracker_NvDCF_perf.yml")
    nvtracker.set_property("enable-batch-process", 1)
    nvtracker.set_property("enable-past-frame", 1)
    nvtracker.set_property("display-tracking-id", 1)

    #---------- [nvds-analytics] ----------

    nvdsanalytics.set_property("config-file", "/opt/nvidia/deepstream/deepstream-6.0/deepstream_python_apps/apps/ParkSight/config_nvdsanalytics.txt")

    # --------------------- PLUGIN ADDITION AND LINKING --------------------

    print("Adding elements to Pipeline \n")
    pipeline.add(source)
    pipeline.add(caps_v4l2src)
    pipeline.add(vidconvsrc)
    pipeline.add(nvvidconvsrc)
    pipeline.add(caps_vidconvsrc)
    pipeline.add(streammux)
    pipeline.add(pgie)
    pipeline.add(nvvidconv)
    pipeline.add(nvosd)  
    pipeline.add(transform)
    pipeline.add(sink)
    pipeline.add(nvtracker)
    pipeline.add(nvdsanalytics)

    print("Linking elements in the Pipeline \n")
    source.link(caps_v4l2src)
    caps_v4l2src.link(vidconvsrc)
    vidconvsrc.link(nvvidconvsrc)
    nvvidconvsrc.link(caps_vidconvsrc)
    srcpad.link(sinkpad)


    streammux.link(queue1)
    queue1.link(pgie)
    pgie.link(queue2)
    queue2.link(nvtracker)
    nvtracker.link(queue3)
    queue3.link(nvdsanalytics)
    nvdsanalytics.link(queue4)
    queue4.link(nvvidconv)
    nvvidconv.link(queue5)
    queue5.link(nvosd)
    nvosd.link(transform)
    transform.link(sink)  

    # create an event loop and feed gstreamer bus mesages to it
    loop = GObject.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect ("message", bus_call, loop)
    fps_streams["stream0"] = GETFPS(0)
    tiler_src_pad=nvdsanalytics.get_static_pad("src")
    if not tiler_src_pad:
        sys.stderr.write(" Unable to get src pad \n")
    else:
        tiler_src_pad.add_probe(Gst.PadProbeType.BUFFER, tiler_src_pad_buffer_probe, 0)

    # List the sources
    print("Now playing...")
    for i, source in enumerate(args):
        if (i != 0):
            print(i, ": ", source)

    print("Starting pipeline \n")
    # start play back and listed to events		
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass
    # cleanup
    print("Exiting app\n")
    pipeline.set_state(Gst.State.NULL)
    client.disconnect()

if __name__ == '__main__':
    sys.exit(main(sys.argv))
