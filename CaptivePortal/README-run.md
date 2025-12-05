# Ejecutar como root (recomendado) o con sudo
sudo python3 server.py

# Crear un usuario vía curl (usa tu ADMIN_TOKEN configurado en server.py)
curl -X POST -H "X-Admin-Token: change-me-admin-token" -d "username=test&password=testpass" http://localhost:8080/admin/create_user

# Probar login desde cliente:
# En un equipo cliente apuntar a cualquier http://example.com -> se redirige al portal (si REDIRECT aplicado)
# O simplemente navegar a http://<IP_LAPTOP>:8080 y hacer login manual.

# Para limpiar (cuidado): reiniciar iptables/policies o reboot. El script no borra reglas automáticamente.
