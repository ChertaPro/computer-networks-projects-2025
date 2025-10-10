import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox


# Configuración base de CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class LinkChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Configurar ventana principal
        self.title("Link-Chat")
        self.geometry("1100x700")  # tamaño inicial más grande
        self.minsize(800, 500)

        # Hacer que toda la ventana sea adaptable
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Crear los diferentes "frames" (pantallas)
        self.start_frame = StartFrame(self, self.show_devices)
        self.devices_frame = DevicesFrame(self, self.show_chat, self.show_start)
        self.chat_frame = ChatFrame(self, self.show_devices)

        # Mostrar el frame inicial
        self.show_frame(self.start_frame)

    def show_frame(self, frame):
        """Oculta todos los frames y muestra el indicado."""
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


# ==========================
# Frame de inicio
# ==========================
class StartFrame(ctk.CTkFrame):
    def __init__(self, master, start_callback):
        super().__init__(master)
        self.start_callback = start_callback

        # Hacer layout adaptable
        # Configurar grid para centrar un contenedor en el medio
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Contenedor central donde se colocarán los widgets (evita superposición)
        center_frame = ctk.CTkFrame(self, fg_color="transparent")
        center_frame.grid(row=1, column=0, sticky="nsew")
        center_frame.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(center_frame, text="Link-Chat", font=ctk.CTkFont(size=26, weight="bold"))
        subtitle = ctk.CTkLabel(center_frame, text="Mensajería a nivel de enlace – demo", font=ctk.CTkFont(size=14))
        start_button = ctk.CTkButton(center_frame, text="Empezar a chatear", command=self.start_callback)
        exit_button = ctk.CTkButton(center_frame, text="Salir", fg_color="gray30", hover_color="gray45", command=self.quit)

        # Colocar elementos centrados dentro del contenedor central con spacing
        title.grid(row=0, column=0, pady=(0, 6), padx=20)
        subtitle.grid(row=1, column=0, pady=(0, 14), padx=20)
        start_button.grid(row=2, column=0, pady=(0, 8))
        exit_button.grid(row=3, column=0)


# ==========================
# Frame de dispositivos
# ==========================
class DevicesFrame(ctk.CTkFrame):
    def __init__(self, master, chat_callback, go_back_callback):
        super().__init__(master)
        self.chat_callback = chat_callback
        self.go_back_callback = go_back_callback

        # Layout adaptable
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Encabezado
        header_frame = ctk.CTkFrame(self)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        header_frame.grid_columnconfigure(0, weight=1)

        header_label = ctk.CTkLabel(header_frame, text="Dispositivos detectados", font=ctk.CTkFont(size=18, weight="bold"))
        header_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        back_button = ctk.CTkButton(header_frame, text="← Volver", width=80, command=self.go_back_callback)
        back_button.grid(row=0, column=1, sticky="e", padx=10)

        # Frame con lista de dispositivos (scrollable)
        self.devices_list = ctk.CTkScrollableFrame(self)
        self.devices_list.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.devices_list.grid_columnconfigure(0, weight=1)

        # Footer
        self.selected_label = ctk.CTkLabel(self, text="Dispositivo seleccionado: –", anchor="w")
        self.selected_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

        # Cargar lista de ejemplo
        self.devices = [
            "10:16:0a:27:1a:32",
            "ac:f3:43:84:a2:ba",
            "de:ad:be:ef:00:01",
            "aa:bb:cc:11:22:33",
            "11:22:33:44:55:66",
            "ff:ee:dd:cc:bb:aa",
        ]
        self.selected_mac = None
        self.load_devices()

    def load_devices(self):
        for widget in self.devices_list.winfo_children():
            widget.destroy()

        for mac in self.devices:
            row_frame = ctk.CTkFrame(self.devices_list)
            row_frame.pack(fill="x", padx=5, pady=3)

            label = ctk.CTkLabel(row_frame, text=mac, width=150, anchor="w")
            label.pack(side="left", padx=5)

            button = ctk.CTkButton(
                row_frame, text="Chatear", width=80,
                command=lambda m=mac: self.select_device(m)
            )
            button.pack(side="right", padx=5)

            # Seleccionar MAC con click
            label.bind("<Button-1>", lambda e, m=mac: self.select_device(m))

    def select_device(self, mac):
        self.selected_mac = mac
        self.selected_label.configure(text=f"Dispositivo seleccionado: {mac}")
        self.chat_callback(mac)


# ==========================
# Frame de chat
# ==========================
class ChatFrame(ctk.CTkFrame):
    def __init__(self, master, go_back_callback):
        super().__init__(master)
        self.go_back_callback = go_back_callback
        self.mac = None

        # Layout adaptable
        # Row 0: header (no expand), Row 1: text area (expand), Row 2: bottom entry (no expand)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # Header
        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.grid(row=0, column=0, sticky="ew")
        self.header_frame.grid_columnconfigure(0, weight=1)

        self.header_label = ctk.CTkLabel(self.header_frame, text="Chat – ", font=ctk.CTkFont(size=16, weight="bold"))
        self.header_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)

        self.back_button = ctk.CTkButton(self.header_frame, text="← Volver", width=80, command=self.go_back_callback)
        self.back_button.grid(row=0, column=1, sticky="e", padx=10)

        # Área de chat (expandible)
        self.text_area = ctk.CTkTextbox(self, state="disabled")
        self.text_area.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # Entrada de mensaje
        bottom_frame = ctk.CTkFrame(self)
        bottom_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        bottom_frame.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(bottom_frame, placeholder_text="Escribe aquí...")
        self.entry.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

        # Botón para adjuntar archivo (aún no implementado)
        self.attach_button = ctk.CTkButton(bottom_frame, text="📎", width=40, command=self.attach_file)
        self.attach_button.grid(row=0, column=1, padx=(5, 2), pady=5)

        self.send_button = ctk.CTkButton(bottom_frame, text="Enviar", width=80, command=self.send_message)
        self.send_button.grid(row=0, column=2, padx=(2, 5), pady=5)

    def set_mac(self, mac):
        self.mac = mac
        self.header_label.configure(text=f"Chat – {mac}")

    def attach_file(self):
        # Mensaje informando que la funcionalidad no está implementada
        messagebox.showinfo("No implementado", "Enviar archivo no está implementado en esta demo.")

    def send_message(self):
        msg = self.entry.get().strip()
        if msg:
            self.text_area.configure(state="normal")
            self.text_area.insert("end", f"Tú: {msg}\n")
            self.text_area.configure(state="disabled")
            self.entry.delete(0, "end")


if __name__ == "__main__":
    app = LinkChatApp()
    app.mainloop()
