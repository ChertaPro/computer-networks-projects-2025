import threading
import time
import os

import gui
import discovery
import mac_utils
import security

def main():
    iface = os.environ.get("LINKCHAT_IFACE", discovery.IFACE_DEFAULT)

    # Obtener MAC local (fallback a zeros si no se puede)
    mac_str = mac_utils.mac_from_sysfs(iface) or "00:00:00:00:00:00"
    src_mac = bytes.fromhex(mac_str.replace(":", ""))

    # Crear LinkDiscovery
    ld = discovery.LinkDiscovery(interface_name=iface, src_mac=src_mac)

    # Ejecutar el loop de discovery en hilo daemon para no bloquear la GUI
    t = threading.Thread(target=ld.start, daemon=True)
    t.start()

    # Intentar crear LinkChatInterface (opcional, puede fallar sin permisos)
    link_iface = None
    try:
        import link_layer
        link_iface = link_layer.LinkChatInterface(interface_name=iface, src_mac=src_mac)
    except Exception as e:
        print(f"[!] No se pudo inicializar LinkChatInterface: {e}")
        link_iface = None
    files_folders_iface = None
    try:
        import files_folders
        files_folders_iface = files_folders.LinkChat(iface, src_mac)
    except Exception as e:
        print(f"[!] No se pudo inicializar LinkChat {e}")
        link_iface = None

    # Iniciar GUI
    app = gui.LinkChatApp()

    # Pasar la interfaz de enlace a la app para que la GUI pueda enviar/recibir
    app.link_iface = link_iface
    app.files_folders_iface = files_folders_iface

    # Si tenemos link_iface, arrancar receptor que actualizará la GUI
    if link_iface:
        def incoming_cb(frame):
            # frame: dict con src_mac (bytes), payload (bytes), ...
            src = frame.get("src_mac").hex(":")
            payload = frame.get("payload", b"")
            text = payload.decode(errors="ignore")
            def _update():
                # asegurar que el dispositivo aparece en la lista
                try:
                    current = set(app.devices_frame.devices)
                    if src not in current:
                        newset = set(current)
                        newset.add(src)
                        app.devices_frame.set_devices(newset)
                except Exception:
                    pass
                # si estamos chateando con ese MAC, mostrar mensaje
                try:
                    if app.chat_frame.mac == src:
                        app.chat_frame.text_area.configure(state="normal")
                        app.chat_frame.text_area.insert("end", f"{src}: {text}\n")
                        app.chat_frame.text_area.configure(state="disabled")
                        app.chat_frame.text_area.see("end")
                except Exception:
                    pass
            # programar en hilo principal
            try:
                app.after(0, _update)
            except Exception:
                pass

        link_iface.start_receiving(incoming_cb)
        def file_received_callback(*args):
            if not args:
                return

            nombre = args[0][:-4]

            def update_gui():
                if app.chat_frame.mac:  # solo actualizar si estamos en la ventana de chat
                    app.chat_frame.text_area.configure(state="normal")
                    app.chat_frame.text_area.insert("end", f"{nombre} fue recibido\n")
                    app.chat_frame.text_area.configure(state="disabled")
                    app.chat_frame.text_area.see("end")  # asegurar scroll al final

            # programar la actualización en el hilo principal de Tkinter
            app.after(0, update_gui)

        files_folders_iface.set_receive_callback(file_received_callback)
        files_folders_iface.start_receiving_file()


    # Flag para evitar múltiples hilos de actualización
    updater_started = {"v": False}

    def start_and_update_devices():
        # Callback que se registra en the app; arranca el hilo que actualiza la lista periódicamente
        if updater_started["v"]:
            return
        updater_started["v"] = True

        def updater(): 
            while True:
                devices = list(ld.devices.keys())
                try:
                    app.devices_frame.set_devices(devices)
                except Exception:
                    pass
                time.sleep(2.0)

        threading.Thread(target=updater, daemon=True).start()
        # actualizar inmediatamente una vez
        app.devices_frame.set_devices(list(ld.devices.keys()))

    # Registrar callback en la app
    app.set_discovery_start_callback(start_and_update_devices)

    app.mainloop()

if __name__ == "__main__":
    main()