import os
import json

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "Memory")
MEMORY_FILE = os.path.join(MEMORY_DIR, "mac_names.json")

# Asegura que la carpeta existe
os.makedirs(MEMORY_DIR, exist_ok=True)

def load_mac_names():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_mac_names(mac_names):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(mac_names, f, ensure_ascii=False, indent=2)

def get_name_for_mac(mac):
    mac_names = load_mac_names()
    return mac_names.get(mac)

def set_name_for_mac(mac, name):
    mac_names = load_mac_names()
    mac_names[mac] = name
    save_mac_names(mac_names)
