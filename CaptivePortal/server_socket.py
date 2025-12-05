# server_socket.py
import os
import json
import socket
import threading
import urllib.parse
import traceback
from http import HTTPStatus

import auth
import firewall
from sessions import SessionManager

BASE_DIR = os.path.dirname(__file__)
WEB_DIR = os.path.join(BASE_DIR, "web")

# CONFIGURACIÓN (ajusta según tu topología)
""" 
John:
LAN_IFACE = "wlp0s20f3"
WAN_IFACE = "enx027a5826373e"

Ramon:

"""

LAN_IFACE = "wlp0s20f3"
WAN_IFACE = "enx027a5826373e"
PORTAL_PORT = 8080
SESSION_DURATION = 3600
ADMIN_TOKEN = "change-me-admin-token"

# inicializar firewall y reglas (requiere permisos)
try:
    firewall.enable_ip_forward()
    firewall.apply_base_rules(LAN_IFACE, WAN_IFACE, portal_port=PORTAL_PORT)
except Exception as e:
    print("Warning: no se pudieron aplicar reglas de firewall:", str(e))

session_mgr = SessionManager(firewall, LAN_IFACE)

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

def handle_client(conn, addr):
    try:
        conn.settimeout(5.0)
        data = b""
        # read headers (until \r\n\r\n)
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(4096)
            if not chunk:
                break
            data += chunk
            if len(data) > 64 * 1024:  # limite headers
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
        method, raw_path, proto = parts[0], parts[1], parts[2]
        path = urllib.parse.urlparse(raw_path).path
        # read body if Content-Length given
        body = rest
        cl = int(headers.get("Content-Length", "0"))
        while len(body) < cl:
            chunk = conn.recv(4096)
            if not chunk:
                break
            body += chunk

        client_ip = addr[0]

        # Rutas
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
                # redirect to /success
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
            # frontend registration endpoint: crea usuario normal (no admin)
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

        # static files fallback (e.g., CSS/JS)
        file_path = path.lstrip("/")
        static = read_static(file_path)
        if static is not None:
            # crude mime
            ctype = "application/octet-stream"
            if file_path.endswith(".html") or file_path.endswith(".htm"):
                ctype = "text/html; charset=utf-8"
            elif file_path.endswith(".js"):
                ctype = "application/javascript"
            elif file_path.endswith(".css"):
                ctype = "text/css"
            elif file_path.endswith(".json"):
                ctype = "application/json"
            conn.sendall(http_response(200, {"Content-Type": ctype}, static))
            conn.close()
            return

        # default: redirect to /
        conn.sendall(http_response(303, {"Location": "/"}, b""))
        conn.close()
    except Exception:
        try:
            tb = traceback.format_exc()
            conn.sendall(http_response(500, {"Content-Type": "text/plain; charset=utf-8"}, tb.encode("utf-8")))
        except Exception:
            pass
        conn.close()

def serve_forever(host="0.0.0.0", port=PORTAL_PORT):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(128)
    print(f"Starting Captive Portal HTTP server (socket) on {host}:{port}")
    try:
        while True:
            conn, addr = sock.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("Shutting down server")
    finally:
        session_mgr.stop()
        try:
            sock.close()
        except Exception:
            pass
        print("Server stopped")

if __name__ == "__main__":
    # Ensure users file exists with an admin default for first run
    try:
        d = auth.load_users()
        if not d.get("users"):
            print("Creating default user 'admin'...")
            auth.create_user("admin", "admin", is_admin=True)
    except Exception as e:
        print("Warning creating default user:", str(e))
    serve_forever()
