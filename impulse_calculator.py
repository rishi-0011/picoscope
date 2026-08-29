import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from PIL import Image, ImageTk

class SmartNavigationToolbar(NavigationToolbar2Tk):
    # Remove native Back and Forward so we can inject our own non-disabling buttons
    toolitems = [t for t in NavigationToolbar2Tk.toolitems if t[0] not in ('Back', 'Forward')]
    
    def __init__(self, canvas, window):
        super().__init__(canvas, window)


# Enable High-DPI Awareness for Windows to prevent blurriness
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass 

# Configure global Matplotlib font sizes to balance with High-DPI
plt.rc('font', size=11)
plt.rc('axes', titlesize=13)
plt.rc('axes', labelsize=11)
plt.rc('xtick', labelsize=10)
plt.rc('ytick', labelsize=10)
plt.rc('legend', fontsize=10)

class IECAnalyzerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("IEC 60060-1 Impulse Waveform Analyzer")
        self.geometry("1400x800")
        
        style = ttk.Style(self)
        
        # --- FIXED ROW HEIGHT FOR 11PT FONT ---
        # Increased rowheight from 28 to 38 so the 11pt text doesn't overlap vertically
        style.configure("Custom.Treeview", font=('Segoe UI', 11), rowheight=55)
        style.configure("Custom.Treeview.Heading", font=('Segoe UI', 11, 'bold'))

        # Variables
        self.file_path = None
        self.data = None
        self.show_markers_var = tk.BooleanVar(value=True)
        self.show_kfilter_var = tk.BooleanVar(value=False)
        self.wav_type_var = tk.StringVar(value="Auto")

        self._build_ui()

    def _build_ui(self):
        # --- Top Toolbar ---
        toolbar = ttk.Frame(self, relief=tk.RAISED, borderwidth=1)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        btn_load = ttk.Button(toolbar, text="📂 Load Waveform", command=self.load_file)
        btn_load.grid(row=0, column=0, padx=(10, 10), pady=10)

        chk_mean_curve = ttk.Checkbutton(toolbar, text="Show IEC Mean Curve", 
                                      variable=self.show_kfilter_var, command=self.update_plot)
        chk_mean_curve.grid(row=0, column=3, padx=(25, 10), pady=10)

        chk_markers = ttk.Checkbutton(toolbar, text="Show Markers", 
                                      variable=self.show_markers_var, command=self.update_plot)
        chk_markers.grid(row=0, column=4, padx=10, pady=10)

        # --- Main Layout (PanedWindow) ---
        paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Left Side: Matplotlib Plot ---
        self.plot_frame = ttk.Frame(paned_window)
        paned_window.add(self.plot_frame, weight=3)

        self.fig, self.ax = plt.subplots(figsize=(8, 6))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        
        # Create a container for the toolbars at the bottom
        toolbar_container = ttk.Frame(self.plot_frame)
        toolbar_container.pack(side=tk.BOTTOM, fill=tk.X)

        self.nav_toolbar = SmartNavigationToolbar(self.canvas, toolbar_container)
        self.nav_toolbar.pack(side=tk.LEFT)

        try:
            import matplotlib.cbook as cbook
            import pathlib
            original_get_data_path = cbook._get_data_path
            
            def hooked_get_data_path(path_type, *args, **kwargs):
                if path_type == 'images' and args:
                    img_name = args[0]
                    local_images = ['left.png', 'right.png', 'up.png', 'down.png',
                                    'left_large.png', 'right_large.png', 'up_large.png', 'down_large.png']
                    if img_name in local_images:
                        import os
                        return (pathlib.Path(os.path.dirname(__file__)) / 'images' / img_name).absolute()
                return original_get_data_path(path_type, *args, **kwargs)
                
            # Temporarily inject our local images into Matplotlib's data path locator
            cbook._get_data_path = hooked_get_data_path
            
            # Use Matplotlib's native _Button method to guarantee 100% pixel-perfect matching
            btn_left = self.nav_toolbar._Button('Pan Left', 'left.png', False, lambda: self.pan_plot('left'))
            btn_right = self.nav_toolbar._Button('Pan Right', 'right.png', False, lambda: self.pan_plot('right'))
            btn_up = self.nav_toolbar._Button('Pan Up', 'up.png', False, lambda: self.pan_plot('up'))
            btn_down = self.nav_toolbar._Button('Pan Down', 'down.png', False, lambda: self.pan_plot('down'))
            
            # _Button packs at the end. We must move them next to the Home button.
            children = self.nav_toolbar.pack_slaves()
            my_btns = children[-4:]
            
            # The Separator is at index 1 because Back/Forward were removed from toolitems
            insert_before = children[1] if len(children) > 5 else None
            
            if insert_before:
                for b in my_btns:
                    b.pack(side=tk.LEFT, before=insert_before)
            
            cbook._get_data_path = original_get_data_path
            
        except Exception as e:
            print("Could not load native pan icons:", e)

        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # --- Right Side: Data Tables ---
        self.right_frame = ttk.Frame(paned_window)
        paned_window.add(self.right_frame, weight=1)

        # 1. Parameter Table
        lbl_params = ttk.Label(self.right_frame, text="IEC 60060-1 Parameters", font=("Segoe UI", 11, "bold"))
        lbl_params.pack(anchor=tk.W, pady=(10, 5))

        self.tree_params = ttk.Treeview(self.right_frame, columns=("Parameter", "Value"), show="headings", height=11, style="Custom.Treeview")
        self.tree_params.heading("Parameter", text="Parameter")
        self.tree_params.heading("Value", text="Value")
        
        self.tree_params.column("Parameter", width=180)
        self.tree_params.column("Value", width=120, anchor="e")
        self.tree_params.pack(fill=tk.X, pady=(0, 20))

        # 2. Tolerance Table
        lbl_tol = ttk.Label(self.right_frame, text="IEC 60060-1 Table - Tolerance Check", font=("Segoe UI", 11, "bold"))
        lbl_tol.pack(anchor=tk.W, pady=(10, 5))

        self.tree_tol = ttk.Treeview(self.right_frame, columns=("Param", "Nominal", "Tol", "Measured", "Pass"), show="headings", height=5, style="Custom.Treeview")
        for col in self.tree_tol["columns"]:
            self.tree_tol.heading(col, text=col)
        
        self.tree_tol.column("Param", width=60)
        self.tree_tol.column("Nominal", width=80, anchor="e")
        self.tree_tol.column("Tol", width=70, anchor="center")
        self.tree_tol.column("Measured", width=80, anchor="e")
        self.tree_tol.column("Pass", width=60, anchor="center")
        self.tree_tol.pack(fill=tk.X)

    def pan_plot(self, direction):
        if not self.data: return
        
        # Save current view to history before panning so Home/Back buttons track it
        if hasattr(self, 'nav_toolbar'):
            self.nav_toolbar.push_current()
            
        x_min, x_max = self.ax.get_xlim()
        y_min, y_max = self.ax.get_ylim()
        
        dx = (x_max - x_min) * 0.15
        dy = (y_max - y_min) * 0.15
        
        if direction == 'left':
            self.ax.set_xlim(x_min - dx, x_max - dx)
        elif direction == 'right':
            self.ax.set_xlim(x_min + dx, x_max + dx)
        elif direction == 'up':
            self.ax.set_ylim(y_min + dy, y_max + dy)
        elif direction == 'down':
            self.ax.set_ylim(y_min - dy, y_max - dy)
            
        self.canvas.draw_idle()

    def load_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Impulse Waveform Data",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            self.file_path = file_path
            self.process_data(file_path)

    def process_data(self, file_path):
        try:
            time, raw_voltage = None, None
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                data_rows = []
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('Time') or line.startswith('CH'):
                        continue
                    parts = line.replace(',', '\t').replace(';', '\t').split()
                    if len(parts) >= 2:
                        try:
                            data_rows.append([float(parts[0]), float(parts[1])])
                        except ValueError:
                            continue
                if len(data_rows) > 10:
                    raw_data = np.array(data_rows)
                    time = raw_data[:, 0]
                    raw_voltage = raw_data[:, 1]
            except Exception:
                pass

            if time is None or raw_voltage is None:
                try:
                    with open(file_path, 'rb') as f:
                        b_data = f.read()
                    for offset in [70, 82, 0, 64, 128]:
                        for fmt in ['>i2', '<i2', '>f4', '<f4', '>f8', '<f8']:
                            try:
                                elem_size = 2 if '2' in fmt else (4 if '4' in fmt else 8)
                                n = (len(b_data) - offset) // elem_size
                                if n < 100: continue
                                raw_v = np.frombuffer(b_data[offset:offset+n*elem_size], dtype=fmt)
                                if not np.any(np.isnan(raw_v)) and not np.any(np.isinf(raw_v)):
                                    if np.std(raw_v) > 0.01:
                                        if np.max(np.abs(raw_v)) > 1000:
                                            raw_v = (raw_v / 32768.0) * 100.0
                                        time = np.linspace(0, 100e-6, len(raw_v))
                                        raw_voltage = raw_v
                                        break
                            except Exception:
                                pass
                        if time is not None: break
                except Exception:
                    pass

            if time is None or raw_voltage is None:
                raise ValueError("No valid text or binary numeric data rows found in file.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not load file:\n{e}")
            return
        # ----------------------------------------------------------------------
        # 1. PREPARE DATA
        # ----------------------------------------------------------------------
        # Remove any DC offset at the very beginning (first 5% of data) if needed
        # but the terminal script doesn't do this, so we strictly follow terminal script.
        t = time
        v_raw = raw_voltage
        dt = t[1] - t[0]

        polarity = -1 if abs(np.min(v_raw)) > abs(np.max(v_raw)) else 1
        v = v_raw * polarity

        idx_peak = int(np.argmax(v))
        Vext = v[idx_peak]
        tp = t[idx_peak]

        # ----------------------------------------------------------------------
        # 2. CROSSING HELPERS
        # ----------------------------------------------------------------------
        def _crossing_time(target, tt, vv):
            idx = np.where(vv >= target)[0]
            if len(idx) == 0:
                raise ValueError("Signal never reaches the requested level.")
            idx = idx[0]
            if idx == 0: return tt[0]
            t0, t1 = tt[idx - 1], tt[idx]
            v0, v1 = vv[idx - 1], vv[idx]
            frac = (target - v0) / (v1 - v0) if (v1 - v0) != 0 else 0
            return t0 + frac * (t1 - t0)

        def _double_exp(tt, A, alpha, beta_p, t0):
            tau = np.clip(tt - t0, 0, None)
            return A * (np.exp(-alpha * tau) - np.exp(-beta_p * tau))

        # ----------------------------------------------------------------------
        # 3. FRONT TIMING (T1, O1)
        # ----------------------------------------------------------------------
        front_t, front_v = t[: idx_peak + 1], v[: idx_peak + 1]
        v30, v90 = 0.30 * Vext, 0.90 * Vext
        
        try:
            t30 = _crossing_time(v30, front_t, front_v)
            t90 = _crossing_time(v90, front_t, front_v)
            T1 = 1.67 * (t90 - t30)
            O1 = t30 - 0.3 * (t90 - t30)
        except Exception:
            t30, t90, T1, O1 = None, None, None, None

        # ----------------------------------------------------------------------
        # 4. TAIL TIMING (T2)
        # ----------------------------------------------------------------------
        tail_t, tail_v = t[idx_peak:], v[idx_peak:]
        v50 = 0.50 * Vext
        idx50 = np.where(tail_v <= v50)[0]
        
        t50, T2 = None, None
        if len(idx50) > 0 and O1 is not None:
            idx50 = idx50[0]
            if idx50 > 0:
                t0_, t1_ = tail_t[idx50 - 1], tail_t[idx50]
                v0_, v1_ = tail_v[idx50 - 1], tail_v[idx50]
                frac = (v50 - v0_) / (v1_ - v0_) if (v1_ - v0_) != 0 else 0
                t50 = t0_ + frac * (t1_ - t0_)
                T2 = t50 - O1

        # ----------------------------------------------------------------------
        # 5. BASE CURVE FIT & BETA
        # ----------------------------------------------------------------------
        base = np.zeros_like(v)
        base_peak = Vext
        beta_os = 0.0
        beta_prime = 0.0
        
        if T1 is not None and T2 is not None and O1 is not None:
            tail_start = tp + 4 * T1
            mask_fit = ((t >= O1) & (t < t90)) | (t > tail_start)
            if mask_fit.sum() < 5:
                mask_fit = t >= O1  # fallback

            A0 = Vext * 1.3
            alpha0 = np.log(2) / max(T2, 1e-9)
            beta0 = 3 / max(T1, 1e-9)
            try:
                from scipy.optimize import curve_fit
                popt, _ = curve_fit(
                    lambda tt, A, a, b: _double_exp(tt, A, a, b, O1),
                    t[mask_fit], v[mask_fit],
                    p0=[A0, alpha0, beta0], maxfev=50000,
                )
                base = _double_exp(t, popt[0], popt[1], popt[2], O1)
                base_peak = np.nanmax(base)
                beta_os = Vext - base_peak
                beta_prime = (beta_os / Vext) * 100.0 if Vext > 0 else 0
            except Exception:
                base = v # fallback
                pass

        # ----------------------------------------------------------------------
        # 6. OSCILLATION FREQUENCY
        # ----------------------------------------------------------------------
        f_osc = np.nan
        if T1 is not None:
            from scipy.signal import find_peaks
            win = (t >= tp - 0.3 * T1) & (t <= tp + 10 * T1)
            t_seg, v_seg = t[win], v[win]
            if len(v_seg) > 5:
                prom = 0.01 * Vext 
                pk, _ = find_peaks(v_seg, prominence=prom)
                tr, _ = find_peaks(-v_seg, prominence=prom)
                extrema_t = np.sort(np.concatenate([t_seg[pk], t_seg[tr]]))
                if len(extrema_t) >= 2:
                    half_periods = np.diff(extrema_t)
                    period = 2 * np.mean(half_periods)
                    f_osc = 1.0 / period

        # ----------------------------------------------------------------------
        # 7. STORE RESULTS
        # ----------------------------------------------------------------------
        # Multiply everything back by polarity for plotting so it draws correctly
        v_peak_plot = Vext * polarity
        base_plot = base * polarity
        
        self.data = {
            'time_us': t * 1e6, 
            'raw_v': v_raw,
            'smooth_v': base_plot, # We repurpose smooth_v as the base curve for plotting
            'v_peak': v_peak_plot,
            'v30': v30 * polarity, 'v50': v50 * polarity, 'v90': v90 * polarity,
            't30_us': t30 * 1e6 if t30 else None,
            't90_us': t90 * 1e6 if t90 else None,
            't50_us': t50 * 1e6 if t50 else None,
            't1_us': T1 * 1e6 if T1 else None,
            't2_us': T2 * 1e6 if T2 else None,
            'o1_us': O1 * 1e6 if O1 else None,
            'beta_pct': beta_prime,
            'osc_freq_khz': f_osc * 1e-3 if not np.isnan(f_osc) else 0
        }

        self.update_tables()
        self.update_plot()

    def refresh_view(self):
        if self.data is not None:
            self.update_tables()
            self.update_plot()

    def update_tables(self):
        for item in self.tree_params.get_children(): self.tree_params.delete(item)
        for item in self.tree_tol.get_children(): self.tree_tol.delete(item)

        d = self.data
        if not d: return

        is_chopped = bool(d['t2_us'] and d['t2_us'] < 15.0)
        
        vp_val = d['v_peak']
        vp_str = f"{vp_val:.1f} V" if abs(vp_val) > 100 else f"{vp_val:.2f} V"
        self.tree_params.insert("", tk.END, values=("Peak (Up)", vp_str))
        
        self.tree_params.insert("", tk.END, values=("Front (T1-filtered)", "N/A"))
        if d['t1_us']: self.tree_params.insert("", tk.END, values=("Front (T1)", f"{d['t1_us']:.2f} µs"))
        
        t2_label = "Chopping Time Tc" if is_chopped else "Half-value T2"
        
        if d['t2_us']: self.tree_params.insert("", tk.END, values=(t2_label, f"{d['t2_us']:.1f} µs"))
        if d['o1_us']: self.tree_params.insert("", tk.END, values=("Virtual Origin O1", f"{d['o1_us']:.3f} µs"))
        
        self.tree_params.insert("", tk.END, values=("", "")) 
        
        self.tree_params.insert("", tk.END, values=("Overshoot β", f"{d.get('beta_pct', 0):.2f} %"))
        self.tree_params.insert("", tk.END, values=("β (K-filtered)", "N/A"))
        self.tree_params.insert("", tk.END, values=("Osc. Freq (f)", f"{d.get('osc_freq_khz', 0):.2f} kHz"))

        if d['t1_us']:
            is_pass = "PASS" if 0.84 <= d['t1_us'] <= 1.56 else "FAIL"
            self.tree_tol.insert("", tk.END, values=("T1", "1.20", "± 30%", f"{d['t1_us']:.2f}", is_pass))
            
        if d['t2_us']:
            if not is_chopped:
                is_pass2 = "PASS" if 40.0 <= d['t2_us'] <= 60.0 else "FAIL"
                self.tree_tol.insert("", tk.END, values=("T2", "50.00", "± 20%", f"{d['t2_us']:.1f}", is_pass2))
            else:
                # Typically 2 to 5 us for chopped, but we'll just show it without strict standard tolerances
                self.tree_tol.insert("", tk.END, values=("Tc", "2-5", "varies", f"{d['t2_us']:.1f}", "N/A"))

    def update_plot(self):
        self.ax.clear()
        d = self.data
        if not d: 
            self.canvas.draw()
            return

        self.ax.plot(d['time_us'], d['raw_v'], label='Raw data', color='#b0c4de', linewidth=1)
        if self.show_kfilter_var.get():
            self.ax.plot(d['time_us'], d['smooth_v'], label='IEC Mean Curve', color='red', linestyle='--')

        if self.show_markers_var.get() and d['t1_us'] is not None:
            v_p = d['v_peak']
            sign = 1 if v_p >= 0 else -1 
            
            markers = [
                (d['t30_us'], d['v30'], '30%', 'purple'),
                (d['t50_us'], d['v50'], '50%', 'blue'),
                (d['t90_us'], d['v90'], '90%', 'green')
            ]
            
            for t_val, v_val, label, color in markers:
                if t_val is not None:
                    self.ax.hlines(v_val, 0, t_val, color=color, linestyle=':', alpha=0.5)
                    self.ax.vlines(t_val, 0, v_val, color=color, linestyle=':', alpha=0.5)
                    self.ax.plot(t_val, v_val, marker='o', color=color)
                    self.ax.text(t_val + 1, v_val, f'{label}', va='center', color=color, fontsize=10)

            o1 = d['o1_us']
            self.ax.plot(o1, 0, marker='o', color='black')
            self.ax.vlines(o1, 0, v_p * 0.15, color='black', linestyle='--', alpha=0.5)
            
            y_t1 = v_p * 0.05 
            self.ax.vlines(o1 + d['t1_us'], 0, y_t1, color='purple', linestyle=':', alpha=0.5)
            self.ax.annotate(
                '', xy=(o1, y_t1), xytext=(o1 + d['t1_us'], y_t1),
                arrowprops=dict(arrowstyle='<->', color='purple', lw=1.5)
            )
            self.ax.text(o1 + (d['t1_us']/2), y_t1 - (v_p * 0.02), f"T1 = {d['t1_us']:.2f} µs", 
                         ha='center', va='top' if sign>0 else 'bottom', color='purple', fontsize=10,
                         bbox=dict(facecolor='white', edgecolor='none', alpha=0.8, pad=1))

            if d['t2_us']:
                y_t2 = v_p * 0.12 
                self.ax.vlines(o1 + d['t2_us'], 0, y_t2, color='blue', linestyle=':', alpha=0.5)
                self.ax.annotate(
                    '', xy=(o1, y_t2), xytext=(o1 + d['t2_us'], y_t2),
                    arrowprops=dict(arrowstyle='<->', color='blue', lw=1.5)
                )
                
                is_chopped = (d['t2_us'] < 15.0)
                t2_plot_label = "Tc" if is_chopped else "T2"
                
                self.ax.text(o1 + (d['t2_us']/2), y_t2 - (v_p * 0.02), f"{t2_plot_label} = {d['t2_us']:.1f} µs", 
                             ha='center', va='top' if sign>0 else 'bottom', color='blue', fontsize=10,
                             bbox=dict(facecolor='white', edgecolor='none', alpha=0.8, pad=1))

        self.ax.set_title("IEC 60060-1 Analysis - Up")
        self.ax.set_xlabel("Time (µs)")
        self.ax.set_ylabel("Voltage (V)")
        self.ax.grid(True, linestyle=':', alpha=0.7)
        self.ax.axhline(0, color='black', linewidth=0.8) 
        self.ax.legend()
        self.fig.tight_layout()
        
        self.canvas.draw()
        
        # Reset the navigation toolbar history so 'Home' restores this exact view
        if hasattr(self, 'nav_toolbar'):
            self.nav_toolbar.update()

if __name__ == "__main__":
    app = IECAnalyzerApp()
    app.mainloop()