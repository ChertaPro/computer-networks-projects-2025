# server_socket.py - Versión con servidor HTTP adicional
import os
import json
import socket
import ssl
import threading
import urllib.parse
import traceback
from http import HTTPStatus

import auth
import firewall
from sessions import SessionManager
from netutils import detect_interfaces
from https_setup import get_cert_paths, verify_cert_exists
import signal

# Al inicio del archivo, después de los imports
def signal_handler(signum, frame):
    """Maneja señales de terminación para cleanup"""
    print("\n[*] Señal recibida, limpiando...")
    if session_mgr:
        session_mgr.stop()
    firewall.restore_iptables()  # ⭐ RESTAURAR AL SALIR ⭐
    print("[✓] Cleanup completado")
    exit(0)

BASE_DIR = os.path.dirname(__file__)
WEB_DIR = os.path.join(BASE_DIR, "web")

# CONFIGURACIÓN
HTTP_PORT = 80          # Puerto HTTP para redirecciones
HTTPS_PORT = 8443       # Puerto HTTPS para el portal
SESSION_DURATION = 3600
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "change-me-admin-token")

# Variable global para el session manager
session_mgr = None

def read_static(path):
    p = os.path.join(WEB_DIR, path.lstrip("/"))
    if not os.path.isfile(p):
        return None
    with open(p, "rb") as f:
        return f.read()

def http_response(status_code=200, headers=None, body=b""):
    status_line = f"HTTP/1.1 {status_code} {HTTPStatus(status_code).phrase}\r\n"
    hdrs = headers or {}
    if "Content-Length" not in hdrs:
        hdrs["Content-Length"] = str(len(body))
    if "Connection" not in hdrs:
        hdrs["Connection"] = "close"
    header_lines = "".join(f"{k}: {v}\r\n" for k, v in hdrs.items())
    return (status_line + header_lines + "\r\n").encode("utf-8") + body

def parse_headers(header_bytes):
    lines = header_bytes.decode("utf-8", errors="replace").split("\r\n")
    request_line = lines[0]
    headers = {}
    for line in lines[1:]:
        if not line:
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    return request_line, headers

def handle_http_redirect(conn, addr):
    """
    Maneja conexiones HTTP en puerto 80.
    Solo redirige a HTTPS para captura de portal cautivo.
    """
    try:
        conn.settimeout(5.0)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 64 * 1024:
                break
        
        if not data:
            conn.close()
            return
        
        head, _ = data.split(b"\r\n\r\n", 1)
        request_line, headers = parse_headers(head)
        parts = request_line.split(" ")
        
        if len(parts) < 3:
            conn.sendall(http_response(400, body=b"Bad request"))
            conn.close()
            return
        
        method, raw_path, _ = parts[0], parts[1], parts[2]
        path = urllib.parse.urlparse(raw_path).path
        client_ip = addr[0]
        
        # Endpoints de detección de portal cautivo
        if method == "GET" and path in ["/generate_204", "/gen_204"]:
            # Android
            if session_mgr and session_mgr.is_allowed(client_ip):
                conn.sendall(http_response(204, body=b""))
            else:
                conn.sendall(http_response(302, {"Location": f"https://portal.local:{HTTPS_PORT}/"}, b""))
            conn.close()
            return
        
        if method == "GET" and path == "/hotspot-detect.html":
            # iOS/macOS
            if session_mgr and session_mgr.is_allowed(client_ip):
                html = b"<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>"
                conn.sendall(http_response(200, {"Content-Type": "text/html"}, html))
            else:
                conn.sendall(http_response(302, {"Location": f"https://portal.local:{HTTPS_PORT}/"}, b""))
            conn.close()
            return
        
        if method == "GET" and path in ["/connecttest.txt", "/ncsi.txt"]:
            # Windows
            if session_mgr and session_mgr.is_allowed(client_ip):
                conn.sendall(http_response(200, body=b"Microsoft Connect Test"))
            else:
                conn.sendall(http_response(302, {"Location": f"https://portal.local:{HTTPS_PORT}/"}, b""))
            conn.close()
            return
        
        # Cualquier otra petición HTTP -> redirigir a HTTPS
        host = headers.get("Host", f"portal.local:{HTTPS_PORT}")
        if ":" not in host:
            host = f"{host}:{HTTPS_PORT}"
        
        redirect_url = f"https://{host}{raw_path}"
        conn.sendall(http_response(302, {"Location": redirect_url}, b""))
        conn.close()
        
    except Exception:
        try:
            conn.sendall(http_response(500, body=b"Internal error"))
        except:
            pass
        conn.close()

def handle_https_client(conn, addr):
    """
    Maneja conexiones HTTPS en puerto 8443 (portal principal).
    """
    try:
        conn.settimeout(5.0)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 64 * 1024:
                break
        
        if not data:
            conn.close()
            return
        
        head, rest = data.split(b"\r\n\r\n", 1)
        request_line, headers = parse_headers(head)
        parts = request_line.split(" ")
        
        if len(parts) < 3:
            conn.sendall(http_response(400, body=b"Bad request"))
            conn.close()
            return
        
        method, raw_path, _ = parts[0], parts[1], parts[2]
        path = urllib.parse.urlparse(raw_path).path
        
        # Leer body si existe Content-Length
        body = rest
        cl = int(headers.get("Content-Length", "0"))
        while len(body) < cl:
            chunk = conn.recv(4096)
            if not chunk:
                break
            body += chunk
        
        client_ip = addr[0]
        
        # Rutas principales
        if method == "GET" and (path == "/" or path.startswith("/index.html")):
            data_b = read_static("index.html")
            if data_b is None:
                conn.sendall(http_response(404, body=b"index not found"))
            else:
                conn.sendall(http_response(200, {"Content-Type": "text/html; charset=utf-8"}, data_b))
            conn.close()
            return
        
        if method == "GET" and path == "/success":
            data_b = read_static("success.html")
            if data_b is None:
                conn.sendall(http_response(404, body=b"success page missing"))
            else:
                conn.sendall(http_response(200, {"Content-Type": "text/html; charset=utf-8"}, data_b))
            conn.close()
            return
        
        if method == "GET" and path.startswith("/status"):
            allowed = session_mgr.is_allowed(client_ip)
            resp = {"ip": client_ip, "allowed": allowed}
            b = json.dumps(resp).encode("utf-8")
            conn.sendall(http_response(200, {"Content-Type": "application/json; charset=utf-8"}, b))
            conn.close()
            return
        
        if method == "POST" and path == "/login":
            params = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"))
            username = params.get("username", [""])[0]
            password = params.get("password", [""])[0]
            if not username or not password:
                conn.sendall(http_response(400, body=b"Missing username or password"))
                conn.close()
                return
            ok = auth.verify_user(username, password)
            if ok:
                session_mgr.add_session(client_ip, username, duration_seconds=SESSION_DURATION)
                conn.sendall(http_response(303, {"Location": "/success"}, b""))
            else:
                conn.sendall(http_response(401, body=b"Invalid credentials"))
            conn.close()
            return
        
        if method == "POST" and path == "/logout":
            session_mgr.revoke_session(client_ip)
            conn.sendall(http_response(200, body=b"Logged out"))
            conn.close()
            return
        
        if method == "POST" and path == "/register":
            params = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"))
            username = params.get("username", [""])[0]
            password = params.get("password", [""])[0]
            if not username or not password:
                conn.sendall(http_response(400, body=b"Missing username/password"))
                conn.close()
                return
            try:
                auth.create_user(username, password, is_admin=False)
            except ValueError as e:
                conn.sendall(http_response(409, body=str(e).encode("utf-8")))
                conn.close()
                return
            conn.sendall(http_response(201, body=b"User created"))
            conn.close()
            return
        
        if method == "POST" and path == "/admin/create_user":
            token = headers.get("X-Admin-Token", "")
            if token != ADMIN_TOKEN:
                conn.sendall(http_response(403, body=b"Forbidden"))
                conn.close()
                return
            params = urllib.parse.parse_qs(body.decode("utf-8", errors="replace"))
            username = params.get("username", [""])[0]
            password = params.get("password", [""])[0]
            is_admin = params.get("is_admin", ["false"])[0].lower() == "true"
            if not username or not password:
                conn.sendall(http_response(400, body=b"Missing username/password"))
                conn.close()
                return
            try:
                auth.create_user(username, password, is_admin=is_admin)
            except ValueError as e:
                conn.sendall(http_response(409, body=str(e).encode("utf-8")))
                conn.close()
                return
            conn.sendall(http_response(201, body=b"User created"))
            conn.close()
            return
        
        # Archivos estáticos
        file_path = path.lstrip("/")
        static = read_static(file_path)
        if static is not None:
            ctype = "application/octet-stream"
            if file_path.endswith(".html") or file_path.endswith(".htm"):
                ctype = "text/html; charset=utf-8"
            elif file_path.endswith(".js"):
                ctype = "application/javascript"
            elif file_path.endswith(".css"):
                ctype = "text/css"
            elif file_path.endswith(".json"):
                ctype = "application/json"
            elif file_path.endswith(".png"):
                ctype = "image/png"
            elif file_path.endswith(".jpg") or file_path.endswith(".jpeg"):
                ctype = "image/jpeg"
            elif file_path.endswith(".svg"):
                ctype = "image/svg+xml"
            conn.sendall(http_response(200, {"Content-Type": ctype}, static))
            conn.close()
            return
        
        # Redirect a /
        conn.sendall(http_response(303, {"Location": "/"}, b""))
        conn.close()
        
    except Exception:
        try:
            tb = traceback.format_exc()
            conn.sendall(http_response(500, {"Content-Type": "text/plain; charset=utf-8"}, tb.encode("utf-8")))
        except:
            pass
        conn.close()

def serve_http(host="0.0.0.0", port=HTTP_PORT):
    """Servidor HTTP simple para redirecciones"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(128)
    print(f"[✓] HTTP redirect server on {host}:{port}")
    
    try:
        while True:
            conn, addr = sock.accept()
            t = threading.Thread(target=handle_http_redirect, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()

def serve_https(host="0.0.0.0", port=HTTPS_PORT):
    """Servidor HTTPS principal"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(128)
    
    try:
        cert_file, key_file = get_cert_paths()
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        sock = context.wrap_socket(sock, server_side=True)
        print(f"[✓] HTTPS portal server on {host}:{port}")
        print(f"[✓] Using certificate: {cert_file}")
    except Exception as e:
        print(f"[✗] Error configurando HTTPS: {e}")
        sock.close()
        return
    
    try:
        while True:
            try:
                conn, addr = sock.accept()
            except ssl.SSLError as e:
                continue
            t = threading.Thread(target=handle_https_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[*] Shutting down HTTPS server...")
    finally:
        session_mgr.stop()
        sock.close()

if __name__ == "__main__":
    print("="*60)
    print("       CAPTIVE PORTAL - Sistema de Autenticación de Red")
    print("="*60)
    
    print("\n[*] Detectando interfaces de red...")
    lan_iface, wan_iface = detect_interfaces()
    
    if lan_iface is None or wan_iface is None:
        print("[✗] ERROR: No se pudieron detectar las interfaces LAN/WAN.")
        exit(1)
    
    print(f"[✓] LAN_IFACE = {lan_iface}")
    print(f"[✓] WAN_IFACE = {wan_iface}")
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    print("\n[*] Verificando certificados SSL...")
    if not verify_cert_exists():
        print("[*] Generando certificado autofirmado...")
        try:
            get_cert_paths()
            print(f"[✓] Certificados generados")
        except Exception as e:
            print(f"[✗] Error: {e}")
            exit(1)
    else:
        print("[✓] Certificados encontrados")
    
    print("\n[*] Configurando firewall...")
    try:
        firewall.enable_ip_forward()
        firewall.apply_base_rules(lan_iface, wan_iface, portal_port=HTTP_PORT)
        print("[✓] Firewall configurado")
    except Exception as e:
        print(f"[✗] ERROR: {e}")
        exit(1)
    
    print("\n[*] Inicializando usuarios...")
    try:
        d = auth.load_users()
        if not d.get("users"):
            auth.create_user("admin", "admin", is_admin=True)
            print("[✓] Usuario 'admin' creado (password: 'admin')")
            print("[!] CAMBIAR PASSWORD EN PRODUCCIÓN")
        else:
            print(f"[✓] {len(d.get('users', []))} usuario(s) cargado(s)")
    except Exception as e:
        print(f"[!] Advertencia: {e}")
    
    print("\n[*] Inicializando sesiones...")
    session_mgr = SessionManager(firewall, lan_iface)
    print("[✓] Session manager iniciado")
    
    # Iniciar servidor HTTP en thread separado
    http_thread = threading.Thread(target=serve_http, daemon=True)
    http_thread.start()
    
    print("\n" + "="*60)
    print(f"🚀 Portal Cautivo listo:")
    print(f"   HTTP:  http://0.0.0.0:{HTTP_PORT}")
    print(f"   HTTPS: https://0.0.0.0:{HTTPS_PORT}")
    print("="*60 + "\n")
    
    # HTTPS es el servidor principal (bloquea hasta Ctrl+C)
    serve_https()