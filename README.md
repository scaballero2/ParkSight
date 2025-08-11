# Configuración de sistema operativo

Después de instalar el sistema operativo, ya sea por sd o sdkmanager, es necesario revisar la instalación de ciertos requerimientos para la correcta ejecución del código. Cabe aclarar que esta guía fue diseñada para jetpack 4.6.x.

Primero es necesario instalar los SDK components directamente en la Jetson. Estos incluyen CUDA/cuDNN/TensorRT y otras librerías indispensables para el correcto funcionamiento del código: 

```bash
sudo apt update
sudo apt install nvidia-jetpack
```



# Configuración de acceso remoto

Este documento presenta una guía paso a paso para implementar el acceso remoto a una maquina con Ubuntu (Jetson)

## Acceder a una red de Zerotier para tener acceso remoto e ip constante

### 1. Instalar ZeroTier

Primeramente es necesario instalar ZeroTier con el siguiente comando

```bash
curl -s https://install.zerotier.com | sudo bash
```

### 2. Inicializar el servicio

Posteriormente se inicia el servicio de ZeroTier para que inicie al energizar el dispositivo:

```bash
sudo systemctl enable zerotier-one
sudo systemctl start zerotier-one
```

Y se verifica el status del servicio

```bash
sudo systemctl status zerotier-one
```

Debe aparecer `Active (running)`

### 3. Unirse a una red

Se ejecuta el siguiente comando para unirse a la red:

```bash
sudo zerotier-cli join <ID_DE_RED>
```

Después de ser autorizado, se podrá verificar la ip del dispositivo con:

```bash
zerotier-cli listnetworks
```

## Configurar (Tegra) para iniciar servidor sin monitor conectado

Se usa un driver de nvidia para iniciar el servidor VNC sin necesidad de una conexión a un monitor. Esto adicionalmente crea un display virtual de 1920x1080.

Con ayuda de la herramienta nano, se edita el siguiente archivo:

```bash
sudo nano /etc/X11/xorg.conf
```

Y se pega el siguiente código:

```bash
# Copyright (c) 2011-2013 NVIDIA CORPORATION.  All Rights Reserved.

#
# This is the minimal configuration necessary to use the Tegra driver.
# Please refer to the xorg.conf man page for more configuration
# options provided by the X server, including display-related options
# provided by RandR 1.2 and higher.

# Disable extensions not useful on Tegra.
Section "Module"
    Disable     "dri"
    SubSection  "extmod"
        Option  "omit xfree86-dga"
    EndSubSection
EndSection

Section "Device"
    Identifier  "Tegra0"
    Driver      "nvidia"
    # Allow X server to be started even if no display devices are connected.
    Option      "AllowEmptyInitialConfiguration" "true"
EndSection

Section "Screen"
    Identifier "Screen0"
    Device     "Tegra0"
    DefaultDepth 24
    SubSection "Display"
        Depth 24
        Modes "1920x1080"
    EndSubSection
EndSection

Section "Monitor"
    Identifier "Monitor0"
    HorizSync 28.0-80.0
    VertRefresh 48.0-75.0
EndSection

```

Finalmente se reinicia la jetson para confirmar y ejecutar los cambios

```bash
sudo reboot now
```

## Instalar y configurar servidor VNC

### 1. Instalar ```x11vnc```

```
sudo apt install x11vnc
```

### 2. Configurar contraseña de conexión

```
x11vnc -storepasswd
```

Esto crea un archivo que contiene la contraseña en ```~/.vnc/passwd```

### 3. Crear servicio de arranque

Para que x11vnc se inicie al energizar la jetson, se crea un servicio ```systemd```

Primero es necesario crear el archivo del servicio

```
sudo nano /etc/systemd/system/x11vnc.service
```

Y se pega lo siguiente:

```
[Unit]
Description=Start x11vnc at startup
After=display-manager.service
Requires=display-manager.service

[Service]
Type=simple
User=tu_usuario  # <-- cambia aquí a tu usuario en la Jetson
ExecStart=/usr/bin/x11vnc -auth guess -forever -loop -noxdamage -repeat -rfbauth /home/tu_usuario/.vnc/passwd -rfbport 5900 -shared
Restart=on-failure

[Install]
WantedBy=graphical.target

```

+ ```-auth guess``` hace que x11vnc intente detectar el archivo de autenticación automáticamente.

+ ```-forever``` mantiene el servidor activo después de una desconexión.

+ ```-rfbport 5900``` puerto por defecto VNC.

Finalmente se recargan los servicios y se habilita el nuevo que se acaba de crear

```
sudo systemctl daemon-reload
sudo systemctl enable x11vnc.service
sudo systemctl start x11vnc.service
```

Y se verifica el estado:

```
sudo systemctl status x11vnc.service
```

## Obtener acceso remoto

En una nueva terminal se ejecuta el siguiente comando

```
ssh -L 5900:localhost:5900 user@ip
```

Esto abre un tunel SSH local, redirigiendo el puerto 5900 de la maquina local al puerto 5900 de la máquina remota.

Ejemplo:
```
ssh -L 5900:localhost:5900 jetsong@192.168.100.129
```

Finalmente, con ayuda de la herramienta ```VNC Viewer``` se establece una nueva conexión a:
```
localhost:5900
```

# Configuración de contenedor y ejecución de código

En este apartado se muestra cómo configurar el contenedor de docker, instalar las librerías dentro del mismo y ejecutar el código.

## Configuración interna

Primero es necesario ejecutar el siguiente comando para obtener la imagen e iniciar el contenedor. Para jetpack 4.6.x:

```bash
sudo docker run -it \
  --name nombre \
  --runtime nvidia \
  --privileged \
  --network host \
  --device /dev/video0 \
  --device=/dev/video1 \
  --group-add video \
  -e DISPLAY=$DISPLAY \
  -e QT_X11_NO_MITSHM=1 \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  nvcr.io/nvidia/deepstream-l4t:6.0.1-triton
```

Ahora es necesario instalar las librerías necesarias para ejecutar/desarrollar código de deepstream en python. Para esto se hará uso de la siguiente [Repo](https://github.com/NVIDIA-AI-IOT/deepstream_python_apps). Para deepstream 6.0.1/Jetpack 4.6.x:

Accedemos a la carpeta madre de deepstream 6.0: 

```bash
cd /opt/nvidia/deepstream/deepstream-6.0/
```

Se instala `python3-pip`

```bash
apt update && apt install -y python3-pip
```

Se descarga el wheel adecuado. Para Jetson Nano: 

```bash
wget https://github.com/NVIDIA-AI-IOT/deepstream_python_apps/releases/download/v1.1.1/pyds-1.1.1-py3-none-linux_aarch64.whl -P /tmp
```

Se instala el binding

```bash
pip3 install /tmp/pyds-1.1.1-py3-none-linux_aarch64.whl
```

Finalmente se clona el repositorio con ejemplos compatibles:

```bash
git clone https://github.com/NVIDIA-AI-IOT/deepstream_python_apps.git
cd deepstream_python_apps
git checkout v1.1.1
```

## Descargar y ejecutar código

Primero, es necesario instalar el modelo. Este puede ser encontrado en [TrafficCamNet](https://catalog.ngc.nvidia.com/orgs/nvidia/teams/tao/models/trafficcamnet). Se descarga la carpeta y se inserta en:

```bash
cd /opt/nvidia/deepstream/deepstream-6.0/samples/models/
```

Dentro de la carpeta se ejecuta el siguiente comando:

```bash
/usr/src/tensorrt/bin/trtexec --onnx=resnet18_trafficcamnet_pruned.onnx --saveEngine=resnet18_trafficcamnet_pruned_fp16.engine --fp16 --explicitBatch
```
`--fp16` es la precisión más balanceada.

Se accede a la siguiente carpeta:

```bash
cd /opt/nvidia/deepstream/deepstream-6.0/deepstream_python_apps/apps
```

Y se clona el siguiente [repo](https://github.com/scaballero2/ParkSight/tree/main)

```bash
git clone https://github.com/scaballero2/ParkSight.git
```