# sessions.py
import threading
import time

class SessionManager:
    def __init__(self, firewall_module, lan_iface, cleanup_interval=10):
        """
        firewall_module: módulo con allow/revoke functions
        lan_iface: interfaz LAN usada para mac-based rules
        """
        self.firewall = firewall_module
        self.lan_iface = lan_iface
        self.sessions = {}  # ip -> {"username":..., "expires": timestamp, "mac": ...}
        self.lock = threading.Lock()
        self.cleanup_interval = max(1, int(cleanup_interval))
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._cleaner, daemon=True)
        self._thread.start()

    def add_session(self, ip, username, duration_seconds=3600):
        if not ip or not username:
            return
        expires = time.time() + max(1, int(duration_seconds))
        mac = None
        try:
            mac = self.firewall.ip_neigh_get_mac(ip)
        except Exception:
            mac = None
        with self.lock:
            self.sessions[ip] = {"username": username, "expires": expires, "mac": mac}
        # Prefer MAC-based allowance if MAC known
        if mac:
            try:
                self.firewall.allow_client_by_mac(mac, self.lan_iface)
            except Exception:
                # fallback a IP-based
                try:
                    self.firewall.allow_client_by_ip(ip)
                except Exception:
                    pass
        else:
            try:
                self.firewall.allow_client_by_ip(ip)
            except Exception:
                pass

    def revoke_session(self, ip):
        with self.lock:
            entry = self.sessions.pop(ip, None)
        if entry:
            mac = entry.get("mac")
            if mac:
                try:
                    self.firewall.revoke_client_by_mac(mac, self.lan_iface)
                    return
                except Exception:
                    pass
            try:
                self.firewall.revoke_client_by_ip(ip)
            except Exception:
                pass

    def is_allowed(self, ip):
        with self.lock:
            e = self.sessions.get(ip)
            if not e:
                return False
            return e["expires"] > time.time()

    def _cleaner(self):
        while not self._stop.is_set():
            now = time.time()
            to_revoke = []
            with self.lock:
                for ip, data in list(self.sessions.items()):
                    if data["expires"] <= now:
                        to_revoke.append(ip)
            for ip in to_revoke:
                try:
                    self.revoke_session(ip)
                except Exception:
                    pass
            self._stop.wait(self.cleanup_interval)

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=2)
