import tkinter as tk
from tkinter import messagebox, ttk
import os
import json
import importlib.util
import importlib
import winsound

from api_client.client import APIClient, APIError, api_client as global_api_client
from resource_loader import asset_path


PREFS_FILE = os.path.join(os.path.expanduser("~"), ".sirc_login.json")


class VentanaLogin(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Iniciar sesión")
        self.resizable(False, False)
        self.configure(bg="#000000")
        try:
            icon_path = asset_path('assets', 'icons', 'home.ico')
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass

        self.api = APIClient()

        # Estilos mínimos
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure(
            'GlassLogin.TEntry',
            fieldbackground='#f7cfee',
            background='#f7cfee',
            foreground='#1f2937',
            insertcolor='#1f2937',
            selectbackground='#f0abfc',
            selectforeground='#1f2937',
            padding=4,
            font=('Segoe UI', 12)
        )
        style.configure(
            'GlassLogin.Primary.TButton',
            background='#374151',
            foreground='#f8fafc',
            borderwidth=0,
            padding=(10, 4),
            font=('Segoe UI Semibold', 8)
        )
        style.map(
            'GlassLogin.Primary.TButton',
            background=[('active', '#111827')],
            foreground=[('disabled', '#cbd5f5')]
        )
        style.configure(
            'GlassLogin.Secondary.TButton',
            background='#374151',
            foreground='#f8fafc',
            borderwidth=0,
            padding=(10, 4),
            font=('Segoe UI Semibold', 8)
        )
        style.map(
            'GlassLogin.Secondary.TButton',
            background=[('active', '#1f2937')],
            foreground=[('disabled', '#d1d5db')]
        )

        # Canvas con imagen de fondo a tamaño fijo
        TARGET_WIDTH = 460
        TARGET_HEIGHT = 360
        self.geometry(f"{TARGET_WIDTH}x{TARGET_HEIGHT}")
        self._bg_img = None  # ImageTk.PhotoImage
        self._img_w = 0
        self._img_h = 0
        try:
            from PIL import Image, ImageTk
            candidates = [
                asset_path('assets', 'icons', 'login_image.png'),
                asset_path('assets', 'iconos', 'login_image.png'),
                asset_path('assets', 'login_bg.png'),
                asset_path('assets', 'login_bg.jpg'),
                asset_path('assets', 'backgrounds', 'login_bg.jpg'),
            ]
            img = None
            for p in candidates:
                if os.path.exists(p):
                    img = Image.open(p)
                    break
            if img is not None:
                try:
                    resample = Image.Resampling.LANCZOS
                except Exception:
                    resample = Image.LANCZOS
                img = img.resize((TARGET_WIDTH, TARGET_HEIGHT), resample)
                self._img_w, self._img_h = TARGET_WIDTH, TARGET_HEIGHT
                self.canvas = tk.Canvas(self, width=TARGET_WIDTH, height=TARGET_HEIGHT, highlightthickness=0, bd=0, bg="#000000")
                self.canvas.pack(fill='both', expand=False)
                self._bg_img = ImageTk.PhotoImage(img)
                self.canvas.create_image(0, 0, image=self._bg_img, anchor='nw')
        except Exception:
            pass

        # Si el canvas no existe (no se pudo cargar imagen), crear uno básico
        if not hasattr(self, 'canvas'):
            self._img_w, self._img_h = TARGET_WIDTH, TARGET_HEIGHT
            self.canvas = tk.Canvas(self, width=TARGET_WIDTH, height=TARGET_HEIGHT, highlightthickness=0, bd=0, bg="#000000")
            self.canvas.pack(fill='both', expand=False)

        # Entradas y checkbox sobre la imagen (coordenadas relativas para fácil ajuste)
        # Coordenadas relativas (0..1) estimadas respecto de la imagen proporcionada
        self._username_pos = (0.465, 0.49)
        self._password_pos = (0.465, 0.6)
        self._remember_pos = (0.31, 0.69)
        entry_width_px = int(self._img_w * 0.34) + 4
        entry_height_px = 28

        self.entry_user = ttk.Entry(self, style='GlassLogin.TEntry')
        self.entry_pass = ttk.Entry(self, show='*', style='GlassLogin.TEntry')
        self.var_remember = tk.BooleanVar(value=True)
        chk_style = 'GlassLogin.Checkbox.TCheckbutton'
        try:
            style.configure(chk_style, font=('Segoe UI', 6))
        except Exception:
            chk_style = None
        chk = ttk.Checkbutton(self, text="Recordarme", variable=self.var_remember, style=chk_style if chk_style else 'TCheckbutton')
        btn_login = ttk.Button(self, text="LOGIN", style='GlassLogin.Primary.TButton', command=self._do_login)
        btn_signup = ttk.Button(self, text="SIGNUP", style='GlassLogin.Secondary.TButton', command=self._open_signup)

        ux = int(self._username_pos[0] * self._img_w)
        uy = int(self._username_pos[1] * self._img_h)
        px = int(self._password_pos[0] * self._img_w)
        py = int(self._password_pos[1] * self._img_h)
        rx = int(self._remember_pos[0] * self._img_w)
        ry = int(self._remember_pos[1] * self._img_h)
        login_x = int(self._img_w * 0.51)
        login_y = int(self._img_h * 0.712)
        signup_x = int(self._img_w * 0.51)
        signup_y = int(self._img_h * 0.872)
        button_width_px = max(82, int(entry_width_px * 0.52))
        button_height_px = max(24, int(entry_height_px * 0.68))

        self.canvas.create_window(ux, uy, window=self.entry_user, width=entry_width_px, height=entry_height_px, anchor='center')
        self.canvas.create_window(px, py, window=self.entry_pass, width=entry_width_px, height=entry_height_px, anchor='center')
        self.canvas.create_window(rx, ry, window=chk, anchor='center')
        self.canvas.create_window(login_x, login_y, window=btn_login, width=button_width_px, height=button_height_px, anchor='center')
        self.canvas.create_window(signup_x, signup_y, window=btn_signup, width=button_width_px, height=button_height_px, anchor='center')

        self.bind("<Return>", lambda e: self._do_login())

        self.result = None  # (tokens, role)
        self._load_prefs()
        self.after(50, self._center_window)

    def _do_login(self):
        username = self.entry_user.get().strip()
        password = self.entry_pass.get().strip()
        if not username or not password:
            messagebox.showwarning("Campos requeridos", "Ingrese usuario y contraseña")
            return
        try:
            tokens = self.api.login(username, password)
            # Propagar token al cliente global usado por el resto de la app
            global_api_client.config.auth_token = self.api.config.auth_token
            global_api_client.session.headers['Authorization'] = self.api.session.headers.get('Authorization', '')
            # ✅ MUY IMPORTANTE: al cambiar de cuenta sin cerrar la app,
            # limpiar cachés del cliente global para no “reusar” empleados/tipos de la cuenta anterior.
            try:
                global_api_client.clear_cache()
                # También limpiar cookies por seguridad (requests Session)
                try:
                    global_api_client.session.cookies.clear()
                except Exception:
                    pass
            except Exception:
                pass
            # Guardar refresh y rol si aplica
            try:
                global_api_client._refresh_token = tokens.get('refresh_token')
                global_api_client._role = tokens.get('role')
            except Exception:
                pass
            # Propagar timezone al cliente global para que los frames lo lean correctamente
            try:
                tz_post = self.api.get_user_timezone() or global_api_client.get_user_timezone()
                if tz_post:
                    global_api_client._timezone = tz_post
            except Exception:
                pass
            # Guardar preferencias
            self._save_prefs(username, password)
            self.result = (tokens, tokens.get('role'), username)
            messagebox.showinfo("Éxito", f"Sesión iniciada como {tokens.get('role')}")
            try:
                play_login_sound()
            except Exception:
                pass
            self.destroy()
        except APIError as e:
            messagebox.showerror("Error de login", e.message)

    def _open_signup(self):
        VentanaSignup(self).wait_window()

    def _center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _load_prefs(self):
        try:
            if os.path.exists(PREFS_FILE):
                with open(PREFS_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                user = data.get('username')
                if user:
                    self.entry_user.insert(0, user)
                remember_user = bool(data.get('remember_user'))
                remember_pass = bool(data.get('remember_pass'))
                self.var_remember.set(remember_user or remember_pass)
                if remember_pass and data.get('password'):
                    self.entry_pass.insert(0, data.get('password'))
        except Exception:
            pass

    def _save_prefs(self, username: str, password: str):
        data = {
            'username': username if self.var_remember.get() else '',
            'remember_user': bool(self.var_remember.get()),
            'remember_pass': bool(self.var_remember.get()),
            'password': password if self.var_remember.get() else ''
        }
        try:
            with open(PREFS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass

def play_login_sound():
    try:
        wav_path = asset_path('assets', 'sounds', 'efecto_login.wav')
        mp3_path = asset_path('assets', 'sounds', 'efecto_login.mp3')
        if os.path.exists(wav_path):
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        if os.path.exists(mp3_path):
            if importlib.util.find_spec('pygame') is not None:
                pygame = importlib.import_module('pygame')
                if not pygame.mixer.get_init():
                    pygame.mixer.init(frequency=44100, size=-16, channels=2)
                try:
                    pygame.mixer.music.load(mp3_path)
                    pygame.mixer.music.set_volume(1.0)
                    pygame.mixer.music.play()
                    return
                except Exception:
                    try:
                        sound = pygame.mixer.Sound(mp3_path)
                        channel = sound.play()
                        if channel is not None:
                            channel.set_volume(1.0)
                            return
                    except Exception:
                        pass
            if importlib.util.find_spec('playsound') is not None:
                try:
                    playsound = importlib.import_module('playsound')
                    playsound.playsound(mp3_path, block=False)
                    return
                except Exception:
                    pass
    except Exception:
        pass

class VentanaSignup(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Registro de cuenta")
        self.geometry("460x360")
        self.resizable(False, False)
        self.configure(bg="#0f172a")

        self.api = APIClient()

        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Card.TFrame', background="#24303f")
        style.configure('Title.TLabel', font=('Segoe UI', 18, 'bold'), background="#000000", foreground="#e5f0ff")
        style.configure('Label.TLabel', font=('Segoe UI', 10), background="#24303f", foreground="#e5e7eb")
        style.configure('Primary.TButton', font=('Segoe UI', 10, 'bold'))
        style.configure('PrimaryLogin.TButton', font=('Segoe UI', 10, 'bold'), padding=(12, 8), background='#0B63B5', foreground='white')
        style.map('PrimaryLogin.TButton', background=[('active', '#0A4F8E'), ('pressed', '#0A4F8E')])

        # Botón volver (pequeño) fuera del formulario
        self.btn_volver = ttk.Button(self, text="←", width=2, command=self._volver_login)
        self.btn_volver.place(x=8, y=6)

        # Fondo
        self._bg_img = None
        try:
            from PIL import Image, ImageTk
            candidates = [
                asset_path('assets', 'icons', 'login_image.png'),
                asset_path('assets', 'iconos', 'login_image.png'),
                asset_path('assets', 'login_bg.png'),
                asset_path('assets', 'login_bg.jpg'),
                asset_path('assets', 'backgrounds', 'login_bg.jpg'),
            ]
            for p in candidates:
                if os.path.exists(p):
                    img = Image.open(p)
                    try:
                        resample = Image.Resampling.LANCZOS
                    except Exception:
                        resample = Image.LANCZOS
                    img = img.resize((460, 360), resample)
                    self._bg_img = ImageTk.PhotoImage(img)
                    break
            if self._bg_img is not None:
                bg_label = ttk.Label(self, image=self._bg_img)
                bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                try:
                    self.btn_volver.lift()
                except Exception:
                    pass
        except Exception:
            pass

        # Título grande
        try:
            title = ttk.Label(self, text="CARTERAS", style='Title.TLabel')
            title.place(relx=0.5, y=26, anchor='n')
        except Exception:
            pass

        card = ttk.Frame(self, style='Card.TFrame', padding=20)
        card.place(relx=0.5, rely=0.48, anchor='center')

        ttk.Label(card, text="Crear cuenta nueva", style='Title.TLabel', background='#24303f').pack(pady=(0, 12))

        ttk.Label(card, text="Nombre del negocio", style='Label.TLabel').pack(anchor='w')
        self.entry_negocio = ttk.Entry(card, width=38)
        self.entry_negocio.pack()

        ttk.Label(card, text="Email (admin)", style='Label.TLabel').pack(anchor='w', pady=(8, 0))
        self.entry_email = ttk.Entry(card, width=38)
        self.entry_email.pack()

        ttk.Label(card, text="Contraseña admin", style='Label.TLabel').pack(anchor='w', pady=(8, 0))
        pass_frame = ttk.Frame(card, style='Card.TFrame')
        pass_frame.pack(fill='x')
        self.entry_pass = ttk.Entry(pass_frame, width=30, show='*')
        self.entry_pass.pack(side='left', fill='x', expand=True)
        self.var_show_signup = tk.BooleanVar(value=False)
        ttk.Checkbutton(pass_frame, text="Mostrar", variable=self.var_show_signup, command=lambda: self.entry_pass.config(show='' if self.var_show_signup.get() else '*')).pack(side='left', padx=(8, 0))

        # Trial / plan
        self.var_trial = tk.BooleanVar(value=False)
        plan_row = ttk.Frame(card, style='Card.TFrame')
        plan_row.pack(fill='x', pady=(10, 4))
        ttk.Checkbutton(plan_row, text="Gratis 1 empleado por 30 días", variable=self.var_trial, command=self._toggle_plan).pack(side='left')
        ttk.Label(plan_row, text="Empleados:", style='Label.TLabel').pack(side='left', padx=(12, 4))
        self.entry_plan = ttk.Entry(plan_row, width=8)
        self.entry_plan.pack(side='left')
        # Estado inicial del plan (gratis desmarcado → entrada habilitada)
        self._toggle_plan()

        ttk.Button(card, text="Crear cuenta", style='PrimaryLogin.TButton', command=self._do_signup).pack(pady=12, fill='x')
        self.after(50, self._center_window)

    def _toggle_plan(self):
        if self.var_trial.get():
            try:
                self.entry_plan.config(state='disabled')
                self.entry_plan.delete(0, tk.END)
                self.entry_plan.insert(0, '1')
            except Exception:
                pass
        else:
            try:
                self.entry_plan.config(state='normal')
            except Exception:
                pass

    def _do_signup(self):
        negocio = self.entry_negocio.get().strip()
        email = self.entry_email.get().strip()
        pwd = self.entry_pass.get().strip()
        if not negocio or not email or not pwd:
            messagebox.showwarning("Campos requeridos", "Complete todos los campos")
            return
        try:
            if self.var_trial.get():
                res = self.api.signup_public(negocio, email, pwd, None)
            else:
                try:
                    n = int(self.entry_plan.get().strip())
                except Exception:
                    messagebox.showwarning("Plan inválido", "Ingrese un número de empleados válido")
                    return
                res = self.api.signup_public(negocio, email, pwd, n)
            messagebox.showinfo("Cuenta creada", f"Cuenta #{res.get('cuenta_id')} creada. Trial: {res.get('trial')}. Máx empleados: {res.get('max_empleados')}")
            self.destroy()
        except APIError as e:
            messagebox.showerror("Error de registro", e.message)

    def _volver_login(self):
        try:
            if self.master is not None:
                self.master.deiconify()
        except Exception:
            pass
        self.destroy()

    def _center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")


