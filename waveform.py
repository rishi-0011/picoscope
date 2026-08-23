import tkinter as tk
from tkinter import ttk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import traceback
import sys
import os
import datetime

# Import refactored modules
from waveform_utils import (
    read_control_info, PicoScopeProxy, parse_time_label, parse_time_to_ns,
    parse_volts_to_mv, get_voltage_range_enum, calc_tb, process_channel
)
from waveform_hw import (
    init_scope, run_hardware_block, is_hardware_ready, fetch_hardware_data
)

def build_waveform_ui(parent_frame, app):
    for widget in parent_frame.winfo_children():
        widget.destroy()

    bg_color = "#8c97a8"
    parent_frame.configure(bg=bg_color)
    
    config = getattr(app, 'config', {})
    ch1_active = config.get('ch1_active', True)
    ch2_active = config.get('ch2_active', False)
    
    app.ch1_type = config.get('ch1_type', 'Voltage')
    app.ch2_type = config.get('ch2_type', 'Voltage')
    app.unit_A = "A" if app.ch1_type == "Current" else "kV"
    app.unit_B = "A" if app.ch2_type == "Current" else "kV"
    
    top_bar = tk.Frame(parent_frame, bg="#333333", height=40)
    top_bar.pack(side="top", fill="x")
    
    app.scope_connected = getattr(app, 'is_scope_connected', False)
    app.chandle = None
    app.status = {}
    
    if app.scope_connected:
        init_scope(app, config)

    def go_back():
        if hasattr(app, 'waveform_job') and app.waveform_job is not None:
            parent_frame.after_cancel(app.waveform_job)
            app.waveform_job = None
            
        if app.chandle:
            try:
                scope_m = read_control_info().get('Scope', 'ps5000a')
                ps_close = PicoScopeProxy(scope_m)
                ps_close.ps5000aCloseUnit(app.chandle)
            except: pass
            app.chandle = None
            
        import setup
        setup.build_setup_ui(parent_frame, app=app)
        setup.update_status(parent_frame, getattr(app, 'is_scope_connected', False))
        
    back_btn = tk.Button(top_bar, text="< Back to Setup", bg="#555555", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", command=go_back)
    back_btn.pack(side="left", padx=10, pady=5)

    def open_save_dialog():
        if app.capture_state != "IDLE":
            from tkinter import messagebox
            messagebox.showwarning("Warning", "Cannot save while actively capturing data. Please wait or stop capture.")
            return

        save_win = tk.Toplevel(parent_frame)
        save_win.title("Save")
        save_win.geometry("500x380")
        save_win.configure(bg="#2b2b2b")
        save_win.grab_set()

        tk.Label(save_win, text="Selected folder path", bg="#2b2b2b", fg="white", font=("Segoe UI", 10)).pack(anchor="w", padx=15, pady=(15, 5))
        path_var = tk.StringVar(value=r"C:\Users\MaharshiM\Documents\Waveforms")
        tk.Entry(save_win, textvariable=path_var, bg="#1e1e1e", fg="white", insertbackground="white", font=("Segoe UI", 10)).pack(fill="x", padx=15, pady=(0, 10))

        tk.Label(save_win, text="File name", bg="#2b2b2b", fg="white", font=("Segoe UI", 10)).pack(anchor="w", padx=15, pady=(5, 5))
        default_name = datetime.datetime.now().strftime("%Y%m%d")
        name_var = tk.StringVar(value=default_name)
        tk.Entry(save_win, textvariable=name_var, bg="#1e1e1e", fg="white", insertbackground="white", font=("Segoe UI", 10)).pack(fill="x", padx=15, pady=(0, 10))

        tk.Label(save_win, text="File type", bg="#2b2b2b", fg="white", font=("Segoe UI", 10)).pack(anchor="w", padx=15, pady=(5, 5))
        type_var = tk.StringVar(value="CSV file")
        cb = ttk.Combobox(save_win, textvariable=type_var, values=["CSV file"], state="readonly", font=("Segoe UI", 10))
        cb.pack(fill="x", padx=15, pady=(0, 20))

        def perform_save():
            import csv
            folder = path_var.get()
            name = name_var.get()
            
            if not os.path.exists(folder):
                os.makedirs(folder)
            
            filepath = os.path.join(folder, f"{name}.csv")
            
            x_data = getattr(app, 'current_x_data', None)
            y_A = getattr(app, 'current_y_data_A', None)
            y_B = getattr(app, 'current_y_data_B', None)
            time_unit = getattr(app, 'current_time_unit', 'ms')

            if x_data is None:
                save_win.destroy()
                return

            with open(filepath, 'w', newline='') as f:
                writer = csv.writer(f)
                headers1 = ["Time"]
                headers2 = [f"({time_unit})"]
                
                has_A = y_A is not None
                has_B = y_B is not None
                
                if has_A:
                    headers1.append("Channel A")
                    headers2.append("(V)")
                if has_B:
                    headers1.append("Channel B")
                    headers2.append("(V)")
                    
                writer.writerow(headers1)
                writer.writerow(headers2)
                writer.writerow([])
                
                for i in range(len(x_data)):
                    row = [f"{x_data[i]:.8f}"]
                    if has_A:
                        row.append(f"{y_A[i]:.8f}")
                    if has_B:
                        row.append(f"{y_B[i]:.8f}")
                    writer.writerow(row)
                    
            save_win.destroy()

        btn_frame = tk.Frame(save_win, bg="#2b2b2b")
        btn_frame.pack(fill="x", side="bottom", pady=15)
        tk.Button(btn_frame, text="Save", bg="#32cd32", fg="black", font=("Segoe UI", 10, "bold"), width=12, command=perform_save).pack(side="left", padx=15)
        tk.Button(btn_frame, text="Cancel", bg="#555555", fg="white", font=("Segoe UI", 10, "bold"), width=12, command=save_win.destroy).pack(side="right", padx=15)

    save_btn = tk.Button(top_bar, text="Save", bg="#4fc3f7", fg="black", font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", command=open_save_dialog)
    save_btn.pack(side="left", padx=5, pady=5)

    def open_parameters_dialog():
        if not hasattr(app, 'latest_y_A') or app.latest_y_A is None:
            messagebox.showwarning("No Data", "No waveform data has been captured yet.")
            return

        try:
            from review import calculate_iec_parameters
            y_raw = app.latest_y_A
            x_sec = getattr(app, 'latest_x_sec', np.linspace(0, 100e-6, len(y_raw)))

            p = calculate_iec_parameters(x_sec, y_raw)

            param_win = tk.Toplevel(parent_frame)
            param_win.title("IEC 60060-1 Calculated Parameters")
            param_win.geometry("520x460")
            param_win.configure(bg="#1e293b")
            param_win.grab_set()

            ch_name = "CH1 " + getattr(app, 'ch1_type', 'Voltage')
            tk.Label(param_win, text=f"Calculated IEC Parameters ({ch_name})", bg="#1e293b", fg="#facc15", font=("Segoe UI", 12, "bold")).pack(pady=(15, 10))

            card = tk.Frame(param_win, bg="#0f172a", bd=1, relief="solid")
            card.pack(fill="both", expand=True, padx=20, pady=5)

            unit_str = "kV" if getattr(app, 'ch1_type', 'Voltage') == 'Voltage' else "A"

            params_list = [
                ("Peak Value (Vp / Ip)", f"{p['v_peak']:.2f} {unit_str}"),
                ("Front Time (T1)", f"{p['t1_us']:.2f} µs" if p['t1_us'] is not None else "--"),
                ("Time to Half-Value (T2)", f"{p['t2_us']:.2f} µs" if p['t2_us'] is not None else "--"),
                ("Virtual Origin (O1)", f"{p['o1_us']:.3f} µs" if p['o1_us'] is not None else "--"),
                ("Overshoot Magnitude (Beta)", f"{p['beta_pct']:.2f} %"),
                ("Oscillation Frequency (f)", f"{p['osc_freq_khz']:.2f} kHz")
            ]

            for label, val in params_list:
                row = tk.Frame(card, bg="#0f172a")
                row.pack(fill="x", padx=15, pady=6)
                tk.Label(row, text=label, bg="#0f172a", fg="#94a3b8", font=("Segoe UI", 10, "bold"), anchor="w").pack(side="left")
                tk.Label(row, text=val, bg="#0f172a", fg="#38bdf8", font=("Segoe UI", 11, "bold"), anchor="e").pack(side="right")

            tk.Button(param_win, text="Close", bg="#3b82f6", fg="white", font=("Segoe UI", 10, "bold"), width=12, command=param_win.destroy).pack(pady=15)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to calculate parameters:\n{e}")

    param_btn = tk.Button(top_bar, text="Parameters", bg="#8b5cf6", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2", command=open_parameters_dialog)
    param_btn.pack(side="left", padx=5, pady=5)
    
    def perform_exit():
        if hasattr(app, 'waveform_job') and app.waveform_job is not None:
            parent_frame.after_cancel(app.waveform_job)
            app.waveform_job = None
            
        if app.chandle:
            try:
                scope_m = read_control_info().get('Scope', 'ps5000a')
                ps_close = PicoScopeProxy(scope_m)
                ps_close.ps5000aCloseUnit(app.chandle)
            except: pass
            app.chandle = None
            
        if app and hasattr(app, 'root'):
            app.root.destroy()
            import sys
            sys.exit(0)

    if app and hasattr(app, 'root'):
        exit_btn = tk.Button(top_bar, text="EXIT", bg="#facc15", fg="black", font=("Segoe UI", 10, "bold"), relief="raised", borderwidth=2, width=12, height=1, pady=0, cursor="hand2", command=perform_exit)
        exit_btn.pack(side="right", padx=10, pady=2)

    status_frame = tk.Frame(top_bar, bg="#333333")
    status_frame.pack(side="right", padx=20, pady=5)
    
    parent_frame.status_canvas = tk.Canvas(status_frame, width=16, height=16, bg="#333333", highlightthickness=0)
    parent_frame.status_canvas.pack(side="left")
    
    is_conn = bool(app.chandle)
    fill_color = "#32cd32" if is_conn else "#ff4c4c"
    
    parent_frame.led = parent_frame.status_canvas.create_oval(2, 2, 14, 14, fill=fill_color, outline="white")
    
    status_text = "Scope Connected" if is_conn else "Scope Disconnected"
    parent_frame.status_label = tk.Label(status_frame, text=status_text, bg="#333333", fg=fill_color, font=("Segoe UI", 10, "bold"))
    parent_frame.status_label.pack(side="left", padx=5)

    # --- NEW LOCAL STATUS UPDATE FUNCTION ---
    def update_local_status(is_connected):
        color = "#32cd32" if is_connected else "#ff4c4c"
        text = "Scope Connected" if is_connected else "Scope Disconnected"
        if hasattr(parent_frame, 'status_canvas') and hasattr(parent_frame, 'led'):
            parent_frame.status_canvas.itemconfig(parent_frame.led, fill=color)
        if hasattr(parent_frame, 'status_label'):
            parent_frame.status_label.config(text=text, fg=color)
    # ----------------------------------------

    total_shots = 1
    if "N° of Shots" in config:
        try:
            total_shots = int(str(config["N° of Shots"]).strip())
        except: pass
    else:
        for k, v in config.items():
            if 'Shots' in k:
                try:
                    total_shots = int(str(v).strip())
                except: pass
                break
    app.total_shots = total_shots
    app.current_shot = 0

    app.update_hardware_requested = True
    
    metrics_frame = tk.Frame(parent_frame, bg="#333333")
    metrics_frame.pack(side="bottom", fill="x", padx=20, pady=(0, 20))
    
    metrics_row1 = tk.Frame(metrics_frame, bg="#333333")
    metrics_row1.pack(fill="x", pady=(5, 2))
    metrics_row2 = tk.Frame(metrics_frame, bg="#333333")
    metrics_row2.pack(fill="x", pady=(2, 5))

    app.chA_vars = {
        'freq': tk.StringVar(value="CH1 Freq: -- Hz"),
        'vpp': tk.StringVar(value=f"CH1 Vpp: -- {app.unit_A}"),
        'max': tk.StringVar(value=f"CH1 Max: -- {app.unit_A}"),
        'min': tk.StringVar(value=f"CH1 Min: -- {app.unit_A}")
    }
    app.chB_vars = {
        'freq': tk.StringVar(value="CH2 Freq: -- Hz"),
        'vpp': tk.StringVar(value=f"CH2 Vpp: -- {app.unit_B}"),
        'max': tk.StringVar(value=f"CH2 Max: -- {app.unit_B}"),
        'min': tk.StringVar(value=f"CH2 Min: -- {app.unit_B}")
    }

    if ch1_active:
        tk.Label(metrics_row1, textvariable=app.chA_vars['freq'], bg="#333333", fg="#32cd32", font=("Segoe UI", 11, "bold"), width=20, anchor="w").pack(side="left", padx=20)
        tk.Label(metrics_row1, textvariable=app.chA_vars['vpp'], bg="#333333", fg="#32cd32", font=("Segoe UI", 11, "bold"), width=20, anchor="w").pack(side="left", padx=20)
        tk.Label(metrics_row1, textvariable=app.chA_vars['max'], bg="#333333", fg="#32cd32", font=("Segoe UI", 11, "bold"), width=20, anchor="w").pack(side="left", padx=20)
        tk.Label(metrics_row1, textvariable=app.chA_vars['min'], bg="#333333", fg="#32cd32", font=("Segoe UI", 11, "bold"), width=20, anchor="w").pack(side="left", padx=20)
    else:
        metrics_row1.pack_forget()

    if ch2_active:
        tk.Label(metrics_row2, textvariable=app.chB_vars['freq'], bg="#333333", fg="#00e5ff", font=("Segoe UI", 11, "bold"), width=20, anchor="w").pack(side="left", padx=20)
        tk.Label(metrics_row2, textvariable=app.chB_vars['vpp'], bg="#333333", fg="#00e5ff", font=("Segoe UI", 11, "bold"), width=20, anchor="w").pack(side="left", padx=20)
        tk.Label(metrics_row2, textvariable=app.chB_vars['max'], bg="#333333", fg="#00e5ff", font=("Segoe UI", 11, "bold"), width=20, anchor="w").pack(side="left", padx=20)
        tk.Label(metrics_row2, textvariable=app.chB_vars['min'], bg="#333333", fg="#00e5ff", font=("Segoe UI", 11, "bold"), width=20, anchor="w").pack(side="left", padx=20)
    else:
        metrics_row2.pack_forget()

    main_content_frame = tk.Frame(parent_frame, bg=bg_color)
    main_content_frame.pack(side="top", fill="both", expand=True, padx=20, pady=(5, 10))

    graph_frame = tk.Frame(main_content_frame, bg=bg_color)
    graph_frame.pack(side="left", fill="both", expand=True, padx=(0, 10))
    
    sidebar_frame = tk.Frame(main_content_frame, bg="#8c97a8", width=320)
    sidebar_frame.pack(side="right", fill="y")
    sidebar_frame.pack_propagate(False)
    
    try:
        from PIL import Image, ImageTk
        logo_path = r"c:\Users\MaharshiM\Music\Picoscope\images\iaas_logo.png"
        if os.path.exists(logo_path):
            img = Image.open(logo_path)
            target_width = 130 
            ratio = target_width / img.width
            target_height = int(img.height * ratio)
            img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)
            app.waveform_logo = ImageTk.PhotoImage(img)
            
            logo_lbl = tk.Label(sidebar_frame, image=app.waveform_logo, bg="#8c97a8")
            logo_lbl.pack(pady=(0, 5))
    except Exception as e:
        print("Could not load logo in waveform:", e)
    
    def add_row(parent, label_text, value_text):
        row = tk.Frame(parent, bg="#8c97a8")
        row.pack(fill="x", padx=10, pady=1)
        tk.Label(row, text=label_text, bg="#8c97a8", fg="white", font=("Segoe UI", 9)).pack(side="left")
        value_lbl = tk.Label(row, text=value_text, bg="#ffffff", fg="black", font=("Segoe UI", 9, "bold"), width=12, anchor="e", padx=5)
        value_lbl.pack(side="right")
        return value_lbl

    impulse_type = config.get('impulse_type', 'Lightning')
    polarity = config.get('polarity', 'Negative')

    if ch1_active:
        imp_frame1 = tk.LabelFrame(sidebar_frame, text="CH1 Impulse Settings", bg="#8c97a8", fg="#000000", font=("Segoe UI", 10, "bold"))
        imp_frame1.pack(fill="x", padx=10, pady=(15, 5))
        add_row(imp_frame1, "Impulse Type", impulse_type)
        add_row(imp_frame1, "Polarity", polarity)
        add_row(imp_frame1, "Expected V [kV]", config.get("Expected Voltage [kV]", "150"))
        add_row(imp_frame1, "Expected I [A]", config.get("Expected Current [A]", "300"))

    if ch2_active:
        imp_frame2 = tk.LabelFrame(sidebar_frame, text="CH2 Impulse Settings", bg="#8c97a8", fg="#00e5ff", font=("Segoe UI", 10, "bold"))
        imp_frame2.pack(fill="x", padx=10, pady=(5, 5))
        add_row(imp_frame2, "Impulse Type", impulse_type)
        add_row(imp_frame2, "Polarity", polarity)
        add_row(imp_frame2, "Expected V [kV]", config.get("Expected Voltage [kV]", "150"))
        add_row(imp_frame2, "Expected I [A]", config.get("Expected Current [A]", "300"))
        
    progress_frame = tk.Frame(sidebar_frame, bg="#8c97a8")
    progress_frame.pack(fill="x", padx=10, pady=(20, 5))
    
    app.progress_label = tk.Label(progress_frame, text=f"Shot 0 of {app.total_shots}", bg="#8c97a8", fg="black", font=("Segoe UI", 11, "bold"))
    app.progress_label.pack(side="top", pady=(0, 5))
    
    app.progress_box_frame = tk.Frame(progress_frame, bg="#8c97a8", height=20)
    app.progress_box_frame.pack(side="top", fill="x", pady=2)
    app.progress_box_frame.pack_propagate(False)
    
    app.box_frames = []
    for i in range(app.total_shots):
        bf = tk.Frame(app.progress_box_frame, bg="#333333", highlightbackground="black", highlightthickness=1)
        bf.pack(side="left", expand=True, fill="both", padx=1)
        app.box_frames.append(bf)
        
    lbl_waiting = tk.Label(progress_frame, text="waiting for waveform... ⏳", bg="#8c97a8", fg="#000000", font=("Segoe UI", 9, "italic", "bold"))
    lbl_waiting.pack(side="top", pady=(5, 0))
    app.lbl_waiting = lbl_waiting

    app._blink_state = True
    app._blink_base_color = "#000000"

    def blink_waiting():
        if not hasattr(app, 'lbl_waiting') or not app.lbl_waiting.winfo_exists():
            return
            
        if "Complete" in getattr(app, 'progress_label', tk.Label()).cget("text"):
            app.lbl_waiting.config(text="", fg="#8c97a8")
            return
            
        app._blink_state = not app._blink_state
        
        # Animate the hourglass by swapping emojis
        current_text = app.lbl_waiting.cget("text")
        if "⏳" in current_text:
            app.lbl_waiting.config(text=current_text.replace("⏳", "⌛"))
        elif "⌛" in current_text:
            app.lbl_waiting.config(text=current_text.replace("⌛", "⏳"))
            
        if app._blink_state:
            app.lbl_waiting.config(fg=app._blink_base_color)
        else:
            app.lbl_waiting.config(fg="#8c97a8")
            
        app.lbl_waiting.after(600, blink_waiting)
        
    blink_waiting()
    
    def draw_progress(current):
        if not hasattr(app, 'box_frames'): return
        for i, bf in enumerate(app.box_frames):
            fill_color = "#32cd32" if i < current else "#333333"
            bf.config(bg=fill_color)
            
    app.draw_progress = draw_progress
    app.draw_progress(0)
    
    fig = Figure(figsize=(10, 6), facecolor="#1e1e1e")
    fig.subplots_adjust(left=0.08, right=0.92, top=0.95, bottom=0.15, hspace=0.3)
    
    ax1 = None
    ax2 = None
    
    if ch1_active and ch2_active:
        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212, sharex=ax1)
    elif ch1_active:
        ax1 = fig.add_subplot(111)
    elif ch2_active:
        ax2 = fig.add_subplot(111)
        
    def setup_ax(ax, title, y_label, color, spine_color="white"):
        ax.set_facecolor("#000000")
        ax.tick_params(colors="white", labelsize=10)
        for spine in ax.spines.values():
            spine.set_color(spine_color)
            spine.set_linewidth(1)
        ax.set_title(title, color="white", fontsize=11, fontweight="bold")
        ax.set_ylabel(y_label, color=color, fontsize=10, fontweight="bold")
        ax.grid(True, color="#555555", linestyle="--", linewidth=0.5)
        
    if ax1 is not None:
        setup_ax(ax1, "Channel 1 Waveform", f"CH1 {app.ch1_type}", "#32cd32")
        ax1.plot([], [], color="#32cd32", linewidth=0.8)
            
    if ax2 is not None:
        setup_ax(ax2, "", f"CH2 {app.ch2_type}", "#00e5ff")
        ax2.plot([], [], color="#00e5ff", linewidth=0.8)
        ax2.set_xlabel("Time", color="white", fontsize=10, fontweight="bold")
        
    def apply_initial_limits(ax1, ax2):
        time_str = config.get('time_str', '100 us')
        val, time_unit, _ = parse_time_label(time_str)
        val = val / 10.0
        x_min = 0.0
        x_max = 10.0 * val

        polarity = config.get('polarity', 'Negative')
        
        if ax1 is not None:
            ax1.set_xlabel(f"Time ({time_unit})", color="white", fontsize=10, fontweight="bold")
            ax1.set_xlim(x_min, x_max)
            ax1.set_xticks(np.linspace(x_min, x_max, 11))
            
            exp_A = float(config.get('Expected Voltage [kV]' if getattr(app, 'ch1_type', 'Voltage') == 'Voltage' else 'Expected Current [A]', 150))
            if exp_A <= 0: exp_A = 10.0
            step_A = exp_A / 10.0
            y_min_A = -1 * step_A if polarity == 'Positive' else -11 * step_A
            y_max_A = 11 * step_A if polarity == 'Positive' else 1 * step_A
            ax1.set_ylim(y_min_A, y_max_A)
            ax1.set_yticks(np.linspace(y_min_A, y_max_A, 13))

        if ax2 is not None:
            ax2.set_xlabel(f"Time ({time_unit})", color="white", fontsize=10, fontweight="bold")
            ax2.set_xlim(x_min, x_max)
            ax2.set_xticks(np.linspace(x_min, x_max, 11))
            
            exp_B = float(config.get('Expected Current [A]' if getattr(app, 'ch2_type', 'Current') == 'Current' else 'Expected Voltage [kV]', 300))
            if exp_B <= 0: exp_B = 10.0
            step_B = exp_B / 10.0
            y_min_B = -1 * step_B if polarity == 'Positive' else -11 * step_B
            y_max_B = 11 * step_B if polarity == 'Positive' else 1 * step_B
            ax2.set_ylim(y_min_B, y_max_B)
            ax2.set_yticks(np.linspace(y_min_B, y_max_B, 13))

    apply_initial_limits(ax1, ax2) 
    
    canvas = FigureCanvasTkAgg(fig, master=graph_frame)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)

    app.capture_state = "IDLE"
    app.meas_history = {
        'A_freq': [], 'A_max': [], 'A_min': [],
        'B_freq': [], 'B_max': [], 'B_min': []
    }

    def start_background_polling():
        if app.capture_state != "DEAD": return
        try:
            conn = app.try_connect_scope()
            if conn != app.is_scope_connected:
                app.is_scope_connected = conn
                update_local_status(conn)
        except Exception:
            pass
        if hasattr(parent_frame, 'winfo_exists') and parent_frame.winfo_exists():
            app.waveform_job = parent_frame.after(1500, start_background_polling)

    def update_graph():
        if app.capture_state != "IDLE": return
        if not app.chandle:
            app.waveform_job = parent_frame.after(500, update_graph)
            return

        try:
            time_str = config.get('time_str', '100 us')
            volt_str_A = "1V"
            volt_str_B = "1V"
            
            total_time_ns = parse_time_to_ns(time_str)
            max_mv_A = parse_volts_to_mv(volt_str_A)
            max_mv_B = parse_volts_to_mv(volt_str_B)
            
            range_enum_A = get_voltage_range_enum(max_mv_A)
            range_enum_B = get_voltage_range_enum(max_mv_B)
            timebase, noSamples = calc_tb(total_time_ns)
            res_str = "14 bits"
            
            success = run_hardware_block(
                app, config, total_time_ns, max_mv_A, max_mv_B, time_str, 
                range_enum_A, range_enum_B, timebase, noSamples, res_str
            )
            
            if not success:
                if not getattr(app, 'is_scope_connected', True):
                    app.capture_state = "DEAD"
                    update_local_status(False)
                    start_background_polling()
                    return
                app.capture_state = "IDLE"
                app.waveform_job = parent_frame.after(100, update_graph)
                return
                
            app.capture_state = "WAITING"
            
            def poll_ready():
                if not getattr(app, 'chandle', None) or app.capture_state != "WAITING": return
                
                if not is_hardware_ready(app):
                    if not getattr(app, 'is_scope_connected', True):
                        app.capture_state = "DEAD"
                        update_local_status(False)
                        start_background_polling()
                        return
                    app.waveform_job = parent_frame.after(10, poll_ready)
                    return
                else:
                    app.capture_state = "READY"
                    fetch_and_draw()
            
            def fetch_and_draw():
                if not getattr(app, 'chandle', None) or app.capture_state != "READY": return
                try:
                    y_data_A, y_data_B, tInt, pre_trig_samples, mx_mv_A, mx_mv_B, nSamp, t_str = fetch_hardware_data(app, config)
                    draw_frame(y_data_A, y_data_B, tInt, pre_trig_samples, mx_mv_A, mx_mv_B, nSamp, t_str)
                    
                    app.current_shot += 1
                    app.progress_label.config(text=f"Shot {app.current_shot} of {app.total_shots}")
                    if hasattr(app, 'draw_progress'):
                        app.draw_progress(app.current_shot)
                        
                except Exception as e:
                    traceback.print_exc()
                    
                app.capture_state = "IDLE"
                if app.current_shot < app.total_shots:
                    def countdown(seconds_left):
                        if seconds_left > 0:
                            if hasattr(app, 'lbl_waiting'):
                                app.lbl_waiting.config(text=f"Waiting {seconds_left}s for next shot... ⏳")
                                app._blink_base_color = "#000000"
                            parent_frame.after(1000, lambda: countdown(seconds_left - 1))
                        else:
                            if hasattr(app, 'lbl_waiting'):
                                app.lbl_waiting.config(text="waiting for waveform... ⏳")
                                app._blink_base_color = "#000000"
                            app.update_hardware_requested = True
                            app.waveform_job = parent_frame.after(10, update_graph)
                    countdown(10)
                else:
                    app.progress_label.config(text="Capture Complete", fg="#000000")
                    app.waveform_job = None

            app.waveform_job = parent_frame.after(10, poll_ready)
                
        except Exception as e:
            traceback.print_exc()
            app.capture_state = "IDLE"
            app.waveform_job = parent_frame.after(50, update_graph)

    def draw_frame(y_data_A, y_data_B, tInt_ns, pre_trig_samples, max_mv_A, max_mv_B, noSamples, time_str):
        if y_data_A is not None:
            process_channel(y_data_A, 'A', app.chA_vars, noSamples, tInt_ns, app.unit_A)
        if y_data_B is not None:
            process_channel(y_data_B, 'B', app.chB_vars, noSamples, tInt_ns, app.unit_B)
            
        val, time_unit, scale_to_ns = parse_time_label(time_str)
        
        start_time_ns = 0
        x_data_ns = start_time_ns + np.arange(noSamples) * tInt_ns
        x_data = x_data_ns / scale_to_ns

        if y_data_A is not None:
            app.latest_y_A = y_data_A
            app.latest_x_sec = x_data_ns * 1e-9
        
        os.makedirs("captured_data", exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        shot_num = getattr(app, 'current_shot', 1)
        filename = f"captured_data/shot_{shot_num}_{ts}.txt"
        
        try:
            with open(filename, 'w') as f:
                ch1_title = f"CH1_{getattr(app, 'ch1_type', 'Voltage')}"
                ch2_title = f"CH2_{getattr(app, 'ch2_type', 'Current')}"
                
                if y_data_A is not None and y_data_B is not None:
                    f.write(f"Time[{time_unit}]\t{ch1_title}\t{ch2_title}\n")
                    for x, ya, yb in zip(x_data, y_data_A, y_data_B):
                        f.write(f"{x:.3f}\t{ya:.3f}\t{yb:.3f}\n")
                elif y_data_A is not None:
                    f.write(f"Time[{time_unit}]\t{ch1_title}\n")
                    for x, ya in zip(x_data, y_data_A):
                        f.write(f"{x:.3f}\t{ya:.3f}\n")
                elif y_data_B is not None:
                    f.write(f"Time[{time_unit}]\t{ch2_title}\n")
                    for x, yb in zip(x_data, y_data_B):
                        f.write(f"{x:.3f}\t{yb:.3f}\n")
        except Exception as e:
            print("Failed to save data:", e)
        
        x_min = 0.0
        x_max = val  
        
        colors = ["#32cd32", "#ff00ff", "#00ffff", "#ff9900", "#ff0000", "#ffff00", "#0000ff", "#8a2be2", "#ff1493", "#00ff7f"]
        c_idx = (getattr(app, 'current_shot', 1) - 1) % len(colors)
        
        def smooth_curve(arr, win=7):
            if arr is None or len(arr) < win: return arr
            return np.convolve(arr, np.ones(win)/win, mode='same')

        if ax1 is not None and y_data_A is not None:
            if ax2 is None:
                ax1.set_xlabel(f"Time ({time_unit})", color="white", fontsize=10, fontweight="bold")
            else:
                ax1.set_xlabel("")
                
            app.latest_y_A = y_data_A
            y_plot_A = smooth_curve(y_data_A, win=7)
            ax1.plot(x_data, y_plot_A, color=colors[c_idx], linewidth=0.8)
            ax1.set_xlim(x_min, x_max)
            ax1.set_xticks(np.linspace(x_min, x_max, 11))
            
            polarity = config.get('polarity', 'Negative')
            exp_A = float(config.get('Expected Voltage [kV]' if getattr(app, 'ch1_type', 'Voltage') == 'Voltage' else 'Expected Current [A]', 150))
            if exp_A <= 0: exp_A = 10.0
            
            step_A = exp_A / 10.0
            if polarity == 'Positive':
                y_min_A = -1 * step_A
                y_max_A = 11 * step_A
            else:
                y_min_A = -11 * step_A
                y_max_A = 1 * step_A
            
            ax1.set_ylim(y_min_A, y_max_A)
            ax1.set_yticks(np.linspace(y_min_A, y_max_A, 13))
            
        if ax2 is not None and y_data_B is not None:
            ax2.set_xlabel(f"Time ({time_unit})", color="white", fontsize=10, fontweight="bold")
            app.latest_y_B = y_data_B
            y_plot_B = smooth_curve(y_data_B, win=7)
            ax2.plot(x_data, y_plot_B, color=colors[c_idx], linewidth=0.8)
            ax2.set_xlim(x_min, x_max)
            ax2.set_xticks(np.linspace(x_min, x_max, 11))
            
            polarity = config.get('polarity', 'Negative')
            exp_B = float(config.get('Expected Voltage [kV]' if getattr(app, 'ch2_type', 'Voltage') == 'Voltage' else 'Expected Current [A]', 150))
            if exp_B <= 0: exp_B = 10.0
            
            step_B = exp_B / 10.0
            if polarity == 'Positive':
                y_min_B = -1 * step_B
                y_max_B = 11 * step_B
            else:
                y_min_B = -11 * step_B
                y_max_B = 1 * step_B
            
            ax2.set_ylim(y_min_B, y_max_B)
            ax2.set_yticks(np.linspace(y_min_B, y_max_B, 13))
            
        app.current_x_data = x_data
        app.current_y_data_A = y_data_A
        app.current_y_data_B = y_data_B
        app.current_time_unit = time_unit
        
        canvas.draw()

    app.waveform_job = parent_frame.after(100, update_graph)