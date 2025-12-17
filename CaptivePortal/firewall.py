# firewall.py - VERSIÓN MEJORADA CON BACKUP/RESTORE
import subprocess
import shutil
import os
import atexit

STATE_BACKUP = "/tmp/captive_portal_iptables.backup"
FORWARD_POLICY_FILE = "/tmp/captive_portal_forward_policy.txt"

def _run_cmd(args):
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

# ===== NUEVAS FUNCIONES DE BACKUP/RESTORE =====

def backup_iptables():
    """Guarda el estado actual de iptables antes de modificarlo"""
    try:
        print("[*] Guardando estado actual de iptables...")
        out = _run_cmd(["iptables-save"])
        with open(STATE_BACKUP, "w") as f:
            f.write(out)
        
        # Guardar política FORWARD actual
        out = _run_cmd(["iptables", "-L", "FORWARD", "-n"])
        for line in out.splitlines():
            if line.startswith("Chain FORWARD"):
                # Extraer política (ACCEPT/DROP)
                if "(policy" in line:
                    policy = line.split("policy ")[1].split()[0].rstrip(")")
                    with open(FORWARD_POLICY_FILE, "w") as f:
                        f.write(policy)
                break
        
        print("[✓] Backup guardado en", STATE_BACKUP)
    except Exception as e:
        print(f"[!] Advertencia: no se pudo guardar backup: {e}")

def restore_iptables():
    """Restaura el estado original de iptables"""
    if os.path.exists(STATE_BACKUP):
        try:
            print("[*] Restaurando estado original de iptables...")
            with open(STATE_BACKUP) as f:
                subprocess.run(["iptables-restore"], input=f.read(), text=True, 
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            os.remove(STATE_BACKUP)
            print("[✓] Iptables restaurado")
        except Exception as e:
            print(f"[!] Error restaurando iptables: {e}")
            print("[!] Ejecuta manualmente: sudo iptables-restore < " + STATE_BACKUP)
    
    if os.path.exists(FORWARD_POLICY_FILE):
        try:
            os.remove(FORWARD_POLICY_FILE)
        except:
            pass

def cleanup_portal_rules(lan_iface, wan_iface, portal_port=80):
    """Limpia solo las reglas específicas del portal (alternativa más quirúrgica)"""
    print("[*] Limpiando reglas del portal cautivo...")
    
    # Restaurar política FORWARD
    if os.path.exists(FORWARD_POLICY_FILE):
        try:
            with open(FORWARD_POLICY_FILE) as f:
                policy = f.read().strip()
            _run_cmd(["iptables", "-P", "FORWARD", policy])
            print(f"[✓] Política FORWARD restaurada a {policy}")
        except Exception as e:
            print(f"[!] Error restaurando política FORWARD: {e}")
            # Fallback seguro
            _run_cmd(["iptables", "-P", "FORWARD", "ACCEPT"])
    
    # Borrar redirecciones PREROUTING (HTTP)
    try:
        _run_cmd(["iptables", "-t", "nat", "-D", "PREROUTING", 
                 "-i", lan_iface, "-p", "tcp", "--dport", str(portal_port), 
                 "-j", "REDIRECT", "--to-ports", str(portal_port)])
    except:
        pass
    
    # Borrar MASQUERADE
    try:
        _run_cmd(["iptables", "-t", "nat", "-D", "POSTROUTING", 
                 "-o", wan_iface, "-j", "MASQUERADE"])
    except:
        pass
    
    # Limpiar cadena FORWARD (opcional - más agresivo)
    try:
        _run_cmd(["iptables", "-F", "FORWARD"])
    except:
        pass
    
    print("[✓] Reglas del portal limpiadas")

# ===== FIN NUEVAS FUNCIONES =====

def enable_ip_forward():
    ensure_iptables_available()
    _run_cmd(["sysctl", "-w", "net.ipv4.ip_forward=1"])

def ip_neigh_get_mac(ip):
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
    try:
        _run_cmd(["iptables", "-t", "nat", "-F"])
    except RuntimeError:
        pass
    try:
        _run_cmd(["iptables", "-F"])
    except RuntimeError:
        pass

def apply_base_rules(lan_iface, wan_iface, portal_port=80):
    """Aplica reglas base para el portal cautivo"""
    ensure_iptables_available()
    
    # ⭐ GUARDAR BACKUP ANTES DE MODIFICAR ⭐
    backup_iptables()
    
    clear_base_rules()

    # 1) Política default FORWARD DROP
    _run_cmd(["iptables", "-P", "FORWARD", "DROP"])
    
    # Permitir tráfico establecido/relacionado
    _run_cmd(["iptables", "-A", "FORWARD", "-m", "conntrack", "--ctstate", "ESTABLISHED,RELATED", "-j", "ACCEPT"])
    
    # ⭐ BLOQUEAR HTTPS PARA NO AUTENTICADOS ⭐
    _run_cmd(["iptables", "-A", "FORWARD", "-i", lan_iface, "-p", "tcp", "--dport", "443", "-j", "DROP"])
    
    # 2) Permitir DNS desde LAN
    _run_cmd(["iptables", "-A", "FORWARD", "-i", lan_iface, "-p", "udp", "--dport", "53", "-j", "ACCEPT"])
    _run_cmd(["iptables", "-A", "FORWARD", "-i", lan_iface, "-p", "tcp", "--dport", "53", "-j", "ACCEPT"])
    _run_cmd(["iptables", "-A", "FORWARD", "-o", lan_iface, "-p", "udp", "--sport", "53", "-j", "ACCEPT"])
    _run_cmd(["iptables", "-A", "FORWARD", "-o", lan_iface, "-p", "tcp", "--sport", "53", "-j", "ACCEPT"])
    
    # 3) Permitir DHCP
    _run_cmd(["iptables", "-A", "INPUT",  "-p", "udp", "--dport", "67:68", "-j", "ACCEPT"])
    _run_cmd(["iptables", "-A", "OUTPUT", "-p", "udp", "--sport", "67:68", "-j", "ACCEPT"])
    
    # Permitir DNS en INPUT
    _run_cmd(["iptables", "-A", "INPUT", "-i", lan_iface, "-p", "udp", "--dport", "53", "-j", "ACCEPT"])
    _run_cmd(["iptables", "-A", "INPUT", "-i", lan_iface, "-p", "tcp", "--dport", "53", "-j", "ACCEPT"])

    # 4) Permitir acceso al servidor HTTP (puerto 80) y HTTPS (puerto 8443)
    _run_cmd(["iptables", "-A", "INPUT", "-i", lan_iface, "-p", "tcp", "--dport", "80", "-j", "ACCEPT"])
    _run_cmd(["iptables", "-A", "INPUT", "-i", lan_iface, "-p", "tcp", "--dport", "8443", "-j", "ACCEPT"])
    
    # 7) MASQUERADE para NAT
    _run_cmd(["iptables", "-t", "nat", "-A", "POSTROUTING", "-o", wan_iface, "-j", "MASQUERADE"])
    
    # ⭐ REGISTRAR CLEANUP AL EXIT ⭐
    atexit.register(lambda: cleanup_portal_rules(lan_iface, wan_iface, portal_port))

def allow_client_by_ip(ip):
    """Permite el acceso completo a un cliente por su IP"""
    _run_cmd(["iptables", "-I", "FORWARD", "1", "-s", ip, "-j", "ACCEPT"])
    _run_cmd(["iptables", "-I", "FORWARD", "1", "-d", ip, "-j", "ACCEPT"])

def allow_client_by_mac(mac, lan_iface):
    """Permite el acceso a un cliente por su MAC address"""
    _run_cmd(["iptables", "-I", "FORWARD", "1", "-i", lan_iface, "-m", "mac", "--mac-source", mac, "-j", "ACCEPT"])
    
def revoke_client_by_ip(ip):
    """Revoca el acceso de un cliente por su IP"""
    try:
        _run_cmd(["iptables", "-D", "FORWARD", "-s", ip, "-j", "ACCEPT"])
    except RuntimeError:
        pass
    try:
        _run_cmd(["iptables", "-D", "FORWARD", "-d", ip, "-j", "ACCEPT"])
    except RuntimeError:
        pass

def revoke_client_by_mac(mac, lan_iface):
    """Revoca el acceso de un cliente por su MAC address"""
    try:
        _run_cmd(["iptables", "-D", "FORWARD", "-i", lan_iface, "-m", "mac", "--mac-source", mac, "-j", "ACCEPT"])
    except RuntimeError:
        pass