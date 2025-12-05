# Imagen base
FROM python:3.12-slim

# Instalar Tkinter + utilidades gráficas + herramientas de red
RUN apt-get update && apt-get install -y \
    python3-tk \
    tk \
    tcl \
    iproute2 \
    iputils-ping \
    net-tools \
    tcpdump \
    libx11-6 \
    libxext6 \
    libxrender1 \
    libxft2 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Copiar el código fuente
COPY ../src /app
COPY ../Tests /app

# Instalar dependencias Python
RUN pip install --no-cache-dir customtkinter cryptography

# Configurar variable de entorno de interfaz
ENV LINKCHAT_IFACE=eth0
ENV DISPLAY=${DISPLAY}

# Comando por defecto
CMD ["python", "main.py"]
