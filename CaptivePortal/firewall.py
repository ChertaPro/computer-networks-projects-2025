# firewall.py
import subprocess
import shutil

def _run_cmd(args):
    # Ejecuta comando sin shell; levanta excepción si falla
    try:
        proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as e:
        raise RuntimeError(f"Command not found: {args[0]}") from e
    if proc.returncode != 0:
        raise RuntimeError(f"Command {args!r} failed: {proc.returncode}\nSTDOUT:{proc.stdout}\nSTDERR:{proc.stderr}")
    return proc.stdout

def ensure_iptables_available():
    if not shutil.which("iptables"):
        raise RuntimeError("iptables not found on PATH")

def enable_ip_forward():
    # Habilitar forwarding en runtime (requiere permisos)
    ensure_iptables_available()  # check early
    _run_cmd(["sysctl", "-w", "net.ipv4.ip_forward=1"])
    # NOTA: persistir en /etc/sysctl.conf es tarea manual (informada en README)

def ip_neigh_get_mac(ip):
    # Obtiene la MAC localmente conocida para una IP usando 'ip neigh'
    if not shutil.which("ip"):
        return None
    try:
        out = _run_cmd(["ip", "neigh", "show", ip])
    except RuntimeError:
        return None
    for line in out.splitlines():
        parts = line.split()
        if "lladdr" in parts:
            i = parts.index("lladdr")
            if i + 1 < len(parts):
                return parts[i + 1]
    return None

def clear_base_rules():
    # Intenta limpiar reglas previas. No falla completamente si no puede.
    try:
        _run_cmd(["iptables", "-t", "nat", "-F"])
    except RuntimeError:
        # puede no existir la tabla o no haber permiso; toleramos
        pass
    try:
        _run_cmd(["iptables", "-F"])
    except RuntimeError:
        pass

def apply_base_rules(lan_iface, wan_iface, portal_port=8080):
    """
    Aplica reglas base:
    - DROP por defecto en FORWARD
    - Redirigir HTTP del LAN a portal_port (REDIRECT)
    - MASQUERADE en WAN
    """
    ensure_iptables_available()
    # Limpia reglas previas (MVP)
    clear_base_rules()

    # 1) Política default FORWARD DROP
    _run_cmd(["iptables", "-P", "FORWARD", "DROP"])
    # permitir tráfico ya establecido/relacionado
    _run_cmd(["iptables", "-A", "FORWARD", "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"])
    #
    # Permitir DNS desde LAN hacia Internet
    _run_cmd(["iptables", "-A", "FORWARD", "-i", lan_iface, "-p", "udp", "--dport", "53", "-j", "ACCEPT"])
    _run_cmd(["iptables", "-A", "FORWARD", "-o", lan_iface, "-p", "udp", "--sport", "53", "-j", "ACCEPT"])
    
    # Permitir DHCP
    _run_cmd(["iptables", "-A", "INPUT",  "-p", "udp", "--dport", "67:68", "-j", "ACCEPT"])
    _run_cmd(["iptables", "-A", "OUTPUT", "-p", "udp", "--sport", "67:68", "-j", "ACCEPT"])

    # Permitir acceso desde LAN al portal cautivo (puerto portal_port)
    _run_cmd(["iptables", "-A", "INPUT", "-i", lan_iface, "-p", "tcp", "--dport", str(portal_port), "-j", "ACCEPT"])

    # Redirigir HTTP desde LAN a portal_port
    _run_cmd(["iptables", "-t", "nat", "-A", "PREROUTING", "-i", lan_iface, "-p", "tcp", "--dport", "80", "-j",
              "REDIRECT", "--to-ports", str(portal_port)])
    
    # MASQUERADE en postrouting por WAN
    _run_cmd(["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", wan_iface, "-j", "MASQUERADE"])

def allow_client_by_ip(ip):
    _run_cmd(["iptables", "-I", "FORWARD", "-s", ip, "-j", "ACCEPT"])
    _run_cmd(["iptables", "-I", "FORWARD", "-d", ip, "-j", "ACCEPT"])

def allow_client_by_mac(mac, lan_iface):
    # Permitir salida del cliente
    _run_cmd(["iptables", "-I", "FORWARD", "-i", lan_iface, "-m", "mac", "--mac-source", mac, "-j", "ACCEPT"])
    # Permitir entrada al cliente (respuesta)
    _run_cmd(["iptables", "-I", "FORWARD", "-o", lan_iface, "-m", "mac", "--mac-destination", mac, "-j", "ACCEPT"])
    
def revoke_client_by_ip(ip):
    # Intentamos borrar; si falla, ignoramos
    try:
        _run_cmd(["iptables", "-D", "FORWARD", "-s", ip, "-j", "ACCEPT"])
    except RuntimeError:
        pass
    try:
        _run_cmd(["iptables", "-D", "FORWARD", "-d", ip, "-j", "ACCEPT"])
    except RuntimeError:
        pass

def revoke_client_by_mac(mac, lan_iface):
    try:
        _run_cmd(["iptables", "-D", "FORWARD", "-m", "mac", "--mac-source", mac, "-i", lan_iface, "-j", "ACCEPT"])
    except RuntimeError:
        pass
