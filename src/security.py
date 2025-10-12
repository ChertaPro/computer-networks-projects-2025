import os
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding as sym_padding
import base64

# ===============================
#  Gestión de claves
# ===============================


def generate_keys_if_needed(priv_path="private_key.pem", pub_path="public_key.pem"):
    if not os.path.exists(priv_path) or not os.path.exists(pub_path):
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        # Guardar clave privada
        with open(priv_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            ))
        # Guardar clave pública
        public_key = private_key.public_key()
        with open(pub_path, "wb") as f:
            f.write(public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            ))

def load_private_key(path="private_key.pem"):
    generate_keys_if_needed(path, path.replace("private", "public"))
    with open(path, "rb") as key_file:
        return serialization.load_pem_private_key(
            key_file.read(), password=None, backend=default_backend()
        )

def load_public_key(path="public_key.pem"):
    generate_keys_if_needed(path.replace("public", "private"), path)
    with open(path, "rb") as key_file:
        return serialization.load_pem_public_key(
            key_file.read(), backend=default_backend()
        )

def serialize_public_key(public_key):
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

def deserialize_public_key(data):
    return serialization.load_pem_public_key(data, backend=default_backend())

# ===============================
#  Cifrado/descifrado asimétrico (RSA)
# ===============================

def encrypt_with_public_key(data: bytes, public_key):
    return public_key.encrypt(
        data,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

def decrypt_with_private_key(ciphertext: bytes, private_key):
    return private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

# ===============================
#  Cifrado/descifrado híbrido (RSA + AES)
# ===============================

def encrypt_large_data(data: bytes, public_key):
    # Generar clave AES aleatoria
    aes_key = os.urandom(32)  # AES-256
    iv = os.urandom(16)
    # Cifrar datos con AES
    padder = sym_padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    # Cifrar clave AES con RSA
    encrypted_key = encrypt_with_public_key(aes_key, public_key)
    # Empaquetar: encrypted_key | iv | encrypted_data
    return base64.b64encode(encrypted_key + iv + encrypted_data)

def decrypt_large_data(ciphertext: bytes, private_key):
    raw = base64.b64decode(ciphertext)
    # Tamaño de clave RSA cifrada depende del tamaño de la clave (por defecto 256 bytes para 2048 bits)
    rsa_key_size = private_key.key_size // 8
    encrypted_key = raw[:rsa_key_size]
    iv = raw[rsa_key_size:rsa_key_size+16]
    encrypted_data = raw[rsa_key_size+16:]
    # Descifrar clave AES
    aes_key = decrypt_with_private_key(encrypted_key, private_key)
    # Descifrar datos
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_data = decryptor.update(encrypted_data) + decryptor.finalize()
    unpadder = sym_padding.PKCS7(128).unpadder()
    data = unpadder.update(padded_data) + unpadder.finalize()
    return data
