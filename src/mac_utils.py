# ===============================
#  FUNCIÓN MAC PC
# ===============================
def mac_from_sysfs(iface):
    path = f"/sys/class/net/{iface}/address"
    try:
        with open(path, "r") as f:
            return f.read().strip().lower()
    except Exception:
        return None