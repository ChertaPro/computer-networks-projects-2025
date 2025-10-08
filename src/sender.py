from link_layer import LinkChatInterface

iface = "wlp0s20f3"
src_mac = bytes.fromhex("10f60a271a32")  # Tu MAC WiFi
dst_mac = bytes.fromhex("ffffffffffff")  # broadcast

lc = LinkChatInterface(iface, src_mac)
msg = "Hola desde Link-Chat!"
lc.send_frame(dst_mac, message_type=0x01, payload=msg.encode())
