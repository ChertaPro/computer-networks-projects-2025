# https_setup.py
import os
import subprocess
import shutil

BASE_DIR = os.path.dirname(__file__)
CERT_DIR = os.path.join(BASE_DIR, "certs")
CERT_FILE = os.path.join(CERT_DIR, "server.crt")
KEY_FILE = os.path.join(CERT_DIR, "server.key")

def ensure_openssl_available():
    """Verifica que openssl esté disponible en el sistema"""
    if not shutil.which("openssl"):
        raise RuntimeError("openssl no está instalado. Instálalo con: apt install openssl")

def generate_self_signed_cert(days=365):
    """
    Genera un certificado autofirmado usando openssl via subprocess.
    
    Args:
        days: Días de validez del certificado (default: 365)
    
    Returns:
        tuple: (cert_path, key_path)
    """
    ensure_openssl_available()
    
    # Crear directorio de certificados si no existe
    os.makedirs(CERT_DIR, exist_ok=True)
    
    # Si ya existen, preguntar si regenerar (en producción podrías saltarte esto)
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        print(f"[*] Certificado ya existe en {CERT_FILE}")
        return CERT_FILE, KEY_FILE
    
    print(f"[*] Generando certificado autofirmado válido por {days} días...")
    
    # Comando openssl para generar certificado autofirmado
    # -nodes: sin contraseña para la clave privada
    # -newkey rsa:2048: genera nueva clave RSA de 2048 bits
    # -keyout: archivo de clave privada
    # -out: archivo de certificado
    # -days: días de validez
    # -subj: información del certificado (evita prompts interactivos)
    
    cmd = [
        "openssl", "req",
        "-x509",
        "-nodes",
        "-newkey", "rsa:2048",
        "-keyout", KEY_FILE,
        "-out", CERT_FILE,
        "-days", str(days),
        "-subj", "/C=US/ST=State/L=City/O=CaptivePortal/CN=portal.local"
    ]
    
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        print(f"[✓] Certificado generado exitosamente:")
        print(f"    Certificado: {CERT_FILE}")
        print(f"    Clave privada: {KEY_FILE}")
        
        # Establecer permisos restrictivos en la clave privada
        os.chmod(KEY_FILE, 0o600)
        
        return CERT_FILE, KEY_FILE
        
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Error generando certificado: {e.stderr}")

def get_cert_paths():
    """
    Devuelve las rutas del certificado y clave privada.
    Si no existen, los genera.
    
    Returns:
        tuple: (cert_path, key_path)
    """
    if not os.path.exists(CERT_FILE) or not os.path.exists(KEY_FILE):
        return generate_self_signed_cert()
    return CERT_FILE, KEY_FILE

def verify_cert_exists():
    """
    Verifica que el certificado y la clave existan.
    
    Returns:
        bool: True si ambos existen, False en caso contrario
    """
    return os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE)

if __name__ == "__main__":
    # Modo standalone: genera certificado cuando se ejecuta directamente
    print("=== Generador de Certificados SSL para Portal Cautivo ===")
    try:
        cert_path, key_path = generate_self_signed_cert()
        print("\n[✓] Proceso completado exitosamente")
        print("\nPuedes usar estos archivos en tu servidor HTTPS:")
        print(f"  Certificado: {cert_path}")
        print(f"  Clave: {key_path}")
    except Exception as e:
        print(f"\n[✗] Error: {e}")
        exit(1)