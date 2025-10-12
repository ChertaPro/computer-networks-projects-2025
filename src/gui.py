# gui.py (corregido)
import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import tkinter.simpledialog as simpledialog
from tkinter import filedialog
import os

# Configuración base de CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


# Hacemos que la app herede de TkinterDnD.Tk (no mezclar con ctk.CTk en la herencia)
class LinkChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()  # inicializa ctk.CTk correctamente

        # --- importante: hacer que el contenido principal llene todo el root ---
        self.title("Link-Chat")
        self.geometry("1100x700")
        self.minsize(800, 500)

        # Configurar grid del root para que los frames ocupen todo el espacio
        # (sin esto los frames se quedan con tamaño mínimo y aparece el fondo blanco)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Callback para discovery
        self.discovery_start_callback = None
        self.link_iface = None
        self.files_folders_iface = None

        # Frames: usamos ctk.CTkFrame y widgets customtkinter dentro del root CTk
        self.start_frame = StartFrame(self, self._on_start_requested)
        self.devices_frame = DevicesFrame(self, self.show_chat, self.show_start)
        self.chat_frame = ChatFrame(self, self.show_devices)

        self.show_frame(self.start_frame)


    def show_frame(self, frame):
        for widget in (self.start_frame, self.devices_frame, self.chat_frame):
            widget.grid_forget()
        frame.grid(row=0, column=0, sticky="nsew")

    def show_start(self):
        self.show_frame(self.start_frame)

    def show_devices(self):
        self.show_frame(self.devices_frame)

    def show_chat(self, mac):
        self.chat_frame.set_mac(mac)
        self.show_frame(self.chat_frame)

    def set_discovery_start_callback(self, cb):
        self.discovery_start_callback = cb

    def _on_start_requested(self):
        if callable(self.discovery_start_callback):
            try:
                self.discovery_start_callback()
            except Exception:
                pass
        self.show_frame(self.devices_frame)


# ----------------------------
# StartFrame (sin cambios funcionales significativos)
# ----------------------------
class StartFrame(ctk.CTkFrame):
    def __init__(self, master, start_callback):
        super().__init__(master)
        self.start_callback = start_callback
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.grid(row=1, column=0, sticky="nsew")
        center_frame.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(center_frame, text="Link-Chat", font=ctk.CTkFont(size=30, weight="bold"))
        subtitle = ctk.CTkLabel(center_frame, text="Mensajería a nivel de enlace – demo", font=ctk.CTkFont(size=16))
        start_button = ctk.CTkButton(center_frame, text="Empezar a chatear", command=self.start_callback,
                                     width=260, height=56, font=ctk.CTkFont(size=16, weight="bold"))
        exit_button = ctk.CTkButton(center_frame, text="Salir", fg_color="gray30", hover_color="gray45", command=self.quit,
                                    width=220, height=48, font=ctk.CTkFont(size=14))

        title.grid(row=0, column=0, pady=(0, 6), padx=20)
        subtitle.grid(row=1, column=0, pady=(0, 14), padx=20)
        start_button.grid(row=2, column=0, pady=(0, 8))
        exit_button.grid(row=3, column=0)


# ----------------------------
# DevicesFrame (pequeños cambios)
# ----------------------------
class DevicesFrame(ctk.CTkFrame):
    def __init__(self, master, chat_callback, go_back_callback):
        super().__init__(master)
        self.chat_callback = chat_callback
        self.go_back_callback = go_back_callback

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(self)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header_frame.grid_columnconfigure(0, weight=1)

        header_label = ctk.CTkLabel(header_frame, text="Dispositivos detectados", font=ctk.CTkFont(size=18, weight="bold"))
        header_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        back_button = ctk.CTkButton(header_frame, text="← Volver", width=140, height=44, command=self.go_back_callback,
                                    font=ctk.CTkFont(size=14))
        back_button.grid(row=0, column=1, sticky="e", padx=10)

        broadcast_button = ctk.CTkButton(header_frame, text="Broadcast", width=160, height=44, command=self._on_broadcast,
                                         font=ctk.CTkFont(size=14))
        broadcast_button.grid(row=0, column=2, sticky="e", padx=5)

        self.devices_list = ctk.CTkScrollableFrame(self)
        self.devices_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.devices_list.grid_columnconfigure(0, weight=1)

        self.selected_label = ctk.CTkLabel(self, text="Dispositivo seleccionado: –", anchor="w",
                                           font=ctk.CTkFont(size=14))
        self.selected_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        self.devices = []
        self.selected_mac = None
        self.load_devices()

    def load_devices(self):
        self.after_idle(self._load_devices_impl)

    def _load_devices_impl(self):
        for widget in self.devices_list.winfo_children():
            widget.destroy()

        if not self.devices:
            empty_label = ctk.CTkLabel(self.devices_list, text="No se han detectado dispositivos todavía.", anchor="w",
                                       font=ctk.CTkFont(size=14))
            empty_label.pack(fill="x", padx=5, pady=8)
            return

        for mac in self.devices:
            row_frame = ctk.CTkFrame(self.devices_list)
            row_frame.pack(fill="x", padx=5, pady=3)

            label = ctk.CTkLabel(row_frame, text=mac, width=260, anchor="w", font=ctk.CTkFont(size=13))
            label.pack(side="left", padx=5)

            button = ctk.CTkButton(
                row_frame, text="Chatear", width=140, height=44,
                command=lambda m=mac: self.select_device(m), font=ctk.CTkFont(size=13, weight="bold")
            )
            button.pack(side="right", padx=5)

            label.bind("<Button-1>", lambda e, m=mac: self.select_device(m))

    def set_devices(self, devices):
        try:
            self.devices = sorted(list(devices))
        except Exception:
            self.devices = list(devices)
        self.load_devices()

    def select_device(self, mac):
        self.selected_mac = mac
        self.selected_label.configure(text=f"Dispositivo seleccionado: {mac}")
        self.chat_callback(mac)

    def _on_broadcast(self):
        msg = simpledialog.askstring("Broadcast", "Mensaje para enviar a todo el mundo:")
        if not msg:
            return
        try:
            link_iface = getattr(self.master, "link_iface", None)
            if link_iface:
                link_iface.send_message("ff:ff:ff:ff:ff:ff", msg)
                messagebox.showinfo("Broadcast", "Mensaje enviado por broadcast.")
            else:
                messagebox.showwarning("Broadcast", "Interfaz no disponible para enviar.")
        except Exception as e:
            messagebox.showerror("Broadcast", f"Error al enviar broadcast: {e}")


# ----------------------------
# ChatFrame (modificaciones: usar tk.Label para DnD)
# ----------------------------
class ChatFrame(ctk.CTkFrame):
    def __init__(self, master, go_back_callback):
        super().__init__(master)
        self.go_back_callback = go_back_callback
        self.mac = None

        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        self.header_label = ctk.CTkLabel(self.header_frame, text="Chat – ", font=ctk.CTkFont(size=18, weight="bold"))
        self.header_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        self.back_button = ctk.CTkButton(self.header_frame, text="← Volver", width=140, height=44,
                                         command=self.go_back_callback, font=ctk.CTkFont(size=14))
        self.back_button.grid(row=0, column=1, sticky="e", padx=10)

        self.text_area = ctk.CTkTextbox(self, state="disabled", font=ctk.CTkFont(size=14))
        self.text_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(bottom_frame, placeholder_text="Escribe aquí...", font=ctk.CTkFont(size=14),
                                  height=44)
        self.entry.bind("<Return>", lambda event: self.send_message())

        self.entry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        self.clear_button = ctk.CTkButton(bottom_frame, text="Limpiar chat", width=120, height=44,
                                  command=self.clear_chat, font=ctk.CTkFont(size=14))
        self.clear_button.grid(row=0, column=3, padx=(5,5), pady=5)

        self.attach_button = ctk.CTkButton(bottom_frame, text="📎", width=64, height=44, command=self.attach_file,
                                           font=ctk.CTkFont(size=14))
        self.attach_button.grid(row=0, column=1, padx=(5, 2), pady=5)

        self.send_button = ctk.CTkButton(bottom_frame, text="Enviar", width=160, height=44, command=self.send_message,
                                         font=ctk.CTkFont(size=14, weight="bold"))
        self.send_button.grid(row=0, column=2, padx=(2, 5), pady=5)

    def clear_chat(self):
        self.text_area.configure(state="normal")
        self.text_area.delete("1.0", "end")
        self.text_area.configure(state="disabled")

    def abrir_ventana_adjuntar(self):
        files_folders_iface = getattr(self.master, "files_folders_iface", None)

        ventana = ctk.CTkToplevel(self)
        ventana.title("Adjuntar archivo o carpeta")
        # Ventana agrandada (antes "520x260")
        ventana.geometry("720x380")
        ventana.transient(self.master)
        ventana.grid_columnconfigure(0, weight=1)
        ventana.grid_rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(ventana, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
        main_frame.grid_columnconfigure(0, weight=1)

        ventana.after(10, ventana.grab_set)

        # Ajustados wraplength para usar el ancho mayor
        ruta_label = ctk.CTkLabel(main_frame, text="Ningún archivo o carpeta seleccionado", anchor="center",
                                font=ctk.CTkFont(size=13), wraplength=680)
        ruta_label.grid(row=0, column=0, sticky="nsew", pady=(0, 12))

        archivo_path = {"path": None}

        # ------------------- Funciones de selección -------------------
        def seleccionar_archivo():
            path = filedialog.askopenfilename(parent=ventana, title="Seleccionar archivo")
            if path:
                archivo_path["path"] = path
                ruta_label.configure(text=f"Archivo seleccionado:\n{path}")

        def seleccionar_carpeta():
            path = filedialog.askdirectory(parent=ventana, title="Seleccionar carpeta")
            if path:
                archivo_path["path"] = path
                ruta_label.configure(text=f"Carpeta seleccionada:\n{path}")

        # ------------------- Botones de selección -------------------
        btn_archivo = ctk.CTkButton(main_frame, text="Seleccionar archivo", command=seleccionar_archivo, height=44)
        btn_archivo.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        btn_carpeta = ctk.CTkButton(main_frame, text="Seleccionar carpeta", command=seleccionar_carpeta, height=44)
        btn_carpeta.grid(row=2, column=0, sticky="ew", pady=(0, 8))

        ayuda_label = ctk.CTkLabel(main_frame, text="Selecciona un archivo o carpeta para enviar.",
                                font=ctk.CTkFont(size=12), wraplength=680, anchor="w", justify="left")
        ayuda_label.grid(row=3, column=0, sticky="ew", pady=(6, 10))

        # ------------------- Función de envío -------------------
        def enviar():
            if archivo_path["path"]:
                try:
                    if files_folders_iface and self.mac:
                        files_folders_iface.send_folder(self.mac, archivo_path["path"])
                        nombre = os.path.basename(archivo_path["path"])
                        self.text_area.configure(state="normal")
                        self.text_area.insert("end", f"Tú: el archivo {nombre} fue enviado\n")
                        self.text_area.configure(state="disabled")
                        ventana.destroy()
                    else:
                        messagebox.showwarning("Error", "Interfaz o destinatario no disponibles.", parent=ventana)
                except Exception as e:
                    messagebox.showerror("Error de envío", f"No se pudo enviar:\n{e}", parent=ventana)
            else:
                messagebox.showwarning("Sin selección", "Por favor, selecciona un archivo o carpeta antes de enviar.", parent=ventana)

        # ------------------- Botón de enviar -------------------
        btn_enviar = ctk.CTkButton(main_frame, text="Enviar", command=enviar, height=44,
                                font=ctk.CTkFont(size=14, weight="bold"))
        btn_enviar.grid(row=4, column=0, sticky="ew", pady=(6, 0))



    def set_mac(self, mac):
        self.mac = mac
        self.header_label.configure(text=f"Chat – {mac}")

    def attach_file(self):
        if not self.mac:
            messagebox.showwarning("Adjuntar archivo", "Selecciona un dispositivo primero.")
            return
        self.abrir_ventana_adjuntar()

    def send_message(self):
        msg = self.entry.get().strip()
        if msg:
            try:
                link_iface = getattr(self.master, "link_iface", None)
                if link_iface and self.mac:
                    link_iface.send_message(self.mac, msg)
                self.text_area.configure(state="normal")
                self.text_area.insert("end", f"Tú: {msg}\n")
                self.text_area.configure(state="disabled")
                self.text_area.see("end")
                self.entry.delete(0, "end")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo enviar el mensaje: {e}")
