FROM nvcr.io/nvidia/deepstream-l4t:6.0.1-triton

ENV DISPLAY=:0
ENV QT_X11_NO_MITSHM=1

USER root

WORKDIR /opt/nvidia/deepstream/deepstream-6.0/

RUN apt-get update && apt-get install -y --no-install-recommends \
        python3-pip \
        python3-setuptools \
        python3-wheel \
        wget \
        git \
    && rm -rf /var/lib/apt/lists/*


RUN wget https://github.com/NVIDIA-AI-IOT/deepstream_python_apps/releases/download/v1.1.1/pyds-1.1.1-py3-none-linux_aarch64.whl -P /tmp \
    && pip3 install /tmp/pyds-1.1.1-py3-none-linux_aarch64.whl \
    && pip3 install paho-mqtt

RUN git clone https://github.com/NVIDIA-AI-IOT/deepstream_python_apps.git \
    && cd deepstream_python_apps \
    && git checkout v1.1.1

WORKDIR /opt/nvidia/deepstream/deepstream-6.0/samples/models/

RUN mkdir -p trafficcamnet_pruned_onnx_v1.0.4

COPY models/trafficcamnet_pruned_onnx_v1.0.4/resnet18_trafficcamnet_pruned.onnx trafficcamnet_pruned_onnx_v1.0.4/
COPY models/trafficcamnet_pruned_onnx_v1.0.4/labels.txt trafficcamnet_pruned_onnx_v1.0.4/
COPY models/trafficcamnet_pruned_onnx_v1.0.4/nvinfer_config.txt trafficcamnet_pruned_onnx_v1.0.4/
COPY models/trafficcamnet_pruned_onnx_v1.0.4/resnet18_trafficcamnet_pruned_int8.txt trafficcamnet_pruned_onnx_v1.0.4/

WORKDIR /opt/nvidia/deepstream/deepstream-6.0/deepstream_python_apps/apps

RUN git clone https://github.com/scaballero2/ParkSight.git

WORKDIR /opt/nvidia/deepstream/deepstream-6.0/deepstream_python_apps/apps/ParkSight


CMD ["python3", "estacionamientoG_cam.py", "/dev/video0"]