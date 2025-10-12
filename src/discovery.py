#!/usr/bin/env python3
import socket
import struct
import time
import threading
import os

# ===============================
#  CONFIGURACIÓN GENERAL
# ===============================

ETH_P_LINKDISCOVERY = 0x88B6     # EtherType propio para el descubrimiento
IFACE_DEFAULT = "wlp0s20f3"      # interfaz por defecto (ajusta según tu sistema)
DISCOVERY_INTERVAL = 3.0         # tiempo entre anuncios (segundos)
TIMEOUT_DEVICE = 10.0            # tiempo sin recibir respuesta antes de eliminar dispositivo

iface = os.environ.get("LINKCHAT_IFACE", IFACE_DEFAULT)

# ===============================
#  CLASE PRINCIPAL: LinkDiscovery
# ===============================

class LinkDiscovery:
    def __init__(self, interface_name=IFACE_DEFAULT, src_mac=b"\x00\x00\x00\x00\x00\x00"):
        self.running = True
        self.interface = interface_name
        self.src_mac = src_mac
        self.sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_LINKDISCOVERY))
        self.sock.bind((self.interface, 0))
        self.devices = {}  # {mac: timestamp_último_contacto}
        print(f"[+] Interfaz {self.interface} inicializada para Link-Discovery")
    
    def stop(self):
        self.running = False

    # ------------------------------
    #  Envío de anuncio (broadcast)
    # ------------------------------
    def send_announcement(self):
        # ac:74:b1:84:a2:ba
        # dst_mac = b"\xff\xff\xff\xff\xff\xff"
        dst_mac = b"\xac\x74\xb1\x84\xa2\xba"
        eth_header = struct.pack("!6s6sH", dst_mac, self.src_mac, ETH_P_LINKDISCOVERY)
        payload = b"LINKDISCOVERY:HELLO"
        frame = eth_header + payload
        self.sock.send(frame)
        print(f"[→] Anuncio enviado por {self.src_mac.hex(':')}")

    # ------------------------------
    #  Recepción de anuncios
    # ------------------------------
    def receive_announcement(self):
        while self.running:
            raw_frame = self.sock.recv(65535)
            if len(raw_frame) < 14:
                continue
            dst_mac, src_mac, eth_type = struct.unpack("!6s6sH", raw_frame[:14])
            if eth_type != ETH_P_LINKDISCOVERY:
                continue
            payload = raw_frame[14:]
            if b"LINKDISCOVERY:HELLO" in payload:# and src_mac != self.src_mac:
                mac_str = src_mac.hex(":")
                self.devices[mac_str] = time.time()
                print(f"[+] Dispositivo detectado: {mac_str}")

    # ------------------------------
    #  Limpieza periódica
    # ------------------------------
    def cleanup_devices(self):
        while self.running:
            now = time.time()
            for mac in list(self.devices.keys()):
                if now - self.devices[mac] > TIMEOUT_DEVICE:
                    del self.devices[mac]
                    print(f"[-] Dispositivo inactivo eliminado: {mac}")
            time.sleep(2)

    # ------------------------------
    #  Bucle principal
    # ------------------------------
    def start(self):
        self.running = True
        self.threads = [
            threading.Thread(target=self.receive_announcement, daemon=True),
            threading.Thread(target=self.cleanup_devices, daemon=True)
        ]
        for t in self.threads:
            t.start()
        while self.running:
            self.send_announcement()
            time.sleep(DISCOVERY_INTERVAL)



'''
# ===============================
#  FUNCIÓN PRINCIPAL
# ===============================

def main():
    iface = IFACE_DEFAULT
    # ⚠️ Cambia esta MAC por la de tu equipo (usa ip link show)
    mac_str = mac_from_sysfs(iface)
    src_mac = bytes.fromhex(mac_str.replace(":", ""))

    ld = LinkDiscovery(interface_name=iface, src_mac=src_mac)
    ld.start()

# ===============================
#  EJECUCIÓN
# ===============================
if __name__ == "__main__":
    main()
'''