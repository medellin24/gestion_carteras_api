import tkinter as tk
from tkinter import messagebox, ttk
import os
import json

from api_client.client import APIClient, APIError, api_client as global_api_client


PREFS_FILE = os.path.join(os.path.expanduser("~"), ".sirc_login.json")


class VentanaLogin(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Iniciar sesión")
        self.geometry("420x360")
        self.resizable(False, False)
        self.configure(bg="#f5f7fb")

        self.api = APIClient()

        # Estilos modernos
        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Card.TFrame', background="#ffffff", relief='flat')
        style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'), background="#ffffff", foreground="#1f2937")
        style.configure('Label.TLabel', font=('Segoe UI', 10), background="#ffffff", foreground="#374151")
        style.configure('TEntry', padding=6)
        style.configure('Primary.TButton', font=('Segoe UI', 10, 'bold'))

        # Contenedor tipo tarjeta
        card = ttk.Frame(self, style='Card.TFrame', padding=20)
        card.place(relx=0.5, rely=0.5, anchor='center')

        ttk.Label(card, text="Bienvenido a SIRC", style='Title.TLabel').pack(pady=(0, 12))
        ttk.Label(card, text="Inicia sesión para continuar", style='Label.TLabel').pack(pady=(0, 8))

        ttk.Label(card, text="Usuario (email)", style='Label.TLabel').pack(anchor='w')
        self.entry_user = ttk.Entry(card, width=36)
        self.entry_user.pack()

        ttk.Label(card, text="Contraseña", style='Label.TLabel').pack(anchor='w', pady=(10, 0))
        pass_frame = ttk.Frame(card, style='Card.TFrame')
        pass_frame.pack(fill='x')
        self.entry_pass = ttk.Entry(pass_frame, width=30, show='*')
        self.entry_pass.pack(side='left', fill='x', expand=True)
        self.var_show = tk.BooleanVar(value=False)
        ttk.Checkbutton(pass_frame, text="Mostrar", variable=self.var_show, command=self._toggle_password).pack(side='left', padx=(8, 0))

        # Recordar datos
        self.var_remember_user = tk.BooleanVar(value=True)
        self.var_remember_pass = tk.BooleanVar(value=False)
        checks = ttk.Frame(card, style='Card.TFrame')
        checks.pack(fill='x', pady=(10, 6))
        ttk.Checkbutton(checks, text="Recordar usuario", variable=self.var_remember_user).pack(side='left')
        ttk.Checkbutton(checks, text="Recordar contraseña", variable=self.var_remember_pass).pack(side='right')

        btns = ttk.Frame(card, style='Card.TFrame')
        btns.pack(pady=(12, 0), fill='x')
        ttk.Button(btns, text="Ingresar", style='Primary.TButton', command=self._do_login).pack(side='left', expand=True, fill='x')
        ttk.Button(btns, text="Registrarse", command=self._open_signup).pack(side='left', expand=True, fill='x', padx=(8, 0))

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
            self.destroy()
        except APIError as e:
            messagebox.showerror("Error de login", e.message)

    def _open_signup(self):
        VentanaSignup(self).wait_window()

    def _toggle_password(self):
        self.entry_pass.config(show='' if self.var_show.get() else '*')

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
                if data.get('remember_user'):  # default True
                    self.var_remember_user.set(True)
                else:
                    self.var_remember_user.set(False)
                if data.get('remember_pass') and data.get('password'):
                    self.var_remember_pass.set(True)
                    self.entry_pass.insert(0, data.get('password'))
        except Exception:
            pass

    def _save_prefs(self, username: str, password: str):
        data = {
            'username': username if self.var_remember_user.get() else '',
            'remember_user': bool(self.var_remember_user.get()),
            'remember_pass': bool(self.var_remember_pass.get()),
            'password': password if self.var_remember_pass.get() else ''
        }
        try:
            with open(PREFS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f)
        except Exception:
            pass


class VentanaSignup(tk.Toplevel):
    def __init__(self, master=None):
        super().__init__(master)
        self.title("Registro de cuenta")
        self.geometry("460x360")
        self.resizable(False, False)
        self.configure(bg="#f5f7fb")

        self.api = APIClient()

        style = ttk.Style(self)
        try:
            style.theme_use('clam')
        except Exception:
            pass
        style.configure('Card.TFrame', background="#ffffff")
        style.configure('Title.TLabel', font=('Segoe UI', 14, 'bold'), background="#ffffff", foreground="#1f2937")
        style.configure('Label.TLabel', font=('Segoe UI', 10), background="#ffffff", foreground="#374151")

        card = ttk.Frame(self, style='Card.TFrame', padding=20)
        card.place(relx=0.5, rely=0.5, anchor='center')

        ttk.Label(card, text="Crear nueva cuenta", style='Title.TLabel').pack(pady=(0, 12))

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

        # Plan
        self.var_trial = tk.BooleanVar(value=True)
        ttk.Checkbutton(card, text="Trial 1 empleado por 30 días", variable=self.var_trial, command=self._toggle_plan).pack(pady=(10, 4), anchor='w')

        self.frame_plan = ttk.Frame(card, style='Card.TFrame')
        ttk.Label(self.frame_plan, text="Número de empleados del plan", style='Label.TLabel').grid(row=0, column=0, padx=4)
        self.entry_plan = ttk.Entry(self.frame_plan, width=10)
        self.entry_plan.grid(row=0, column=1, padx=4)
        self.frame_plan.pack_forget()

        ttk.Button(card, text="Crear cuenta", style='Primary.TButton', command=self._do_signup).pack(pady=12, fill='x')
        self.after(50, self._center_window)

    def _toggle_plan(self):
        if self.var_trial.get():
            self.frame_plan.pack_forget()
        else:
            self.frame_plan.pack(pady=6)

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

    def _center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw // 2) - (w // 2)
        y = (sh // 2) - (h // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")


