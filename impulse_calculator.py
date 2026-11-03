import numpy as np
import os
import math
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from PIL import Image, ImageTk

try:
    from formula_engine import FormulaEngine
except ImportError:
    class FormulaEngine:
        def __init__(self, filepath=None):
            if filepath is None:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                filepath = os.path.join(base_dir, "formulas.txt")
            self.filepath = filepath
            self.formulas = []
            self.load()

        def load(self, filepath=None):
            if filepath: self.filepath = filepath
            self.formulas = []
            if not os.path.exists(self.filepath): return
            with open(self.filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line.startswith("//"): continue
                    if "=" in line:
                        parts = line.split("=", 1)
                        var_name, expr = parts[0].strip(), parts[1].strip()
                        if var_name and expr:
                            self.formulas.append((var_name, expr))

        def evaluate(self, inputs):
            context = {
                "abs": abs, "min": min, "max": max,
                "sqrt": math.sqrt, "exp": math.exp, "log": math.log,
                "np": np, "math": math
            }
            for k, v in inputs.items(): context[k] = v
            for var_name, expr in self.formulas:
                try:
                    context[var_name] = eval(expr, {"__builtins__": None}, context)
                except Exception:
                    context[var_name] = None
            return context

        def get_raw_text(self):
            if os.path.exists(self.filepath):
                with open(self.filepath, "r", encoding="utf-8") as f: return f.read()
            return ""

        def save_raw_text(self, text):
            with open(self.filepath, "w", encoding="utf-8") as f: f.write(text)
            self.load()


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
        self.show_mean_var = tk.BooleanVar(value=False)         # Toggle for IEC Mean (Base) Curve
        # [K-FACTOR FILTER] Variable to toggle display of k-factor filtered curve (vkfilt)
        self.show_kfilter_var = tk.BooleanVar(value=True)
        self.wav_type_var = tk.StringVar(value="Auto")
        
        # Initialize dynamic formula engine from formulas.txt
        self.formula_engine = FormulaEngine()

        self._build_ui()

    def _build_ui(self):
        # --- Top Toolbar ---
        toolbar = ttk.Frame(self, relief=tk.RAISED, borderwidth=1)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        btn_load = ttk.Button(toolbar, text="📂 Load Waveform", command=self.load_file)
        btn_load.grid(row=0, column=0, padx=(10, 10), pady=10)

        chk_mean_curve = ttk.Checkbutton(toolbar, text="Show IEC Mean Curve", 
                                      variable=self.show_mean_var, command=self.update_plot)
        chk_mean_curve.grid(row=0, column=2, padx=(15, 10), pady=10)

        # [K-FACTOR FILTER] Checkbox to toggle display of k-factor filtered curve (vkfilt - Annex B)
        chk_kfilter_curve = ttk.Checkbutton(toolbar, text="Show K-Factor Curve (vkfilt)", 
                                          variable=self.show_kfilter_var, command=self.update_plot)
        chk_kfilter_curve.grid(row=0, column=3, padx=(10, 10), pady=10)

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
            
            # Step 1: Proprietary IAAS DAT Binary & Encrypted Unpacking
            try:
                with open(file_path, 'rb') as f:
                    b_data = f.read()
                if b_data.startswith(b"IAAS_DAT_V1\x00") or b_data.startswith(b"IAAS"):
                    from iaas_crypto import decrypt_iaas_dat
                    x_dec, y_A_dec, y_B_dec, _ = decrypt_iaas_dat(b_data)
                    time = x_dec
                    raw_voltage = y_A_dec
            except Exception:
                pass

            # Step 2: Plain Text File Parsing (.csv, .txt)
            if time is None or raw_voltage is None:
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
        # 3. FRONT TIMING (T1, O1) - DYNAMIC VIA FORMULAS.TXT
        # ----------------------------------------------------------------------
        # Always reload formulas from formulas.txt for latest changes
        self.formula_engine.load()

        # Evaluate threshold levels from formulas.txt
        thresh_eval = self.formula_engine.evaluate({'Vext': Vext})
        v30 = thresh_eval.get('v30')
        v90 = thresh_eval.get('v90')
        v50 = thresh_eval.get('v50')
        if v30 is None: v30 = 0.30 * Vext
        if v90 is None: v90 = 0.90 * Vext
        if v50 is None: v50 = 0.50 * Vext

        front_t, front_v = t[: idx_peak + 1], v[: idx_peak + 1]
        
        try:
            t30 = _crossing_time(v30, front_t, front_v)
            t90 = _crossing_time(v90, front_t, front_v)
            calc_front = self.formula_engine.evaluate({
                'Vext': Vext,
                't30': t30,
                't90': t90,
                'tp': tp
            })
            T1 = calc_front.get('T1')
            O1 = calc_front.get('O1')
            if T1 is None:
                T1 = (t90 - t30) / 0.6
            if O1 is None:
                O1 = t30 - 0.3 * T1
        except Exception:
            t30, t90, T1, O1 = None, None, None, None

        # ----------------------------------------------------------------------
        # [THIS CODE FOR FORMULAS: CHOPPING DETECTION & TIMING]
        # Detect if the impulse is chopped (on tail or front) or a full wave
        # ----------------------------------------------------------------------
        # [THIS CODE FOR FORMULAS: 4. CHOPPING DETECTION (Tc) PER IEC 60060-1]
        # Chopping causes an abrupt, catastrophic voltage collapse (>100% of peak / µs).
        # We smooth over ~50 ns to eliminate sample-step noise and identify the
        # true steepest collapse and its breakaway instant (instant of chopping).
        # ----------------------------------------------------------------------
        win_len = max(3, int(0.05e-6 / dt))
        kernel = np.ones(win_len) / win_len
        v_smooth = np.convolve(v, kernel, mode='same')
        dv_dt = np.gradient(v_smooth, dt)
        
        chop_thresh = -1.0 * Vext / 1e-6
        steepest_idx = np.argmin(dv_dt)
        min_slope = dv_dt[steepest_idx]
        
        is_chopped = False
        is_front_chopped = False
        is_tail_chopped = False
        idx_chop = None
        t_chop = None
        Tc = None
        
        if min_slope < chop_thresh:
            # Verify that this steep slope actually causes a permanent collapse (>40% of peak)
            window_pts = max(5, int(1.5e-6 / dt))
            v_before = v[max(0, steepest_idx - window_pts // 2)]
            v_after = v[min(len(v) - 1, steepest_idx + window_pts)]
            if (v_before - v_after) > 0.40 * Vext:
                is_chopped = True
                
                # Trace back to the breakaway instant where the collapse started
                idx_s = steepest_idx
                while idx_s > 0 and dv_dt[idx_s] < 0.15 * min_slope:
                    idx_s -= 1
                
                idx_chop = idx_s
                t_chop = t[idx_chop]
                if O1 is not None:
                    calc_chop = self.formula_engine.evaluate({
                        'Vext': Vext,
                        't30': t30,
                        't90': t90,
                        't_chop': t_chop,
                        'O1': O1,
                        'T1': T1,
                        'tp': tp
                    })
                    Tc = calc_chop.get('Tc')
                    if Tc is None:
                        Tc = t_chop - O1
                    
                # Classify front-chopped vs tail-chopped per IEC 60060-1
                if t90 is not None and t_chop < (t90 - 0.05 * (t90 - t30)):
                    is_front_chopped = True
                elif t90 is None:
                    is_front_chopped = True
                else:
                    is_tail_chopped = True

        # ----------------------------------------------------------------------
        # [THIS CODE FOR FORMULAS: 4. TAIL TIMING (T2 for full, Tc for chopped)]
        # ----------------------------------------------------------------------
        t50, T2 = None, None
        if not is_chopped:
            tail_t, tail_v = t[idx_peak:], v[idx_peak:]
            idx50 = np.where(tail_v <= v50)[0]
            if len(idx50) > 0 and O1 is not None:
                idx50 = idx50[0]
                if idx50 > 0:
                    t0_, t1_ = tail_t[idx50 - 1], tail_t[idx50]
                    v0_, v1_ = tail_v[idx50 - 1], tail_v[idx50]
                    frac = (v50 - v0_) / (v1_ - v0_) if (v1_ - v0_) != 0 else 0
                    t50 = t0_ + frac * (t1_ - t0_)
                    
                    calc_tail = self.formula_engine.evaluate({
                        'Vext': Vext,
                        't30': t30,
                        't90': t90,
                        't50': t50,
                        'O1': O1,
                        'T1': T1,
                        'tp': tp
                    })
                    T2 = calc_tail.get('T2')
                    if T2 is None:
                        T2 = t50 - O1
        else:
            # For chopped impulse, record chopping time Tc
            T2 = Tc

        # ----------------------------------------------------------------------
        # [THIS CODE FOR FORMULAS: 5. BASE CURVE FIT FOR FULL & CHOPPED WAVES]
        # Fits an ideal double-exponential curve to non-oscillating regions:
        # - Full Wave: fits (A, alpha, beta) across front and post-crest tail.
        # - Tail-Chopped Wave: fits (Ubase, beta) strictly on pre-chop data with
        #   peak aligned at physical crest tp and constraint Ubase <= Vext.
        # - Continuous Mean Curve: generates the full smooth double-exponential
        #   impulse curve with smooth 50 µs tail decay across the timeline.
        # ----------------------------------------------------------------------
        base = np.zeros_like(v)
        base_peak = Vext
        
        def _get_alpha_for_tau_p(beta_val, tau_p_val):
            target = beta_val * np.exp(-beta_val * tau_p_val)
            a_max = 1.0 / tau_p_val - 1e-9
            a_min = 1e-6
            try:
                from scipy.optimize import brentq
                return brentq(lambda a: a * np.exp(-a * tau_p_val) - target, a_min, a_max)
            except Exception:
                return 14600.0

        if O1 is not None and T1 is not None:
            try:
                from scipy.optimize import curve_fit, minimize
                alpha_nom = np.log(2) / 50e-6
                beta0 = 3.0 / max(T1, 1e-9)
                tau_p = max(1e-7, tp - O1)
                
                if not is_chopped:
                    # Full impulse fit
                    tail_start = tp + 3 * T1
                    mask_fit = ((t >= O1) & (t < tp)) | (t >= tail_start)
                    if mask_fit.sum() < 5:
                        mask_fit = t >= O1
                        
                    if T2 is not None:
                        alpha0 = np.log(2) / max(T2, 1e-9)
                    else:
                        # Estimate alpha from available tail points when recording window ends before 50%
                        mask_tail = t >= tail_start
                        if mask_tail.sum() >= 5:
                            t_tail = t[mask_tail]
                            v_tail = v[mask_tail]
                            poly = np.polyfit(t_tail - O1, np.log(np.maximum(1e-3, v_tail)), 1)
                            alpha0 = max(100.0, min(1e5, -poly[0]))
                        else:
                            alpha0 = alpha_nom
                            
                    A0 = Vext * 1.05
                    
                    popt, _ = curve_fit(
                        lambda tt, A, a, b: _double_exp(tt, A, a, b, O1),
                        t[mask_fit], v[mask_fit],
                        p0=[A0, alpha0, beta0],
                        bounds=([0.7 * Vext, 100.0, 1e5], [2.0 * Vext, 5e5, 1e8]),
                        maxfev=50000,
                    )
                    base = _double_exp(t, popt[0], popt[1], popt[2], O1)
                    base_peak = np.nanmax(base)
                    if base_peak > Vext:
                        base *= (Vext / base_peak)
                        base_peak = Vext
                    if T2 is None and popt[1] > 0:
                        T2 = np.log(2) / popt[1]
                elif is_tail_chopped and idx_chop is not None:
                    # Tail/crest-chopped impulse: fit (U_base, beta) strictly on intact pre-chop data
                    # with constraint U_base <= Vext and crest peak aligned at tp
                    t_fit_end = max(tp, t_chop)
                    mask_fit = (t >= O1) & (t <= t_fit_end)
                    t_fit = t[mask_fit]
                    v_fit = v[mask_fit]
                    tau_fit = t_fit - O1
                    
                    if len(t_fit) >= 5:
                        def loss(params):
                            U_b, b_val = params
                            a_val = _get_alpha_for_tau_p(b_val, tau_p)
                            denom = np.exp(-a_val * tau_p) - np.exp(-b_val * tau_p)
                            if denom <= 1e-6:
                                return 1e12
                            A = U_b / denom
                            u_model = A * (np.exp(-a_val * tau_fit) - np.exp(-b_val * tau_fit))
                            return np.sum((u_model - v_fit)**2)

                        res = minimize(
                            loss,
                            x0=[Vext * 0.98, 2.5 / tau_p],
                            bounds=[(0.70 * Vext, 1.00 * Vext), (0.5 / tau_p, 20.0 / tau_p)],
                            method='L-BFGS-B'
                        )
                        U_base_opt, beta_opt = res.x
                        alpha_opt = _get_alpha_for_tau_p(beta_opt, tau_p)
                        denom = np.exp(-alpha_opt * tau_p) - np.exp(-beta_opt * tau_p)
                        A_opt = U_base_opt / max(1e-6, denom)
                        
                        tau_all = np.maximum(0.0, t - O1)
                        base = np.zeros_like(t)
                        m_front = (t >= O1) & (t <= tp)
                        base[m_front] = A_opt * (np.exp(-alpha_opt * tau_all[m_front]) - np.exp(-beta_opt * tau_all[m_front]))
                        
                        # Continuous smooth nominal 50 µs tail decay for prospective visualization
                        m_tail = t > tp
                        base[m_tail] = U_base_opt * np.exp(-alpha_nom * (t[m_tail] - tp))
                        base_peak = U_base_opt
                    else:
                        raise ValueError("Insufficient points for chopped fit")
                else:
                    # Front-chopped prospective curve: standard double-exponential based on measured front
                    t_peak_est = np.log(beta0 / alpha_nom) / (beta0 - alpha_nom)
                    A_est = Vext / max(1e-6, np.exp(-alpha_nom * t_peak_est) - np.exp(-beta0 * t_peak_est))
                    base = _double_exp(t, A_est, alpha_nom, beta0, O1)
                    base_peak = np.nanmax(base)
                    if base_peak > Vext:
                        base *= (Vext / base_peak)
                        base_peak = Vext
            except Exception as e:
                # Analytical fallback: standard double-exponential curve matching Vext and T1 with 50 µs tail
                alpha_fallback = np.log(2) / 50e-6
                beta_fallback = 3.0 / max(T1 if T1 else 1.2e-6, 1e-9)
                t_p_est = np.log(beta_fallback / alpha_fallback) / (beta_fallback - alpha_fallback)
                A_fallback = Vext / max(1e-6, np.exp(-alpha_fallback * t_p_est) - np.exp(-beta_fallback * t_p_est))
                base = _double_exp(t, A_fallback, alpha_fallback, beta_fallback, O1 if O1 else t[0])
                base_peak = np.nanmax(base)
                if base_peak > Vext:
                    base *= (Vext / base_peak)
                    base_peak = Vext

        # ----------------------------------------------------------------------
        # [THIS CODE FOR FORMULAS: 5b. K-FACTOR FILTERED CURVE (vkfilt - ANNEX B)]
        # Applies standardized digital low-pass filter (cutoff ~500 kHz).
        # For tail-chopped waves, residual is windowed prior to chopping collapse
        # to prevent Gibbs ringing from corrupting the crest peak.
        # ----------------------------------------------------------------------
        v_kfilt = np.copy(v)
        Up_kfilt = Vext
        beta_raw_pct = None
        beta_dash_pct = None
        
        if not is_front_chopped:
            try:
                residual = v - base
                
                # Taper residual to 0 before the chopping cliff to eliminate Gibbs ringing
                if is_tail_chopped and idx_chop is not None:
                    taper_len = min(idx_chop, max(5, int(0.3e-6 / dt)))
                    taper = np.linspace(1.0, 0.0, taper_len)
                    residual[idx_chop - taper_len:idx_chop] *= taper
                    residual[idx_chop:] = 0.0

                n_pts = len(t)
                dt_s = dt if dt > 0 else 1e-9
                r_fft = np.fft.rfft(residual)
                freqs_mhz = np.fft.rfftfreq(n_pts, d=dt_s) * 1e-6
                
                # k(f) filter transfer function
                k_filter_h = 1.0 / (1.0 + 2.2 * (freqs_mhz ** 2))
                r_filt = np.fft.irfft(r_fft * k_filter_h, n=n_pts)
                
                v_kfilt = base + r_filt
                if is_tail_chopped and idx_chop is not None:
                    v_kfilt[idx_chop:] = v[idx_chop:]
                    Up_kfilt = float(np.nanmax(v_kfilt[:idx_chop]))
                else:
                    Up_kfilt = float(np.nanmax(v_kfilt))

                # --------------------------------------------------------------
                # [THIS CODE FOR FORMULAS: 5c. BETA & BETA DASH IN % VIA FORMULAS.TXT]
                # --------------------------------------------------------------
                ref_Up = base_peak if (base_peak is not None and base_peak > 0) else Vext
                calc_overshoot = self.formula_engine.evaluate({
                    'Vext': Vext,
                    'Ubase': ref_Up,
                    'Up_kfilt': Up_kfilt,
                    'T1': T1,
                    'O1': O1,
                    't30': t30,
                    't90': t90,
                    't50': t50,
                    't_chop': t_chop,
                    'tp': tp
                })
                beta_raw_pct = calc_overshoot.get('beta')
                beta_dash_pct = calc_overshoot.get('beta_dash')
                if beta_raw_pct is None:
                    beta_raw_pct = max(0.0, ((Vext - ref_Up) / ref_Up) * 100.0) if ref_Up > 0 else 0.0
                else:
                    beta_raw_pct = max(0.0, float(beta_raw_pct))

                if beta_dash_pct is None:
                    beta_dash_pct = max(0.0, ((Up_kfilt - ref_Up) / ref_Up) * 100.0) if ref_Up > 0 else 0.0
                else:
                    beta_dash_pct = max(0.0, float(beta_dash_pct))
            except Exception as e:
                print(f"[K-FACTOR FILTER] Warning: {e}")
                v_kfilt = np.copy(base)
                Up_kfilt = base_peak
                beta_raw_pct = 0.0
                beta_dash_pct = 0.0

        # Steepness calculation (kV/µs) via formulas.txt [Clause 7.1.30]
        steepness_kv_us = None
        if T1 is not None and T1 > 0:
            calc_s = self.formula_engine.evaluate({'Vext': Vext, 'T1': T1 * 1e6})
            s_val = calc_s.get('S')
            if s_val is not None:
                steepness_kv_us = float(s_val)
            else:
                steepness_kv_us = Vext / (T1 * 1e6)

        # ----------------------------------------------------------------------
        # [THIS CODE FOR FORMULAS: 6. CREST OSCILLATION FREQUENCY]
        # ----------------------------------------------------------------------
        f_osc = np.nan
        if T1 is not None and not is_front_chopped:
            from scipy.signal import find_peaks
            win_end = min(t_chop if (is_tail_chopped and t_chop) else t[-1], tp + 10 * T1)
            win = (t >= tp - 0.3 * T1) & (t <= win_end)
            t_seg, v_seg = t[win], v[win]
            if len(v_seg) > 5:
                prom = 0.05 * Vext 
                pk, _ = find_peaks(v_seg, prominence=prom)
                tr, _ = find_peaks(-v_seg, prominence=prom)
                extrema_t = np.sort(np.concatenate([t_seg[pk], t_seg[tr]]))
                if len(extrema_t) >= 2:
                    half_periods = np.diff(extrema_t)
                    period = 2 * np.mean(half_periods)
                    f_osc = 1.0 / period

        # ----------------------------------------------------------------------
        # [THIS CODE FOR FORMULAS: 7. STORE RESULTS]
        # ----------------------------------------------------------------------
        v_peak_plot = Vext * polarity
        base_plot = base * polarity
        base_peak_plot = base_peak * polarity
        v_kfilt_plot = v_kfilt * polarity
        Up_kfilt_plot = Up_kfilt * polarity
        
        # For chopped impulses, terminate the displayed IEC Mean Curve at the chopping collapse (Tc)
        if is_chopped and idx_chop is not None:
            idx_stop = max(idx_peak, idx_chop)
            base_plot[idx_stop + 1:] = np.nan
        
        self.data = {
            'time_us': t * 1e6, 
            'raw_v': v_raw,
            'smooth_v': base_plot,
            'v_kfilt': v_kfilt_plot,
            'u_pkfilt': Up_kfilt_plot,
            'v_peak': v_peak_plot,
            'v_base_peak': base_peak_plot,
            'v30': v30 * polarity, 'v50': v50 * polarity, 'v90': v90 * polarity,
            't30_us': t30 * 1e6 if t30 else None,
            't90_us': t90 * 1e6 if t90 else None,
            't50_us': t50 * 1e6 if t50 else None,
            't1_us': T1 * 1e6 if T1 else None,
            't2_us': T2 * 1e6 if T2 else None,
            'o1_us': O1 * 1e6 if O1 else None,
            'is_chopped': is_chopped,
            'is_front_chopped': is_front_chopped,
            'is_tail_chopped': is_tail_chopped,
            'tc_us': Tc * 1e6 if Tc else None,
            'steepness_kv_us': steepness_kv_us,
            'beta_raw_pct': beta_raw_pct,
            'beta_dash_pct': beta_dash_pct,
            'beta_pct': beta_dash_pct,
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

        is_chopped = bool(d.get('is_chopped', False))
        is_front_chopped = bool(d.get('is_front_chopped', False))
        
        vp_val = d['v_peak']
        vp_str = f"{vp_val:.2f} kV"
        peak_label = "Chopping Voltage (Uc)" if is_front_chopped else "Peak Voltage (Up / Vp)"
        self.tree_params.insert("", tk.END, values=(peak_label, vp_str))

        # [K-FACTOR FILTER] Display Filtered Peak Voltage Up,kfilt (Annex B)
        if not is_front_chopped and d.get('u_pkfilt') is not None:
            self.tree_params.insert("", tk.END, values=("Filtered Peak (Up,kfilt)", f"{d['u_pkfilt']:.2f} kV"))

        if not is_front_chopped and d.get('v_base_peak'):
            self.tree_params.insert("", tk.END, values=("Base Curve Peak (Ubase)", f"{d['v_base_peak']:.2f} kV"))
        
        if d['t1_us']: self.tree_params.insert("", tk.END, values=("Front Time (T1)", f"{d['t1_us']:.2f} µs"))
        
        t2_label = "Chopping Time (Tc)" if is_chopped else "Half-value Time (T2)"
        
        if d['t2_us']: self.tree_params.insert("", tk.END, values=(t2_label, f"{d['t2_us']:.1f} µs"))
        if d['o1_us']: self.tree_params.insert("", tk.END, values=("Virtual Origin (O1)", f"{d['o1_us']:.3f} µs"))
        if d.get('steepness_kv_us'): self.tree_params.insert("", tk.END, values=("Virtual Steepness (S)", f"{d['steepness_kv_us']:.2f} kV/µs"))
        
        beta_raw = d.get('beta_raw_pct')
        beta_dash = d.get('beta_dash_pct')
        
        if is_front_chopped:
            self.tree_params.insert("", tk.END, values=("Beta (β)", "N/A (Front Chopped)"))
            self.tree_params.insert("", tk.END, values=("Beta Dash (β')", "N/A (Front Chopped)"))
            self.tree_params.insert("", tk.END, values=("Overshoot Status", "N/A (Front Chopped)"))
        else:
            beta_eval = "≤ 5% (Negligible)" if (beta_dash is not None and beta_dash <= 5.0) else "> 5% (Significant)"
            beta_raw_str = f"{beta_raw:.2f} %" if beta_raw is not None else "N/A"
            beta_dash_str = f"{beta_dash:.2f} %" if beta_dash is not None else "N/A"
            self.tree_params.insert("", tk.END, values=("Beta (β)", beta_raw_str))
            self.tree_params.insert("", tk.END, values=("Beta Dash (β')", beta_dash_str))
            self.tree_params.insert("", tk.END, values=("Overshoot Status", beta_eval))
            
        self.tree_params.insert("", tk.END, values=("Oscillation Freq (f)", f"{d.get('osc_freq_khz', 0):.2f} kHz"))

        if d['t1_us']:
            is_pass = "PASS" if 0.84 <= d['t1_us'] <= 1.56 else "FAIL"
            self.tree_tol.insert("", tk.END, values=("T1", "1.20 µs", "± 30%", f"{d['t1_us']:.2f} µs", is_pass))
            
        if d['t2_us']:
            if not is_chopped:
                is_pass2 = "PASS" if 40.0 <= d['t2_us'] <= 60.0 else "FAIL"
                self.tree_tol.insert("", tk.END, values=("T2", "50.00 µs", "± 20%", f"{d['t2_us']:.1f} µs", is_pass2))
            else:
                self.tree_tol.insert("", tk.END, values=("Tc", "2-5 µs", "varies", f"{d['t2_us']:.1f} µs", "N/A"))

        if not is_front_chopped and beta_dash is not None:
            is_pass_beta = "PASS" if beta_dash <= 5.0 else "WARNING (>5%)"
            self.tree_tol.insert("", tk.END, values=("β'", "≤ 5.00%", "IEC 60060-1", f"{beta_dash:.2f} %", is_pass_beta))
        else:
            self.tree_tol.insert("", tk.END, values=("β'", "≤ 5.00%", "IEC 60060-1", "N/A", "N/A"))

    def update_plot(self):
        self.ax.clear()
        d = self.data
        if not d: 
            self.canvas.draw()
            return

        self.ax.plot(d['time_us'], d['raw_v'], label='Raw data', color='#b0c4de', linewidth=1)

        # Plot IEC Mean Curve (Base double exponential) if toggled
        if self.show_mean_var.get():
            self.ax.plot(d['time_us'], d['smooth_v'], label='IEC Mean Curve (Base)', color='red', linestyle='--', linewidth=1.5)

        # [K-FACTOR FILTER] Plot K-Factor Filtered Curve vkfilt (Annex B) if toggled
        if self.show_kfilter_var.get() and 'v_kfilt' in d:
            self.ax.plot(d['time_us'], d['v_kfilt'], label=r'K-Factor Filtered ($v_{\mathrm{kfilt}}$)', color='#ff7f0e', linewidth=1.8)

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

            if d['t2_us'] and (o1 + d['t2_us'] <= d['time_us'][-1]):
                y_t2 = v_p * 0.12 
                self.ax.vlines(o1 + d['t2_us'], 0, y_t2, color='blue', linestyle=':', alpha=0.5)
                self.ax.annotate(
                    '', xy=(o1, y_t2), xytext=(o1 + d['t2_us'], y_t2),
                    arrowprops=dict(arrowstyle='<->', color='blue', lw=1.5)
                )
                
                is_chopped = bool(d.get('is_chopped', d['t2_us'] < 15.0))
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
    import sys
    app = IECAnalyzerApp()
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        app.file_path = sys.argv[1]
        app.process_data(sys.argv[1])
    app.mainloop()