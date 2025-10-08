import socket
import struct

# EtherType reservado para Link-Chat (no estándar, pero válido para uso experimental)
ETH_P_LINKCHAT = 0x88B5

class LinkChatInterface:
    def __init__(self, interface_name: str, src_mac: bytes):
        """
        interface_name: nombre de la interfaz de red (ej. 'eno1', 'eth0', 'enp4s0')
        src_mac: dirección MAC origen en bytes (b'\xe0\x73\xe7\xca\x14\xfa')
        """
        self.interface = interface_name
        self.src_mac = src_mac
        self.sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_LINKCHAT))
        self.sock.bind((self.interface, 0))

    def send_frame(self, dst_mac: bytes, message_type: int, payload: bytes):
        """
        Construye y envía una trama Ethernet personalizada.
        """
        length = len(payload)
        eth_header = struct.pack("!6s6sH", dst_mac, self.src_mac, ETH_P_LINKCHAT)
        frame = eth_header + struct.pack("!BH", message_type, length) + payload
        self.sock.send(frame)
        print(f"[+] Trama enviada ({length} bytes) → {dst_mac.hex(':')}")

    def receive_frame(self):
        """
        Escucha una trama y devuelve los datos decodificados.
        """
        raw_frame = self.sock.recv(2048)
        dst_mac, src_mac, eth_type = struct.unpack("!6s6sH", raw_frame[:14])

        if eth_type != ETH_P_LINKCHAT:
            return None  # No es una trama de nuestro protocolo

        msg_type, length = struct.unpack("!BH", raw_frame[14:17])
        payload = raw_frame[17:17 + length]

        return {
            "src_mac": src_mac,
            "dst_mac": dst_mac,
            "msg_type": msg_type,
            "length": length,
            "payload": payload
        }
