# netutils.py
import subprocess
import re


def _run(cmd):
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return proc.stdout.strip()


def detect_wan_interface():
    """
    Detecta la interfaz de salida a Internet buscando la default route.
    """
    out = _run(["ip", "route"])
    for line in out.splitlines():
        if line.startswith("default"):
            parts = line.split()
            if "dev" in parts:
                return parts[parts.index("dev") + 1]
    return None


def detect_lan_interface(wan_iface):
    """
    Detecta la interfaz LAN con IP privada (192.168.x, 10.x, 172.16-31.x).
    Excluye la interfaz WAN.
    """
    out = _run(["ip", "addr"])
    iface = None
    current = None

    for line in out.splitlines():
        if re.match(r"\d+:\s", line):
            current = line.split(":")[1].strip()
            continue

        if "inet " in line:
            if current == wan_iface:
                continue

            ip = line.split()[1].split("/")[0]

            if ip.startswith("192.168.") or ip.startswith("10.") or (
                ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31
            ):
                return current

    return None


def detect_interfaces():
    wan = detect_wan_interface()
    lan = detect_lan_interface(wan)
    return lan, wan
