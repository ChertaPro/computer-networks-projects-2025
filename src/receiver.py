from link_layer import LinkChatInterface

iface = "wlp0s20f3"
src_mac = bytes.fromhex("ac74b184a2ba")

lc = LinkChatInterface(iface, src_mac)
print("[*] Escuchando tramas Link-Chat...\n")

while True:
    frame = lc.receive_frame()
    if frame:
        print(f"[+] Mensaje recibido de {frame['src_mac'].hex(':')}")
        print(f"Tipo: {frame['msg_type']}, Longitud: {frame['length']}")
        print("Contenido:", frame["payload"].decode(errors='ignore'))
        print("-" * 50)
