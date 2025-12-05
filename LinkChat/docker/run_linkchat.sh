#!/bin/bash
set -e

# Elimina contenedores previos si existen y silencia la salida/errores (evita fallos si no existen).
docker rm -f linkchat_node1 linkchat_node2 >/dev/null 2>&1 || true
# Elimina la red Docker previa si existe.
docker network rm linkchat_net >/dev/null 2>&1 || true

# pasar DISPLAY al build para evitar la advertencia de UndefinedVar
# Se pasa la variable DISPLAY como argumento de build para que no haya warnings
docker build --build-arg DISPLAY="$DISPLAY" -t linkchat_image -f Dockerfile ..

# crear la red solo si no existe (evita el error)
# Se inspecciona la red y, si la inspección falla, se crea la red con subnet fija.
docker network inspect linkchat_net >/dev/null 2>&1 || \
  docker network create --driver bridge --subnet 172.28.0.0/16 linkchat_net >/dev/null


# Permitir conexiones X11 locales desde root (necesario para aplicaciones gráficas dentro del contenedor).
# Nota: xhost +local:root cambia control de acceso X y debe usarse con precaución.
xhost +local:root >/dev/null

# Arranca el primer contenedor en segundo plano con:
# - nombre y hostname
# - privilegios extendidos (--privileged)
# - variable DISPLAY exportada para forwarding X11
# - montaje del socket X11 para poder mostrar GUI en el host
# - conexión a la red creada con IP fija
docker run -dit \
  --name linkchat_node1 \
  --hostname node1 \
  --privileged \
  --env DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  --network linkchat_net \
  --ip 172.28.0.2 \
  linkchat_image

# Arranca el segundo contenedor con configuración equivalente y una IP distinta.
docker run -dit \
  --name linkchat_node2 \
  --hostname node2 \
  --privileged \
  --env DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  --network linkchat_net \
  --ip 172.28.0.3 \
  linkchat_image

# Lista los contenedores en ejecución para verificar que todo está activo.
docker ps
