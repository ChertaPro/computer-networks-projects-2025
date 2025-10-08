import socket, struct, os, hashlib

ETH_P_LINKCHAT = 0x88B5
MSG_FILE = 1
CHUNK_SIZE = 1200
RECV_BUF = 65535

RAMITO_MAC = b'\x10\xf6\x0a\x27\x1a\x32'
JOSMITO_MAC = b'\xac\x74\xb1\x84\xa2\xba'
FILE = "1.jpg"

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
        self.pending = {}  # filehash_hex -> {'path', 'chunks'(set), 'name'(opt), 'size'(opt), 'hash'(bytes)}
        print(f"[+] iface {iface} listo")

    def send_frame(self, dst, t, payload):
        self.sock.send(struct.pack("!6s6sH", dst, self.src_mac, ETH_P_LINKCHAT) + struct.pack("!BH", t, len(payload)) + payload)

    def recv_frame(self):
        f = self.sock.recv(RECV_BUF)
        if len(f) < 17: return None
        d,s,et = struct.unpack("!6s6sH", f[:14])
        if et != ETH_P_LINKCHAT: return None
        t,l = struct.unpack("!BH", f[14:17])
        return dict(src=s, type=t, payload=f[17:17+l])

    def _meta_pack(self, name, size, h):
        n = name.encode(); fmt = f"!B{len(n)}sQ16s"; return struct.pack(fmt, len(n), n, size, h)
    def _meta_unpack(self, p):
        n = p[0]; fmt = f"!B{n}sQ16s"; sz = struct.calcsize(fmt)
        _, name, size, h = struct.unpack(fmt, p[:sz]); return {"name": name.decode(), "size": size, "hash": h}, sz

    def send_file(self, dst, path):
        name, size = os.path.basename(path), os.path.getsize(path)
        h = md5sum(path)
        meta = self._meta_pack(name, size, h)
        with open(path, "rb") as f:
            if size <= CHUNK_SIZE:
                self.send_frame(dst, MSG_FILE, meta + f.read())
                print(f"[+] enviado pequeño {name} ({size}B)")
                return
            self.send_frame(dst, MSG_FILE, meta)
            i = 0
            while (c := f.read(CHUNK_SIZE)):
                self.send_frame(dst, MSG_FILE, h + struct.pack("!H", i) + c)
                i += 1
            print(f"[+] enviado {name} en {i} chunks")

    def recv_loop(self):
        os.makedirs("downloads/tmp", exist_ok=True)
        print("[+] escuchando...")
        while True:
            frm = self.recv_frame()
            if not frm or frm["type"] != MSG_FILE: continue
            p = frm["payload"]
            # intentar interpretar como metadata (si falla -> es chunk)
            try:
                meta, off = self._meta_unpack(p)
                rest = p[off:]
                hhex = meta["hash"].hex()
                tmp = os.path.join("downloads/tmp", f"{hhex}.part")
                # si vienen datos (archivo pequeño en la misma trama)
                if rest:
                    os.makedirs("downloads", exist_ok=True)
                    final = os.path.join("downloads", meta["name"])
                    with open(final, "wb") as o: o.write(rest)
                    if hashlib.md5(rest).digest() == meta["hash"]:
                        print(f"[+] recibido {meta['name']} ({meta['size']}B)")
                    else:
                        print("[-] hash no coincide (pequeño)")
                    continue
                # metadata sola -> preparar .part (truncate al tamaño)
                with open(tmp, "wb") as t: t.truncate(meta["size"])
                self.pending[hhex] = {"path": tmp, "chunks": set(), "name": meta["name"], "size": meta["size"], "hash": meta["hash"]}
                # si ya estaban chunks escritos antes (rarísimo), comprobamos completitud
                total = (meta["size"] + CHUNK_SIZE - 1)//CHUNK_SIZE
                if len(self.pending[hhex]["chunks"]) >= total:
                    self._try_finalize(hhex)
                print(f"[+] preparado para recibir {meta['name']} ({meta['size']}B)")
            except Exception:
                # tratar como chunk: [16B hash][2B idx][data...]
                if len(p) < 18: continue
                h = p[:16]; idx = struct.unpack("!H", p[16:18])[0]; data = p[18:]
                hhex = h.hex()
                tmp = os.path.join("downloads/tmp", f"{hhex}.part")
                # escribir en offset (crear si no existe)
                os.makedirs("downloads/tmp", exist_ok=True)
                mode = "r+b" if os.path.exists(tmp) else "w+b"
                with open(tmp, mode) as t:
                    t.seek(idx * CHUNK_SIZE)
                    t.write(data)
                ent = self.pending.get(hhex)
                if not ent:
                    # crear entrada parcial sin metadata aún
                    self.pending[hhex] = {"path": tmp, "chunks": {idx}, "name": None, "size": None, "hash": h}
                else:
                    ent["chunks"].add(idx)
                    # si conocemos size -> verificar completitud
                    if ent.get("size"):
                        total = (ent["size"] + CHUNK_SIZE - 1)//CHUNK_SIZE
                        if len(ent["chunks"]) >= total:
                            self._try_finalize(hhex)

    def _try_finalize(self, hhex):
        ent = self.pending.get(hhex)
        if not ent or not ent.get("name") or not ent.get("size"): return
        # verificar md5 del .part
        cur = hashlib.md5()
        with open(ent["path"], "rb") as f:
            for b in iter(lambda: f.read(8192), b''):
                cur.update(b)
        if cur.digest() == ent["hash"]:
            final = os.path.join("downloads", ent["name"]); os.replace(ent["path"], final)
            print(f"[+] archivo reensamblado: {final}")
            del self.pending[hhex]
        else:
            print("[-] hash final no coincide")

if __name__ == "__main__":
    iface = "wlp0s20f3"
    dst = RAMITO_MAC
    src = JOSMITO_MAC
    chat = LinkChat(iface, src)

    # crear prueba si no existe
    test = FILE
    if not os.path.exists(test):
        with open(test, "w") as f:
            f.write("prueba grande\n" * 2000)

    # enviar y (opcional) escuchar
    chat.send_file(dst, test)
    # chat.recv_loop()
