import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import numpy as np
import os
import pathlib
from scipy.optimize import curve_fit
from scipy.signal import find_peaks

# ----------------------------------------------------------------------
# CALCULATION ENGINE (Exact math from impulse_calculator.py)
# ----------------------------------------------------------------------
def calculate_iec_parameters(time, raw_voltage):
    t = time
    v_raw = raw_voltage
    
    # Polarity detection
    polarity = -1 if abs(np.min(v_raw)) > abs(np.max(v_raw)) else 1
    v = v_raw * polarity

    idx_peak = int(np.argmax(v))
    Vext = v[idx_peak]
    tp = t[idx_peak]

    def _crossing_time(target, tt, vv):
        idx = np.where(vv >= target)[0]
        if len(idx) == 0:
            raise ValueError("Signal never reaches requested level.")
        idx = idx[0]
        if idx == 0: return tt[0]
        t0, t1 = tt[idx - 1], tt[idx]
        v0, v1 = vv[idx - 1], vv[idx]
        frac = (target - v0) / (v1 - v0) if (v1 - v0) != 0 else 0
        return t0 + frac * (t1 - t0)

    def _double_exp(tt, A, alpha, beta_p, t0):
        tau = np.clip(tt - t0, 0, None)
        return A * (np.exp(-alpha * tau) - np.exp(-beta_p * tau))

    # Front Timing (T1, O1)
    front_t, front_v = t[: idx_peak + 1], v[: idx_peak + 1]
    v30, v90 = 0.30 * Vext, 0.90 * Vext
    
    try:
        t30 = _crossing_time(v30, front_t, front_v)
        t90 = _crossing_time(v90, front_t, front_v)
        T1 = 1.67 * (t90 - t30)
        O1 = t30 - 0.3 * (t90 - t30)
    except Exception:
        t30, t90, T1, O1 = None, None, None, None

    # Tail Timing (T2)
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

    # Base Curve Fit & Overshoot Beta
    base = np.zeros_like(v)
    base_peak = Vext
    beta_prime = 0.0
    
    if T1 is not None and T2 is not None and O1 is not None:
        tail_start = tp + 4 * T1
        mask_fit = ((t >= O1) & (t < t90)) | (t > tail_start)
        if mask_fit.sum() < 5:
            mask_fit = t >= O1

        A0 = Vext * 1.3
        alpha0 = np.log(2) / max(T2, 1e-9)
        beta0 = 3 / max(T1, 1e-9)
        try:
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
            base = v

    # Oscillation Frequency
    f_osc = np.nan
    if T1 is not None:
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

    v_peak_plot = Vext * polarity
    base_plot = base * polarity
    
    return {
        'time_us': t * 1e6, 
        'raw_v': v_raw,
        'smooth_v': base_plot,
        'v_peak': v_peak_plot,
        'v30': v30 * polarity if 'v30' in locals() else 0,
        'v50': v50 * polarity if 'v50' in locals() else 0,
        'v90': v90 * polarity if 'v90' in locals() else 0,
        't30_us': t30 * 1e6 if t30 else None,
        't90_us': t90 * 1e6 if t90 else None,
        't50_us': t50 * 1e6 if t50 else None,
        't1_us': T1 * 1e6 if T1 else None,
        't2_us': T2 * 1e6 if T2 else None,
        'o1_us': O1 * 1e6 if O1 else None,
        'beta_pct': beta_prime,
        'osc_freq_khz': f_osc * 1e-3 if not np.isnan(f_osc) else 0
    }

# ----------------------------------------------------------------------
# SMART NAVIGATION TOOLBAR WITH NATIVE CUSTOM ARROWS & MK BUTTON
# ----------------------------------------------------------------------
class SmartReviewNavToolbar(NavigationToolbar2Tk):
    toolitems = [t for t in NavigationToolbar2Tk.toolitems if t[0] not in ('Back', 'Forward')]

    def __init__(self, canvas, window, pan_callback=None, mk_callback=None, home_callback=None):
        super().__init__(canvas, window)
        self.pan_callback = pan_callback
        self.mk_callback = mk_callback
        self.home_callback = home_callback
        self._inject_custom_arrows()
        self._add_mk_button()
        self._make_compact()

        if hasattr(self, 'message'):
            try: self.message.pack_forget()
            except: pass
        if hasattr(self, 'loc_label'):
            try: self.loc_label.pack_forget()
            except: pass

    def set_message(self, s):
        pass

    def home(self, *args):
        super().home(*args)
        if self.home_callback:
            self.home_callback()
        else:
            self.canvas.draw_idle()

    def _inject_custom_arrows(self):
        try:
            import matplotlib.cbook as cbook
            original_get_data_path = cbook._get_data_path

            def hooked_get_data_path(path_type, *args, **kwargs):
                if path_type == 'images' and args:
                    img_name = args[0]
                    local_images = ['left.png', 'right.png', 'up.png', 'down.png',
                                    'left_large.png', 'right_large.png', 'up_large.png', 'down_large.png']
                    if img_name in local_images:
                        base_dir = pathlib.Path(os.path.dirname(__file__)) / 'images'
                        return (base_dir / img_name).absolute()
                return original_get_data_path(path_type, *args, **kwargs)

            cbook._get_data_path = hooked_get_data_path

            btn_left = self._Button('Pan Left', 'left.png', False, lambda: self._do_pan('left'))
            btn_right = self._Button('Pan Right', 'right.png', False, lambda: self._do_pan('right'))
            btn_up = self._Button('Pan Up', 'up.png', False, lambda: self._do_pan('up'))
            btn_down = self._Button('Pan Down', 'down.png', False, lambda: self._do_pan('down'))

            children = self.pack_slaves()
            my_btns = children[-4:]
            insert_before = children[1] if len(children) > 5 else None

            if insert_before:
                for b in my_btns:
                    b.pack(side=tk.LEFT, before=insert_before)

            cbook._get_data_path = original_get_data_path
        except Exception as e:
            print("Could not load native pan icons in review toolbar:", e)

    def _add_mk_button(self):
        btn_mk = tk.Button(self, text="MK", font=("Segoe UI", 8, "bold"), bg="#facc15", fg="black",
                           width=3, relief="raised", bd=1, cursor="hand2", command=self._do_mk)
        btn_mk.pack(side=tk.LEFT, padx=2)

    def _do_mk(self):
        if self.mk_callback:
            self.mk_callback()

    def _do_pan(self, direction):
        if self.pan_callback:
            self.pan_callback(direction)

    def _make_compact(self):
        for child in self.winfo_children():
            if isinstance(child, (tk.Button, ttk.Button)):
                try:
                    child.configure(padx=0, pady=0)
                except Exception:
                    pass

# ----------------------------------------------------------------------
# REVIEW TAB UI BUILDER
# ----------------------------------------------------------------------
def build_review_ui(parent_frame, app=None):
    for widget in parent_frame.winfo_children():
        widget.destroy()

    bg_color = "#8c97a8"
    parent_frame.configure(bg=bg_color)
    parent_frame.rowconfigure(0, weight=0)
    parent_frame.rowconfigure(1, weight=1)
    parent_frame.columnconfigure(0, weight=1)

    ch_data = {"Ch1": None, "Ch2": None}
    show_markers = {"Ch1": True, "Ch2": True}

    # ----------------------------------------------------
    # Top Tab Navigation Bar
    # ----------------------------------------------------
    tab_frame = tk.Frame(parent_frame, bg="#333333")
    tab_frame.grid(row=0, column=0, sticky="ew")

    import setup

    def go_setup(e=None):
        setup.build_setup_ui(parent_frame, app)
        setup.update_status(parent_frame, getattr(app, 'is_scope_connected', False))

    def go_tab(t_name):
        if t_name == "Review":
            build_review_ui(parent_frame, app)
        else:
            setup.show_empty_tab_page(parent_frame, app, t_name)

    tabs = ["Setup", "View", "Review", "Analysis"]
    for t in tabs:
        if t == "Review":
            lbl = tk.Label(tab_frame, text=t, bg="#e53935", fg="white", width=10, font=("Segoe UI", 10, "bold"), pady=5)
        else:
            lbl = tk.Label(tab_frame, text=t, bg="#555555", fg="white", width=10, font=("Segoe UI", 10), pady=5, cursor="hand2")
            if t == "Setup":
                lbl.bind("<Button-1>", go_setup)
            else:
                lbl.bind("<Button-1>", lambda e, name=t: go_tab(name))
        lbl.pack(side="left", padx=1 if t != "Setup" else 0)

    # Exit Button
    if app:
        exit_btn = tk.Button(tab_frame, text="EXIT", bg="#facc15", fg="black", font=("Segoe UI", 10, "bold"),
                             relief="raised", borderwidth=2, width=12, height=1, pady=0, cursor="hand2",
                             command=app.root.quit)
        exit_btn.pack(side="right", padx=10, pady=2)

    # Status LED & Label
    status_frame = tk.Frame(tab_frame, bg="#333333")
    status_frame.pack(side="right", padx=20, pady=5)

    status_canvas = tk.Canvas(status_frame, width=16, height=16, bg="#333333", highlightthickness=0)
    status_canvas.pack(side="left")
    is_conn = getattr(app, 'is_scope_connected', False)
    status_color = "#32cd32" if is_conn else "#ff4c4c"
    status_text = "Scope Connected" if is_conn else "Scope Disconnected"
    status_canvas.create_oval(2, 2, 14, 14, fill=status_color, outline="white")

    status_lbl = tk.Label(status_frame, text=status_text, bg="#333333", fg=status_color, font=("Segoe UI", 10, "bold"))
    status_lbl.pack(side="left", padx=5)

    # ----------------------------------------------------
    # Main Content Area
    # ----------------------------------------------------
    content_frame = tk.Frame(parent_frame, bg=bg_color)
    content_frame.grid(row=1, column=0, sticky="nsew", padx=15, pady=10)
    content_frame.columnconfigure(0, weight=1)
    content_frame.rowconfigure(1, weight=1)

    # Top Header Row: "Review" title in center, Logo on right
    header_frame = tk.Frame(content_frame, bg=bg_color)
    header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
    header_frame.columnconfigure(0, weight=1)

    title_label = tk.Label(header_frame, text="Review", bg=bg_color, fg="#1e293b",
                           font=("Segoe UI", 20, "bold"))
    title_label.pack(side="top", expand=True)

    # Logo on top right corner
    try:
        from PIL import Image, ImageTk
        logo_path = r"c:\Users\MaharshiM\Music\Picoscope\images\carona_transparent.png"
        if not os.path.exists(logo_path):
            logo_path = r"c:\Users\MaharshiM\Music\Picoscope\images\iaas_logo.png"

        if os.path.exists(logo_path):
            img = Image.open(logo_path)
            img.thumbnail((140, 50))
            app.review_logo_img = ImageTk.PhotoImage(img)
            logo_lbl = tk.Label(header_frame, image=app.review_logo_img, bg=bg_color)
            logo_lbl.place(relx=1.0, rely=0.0, anchor="ne")
    except Exception as e:
        print("Review logo load error:", e)

    # ----------------------------------------------------
    # Center Split Frame: Sub-tabs & Plots (Left), Sidebar (Right)
    # ----------------------------------------------------
    main_split = tk.Frame(content_frame, bg=bg_color)
    main_split.grid(row=1, column=0, sticky="nsew")
    main_split.columnconfigure(0, weight=1)
    main_split.columnconfigure(1, weight=0)
    main_split.rowconfigure(0, weight=1)

    # Left Container (Sub-tabs + Plots)
    left_container = tk.Frame(main_split, bg=bg_color)
    left_container.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
    left_container.columnconfigure(0, weight=1)
    left_container.rowconfigure(1, weight=1)

    # Sub-tabs bar above plots (Channel 1&2, Channel 1, Channel 2)
    subtab_frame = tk.Frame(left_container, bg=bg_color)
    subtab_frame.grid(row=0, column=0, sticky="w", pady=(0, 5))

    active_subtab = tk.StringVar(value="Channel 1&2")

    btn_ch12 = tk.Button(subtab_frame, text="Channel 1&2", font=("Segoe UI", 9, "bold"),
                         relief="raised", bd=2, width=12, bg="#d1d5db", fg="black")
    btn_ch1 = tk.Button(subtab_frame, text="Channel 1", font=("Segoe UI", 9),
                        relief="raised", bd=1, width=12, bg="#9ca3af", fg="black")
    btn_ch2 = tk.Button(subtab_frame, text="Channel 2", font=("Segoe UI", 9),
                        relief="raised", bd=1, width=12, bg="#9ca3af", fg="black")

    btn_ch12.pack(side="left", padx=(0, 2))
    btn_ch1.pack(side="left", padx=2)
    btn_ch2.pack(side="left", padx=2)

    # Plot Frame
    plot_frame = tk.Frame(left_container, bg="#c8cee0", bd=2, relief="groove")
    plot_frame.grid(row=1, column=0, sticky="nsew")

    # Embedded Matplotlib Figure
    fig = Figure(figsize=(7, 5), facecolor="#c8cee0")
    canvas = FigureCanvasTkAgg(fig, master=plot_frame)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    # Helper function to plot a channel waveform
    def render_channel_plot(ax, d, title_text="Channel", show_mk=True):
        ax.clear()
        ax.set_facecolor("#dce2ee")
        ax.grid(True, color="#a0a8b8", linestyle="-", linewidth=0.7)
        ax.set_ylabel("Voltage [kV]", fontsize=9, fontweight="bold")
        ax.set_xlabel("Time [s]", fontsize=9, fontweight="bold")
        ax.tick_params(labelsize=8)

        if not d:
            ax.set_title(f"{title_text} - No Data Loaded", fontsize=10, fontweight="bold")
            return

        time_s = d['time_us'] * 1e-6
        ax.plot(time_s, d['raw_v'], label='Raw Waveform', color='#1e3a8a', linewidth=1.2)

        if show_mk and d['t1_us'] is not None:
            v_p = d['v_peak']
            sign = 1 if v_p >= 0 else -1

            markers = [
                (d['t30_us'] * 1e-6 if d['t30_us'] else None, d['v30'], '30%', 'purple'),
                (d['t50_us'] * 1e-6 if d['t50_us'] else None, d['v50'], '50%', 'blue'),
                (d['t90_us'] * 1e-6 if d['t90_us'] else None, d['v90'], '90%', 'green')
            ]

            for t_val, v_val, label, color in markers:
                if t_val is not None:
                    ax.hlines(v_val, 0, t_val, color=color, linestyle=':', alpha=0.6)
                    ax.vlines(t_val, 0, v_val, color=color, linestyle=':', alpha=0.6)
                    ax.plot(t_val, v_val, marker='o', color=color, markersize=4)
                    ax.text(t_val, v_val, f' {label}', va='center', color=color, fontsize=8, fontweight="bold")

            o1_s = d['o1_us'] * 1e-6 if d['o1_us'] else 0
            t1_s = d['t1_us'] * 1e-6 if d['t1_us'] else 0

            ax.plot(o1_s, 0, marker='o', color='black', markersize=4)
            ax.vlines(o1_s, 0, v_p * 0.15, color='black', linestyle='--', alpha=0.6)

            y_t1 = v_p * 0.05
            ax.vlines(o1_s + t1_s, 0, y_t1, color='purple', linestyle=':', alpha=0.6)
            ax.annotate(
                '', xy=(o1_s, y_t1), xytext=(o1_s + t1_s, y_t1),
                arrowprops=dict(arrowstyle='<->', color='purple', lw=1.2)
            )
            ax.text(o1_s + (t1_s / 2), y_t1, f" T1 = {d['t1_us']:.2f} µs ",
                    ha='center', va='bottom' if sign > 0 else 'top', color='purple', fontsize=8,
                    bbox=dict(facecolor='white', edgecolor='none', alpha=0.8, pad=1))

            if d['t2_us']:
                t2_s = d['t2_us'] * 1e-6
                y_t2 = v_p * 0.12
                ax.vlines(o1_s + t2_s, 0, y_t2, color='blue', linestyle=':', alpha=0.6)
                ax.annotate(
                    '', xy=(o1_s, y_t2), xytext=(o1_s + t2_s, y_t2),
                    arrowprops=dict(arrowstyle='<->', color='blue', lw=1.2)
                )

                is_chopped = (d['t2_us'] < 15.0)
                t2_plot_label = "Tc" if is_chopped else "T2"

                ax.text(o1_s + (t2_s / 2), y_t2, f" {t2_plot_label} = {d['t2_us']:.1f} µs ",
                        ha='center', va='bottom' if sign > 0 else 'top', color='blue', fontsize=8,
                        bbox=dict(facecolor='white', edgecolor='none', alpha=0.8, pad=1))

        ax.set_title(f"{title_text} - IEC 60060-1 Waveform", fontsize=10, fontweight="bold")
        ax.legend(loc="upper right", fontsize=8)

    def draw_plots(mode="Channel 1&2"):
        fig.clear()

        if mode == "Channel 1&2":
            ax1 = fig.add_subplot(211)
            ax2 = fig.add_subplot(212)
            render_channel_plot(ax1, ch_data["Ch1"], "Channel 1", show_markers["Ch1"])
            render_channel_plot(ax2, ch_data["Ch2"], "Channel 2", show_markers["Ch2"])

        elif mode == "Channel 1":
            ax1 = fig.add_subplot(111)
            render_channel_plot(ax1, ch_data["Ch1"], "Channel 1", show_markers["Ch1"])

        elif mode == "Channel 2":
            ax2 = fig.add_subplot(111)
            render_channel_plot(ax2, ch_data["Ch2"], "Channel 2", show_markers["Ch2"])

        fig.tight_layout()
        canvas.draw()
        if hasattr(app, 'tb_ch1') and app.tb_ch1: app.tb_ch1.update()
        if hasattr(app, 'tb_ch2') and app.tb_ch2: app.tb_ch2.update()

    def toggle_markers(ch_key):
        show_markers[ch_key] = not show_markers[ch_key]
        draw_plots(active_subtab.get())

    def set_subtab(selected_mode):
        active_subtab.set(selected_mode)
        for b, m in [(btn_ch12, "Channel 1&2"), (btn_ch1, "Channel 1"), (btn_ch2, "Channel 2")]:
            if m == selected_mode:
                b.config(bg="#e53935", fg="white", font=("Segoe UI", 9, "bold"), bd=2)
            else:
                b.config(bg="#9ca3af", fg="black", font=("Segoe UI", 9), bd=1)
        draw_plots(selected_mode)

    btn_ch12.config(command=lambda: set_subtab("Channel 1&2"))
    btn_ch1.config(command=lambda: set_subtab("Channel 1"))
    btn_ch2.config(command=lambda: set_subtab("Channel 2"))

    # ----------------------------------------------------
    # Action Functions
    # ----------------------------------------------------
    def load_channel_file(ch_key):
        file_path = filedialog.askopenfilename(
            title=f"Select Waveform Data for {ch_key}",
            filetypes=[("Data files", "*.txt *.csv *.dat"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            raw_data = np.loadtxt(file_path)
            time_arr = raw_data[:, 0]
            volt_arr = raw_data[:, 1]

            calc_res = calculate_iec_parameters(time_arr, volt_arr)
            ch_data[ch_key] = calc_res
            draw_plots(active_subtab.get())
            messagebox.showinfo("Success", f"Successfully loaded and calculated IEC parameters for {ch_key}!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to parse and calculate waveform data:\n{e}")

    def show_parameters_dialog(ch_key):
        d = ch_data[ch_key]
        if not d:
            messagebox.showwarning("No Data", f"No waveform data loaded for {ch_key}. Please click 'Load...' first.")
            return

        param_win = tk.Toplevel(parent_frame)
        param_win.title(f"IEC 60060-1 Parameters - {ch_key}")
        param_win.geometry("520x450")
        param_win.configure(bg="#2b2b2b")
        param_win.grab_set()

        style = ttk.Style(param_win)
        style.configure("Review.Treeview", font=('Segoe UI', 10), rowheight=26)
        style.configure("Review.Treeview.Heading", font=('Segoe UI', 10, 'bold'))

        tk.Label(param_win, text=f"Calculated IEC Parameters ({ch_key})", bg="#2b2b2b", fg="#facc15",
                 font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(15, 5))

        tree_params = ttk.Treeview(param_win, columns=("Parameter", "Value"), show="headings", height=7, style="Review.Treeview")
        tree_params.heading("Parameter", text="Parameter")
        tree_params.heading("Value", text="Value")
        tree_params.column("Parameter", width=260)
        tree_params.column("Value", width=180, anchor="e")
        tree_params.pack(fill="x", padx=15, pady=(0, 15))

        is_chopped = bool(d['t2_us'] and d['t2_us'] < 15.0)
        vp_val = d['v_peak']
        vp_str = f"{vp_val:.1f} V" if abs(vp_val) > 100 else f"{vp_val:.2f} V"

        tree_params.insert("", tk.END, values=("Peak Voltage (Vp)", vp_str))
        if d['t1_us']: tree_params.insert("", tk.END, values=("Front Time (T1)", f"{d['t1_us']:.2f} µs"))
        
        t2_label = "Chopping Time (Tc)" if is_chopped else "Half-value Time (T2)"
        if d['t2_us']: tree_params.insert("", tk.END, values=(t2_label, f"{d['t2_us']:.1f} µs"))
        if d['o1_us']: tree_params.insert("", tk.END, values=("Virtual Origin (O1)", f"{d['o1_us']:.3f} µs"))
        
        tree_params.insert("", tk.END, values=("Overshoot (β)", f"{d.get('beta_pct', 0):.2f} %"))
        tree_params.insert("", tk.END, values=("Oscillation Freq (f)", f"{d.get('osc_freq_khz', 0):.2f} kHz"))

        tk.Label(param_win, text="IEC 60060-1 Tolerance Verification", bg="#2b2b2b", fg="white",
                 font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=15, pady=(5, 5))

        tree_tol = ttk.Treeview(param_win, columns=("Param", "Nominal", "Tol", "Measured", "Pass"), show="headings", height=3, style="Review.Treeview")
        for col in ["Param", "Nominal", "Tol", "Measured", "Pass"]:
            tree_tol.heading(col, text=col)
        
        tree_tol.column("Param", width=70)
        tree_tol.column("Nominal", width=90, anchor="e")
        tree_tol.column("Tol", width=80, anchor="center")
        tree_tol.column("Measured", width=100, anchor="e")
        tree_tol.column("Pass", width=80, anchor="center")
        tree_tol.pack(fill="x", padx=15, pady=(0, 15))

        if d['t1_us']:
            is_pass = "PASS" if 0.84 <= d['t1_us'] <= 1.56 else "FAIL"
            tree_tol.insert("", tk.END, values=("T1", "1.20 µs", "± 30%", f"{d['t1_us']:.2f} µs", is_pass))

        if d['t2_us']:
            if not is_chopped:
                is_pass2 = "PASS" if 40.0 <= d['t2_us'] <= 60.0 else "FAIL"
                tree_tol.insert("", tk.END, values=("T2", "50.00 µs", "± 20%", f"{d['t2_us']:.1f} µs", is_pass2))
            else:
                tree_tol.insert("", tk.END, values=("Tc", "2-5 µs", "varies", f"{d['t2_us']:.1f} µs", "N/A"))

        tk.Button(param_win, text="Close", bg="#e53935", fg="white", font=("Segoe UI", 10, "bold"),
                  command=param_win.destroy, width=10).pack(pady=10)

    def remove_channel_wave(ch_key):
        ch_data[ch_key] = None
        draw_plots(active_subtab.get())
        messagebox.showinfo("Removed", f"Cleared waveform data for {ch_key}.")

    def pan_plot_channel(direction, target_ch="Ch1"):
        tb = getattr(app, 'tb_ch1', None) if target_ch == "Ch1" else getattr(app, 'tb_ch2', None)
        if tb and hasattr(tb, 'push_current'):
            try: tb.push_current()
            except: pass

        axes_list = fig.get_axes()
        if not axes_list: return
        ax = axes_list[0] if (target_ch == "Ch1" or len(axes_list) == 1) else axes_list[1]
        
        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()
        dx = (x_max - x_min) * 0.15
        dy = (y_max - y_min) * 0.15
        if direction == 'left': ax.set_xlim(x_min - dx, x_max - dx)
        elif direction == 'right': ax.set_xlim(x_min + dx, x_max + dx)
        elif direction == 'up': ax.set_ylim(y_min + dy, y_max + dy)
        elif direction == 'down': ax.set_ylim(y_min - dy, y_max - dy)
        canvas.draw_idle()

    def export_data():
        if not ch_data["Ch1"] and not ch_data["Ch2"]:
            messagebox.showwarning("No Data", "No waveform data loaded to export.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Export Review Parameters",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt")]
        )
        if not save_path: return

        try:
            with open(save_path, "w") as f:
                f.write("Channel,Vp_V,T1_us,T2_us,O1_us,Beta_pct,OscFreq_kHz\n")
                for ch in ["Ch1", "Ch2"]:
                    d = ch_data[ch]
                    if d:
                        f.write(f"{ch},{d['v_peak']:.2f},{d['t1_us'] or 0:.2f},{d['t2_us'] or 0:.2f},{d['o1_us'] or 0:.3f},{d.get('beta_pct',0):.2f},{d.get('osc_freq_khz',0):.2f}\n")
            messagebox.showinfo("Exported", f"Successfully exported review parameters to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export data:\n{e}")

    def save_all_as():
        if not ch_data["Ch1"] and not ch_data["Ch2"]:
            messagebox.showwarning("No Data", "No waveform data loaded to save.")
            return

        save_path = filedialog.asksaveasfilename(
            title="Save Plot Image",
            defaultextension=".png",
            filetypes=[("PNG Image", "*.png"), ("PDF Document", "*.pdf")]
        )
        if save_path:
            fig.savefig(save_path)
            messagebox.showinfo("Saved", f"Successfully saved plot image to:\n{save_path}")

    # ----------------------------------------------------
    # Right Control Sidebar (Review Ch1 & Review Ch2 controls)
    # ----------------------------------------------------
    sidebar = tk.Frame(main_split, bg="#8c97a8", bd=2, relief="groove", padx=5, pady=4)
    sidebar.grid(row=0, column=1, sticky="ns")
    sidebar.columnconfigure(0, weight=1)

    # --- SECTION 1: Review Ch1 ---
    ch1_sec = tk.Frame(sidebar, bg="#8c97a8")
    ch1_sec.pack(fill="x", pady=(0, 2))

    tk.Label(ch1_sec, text="Review Ch1", bg="#8c97a8", fg="#facc15",
             font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 2))

    tk.Button(ch1_sec, text="Load...", bg="#facc15", fg="black", font=("Segoe UI", 8, "bold"),
              relief="raised", bd=2, pady=1, command=lambda: load_channel_file("Ch1")).pack(fill="x", pady=2)

    tk.Button(ch1_sec, text="Remove Wave", bg="#f97316", fg="black", font=("Segoe UI", 8, "bold"),
              relief="raised", bd=2, pady=1, command=lambda: remove_channel_wave("Ch1")).pack(fill="x", pady=2)

    tk.Button(ch1_sec, text="Parameters", bg="#881337", fg="white", font=("Segoe UI", 8, "bold"),
              relief="raised", bd=2, pady=1, command=lambda: show_parameters_dialog("Ch1")).pack(fill="x", pady=2)

    # Compact Native Toolbar under Parameters for Ch1 (includes custom Pan Arrows + MK button)
    tb_ch1_frame = tk.Frame(ch1_sec, bg="#8c97a8")
    tb_ch1_frame.pack(fill="x", pady=(1, 3))
    app.tb_ch1 = SmartReviewNavToolbar(canvas, tb_ch1_frame, pan_callback=lambda d: pan_plot_channel(d, "Ch1"),
                                       mk_callback=lambda: toggle_markers("Ch1"),
                                       home_callback=lambda: draw_plots(active_subtab.get()))
    app.tb_ch1.pack(side="left")

    # Separator
    ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=4)

    # --- SECTION 2: Active Wave Row ---
    active_wave_frame = tk.Frame(sidebar, bg="#8c97a8")
    active_wave_frame.pack(fill="x", pady=2)

    tk.Label(active_wave_frame, text="Active Wave", bg="#8c97a8", fg="#1e293b",
             font=("Segoe UI", 8, "bold")).pack(side="left", padx=(0, 3))

    blue_box = tk.Label(active_wave_frame, bg="#0000ff", width=2, height=1, relief="solid", bd=1)
    blue_box.pack(side="left", padx=(0, 3))

    spin_wave = tk.Spinbox(active_wave_frame, from_=1, to=99, width=3, font=("Segoe UI", 8, "bold"), justify="center")
    spin_wave.pack(side="left")

    # Separator
    ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=4)

    # --- SECTION 3: Review Ch2 ---
    ch2_sec = tk.Frame(sidebar, bg="#8c97a8")
    ch2_sec.pack(fill="x", pady=(0, 2))

    tk.Label(ch2_sec, text="Review Ch2", bg="#8c97a8", fg="#2563eb",
             font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 2))

    tk.Button(ch2_sec, text="Load...", bg="#facc15", fg="black", font=("Segoe UI", 8, "bold"),
              relief="raised", bd=2, pady=1, command=lambda: load_channel_file("Ch2")).pack(fill="x", pady=2)

    tk.Button(ch2_sec, text="Remove Wave", bg="#f97316", fg="black", font=("Segoe UI", 8, "bold"),
              relief="raised", bd=2, pady=1, command=lambda: remove_channel_wave("Ch2")).pack(fill="x", pady=2)

    tk.Button(ch2_sec, text="Parameters", bg="#881337", fg="white", font=("Segoe UI", 8, "bold"),
              relief="raised", bd=2, pady=1, command=lambda: show_parameters_dialog("Ch2")).pack(fill="x", pady=2)

    tk.Button(ch2_sec, text="Save All as...", bg="#2563eb", fg="white", font=("Segoe UI", 8, "bold"),
              relief="raised", bd=2, pady=1, command=save_all_as).pack(fill="x", pady=2)

    tk.Button(ch2_sec, text="Export", bg="#facc15", fg="black", font=("Segoe UI", 8, "bold"),
              relief="raised", bd=2, pady=1, command=export_data).pack(fill="x", pady=2)

    tk.Button(ch2_sec, text="Print", bg="#60a5fa", fg="black", font=("Segoe UI", 8, "bold"),
              relief="raised", bd=2, pady=1, command=save_all_as).pack(fill="x", pady=2)

    # Compact Native Toolbar under Parameters/Print for Ch2 (includes custom Pan Arrows + MK button)
    tb_ch2_frame = tk.Frame(ch2_sec, bg="#8c97a8")
    tb_ch2_frame.pack(fill="x", pady=(1, 3))
    app.tb_ch2 = SmartReviewNavToolbar(canvas, tb_ch2_frame, pan_callback=lambda d: pan_plot_channel(d, "Ch2"),
                                       mk_callback=lambda: toggle_markers("Ch2"),
                                       home_callback=lambda: draw_plots(active_subtab.get()))
    app.tb_ch2.pack(side="left")

    # Initial plot rendering
    set_subtab("Channel 1&2")

