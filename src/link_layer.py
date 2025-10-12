#!/usr/bin/env python3
from time import sleep
import socket
import struct
import math
import threading
import os



# ===============================
#  CONFIGURACIÓN GENERAL
# ===============================

ETH_P_LINKCHAT = 0x88B5     # EtherType reservado para Link-Chat (no estándar)
MAX_PAYLOAD_SIZE = 1400     # tamaño máximo de datos por trama Ethernet (~1500B)
IFACE_DEFAULT = "wlp0s20f3" # interfaz por defecto

iface = os.environ.get("LINKCHAT_IFACE", IFACE_DEFAULT)

# ===============================
#  CLASE PRINCIPAL: LinkChatInterface
# ===============================

class LinkChatInterface:
    def __init__(self, interface_name=IFACE_DEFAULT, src_mac=b"\x00\x00\x00\x00\x00\x00"):
        self.running = True
        self.interface = interface_name
        self.src_mac = src_mac
        self.sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_LINKCHAT))
        self.sock.bind((self.interface, 0))
        print(f"[+] Interfaz {self.interface} inicializada para Link-Chat")

    def stop(self):
        self.running = False

    # ---------------------------------
    #  Envío de mensajes (con fragmentación)
    # ---------------------------------
    def send_frame(self, dst_mac: bytes, message_type: int, payload: bytes):
        total_fragments = math.ceil(len(payload) / MAX_PAYLOAD_SIZE)
        for i in range(total_fragments):
            sleep(0.1)  # evitar saturar la red
            start = i * MAX_PAYLOAD_SIZE
            end = start + MAX_PAYLOAD_SIZE
            fragment = payload[start:end]
            frag_length = len(fragment)

            # Cabecera LinkChat (6 bytes)
            # message_type:1 | total_frags:1 | frag_index:2 | frag_length:2
            header = struct.pack("!BBHH", message_type, total_fragments, i, frag_length)

            # Cabecera Ethernet (14 bytes)
            eth_header = struct.pack("!6s6sH", dst_mac, self.src_mac, ETH_P_LINKCHAT)

            frame = eth_header + header + fragment
            self.sock.send(frame)

        print(f"[+] Mensaje enviado ({len(payload)} bytes en {total_fragments} fragmentos) ✅")

    # ---------------------------------
    #  Recepción de mensajes (reensamblado)
    # ---------------------------------
    def receive_frame(self):
        """Recibe tramas y reconstruye mensajes largos (según MAC origen)."""
        reassembly_buffer = {}

        while self.running:
            raw_frame = self.sock.recv(65535)

            # Validar longitud mínima de cabecera Ethernet
            if len(raw_frame) < 20:  # 14 (Ethernet) + 6 (LinkChat)
                continue

            dst_mac, src_mac, eth_type = struct.unpack("!6s6sH", raw_frame[:14])

            # Filtrar solo tramas del tipo LinkChat
            if eth_type != ETH_P_LINKCHAT:
                continue

            try:
                # Leer cabecera LinkChat (6 bytes)
                msg_type, total_frags, frag_index, frag_len = struct.unpack("!BBHH", raw_frame[14:20])
            except struct.error:
                continue  # Trama corrupta o incompleta

            if len(raw_frame) < 20 + frag_len:
                continue  # Fragmento incompleto

            payload = raw_frame[20:20 + frag_len]

            # Ensamblar mensaje por MAC origen
            key = src_mac
            if key not in reassembly_buffer:
                reassembly_buffer[key] = [None] * total_frags

            reassembly_buffer[key][frag_index] = payload

            # Si ya tenemos todos los fragmentos → mensaje completo
            if all(reassembly_buffer[key]):
                full_message = b"".join(reassembly_buffer[key])
                del reassembly_buffer[key]
                return {
                    "src_mac": src_mac,
                    "dst_mac": dst_mac,
                    "msg_type": msg_type,
                    "payload": full_message,
                    "length": len(full_message)
                }

    def start_receiving(self, callback):
        """Arranca un hilo que invoca callback(frame_dict) por cada mensaje recibido."""
        def _loop():
            while self.running:
                try:
                    frame = self.receive_frame()
                    if frame and callable(callback):
                        try:
                            callback(frame)
                        except Exception:
                            pass
                except Exception:
                    # evitar terminar el hilo por errores puntuales
                    pass
        self.thread = threading.Thread(target=_loop, daemon=True)
        self.thread.start()
        print("[*] Receptor Link-Chat iniciado en background")

    def send_message(self, dst_mac, message, message_type=1):
        """Conveniencia: dst_mac puede ser str ('ff:...') o bytes; message str o bytes."""
        if isinstance(message, str):
            payload = message.encode()
        else:
            payload = bytes(message)
        if isinstance(dst_mac, str):
            dst = self._parse_mac_str(dst_mac)
        elif isinstance(dst_mac, (bytes, bytearray)):
            dst = bytes(dst_mac)
        else:
            raise ValueError("dst_mac debe ser str o bytes")
        self.send_frame(dst, message_type=message_type, payload=payload)

    @staticmethod
    def _parse_mac_str(mac_str):
        """Convierte una dirección MAC en formato string ('ff:ff:ff:ff:ff:ff') a bytes."""
        return bytes(int(b, 16) for b in mac_str.split(":"))
    
'''
# ===============================
#  FUNCIÓN PRINCIPAL (MODO INTERACTIVO)
# ===============================

def main():
    iface = IFACE_DEFAULT

    sender_mac = bytes.fromhex("ac74b184a2ba")   # MAC del emisor (ajusta según tu equipo)
    receiver_mac = bytes.fromhex("10f60a271a32") # MAC destino o ff:ff:ff:ff:ff:ff para broadcast

    lc = LinkChatInterface(iface, sender_mac)

    # Función para recibir mensajes en un hilo aparte
    def recv_loop():
        print("[*] Escuchando mensajes Link-Chat...\n")
        while True:
            frame = lc.receive_frame()
            if frame:
                print("\n" + "-" * 60)
                print(f"[+] Mensaje recibido de {frame['src_mac'].hex(':')}")
                print(f"Tipo: {frame['msg_type']}  |  Longitud: {frame['length']} bytes")
                print("Contenido:", frame["payload"].decode(errors='ignore'))
                texto = frame["payload"].decode(errors='ignore')
                with open("nuevo_archivo.txt", "w", encoding="utf-8") as f:
                    f.write(texto)
                print("-" * 60)
                print("Escribe tu mensaje: ", end="", flush=True)
    # Lanzar el hilo de recepción
    threading.Thread(target=recv_loop, daemon=True).start()

    # Bucle principal de envío
    while True:
        try:
            msg = input("Escribe tu mensaje: ").strip()
            if not msg:
                continue
            lc.send_frame(receiver_mac, message_type=1, payload=msg.encode())
        except KeyboardInterrupt:
            print("\n[!] Saliendo del programa...")
            break

# ===============================
#  EJECUCIÓN
# ===============================
if __name__ == "__main__":
    main()
'''