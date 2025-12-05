# auth.py
import json
import os
import secrets
import hashlib
import time

BASE_DIR = os.path.dirname(__file__)
USERS_FILE = os.path.join(BASE_DIR, "users.json")
# Puedes ajustar si lo deseas (20000 puede ser costoso en máquinas débiles)
HASH_ROUNDS = 20000  # iteraciones SHA256

def _ensure_file():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, "w") as f:
            json.dump({"users": []}, f)

def load_users():
    _ensure_file()
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        # fichero corrupto o problema I/O: re-inicializar
        data = {"users": []}
        save_users(data)
        return data

def save_users(data):
    # sobrescribe atomically escribiendo a temp y moviendo (simple)
    tmp = USERS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, USERS_FILE)

def generate_salt(n=16):
    # token_hex(n) genera 2*n hex chars
    return secrets.token_hex(n)

def hash_password(password, salt, rounds=HASH_ROUNDS):
    if password is None:
        raise ValueError("password required")
    # iterated SHA256 over salt+password
    h = hashlib.sha256((salt + password).encode("utf-8")).digest()
    for _ in range(max(1, rounds) - 1):
        h = hashlib.sha256(h).digest()
    return h.hex()

def create_user(username, password, is_admin=False):
    if not username or not password:
        raise ValueError("username and password required")
    data = load_users()
    if any(u.get("username") == username for u in data.get("users", [])):
        raise ValueError("user exists")
    salt = generate_salt()
    h = hash_password(password, salt)
    user = {
        "username": username,
        "salt": salt,
        "hash": h,
        "is_admin": bool(is_admin),
        "created_at": int(time.time())
    }
    data.setdefault("users", []).append(user)
    save_users(data)
    return user

def verify_user(username, password):
    if not username or password is None:
        return False
    data = load_users()
    for u in data.get("users", []):
        if u.get("username") == username:
            expected = u.get("hash")
            salt = u.get("salt")
            if salt is None or expected is None:
                return False
            candidate = hash_password(password, salt)
            return secrets.compare_digest(candidate, expected)
    return False
