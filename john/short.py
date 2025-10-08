import socket, struct, os, time, hashlib

ETH_P_LINKCHAT = 0x88B5
MSG_FILE = 1
CHUNK_SIZE = 1200
RECV_BUF = 65535

def md5sum(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(8192), b''):
            h.update(b)
    return h.digest()  # 16 bytes

class LinkChat:
    def __init__(self, iface, src_mac):
        self.sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_LINKCHAT))
        self.sock.bind((iface, 0))
        self.src_mac = src_mac
        print(f"[+] Interfaz {iface} lista")

    def send_frame(self, dst_mac, t, payload):
        frame = struct.pack("!6s6sH", dst_mac, self.src_mac, ETH_P_LINKCHAT) + struct.pack("!BH", t, len(payload)) + payload
        self.sock.send(frame)

    def recv_frame(self):
        f = self.sock.recv(RECV_BUF)
        if len(f) < 17: return None
        d, s, et = struct.unpack("!6s6sH", f[:14])
        if et != ETH_P_LINKCHAT: return None
        t, l = struct.unpack("!BH", f[14:17])
        return dict(src=s, type=t, payload=f[17:17+l])

    def _meta_pack(self, name, size, h):
        n = name.encode(); fmt = f"!B{len(n)}sQ16s"; return struct.pack(fmt, len(n), n, size, h)
    def _meta_unpack(self, p):
        n = p[0]; fmt = f"!B{n}sQ16s"; _, name, size, h = struct.unpack(fmt, p[:struct.calcsize(fmt)])
        return {"name": name.decode(), "size": size, "hash": h}, struct.calcsize(fmt)

    def send_file(self, dst, path):
        name, size = os.path.basename(path), os.path.getsize(path)
        h = md5sum(path)
        meta = self._meta_pack(name, size, h)
        with open(path, "rb") as f:
            if size <= CHUNK_SIZE:
                self.send_frame(dst, MSG_FILE, meta + f.read())
                print(f"[+] Enviado pequeño '{name}' ({size} B)")
            else:
                self.send_frame(dst, MSG_FILE, meta)
                i = 0
                while (c := f.read(CHUNK_SIZE)):
                    self.send_frame(dst, MSG_FILE, h + struct.pack("!H", i) + c)
                    i += 1
                print(f"[+] Enviado '{name}' en {i} fragmentos")

    def recv_loop(self):
        print("[+] Escuchando...")
        while True:
            f = self.recv_frame()
            if not f or f["type"] != MSG_FILE: continue
            p = f["payload"]
            if len(p) < 1: continue
            n = p[0]
            if len(p) >= struct.calcsize(f"!B{n}sQ16s"):
                meta, off = self._meta_unpack(p)
                rest = p[off:]
                path = os.path.join("downloads", meta["name"])
                os.makedirs("downloads", exist_ok=True)
                with open(path, "wb") as o:
                    o.write(rest)
                if hashlib.md5(rest).digest() == meta["hash"]:
                    print(f"[+] Recibido '{meta['name']}' ({meta['size']} B)")
            else:
                print("[?] Fragmento recibido (omitido para simplicidad)")

if __name__ == "__main__":
    iface = "wlp0s20f3"
    mac = b'\xac\x74\xb1\x84\xa2\xba'
    chat = LinkChat(iface, mac)

    # Crear archivo de prueba
    test = "documento.txt"

    # MAC destino = misma para prueba local
    dst = b'\x10\xf6\x0a\x27\x1a\x32'
    chat.send_file(dst, test)
    # chat.recv_loop()
