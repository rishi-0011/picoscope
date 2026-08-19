import ctypes
import os
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from PIL import Image, ImageTk
import sys

def read_control_info():
    config = {'Scope': 'ps5000a', 'Serial no.': None, 'Hardware resolution': '14BIT'}
    info_path = r"c:\Users\MaharshiM\Music\Picoscope\control info.txt"
    if os.path.exists(info_path):
        with open(info_path, 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    k, v = [x.strip() for x in line.split(':', 1)]
                    if v.lower() in ('none', ''): v = None
                    if k.lower().startswith('scope'): config['Scope'] = v
                    elif k.lower().startswith('serial'): config['Serial no.'] = v
                    elif k.lower().startswith('hardware'): config['Hardware resolution'] = v
    return config


try:
    import cv2
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "opencv-python"])
    import cv2

class PicoScopeApp:
    def __init__(self, root):
        self.root = root
        self.root.title('IAAS-Impulse Acquisition & Analysis Software')
        self.root.withdraw()
        
        self.is_scope_connected = False
        
        # --- Splash Screen Window ---
        self.splash = tk.Toplevel()
        self.splash.title("Loading...")
        
        self.splash_w = 600
        self.splash_h = 280
        self.result_square_size = 450
        
        self.splash.geometry(f"{self.splash_w}x{self.splash_h}")
        self.splash.configure(bg="#000000")
        self.splash.overrideredirect(True)
        
        screen_width = self.splash.winfo_screenwidth()
        screen_height = self.splash.winfo_screenheight()
        x = (screen_width // 2) - (self.splash_w // 2)
        y = (screen_height // 2) - (self.splash_h // 2)
        self.splash.geometry(f"{self.splash_w}x{self.splash_h}+{x}+{y}")
        
        self.video_path = r"C:\Users\MaharshiM\Music\Picoscope\IAAS.mp4"
        self.splash_label = tk.Label(self.splash, bg="#000000")
        self.splash_label.pack(expand=True, fill="both")
        
        if os.path.exists(self.video_path):
            self.cap = cv2.VideoCapture(self.video_path)
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.frame_delay = int(1000 / fps) if fps > 0 else 33
            
            self.alpha = 0.0
            self.splash.attributes("-alpha", self.alpha)
            self.fade_in_complete = False
            
            self.play_video_frame()
        else:
            self.splash_label.config(text="IAAS", font=("Segoe UI", 36, "bold"), fg="#ff4b4b")
            self.root.after(3000, self.close_splash)

    def play_video_frame(self):
        ret, frame = self.cap.read()
        
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self.cap.read()
            
        if ret:
            if not self.fade_in_complete:
                if self.alpha < 1.0:
                    self.alpha += 0.05
                    self.splash.attributes("-alpha", min(self.alpha, 1.0))
                else:
                    self.fade_in_complete = True
                    self.root.after(2500, self.start_fade_out)

            elif hasattr(self, 'fade_out_started') and self.fade_out_started:
                if self.alpha > 0.0:
                    self.alpha -= 0.05
                    self.splash.attributes("-alpha", max(self.alpha, 0.0))
                else:
                    self.close_splash()
                    return

            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img_open = Image.fromarray(frame).resize((self.splash_w, self.splash_h), Image.Resampling.LANCZOS)
            self.img_tk = ImageTk.PhotoImage(img_open)
            
            self.splash_label.config(image=self.img_tk)
            self.root.after(self.frame_delay, self.play_video_frame)

    def start_fade_out(self):
        self.fade_out_started = True

    def close_splash(self):
        if hasattr(self, 'cap'):
            self.cap.release()
        self.splash.destroy()
        self.initialize_direct_scan()

    def initialize_direct_scan(self):
        self.root.deiconify()
        self.root.overrideredirect(True)
        
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width // 2) - (self.result_square_size // 2)
        y = (screen_height // 2) - (self.result_square_size // 2)
        
        self.root.geometry(f"{self.result_square_size}x{self.result_square_size}+{x}+{y}")
        self.root.resizable(False, False)
        self.root.configure(bg="#ffffff")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.isolated_frame = tk.Frame(self.root, bg="#ffffff")
        self.isolated_frame.grid(row=0, column=0, sticky="nsew")
        
        self.isolated_frame.columnconfigure(0, weight=1)
        self.isolated_frame.rowconfigure(0, weight=1)

        self.run_hardware_scan()

    def try_connect_scope(self):
        """
        Actually checks if the physical hardware is connected by enumerating units,
        while suppressing the PicoScope splash screen using ctypes.
        """
        import threading
        import time

        def hide_splash():
            import ctypes
            try:
                EnumWindows = ctypes.windll.user32.EnumWindows
                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
                GetClassName = ctypes.windll.user32.GetClassNameW
                IsWindowVisible = ctypes.windll.user32.IsWindowVisible
                ShowWindow = ctypes.windll.user32.ShowWindow

                def foreach_window(hwnd, lParam):
                    if IsWindowVisible(hwnd):
                        buff = ctypes.create_unicode_buffer(256)
                        GetClassName(hwnd, buff, 256)
                        if 'PicoScope' in buff.value:
                            ShowWindow(hwnd, 0)
                    return True

                for _ in range(1000):
                    EnumWindows(EnumWindowsProc(foreach_window), 0)
                    time.sleep(0.005)
            except Exception:
                pass

        threading.Thread(target=hide_splash, daemon=True).start()

        try:
            import ctypes
            import importlib
            
            c_info = read_control_info()
            scope_model = c_info.get('Scope', 'ps5000a')
            
            picosdk_module = importlib.import_module(f"picosdk.{scope_model}")
            ps = getattr(picosdk_module, scope_model)
            
            count = ctypes.c_int16(0)
            serials_buffer = ctypes.create_string_buffer(256)
            serial_length = ctypes.c_int16(256)
            
            enum_func = getattr(ps, f"{scope_model}EnumerateUnits")
            status = enum_func(ctypes.byref(count), serials_buffer, ctypes.byref(serial_length))
            if count.value > 0:
                return True
            return False
        except Exception as e:
            print("Enum Error:", e)
            return False

    def run_hardware_scan(self):
        self.show_progress_screen("Detecting scope.........")
        self.root.after(2000, self._perform_scan)

    def show_progress_screen(self, message):
        for widget in self.isolated_frame.winfo_children():
            widget.destroy()

        progress_card = tk.Frame(self.isolated_frame, bg="#ffffff", padx=25, pady=25, bd=0)
        progress_card.grid(row=0, column=0, padx=20, sticky="ew")
        progress_card.columnconfigure(0, weight=1)

        try:
            img_path = r"c:\Users\MaharshiM\Music\Picoscope\images\iaas_logo.png"
            if os.path.exists(img_path):
                img = Image.open(img_path)
                img.thumbnail((390, 130))
                self.logo_img_progress = ImageTk.PhotoImage(img)
                logo_label = tk.Label(progress_card, image=self.logo_img_progress, bg="#ffffff")
                logo_label.grid(row=0, column=0, pady=(0, 15))
        except Exception:
            pass

        self.progress_text_label = tk.Label(
            progress_card,
            text=message,
            font=("Segoe UI", 12, "bold"),
            bg="#ffffff",
            fg="#000000",
            justify="center",
            anchor="center",
            wraplength=370
        )
        self.progress_text_label.grid(row=1, column=0, sticky="ew", pady=(0, 15))

        self.progress_bar = ttk.Progressbar(progress_card, orient="horizontal", length=300, mode="indeterminate")
        self.progress_bar.grid(row=2, column=0, pady=(0, 10))
        self.progress_bar.start(15)

    def _perform_scan(self):
        self.is_scope_connected = self.try_connect_scope()
        self.is_demo_mode = False
        if self.is_scope_connected:
            self.show_clean_result_screen("Scope found", bg_color="#ffffff", text_color="#16a34a", is_error=False)
            self.root.after(1500, self.show_setup_screen)
        else:
            self.is_scope_connected = True
            self.is_demo_mode = True
            self.show_clean_result_screen("Hardware missing. Entering DEMO MODE...", bg_color="#ffffff", text_color="#f59e0b", is_error=False)
            self.root.after(2000, self.show_setup_screen)

    def show_setup_screen(self):
        self.root.geometry("800x500")
        self.root.resizable(True, True)
        self.root.state("zoomed")
        self.root.overrideredirect(True)
        self.root.configure(bg="#8c97a8")
        self.isolated_frame.configure(bg="#8c97a8")
        
        import setup
        setup.build_setup_ui(self.isolated_frame, app=self)
        setup.update_status(self.isolated_frame, self.is_scope_connected)

    def show_waveform_screen(self):
        import waveform
        waveform.build_waveform_ui(self.isolated_frame, app=self)

    def show_clean_result_screen(self, message, bg_color, text_color, is_error=False):
        for widget in self.isolated_frame.winfo_children():
            widget.destroy()

        clean_card = tk.Frame(self.isolated_frame, bg=bg_color, padx=25, pady=25, bd=0)
        clean_card.grid(row=0, column=0, padx=20, sticky="ew")
        clean_card.columnconfigure(0, weight=1)
        
        try:
            img_path = r"c:\Users\MaharshiM\Music\Picoscope\images\iaas_logo.png"
            if os.path.exists(img_path):
                img = Image.open(img_path)
                img.thumbnail((390, 130))
                self.logo_img_result = ImageTk.PhotoImage(img)
                logo_label = tk.Label(clean_card, image=self.logo_img_result, bg=bg_color)
                logo_label.grid(row=0, column=0, pady=(0, 15))
        except Exception:
            pass

        self.result_text_label = tk.Label(
            clean_card,
            text=message,
            font=("Segoe UI", 12, "bold"),
            bg=bg_color,
            fg=text_color,
            justify="center",
            anchor="center",
            wraplength=370
        )
        self.result_text_label.grid(row=1, column=0, sticky="ew")

        if is_error:
            exit_button = tk.Button(
                clean_card,
                text="Exit",
                font=("Segoe UI", 10, "bold"),
                bg="#dc2626",
                fg="white",
                bd=0,
                padx=15,
                pady=6,
                cursor="hand2",
                command=self.root.quit
            )
            exit_button.grid(row=2, column=0, pady=(15, 0))
            self.root.after(10000, self.root.quit)

if __name__ == "__main__":
    app_window = tk.Tk()
    app = PicoScopeApp(app_window)
    app_window.mainloop()