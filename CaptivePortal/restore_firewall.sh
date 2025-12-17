#!/bin/bash
# restore_firewall.sh - Restauración de emergencia

echo "[*] Restaurando firewall a estado seguro..."

# Opción 1: Restaurar desde backup si existe
if [ -f /tmp/captive_portal_iptables.backup ]; then
    echo "[*] Restaurando desde backup..."
    sudo iptables-restore < /tmp/captive_portal_iptables.backup
    sudo rm /tmp/captive_portal_iptables.backup
else
    echo "[!] No hay backup, limpiando manualmente..."
    
    # Opción 2: Limpieza manual
    sudo iptables -t nat -F
    sudo iptables -F
    sudo iptables -P FORWARD ACCEPT
    sudo iptables -P INPUT ACCEPT
    sudo iptables -P OUTPUT ACCEPT
fi

# Reiniciar NetworkManager
echo "[*] Reiniciando NetworkManager..."
sudo systemctl restart NetworkManager

echo "[✓] Firewall restaurado"
echo "[*] Verifica con: sudo iptables -L -n -v"