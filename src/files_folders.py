import socket, struct, os, hashlib, time, threading
import zipfile

ETH_P_LINKCHAT = 0x88B5
MSG_FILE = 1
CHUNK_SIZE = 1460
RECV_BUF = 65535

def md5sum(path):
    h = hashlib.md5()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(8192), b''):
            h.update(b)
    return h.digest()

def prepare_zip(path):
    os.makedirs("downloads/tmp", exist_ok=True)

    base = os.path.basename(os.path.normpath(path))
    zip_dest = os.path.join("downloads/tmp", f"{base}.zip")

    if os.path.exists(zip_dest):
        os.remove(zip_dest)

    if os.path.isdir(path):
        with zipfile.ZipFile(zip_dest, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(path):
                for file in files:
                    abs_path = os.path.join(root, file)
                    # arcname relativo a path.parent para mantener carpeta dentro del zip
                    rel_path = os.path.relpath(abs_path, os.path.join(path, ".."))
                    zf.write(abs_path, arcname=rel_path)
    else:
        # archivo simple
        with zipfile.ZipFile(zip_dest, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(path, arcname=os.path.basename(path))

    return zip_dest, True


def try_unzip_and_cleanup(final_path):
    try:
        if not final_path.lower().endswith('.zip'):
            return
        # Extraer en downloads/ (si el zip contiene una carpeta, se recreará esa carpeta)
        extract_to = "downloads"
        with zipfile.ZipFile(final_path, 'r') as zf:
            zf.extractall(extract_to)
        # Eliminar el zip final recibido
        try:
            os.remove(final_path)
        except Exception as e:
            print(f"[-] no pude borrar zip final {final_path}: {e}")
        # Eliminar zips auxiliares en downloads/tmp (los creados por prepare_zip)
        tmpdir = "downloads/tmp"
        if os.path.isdir(tmpdir):
            for f in os.listdir(tmpdir):
                if f.lower().endswith('.zip'):
                    fp = os.path.join(tmpdir, f)
                    try:
                        os.remove(fp)
                    except Exception:
                        pass
        print(f"[+] zip {os.path.basename(final_path)} descomprimido en {extract_to} y zips auxiliares borrados")
    except zipfile.BadZipFile:
        print("[-] zip corrupto o no es un zip válido al intentar descomprimir")
    except Exception as e:
        print(f"[-] error al descomprimir/limpiar: {e}")

class LinkChat:
    def __init__(self, iface, src_mac):
        self.sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.htons(ETH_P_LINKCHAT))
        self.sock.bind((iface, 0))
        self.src_mac = src_mac
        self.pending = {}  # filehash_hex -> {'path','chunks'(set),'name','size','hash'(bytes)}
        print(f"[+] iface {iface} listo")

    def _mac_to_bytes(self, mac):
        """Convierte una dirección MAC en formato string a bytes (6B)."""
        if isinstance(mac, bytes) and len(mac) == 6:
            return mac
        if isinstance(mac, str):
            mac = mac.replace(":", "").replace("-", "")
            return bytes.fromhex(mac)
        raise ValueError(f"Formato de MAC inválido: {mac}")

    def set_receive_callback(self, callback):
        # callback(nombre:str, tam_kb:float)
        self._callback = callback

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
        n = name.encode('utf-8'); fmt = f"!B{len(n)}sQ16s"
        return struct.pack(fmt, len(n), n, size, h)

    def _meta_unpack(self, p):
        # Return (metadata_dict, struct_size) or raise ValueError if not enough bytes
        if len(p) < 1:
            raise ValueError("payload vacío")
        n = p[0]
        if n == 0 or n > 255:
            raise ValueError("name_len inválido")
        fmt = f"!B{n}sQ16s"
        sz = struct.calcsize(fmt)
        if len(p) < sz:
            raise ValueError("payload demasiado corto para metadata")
        # Unpack and ensure name decodes as UTF-8; if it doesn't, treat as chunk upstream
        _, name, size, h = struct.unpack(fmt, p[:sz])
        try:
            name_s = name.decode('utf-8')
        except UnicodeDecodeError:
            raise ValueError("nombre no UTF-8 -> probablemente no es metadata")
        return {"name": name_s, "size": size, "hash": h}, sz

    def send_file(self, dst, path):
        dst = self._mac_to_bytes(dst)  # <-- conversión segura aquí
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
                self.send_frame(dst, MSG_FILE, h + struct.pack("!I", i) + c)
                i += 1
                time.sleep(0.01)
            print(f"[+] enviado {name} en {i} chunks")


    def recv_loop(self):
        os.makedirs("downloads/tmp", exist_ok=True)
        print("[+] escuchando...")
        while True:
            frm = self.recv_frame()
            if not frm or frm["type"] != MSG_FILE: continue
            p = frm["payload"]

            # Intentamos interpretar metadata sólo si hay suficientes bytes para leer name_len + rest
            is_meta = False
            try:
                meta, off = self._meta_unpack(p)
                is_meta = True
            except Exception:
                is_meta = False

            if is_meta:
                rest = p[off:]
                hhex = meta["hash"].hex()
                tmp = os.path.join("downloads/tmp", f"{hhex}.part")
                # archivo pequeño enviado en la misma trama
                if rest:
                    os.makedirs("downloads", exist_ok=True)
                    final = os.path.join("downloads", meta["name"])
                    with open(final, "wb") as o:
                        o.write(rest)
                    if hashlib.md5(rest).digest() == meta["hash"]:
                        print(f"[+] recibido {meta['name']} ({meta['size']}B)")
                        # Si es zip, descomprimir y limpiar
                        try_unzip_and_cleanup(final)
                    continue
                # metadata sola -> preparar .part (truncate al tamaño)
                with open(tmp, "wb") as t: t.truncate(meta["size"])
                self.pending[hhex] = {"path": tmp, "chunks": set(), "name": meta["name"], "size": meta["size"], "hash": meta["hash"]}
                total = (meta["size"] + CHUNK_SIZE - 1)//CHUNK_SIZE
                if len(self.pending[hhex]["chunks"]) >= total:
                    self._try_finalize(hhex)
                print(f"[+] preparado para recibir {meta['name']} ({meta['size']}B)")
            else:
                # tratar como chunk: [16B hash][4B idx][data...]
                if len(p) < 21:  # 16 + 4 + at least 1 byte data
                    continue
                h = p[:16]
                idx = struct.unpack("!I", p[16:20])[0]
                data = p[20:]
                hhex = h.hex()
                tmp = os.path.join("downloads/tmp", f"{hhex}.part")
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
                    if ent.get("size"):
                        total = (ent["size"] + CHUNK_SIZE - 1)//CHUNK_SIZE
                        if len(ent["chunks"]) >= total:
                            self._try_finalize(hhex)

    def _try_finalize(self, hhex):
        ent = self.pending.get(hhex)
        if not ent or not ent.get("name") or not ent.get("size"): return
        cur = hashlib.md5()
        with open(ent["path"], "rb") as f:
            for b in iter(lambda: f.read(8192), b''):
                cur.update(b)
        if cur.digest() == ent["hash"]:
            final = os.path.join("downloads", ent["name"])
            os.makedirs("downloads", exist_ok=True)
            # mover .part a final
            try:
                os.replace(ent["path"], final)
            except Exception as e:
                print(f"[-] error al mover archivo reensamblado: {e}")
                return
            print(f"[+] archivo reensamblado: {final}")
            # Invocar callback si existe
            if hasattr(self, "_callback") and callable(self._callback):
                nombre = os.path.basename(final)
                self._callback(nombre)  # enviamos nombre y tamaño
            # Descomprimir zip si aplica
            try_unzip_and_cleanup(final)
            del self.pending[hhex]
        else:
            print("[-] hash final no coincide")

    def start_receiving_file(self, callback=None):
        """
        Inicia recv_loop en un hilo. Si pasas callback, el recv_loop actual (que imprime) 
        no lo usa; para integrar callback habría que modificar recv_loop para invocar callback
        cuando se reensambla un archivo. Por ahora, simplificamos: arrancamos recv_loop en un hilo.
        """
        def _runner():
            try:
                self.recv_loop()
            except Exception as e:
                print(f"[-] recv_loop terminó con error: {e}")
        threading.Thread(target=_runner, daemon=True).start()

    def send_folder(self, dst, file_path):
        """
        dst: destino (se asume correcto para send_file; la conversión a bytes debe hacerse
             en la capa que instancie LinkChat, si trabaja con strings MAC).
        file_path: ruta del archivo o carpeta a enviar.
        """
        dst = self._mac_to_bytes(dst) 
        zip_path, created = prepare_zip(file_path)
        try:
            self.send_file(dst, zip_path)
        finally:
            if created and os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except Exception as e:
                    print(f"[-] no pude borrar zip auxiliar {zip_path}: {e}")