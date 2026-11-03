import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import traceback
import sys
import os
import datetime
from PIL import Image, ImageTk

# Import refactored modules
from waveform_utils import (
    read_control_info, PicoScopeProxy, parse_time_label, parse_time_to_ns,
    parse_volts_to_mv, get_voltage_range_enum, calc_tb, process_channel
)
from waveform_hw import (
    init_scope, run_hardware_block, is_hardware_ready, fetch_hardware_data
)
from review import SmartReviewNavToolbar

def build_waveform_ui(parent_frame, app):
    for widget in parent_frame.winfo_children():
        widget.destroy()

    # Exact setup/review theme background color
    bg_color = "#8c97a8"
    parent_frame.configure(bg=bg_color)
    
    config = getattr(app, 'config', {})
    ch1_active = config.get('ch1_active', True)
    ch2_active = config.get('ch2_active', True)
    
    app.ch1_type = config.get('ch1_type', 'Voltage')
    app.ch2_type = config.get('ch2_type', 'Current')
    app.unit_A = "A" if app.ch1_type == "Current" else "kV"
    app.unit_B = "A" if app.ch2_type == "Current" else "kV"
    
    app.scope_connected = getattr(app, 'is_scope_connected', False)
    app.chandle = getattr(app, 'chandle', None)
    app.status = getattr(app, 'status', {})
    
    if app.scope_connected and app.chandle is None:
        init_scope(app, config)

    # -------------------------------------------------------------
    # Navigation Handlers
    # -------------------------------------------------------------
    def go_back():
        if hasattr(app, 'waveform_job') and app.waveform_job is not None:
            parent_frame.after_cancel(app.waveform_job)
            app.waveform_job = None
            
        if getattr(app, 'chandle', None):
            try:
                scope_m = read_control_info().get('Scope', 'ps5000a')
                ps_close = PicoScopeProxy(scope_m)
                ps_close.ps5000aStop(app.chandle)
            except: pass
            
        import setup
        setup.build_setup_ui(parent_frame, app=app)
        setup.update_status(parent_frame, getattr(app, 'is_scope_connected', False))

    def go_review():
        if hasattr(app, 'waveform_job') and app.waveform_job is not None:
            parent_frame.after_cancel(app.waveform_job)
            app.waveform_job = None
            
        if getattr(app, 'chandle', None):
            try:
                scope_m = read_control_info().get('Scope', 'ps5000a')
                ps_close = PicoScopeProxy(scope_m)
                ps_close.ps5000aStop(app.chandle)
            except: pass
            
        import review
        review.build_review_ui(parent_frame, app=app)

    def perform_exit():
        if hasattr(app, 'waveform_job') and app.waveform_job is not None:
            try: parent_frame.after_cancel(app.waveform_job)
            except: pass
            app.waveform_job = None
            
        if app and hasattr(app, 'exit_app'):
            app.exit_app()
        else:
            if getattr(app, 'chandle', None):
                try:
                    scope_m = read_control_info().get('Scope', 'ps5000a')
                    ps_close = PicoScopeProxy(scope_m)
                    ps_close.ps5000aCloseUnit(app.chandle)
                except: pass
                app.chandle = None
            if app and hasattr(app, 'root'):
                try: app.root.destroy()
                except: pass
            import os
            os._exit(0)

    # -------------------------------------------------------------
    # 1. Exact Top Navigation Bar (matching Setup screen)
    # -------------------------------------------------------------
    top_bar = tk.Frame(parent_frame, bg="#333333", height=40)
    top_bar.pack(side="top", fill="x")

    lbl_setup = tk.Label(top_bar, text="Setup", bg="#555555", fg="white", width=10, font=("Segoe UI", 10), pady=5, cursor="hand2")
    lbl_setup.pack(side="left", padx=1)
    lbl_setup.bind("<Button-1>", lambda e: go_back())

    lbl_view = tk.Label(top_bar, text="View", bg="#e53935", fg="white", width=10, font=("Segoe UI", 10, "bold"), pady=5)
    lbl_view.pack(side="left", padx=1)

    lbl_review = tk.Label(top_bar, text="Review", bg="#555555", fg="white", width=10, font=("Segoe UI", 10), pady=5, cursor="hand2")
    lbl_review.pack(side="left", padx=1)
    lbl_review.bind("<Button-1>", lambda e: go_review())

    lbl_analysis = tk.Label(top_bar, text="Analysis", bg="#555555", fg="white", width=10, font=("Segoe UI", 10), pady=5, cursor="hand2")
    lbl_analysis.pack(side="left", padx=1)

    # Exit Button
    exit_btn = tk.Button(top_bar, text="EXIT", bg="#facc15", fg="black", font=("Segoe UI", 10, "bold"), relief="raised", borderwidth=2, width=12, height=1, pady=0, cursor="hand2", command=perform_exit)
    exit_btn.pack(side="right", padx=10, pady=2)

    # Status LED & Label
    status_frame = tk.Frame(top_bar, bg="#333333")
    status_frame.pack(side="right", padx=20, pady=5)

    parent_frame.status_canvas = tk.Canvas(status_frame, width=16, height=16, bg="#333333", highlightthickness=0)
    parent_frame.status_canvas.pack(side="left")

    is_conn = bool(app.chandle) or getattr(app, 'is_scope_connected', False)
    fill_color = "#32cd32" if is_conn else "#ff4c4c"
    parent_frame.led = parent_frame.status_canvas.create_oval(2, 2, 14, 14, fill=fill_color, outline="white")

    status_text = "Scope Connected" if is_conn else "Scope Disconnected"
    parent_frame.status_label = tk.Label(status_frame, text=status_text, bg="#333333", fg=fill_color, font=("Segoe UI", 10, "bold"))
    parent_frame.status_label.pack(side="left", padx=5)

    # -------------------------------------------------------------
    # 2. Header Area: Centered "View" Title + Logo on Right
    # -------------------------------------------------------------
    header_frame = tk.Frame(parent_frame, bg=bg_color, height=45)
    header_frame.pack(side="top", fill="x", padx=10, pady=(2, 0))

    lbl_title = tk.Label(header_frame, text="View", bg=bg_color, fg="white", font=("Segoe UI", 16, "bold"))
    lbl_title.place(relx=0.48, rely=0.5, anchor="center")

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    wsts_path = os.path.join(BASE_DIR, "images", "exact_wsts.png")
    if os.path.exists(wsts_path):
        wsts_img = Image.open(wsts_path).resize((115, 52), Image.Resampling.LANCZOS)
        app.wsts_tk = ImageTk.PhotoImage(wsts_img)
        lbl_wsts = tk.Label(header_frame, image=app.wsts_tk, bg=bg_color)
        lbl_wsts.pack(side="right", padx=10)

    # -------------------------------------------------------------
    # 3. Content Area: Left (Channel Tabs + Graphs) & Right (Sidebar)
    # -------------------------------------------------------------
    content_frame = tk.Frame(parent_frame, bg=bg_color)
    content_frame.pack(side="top", fill="both", expand=True, padx=8, pady=(0, 4))

    # PACK SIDEBAR FIRST (Fixed width on right: 230px)
    sidebar = tk.Frame(content_frame, bg=bg_color, bd=2, relief="groove", width=230)
    sidebar.pack(side="right", fill="y", padx=(6, 2))
    sidebar.pack_propagate(False)

    # Left Container: Channel Tabs + Oscilloscope Plots
    left_area = tk.Frame(content_frame, bg=bg_color)
    left_area.pack(side="left", fill="both", expand=True)

    # Channel Tabs Strip (Enlarged)
    tabs_frame = tk.Frame(left_area, bg=bg_color)
    tabs_frame.pack(side="top", anchor="w", padx=2)

    tab_12 = tk.Label(tabs_frame, text="Channel 1&2", bg="#acb4cf", fg="black", font=("Segoe UI", 9, "bold"), padx=16, pady=4, relief="groove", bd=2, cursor="hand2")
    tab_12.pack(side="left", padx=(0, 2))

    tab_1 = tk.Label(tabs_frame, text="Channel 1", bg="#7b879c", fg="#222222", font=("Segoe UI", 9, "bold"), padx=16, pady=4, relief="raised", bd=2, cursor="hand2")
    tab_1.pack(side="left", padx=2)

    tab_2 = tk.Label(tabs_frame, text="Channel 2", bg="#7b879c", fg="#222222", font=("Segoe UI", 9, "bold"), padx=16, pady=4, relief="raised", bd=2, cursor="hand2")
    tab_2.pack(side="left", padx=2)

    # Outer container with 3D groove border around the plots
    plots_panel = tk.Frame(left_area, bg=bg_color, bd=2, relief="groove")
    plots_panel.pack(side="top", fill="both", expand=True, padx=2, pady=(0, 2))

    # Limits and Ticks
    time_str = config.get('time_str', '100 us')
    val_time, time_unit, _ = parse_time_label(time_str)
    x_max = val_time * 1e-6 if time_unit == 'us' else val_time * 1e-3
    if x_max <= 0: x_max = 100e-6

    # Top plot: Voltage [kV], -220 to 20
    y_limits_v = (-220.0, 20.0)
    y_ticks_v = np.linspace(-220, 20, 13)
    y_labels_v = [f"{int(v)}" for v in y_ticks_v]

    # Bottom plot: Current [A], -220 to 220
    y_limits_i = (-220.0, 220.0)
    y_ticks_i = [-220, -150, -100, -50, 0, 50, 100, 150, 220]
    y_labels_i = [f"{v}" for v in y_ticks_i]

    def create_oscilloscope_panel(parent, y_label, y_limits, y_ticks, y_tick_labels):
        card = tk.Frame(parent, bg=bg_color)
        card.pack(fill="both", expand=True, padx=4, pady=2)

        fig = Figure(figsize=(7.5, 2.7), facecolor=bg_color, dpi=100)
        fig.subplots_adjust(left=0.07, right=0.985, top=0.96, bottom=0.18)
        ax = fig.add_subplot(111)

        ax.set_facecolor("#adb4ce")
        for spine in ax.spines.values():
            spine.set_color("#2b303a")
            spine.set_linewidth(1.0)

        # Subtle oscilloscope grid lines
        ax.grid(True, color="#989ebb", linestyle="-", linewidth=0.7)
        ax.axhline(0, color="#1e293b", linewidth=1.0)

        # Y-axis
        ax.set_ylabel(y_label, color="black", fontsize=8.5, fontweight="bold", labelpad=2)
        ax.set_ylim(y_limits)
        ax.set_yticks(y_ticks)
        ax.set_yticklabels(y_tick_labels, color="black", fontsize=7.5, fontweight="bold")
        ax.tick_params(axis='y', colors="black", direction='in', length=4, pad=3)

        # X-axis
        xticks = np.linspace(0, x_max, 11)
        ax.set_xlim(0, x_max)
        ax.set_xticks(xticks)
        xlabels = ["0.0E+0"] + [f"{x*1e6:.1f}E-6" for x in xticks[1:]]
        ax.set_xticklabels(xlabels, color="black", fontsize=7.5, fontweight="bold")
        ax.tick_params(axis='x', colors="black", direction='in', length=4, pad=3)

        canvas = FigureCanvasTkAgg(fig, master=card)
        canvas.draw()
        canvas.get_tk_widget().pack(fill="both", expand=True)

        # Bottom strip: Time [s] label + Scrollbar
        bot_strip = tk.Frame(card, bg=bg_color, height=16)
        bot_strip.pack(fill="x", padx=(45, 12), pady=(0, 2))

        lbl_time = tk.Label(bot_strip, text="Time [s]", bg=bg_color, fg="black", font=("Segoe UI", 8, "bold"))
        lbl_time.pack(side="left", padx=(260, 15))

        sb = tk.Canvas(bot_strip, height=12, bg="#707c96", highlightthickness=1, highlightbackground="#444d62")
        sb.pack(side="left", fill="x", expand=True)
        sb.create_rectangle(80, 1, 240, 11, fill="#87b0dc", outline="#5680ac")

        return card, fig, ax, canvas, sb

    card1, fig1, ax1, canvas1, sb1 = create_oscilloscope_panel(plots_panel, f"{app.ch1_type}[{app.unit_A}]", y_limits_v, y_ticks_v, y_labels_v)
    card2, fig2, ax2, canvas2, sb2 = create_oscilloscope_panel(plots_panel, f"{app.ch2_type}[{app.unit_B}]", y_limits_i, y_ticks_i, y_labels_i)

    # -------------------------------------------------------------
    # 4. Right Sidebar: Clean Review-Style Native Buttons
    # -------------------------------------------------------------
    def open_save_dialog():
        save_win = tk.Toplevel(parent_frame)
        save_win.title("Save Waveform")
        save_win.geometry("500x380")
        save_win.configure(bg="#2b2b2b")
        save_win.grab_set()

        capture_default_dir = getattr(app, 'config', {}).get('test_path') or os.path.join(os.path.dirname(os.path.abspath(__file__)), "Capture Data")
        os.makedirs(capture_default_dir, exist_ok=True)

        tk.Label(save_win, text="Selected folder path", bg="#2b2b2b", fg="white", font=("Segoe UI", 10)).pack(anchor="w", padx=15, pady=(15, 5))
        path_var = tk.StringVar(value=capture_default_dir)
        tk.Entry(save_win, textvariable=path_var, bg="#1e1e1e", fg="white", insertbackground="white", font=("Segoe UI", 10)).pack(fill="x", padx=15, pady=(0, 10))

        tk.Label(save_win, text="File name", bg="#2b2b2b", fg="white", font=("Segoe UI", 10)).pack(anchor="w", padx=15, pady=(5, 5))
        default_name = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        name_var = tk.StringVar(value=default_name)
        tk.Entry(save_win, textvariable=name_var, bg="#1e1e1e", fg="white", insertbackground="white", font=("Segoe UI", 10)).pack(fill="x", padx=15, pady=(0, 10))

        tk.Label(save_win, text="File type", bg="#2b2b2b", fg="white", font=("Segoe UI", 10)).pack(anchor="w", padx=15, pady=(5, 5))
        type_var = tk.StringVar(value="CSV file (.csv)")
        cb = ttk.Combobox(save_win, textvariable=type_var, values=["CSV file (.csv)", "TXT file (.txt)", "DAT file (.dat)"], state="readonly", font=("Segoe UI", 10))
        cb.pack(fill="x", padx=15, pady=(0, 20))

        def perform_save():
            import csv
            folder = path_var.get()
            name = name_var.get().strip() or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            selected_type = type_var.get()

            ext = ".dat" if "DAT" in selected_type else (".txt" if "TXT" in selected_type else ".csv")
            base_name = os.path.splitext(name)[0]
            os.makedirs(folder, exist_ok=True)
            filepath = os.path.join(folder, f"{base_name}{ext}")

            x_data = getattr(app, 'current_x_data', None)
            y_A = getattr(app, 'current_y_data_A', None)
            y_B = getattr(app, 'current_y_data_B', None)

            if x_data is None:
                messagebox.showwarning("No Data", "No captured waveform data available to save.")
                save_win.destroy()
                return

            has_A = y_A is not None
            has_B = y_B is not None

            if ext == ".dat":
                from iaas_crypto import pack_binary_dat
                bin_bytes = pack_binary_dat(x_data, y_A, y_B, 'us')
                with open(filepath, 'wb') as f:
                    f.write(bin_bytes)
            elif ext == ".csv":
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    h1 = ["Time (s)"]
                    if has_A: h1.append(f"CH1 {app.ch1_type}")
                    if has_B: h1.append(f"CH2 {app.ch2_type}")
                    writer.writerow(h1)
                    for i in range(len(x_data)):
                        row = [f"{x_data[i]:.8e}"]
                        if has_A: row.append(f"{y_A[i]:.6f}")
                        if has_B: row.append(f"{y_B[i]:.6f}")
                        writer.writerow(row)
            else:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"Time[s]\tCH1_{app.ch1_type}\tCH2_{app.ch2_type}\n")
                    for i in range(len(x_data)):
                        v1 = y_A[i] if has_A else 0.0
                        v2 = y_B[i] if has_B else 0.0
                        f.write(f"{x_data[i]:.8e}\t{v1:.6f}\t{v2:.6f}\n")

            save_win.destroy()
            messagebox.showinfo("Saved", f"Successfully saved captured waveform to:\n{filepath}")

        btn_f = tk.Frame(save_win, bg="#2b2b2b")
        btn_f.pack(fill="x", side="bottom", pady=15)
        tk.Button(btn_f, text="Save", bg="#32cd32", fg="black", font=("Segoe UI", 10, "bold"), width=12, command=perform_save).pack(side="left", padx=15)
        tk.Button(btn_f, text="Cancel", bg="#555555", fg="white", font=("Segoe UI", 10, "bold"), width=12, command=save_win.destroy).pack(side="right", padx=15)

    def perform_print():
        try:
            save_path = filedialog.asksaveasfilename(
                defaultextension=".png",
                filetypes=[("PNG Image", "*.png"), ("PDF Document", "*.pdf"), ("All Files", "*.*")],
                title="Save Screen Snapshot"
            )
            if save_path:
                fig1.savefig(save_path, dpi=300, facecolor=fig1.get_facecolor())
                messagebox.showinfo("Saved", f"Snapshot successfully saved to:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save snapshot:\n{e}")

    def render_parameters_content(panel, ch_name="CH1"):
        for w in panel.winfo_children():
            w.destroy()

        y_raw = getattr(app, 'latest_y_A', None) if ch_name == "CH1" else getattr(app, 'latest_y_B', None)
        unit_str = app.unit_A if ch_name == "CH1" else app.unit_B
        ch_type = app.ch1_type if ch_name == "CH1" else app.ch2_type

        card = tk.Frame(panel, bg="#1e293b", bd=2, relief="groove")
        card.pack(fill="both", expand=True, padx=2, pady=2)

        # Header with title and close button
        head_bar = tk.Frame(card, bg="#1e293b")
        head_bar.pack(fill="x", padx=6, pady=(4, 2))
        
        lbl_head = tk.Label(head_bar, text=f"{ch_name} Parameters", bg="#1e293b",
                            fg="#facc15" if ch_name == "CH1" else "#38bdf8",
                            font=("Segoe UI", 8, "bold"))
        lbl_head.pack(side="left")

        btn_close = tk.Label(head_bar, text="✕", bg="#1e293b", fg="#94a3b8",
                             font=("Segoe UI", 9, "bold"), cursor="hand2")
        btn_close.pack(side="right")
        btn_close.bind("<Button-1>", lambda e: panel.pack_forget())

        # Divider
        tk.Frame(card, height=1, bg="#475569").pack(fill="x", padx=6, pady=(0, 4))

        if y_raw is None:
            tk.Label(card, text="No waveform captured yet.\nClick ENTER on Setup.",
                     bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 8, "italic"),
                     justify="center").pack(expand=True, pady=15)
            return

        try:
            from review import calculate_iec_parameters
            x_sec = getattr(app, 'latest_x_sec', np.linspace(0, x_max, len(y_raw)))
            p = calculate_iec_parameters(x_sec, y_raw)

            is_chopped = bool(p.get('is_chopped', False))
            is_front_chopped = bool(p.get('is_front_chopped', False))

            peak_label = "Uc (Chop)" if is_front_chopped else ("Vp (Peak)" if ch_type == "Voltage" else "Ip (Peak)")
            vp_val = f"{p['v_peak']:.2f} {unit_str}"
            t1_val = f"{p['t1_us']:.2f} µs" if p['t1_us'] is not None else "--"
            t2_label = "Tc (Chop)" if is_chopped else "T2 (Tail)"
            t2_val = f"{p['t2_us']:.1f} µs" if p['t2_us'] is not None else "--"
            o1_val = f"{p['o1_us']:.3f} µs" if p['o1_us'] is not None else "--"

            beta_raw_val = p.get('beta_raw_pct')
            beta_raw_str = f"{beta_raw_val:.2f} %" if beta_raw_val is not None else "--"

            beta_dash_val = p.get('beta_dash_pct')
            beta_dash_str = f"{beta_dash_val:.2f} %" if beta_dash_val is not None else "--"
            beta_color = "#34d399" if (beta_dash_val is not None and beta_dash_val <= 5.0) else "#f87171"

            f_val = f"{p['osc_freq_khz']:.2f} kHz" if p.get('osc_freq_khz', 0) > 0 else "--"

            peak_name = "Uc" if is_front_chopped else ("Vp" if ch_type == "Voltage" else "Ip")
            t2_name = "Tc" if is_chopped else "T2"

            rows = [
                (peak_name, vp_val, "#38bdf8"),
                ("T1", t1_val, "#ffffff"),
                (t2_name, t2_val, "#ffffff"),
                ("O1", o1_val, "#cbd5e1"),
                ("β", beta_raw_str, "#facc15"),
                ("β'", beta_dash_str, beta_color),
                ("f", f_val, "#cbd5e1"),
            ]
            if is_chopped and p.get('steepness_kv_us'):
                rows.append(("S", f"{p['steepness_kv_us']:.1f} kV/µs", "#facc15"))

            rows_frame = tk.Frame(card, bg="#1e293b")
            rows_frame.pack(fill="both", expand=True, padx=6, pady=(0, 2))

            for name, val, col in rows:
                r = tk.Frame(rows_frame, bg="#1e293b")
                r.pack(fill="x", pady=2)
                tk.Label(r, text=name, bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 7, "bold"), anchor="w").pack(side="left")
                tk.Label(r, text=val, bg="#1e293b", fg=col, font=("Segoe UI", 7, "bold"), anchor="e").pack(side="right")

            # Status footer
            if is_front_chopped:
                status_text = "FRONT CHOPPED"
                status_color = "#f59e0b"
            elif is_chopped:
                status_text = "TAIL CHOPPED"
                status_color = "#38bdf8"
            else:
                is_pass = (p['t1_us'] is not None and 0.84 <= p['t1_us'] <= 1.56 and
                           p['t2_us'] is not None and 40.0 <= p['t2_us'] <= 60.0 and
                           (beta_dash_val is None or beta_dash_val <= 5.0))
                status_text = "IEC PASS" if is_pass else ("β'>5% WARN" if (beta_dash_val and beta_dash_val > 5.0) else "OUT OF TOL")
                status_color = "#34d399" if is_pass else "#f87171"
            
            badge_f = tk.Frame(card, bg="#0f172a", bd=1, relief="solid")
            badge_f.pack(fill="x", padx=6, pady=(2, 4))
            tk.Label(badge_f, text=status_text, bg="#0f172a", fg=status_color,
                     font=("Segoe UI", 7, "bold"), pady=1).pack(anchor="center")

        except Exception as e:
            tk.Label(card, text=f"Calc Error:\n{e}", bg="#1e293b", fg="#ef4444",
                     font=("Segoe UI", 8)).pack(expand=True, pady=10)

    def toggle_parameters(ch_name="CH1"):
        panel = param_panel_ch1 if ch_name == "CH1" else param_panel_ch2
        if panel.winfo_ismapped():
            panel.pack_forget()
        else:
            if ch_name == "CH1":
                panel.pack(side="top", fill="both", expand=True, pady=(8, 4))
            else:
                panel.pack(side="top", fill="both", expand=True, pady=(4, 2))
            render_parameters_content(panel, ch_name)

    # Navigation Toolbar Pan Handlers
    def pan_channel(direction, ch_name):
        ax = ax1 if ch_name == "CH1" else ax2
        canvas = canvas1 if ch_name == "CH1" else canvas2
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        dx = (cur_xlim[1] - cur_xlim[0]) * 0.15
        dy = (cur_ylim[1] - cur_ylim[0]) * 0.15
        if direction == 'left': ax.set_xlim(cur_xlim[0] - dx, cur_xlim[1] - dx)
        elif direction == 'right': ax.set_xlim(cur_xlim[0] + dx, cur_xlim[1] + dx)
        elif direction == 'up': ax.set_ylim(cur_ylim[0] + dy, cur_ylim[1] + dy)
        elif direction == 'down': ax.set_ylim(cur_ylim[0] - dy, cur_ylim[1] - dy)
        canvas.draw_idle()

    def reset_channel(ch_name):
        ax = ax1 if ch_name == "CH1" else ax2
        canvas = canvas1 if ch_name == "CH1" else canvas2
        ax.set_xlim(0, x_max)
        if ch_name == "CH1": ax.set_ylim(y_limits_v)
        else: ax.set_ylim(y_limits_i)
        canvas.draw_idle()

    # =============================================================
    # SIDEBAR WIDGETS (EXACT NATIVE REVIEW BUTTON STYLING & ALIGNMENT)
    # =============================================================

    # --- SECTION 1: Channel 1 Sidebar (matches Card 1 height) ---
    sidebar_ch1 = tk.Frame(sidebar, bg=bg_color)
    sidebar_ch1.pack(side="top", fill="both", expand=True, padx=6, pady=(4, 2))

    # Top Action Buttons: Save & Print
    top_btns = tk.Frame(sidebar_ch1, bg=bg_color)
    top_btns.pack(side="top", fill="x", pady=(2, 0))

    btn_save = tk.Button(top_btns, text="Save", bg="#2563eb", fg="white", font=("Segoe UI", 10, "bold"),
                         relief="raised", bd=2, pady=3, cursor="hand2", command=open_save_dialog)
    btn_save.pack(fill="x", pady=(0, 6))

    btn_print = tk.Button(top_btns, text="Print", bg="#60a5fa", fg="black", font=("Segoe UI", 10, "bold"),
                          relief="raised", bd=2, pady=3, cursor="hand2", command=perform_print)
    btn_print.pack(fill="x")

    # Bottom of Section 1: Toolbar, Parameters, View Ch1
    tb_ch1_frame = tk.Frame(sidebar_ch1, bg=bg_color)
    tb_ch1_frame.pack(side="bottom", fill="x", pady=(0, 2))
    app.tb_ch1 = SmartReviewNavToolbar(canvas1, tb_ch1_frame, pan_callback=lambda d: pan_channel(d, "CH1"),
                                       mk_callback=None,
                                       home_callback=lambda: reset_channel("CH1"),
                                       icon_size=16)
    app.tb_ch1.pack(fill="x", expand=True)

    btn_param1 = tk.Button(sidebar_ch1, text="Parameters", bg="#881337", fg="white", font=("Segoe UI", 10, "bold"),
                           relief="raised", bd=2, pady=3, cursor="hand2", command=lambda: toggle_parameters("CH1"))
    btn_param1.pack(side="bottom", fill="x", pady=(0, 6))

    lbl_ch1 = tk.Label(sidebar_ch1, text="View Ch1", bg=bg_color, fg="#facc15", font=("Segoe UI", 11, "bold"))
    lbl_ch1.pack(side="bottom", anchor="w", pady=(0, 2))

    # Middle parameters container for Channel 1 (between Print and View Ch1)
    param_panel_ch1 = tk.Frame(sidebar_ch1, bg=bg_color)
    app.btn_param1 = btn_param1
    app.param_panel_ch1 = param_panel_ch1

    # --- SECTION 2: Active Wave Row (Middle Gap between plots) ---
    active_wave_frame = tk.Frame(sidebar, bg=bg_color)
    active_wave_frame.pack(side="top", fill="x", padx=6, pady=(2, 2))

    tk.Label(active_wave_frame, text="Active Wave", bg=bg_color, fg="#1e293b",
             font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 5))

    blue_box = tk.Label(active_wave_frame, bg="#0000ff", width=4, height=1, relief="solid", bd=1)
    blue_box.pack(side="left", padx=(0, 5))

    app.spin_wave = tk.Spinbox(active_wave_frame, from_=1, to=99, width=4, font=("Segoe UI", 9, "bold"), justify="center")
    app.spin_wave.pack(side="left")

    # --- SECTION 3: Channel 2 Sidebar (matches Card 2 height) ---
    sidebar_ch2 = tk.Frame(sidebar, bg=bg_color)
    sidebar_ch2.pack(side="top", fill="both", expand=True, padx=6, pady=(2, 4))

    # Bottom of Section 3: Toolbar, Parameters, View Ch2
    tb_ch2_frame = tk.Frame(sidebar_ch2, bg=bg_color)
    tb_ch2_frame.pack(side="bottom", fill="x", pady=(0, 2))
    app.tb_ch2 = SmartReviewNavToolbar(canvas2, tb_ch2_frame, pan_callback=lambda d: pan_channel(d, "CH2"),
                                       mk_callback=None,
                                       home_callback=lambda: reset_channel("CH2"),
                                       icon_size=16)
    app.tb_ch2.pack(fill="x", expand=True)

    btn_param2 = tk.Button(sidebar_ch2, text="Parameters", bg="#881337", fg="white", font=("Segoe UI", 10, "bold"),
                           relief="raised", bd=2, pady=3, cursor="hand2", command=lambda: toggle_parameters("CH2"))
    btn_param2.pack(side="bottom", fill="x", pady=(0, 6))

    lbl_ch2 = tk.Label(sidebar_ch2, text="View Ch2", bg=bg_color, fg="#38bdf8", font=("Segoe UI", 11, "bold"))
    lbl_ch2.pack(side="bottom", anchor="w", pady=(0, 2))

    # Middle parameters container for Channel 2
    param_panel_ch2 = tk.Frame(sidebar_ch2, bg=bg_color)

    # -------------------------------------------------------------
    # Channel View Switching
    # -------------------------------------------------------------
    def set_channel_view(view_mode):
        tab_12.config(
            bg="#acb4cf" if view_mode == "Channel 1&2" else "#7b879c",
            fg="black" if view_mode == "Channel 1&2" else "#222222",
            relief="groove" if view_mode == "Channel 1&2" else "raised"
        )
        tab_1.config(
            bg="#acb4cf" if view_mode == "Channel 1" else "#7b879c",
            fg="black" if view_mode == "Channel 1" else "#222222",
            relief="groove" if view_mode == "Channel 1" else "raised"
        )
        tab_2.config(
            bg="#acb4cf" if view_mode == "Channel 2" else "#7b879c",
            fg="black" if view_mode == "Channel 2" else "#222222",
            relief="groove" if view_mode == "Channel 2" else "raised"
        )

        if view_mode == "Channel 1&2":
            card1.pack(fill="both", expand=True, padx=4, pady=2)
            card2.pack(fill="both", expand=True, padx=4, pady=2)
            sidebar_ch1.pack(side="top", fill="both", expand=True, padx=8, pady=(4, 2))
            active_wave_frame.pack(side="top", fill="x", padx=8, pady=(2, 2))
            sidebar_ch2.pack(side="top", fill="both", expand=True, padx=8, pady=(2, 4))
        elif view_mode == "Channel 1":
            card2.pack_forget()
            card1.pack(fill="both", expand=True, padx=4, pady=2)
            sidebar_ch2.pack_forget()
            active_wave_frame.pack_forget()
            sidebar_ch1.pack(side="top", fill="both", expand=True, padx=8, pady=(4, 2))
        elif view_mode == "Channel 2":
            card1.pack_forget()
            card2.pack(fill="both", expand=True, padx=4, pady=2)
            sidebar_ch1.pack_forget()
            active_wave_frame.pack_forget()
            sidebar_ch2.pack(side="top", fill="both", expand=True, padx=8, pady=(2, 4))

    tab_12.bind("<Button-1>", lambda e: set_channel_view("Channel 1&2"))
    tab_1.bind("<Button-1>", lambda e: set_channel_view("Channel 1"))
    tab_2.bind("<Button-1>", lambda e: set_channel_view("Channel 2"))

    # Initial view
    if ch1_active and ch2_active:
        set_channel_view("Channel 1&2")
    elif ch1_active:
        set_channel_view("Channel 1")
    elif ch2_active:
        set_channel_view("Channel 2")
    else:
        set_channel_view("Channel 1&2")

    # -------------------------------------------------------------
    # Waveform Hardware Acquisition Engine
    # -------------------------------------------------------------
    app.total_shots = 1
    if "N° of Shots" in config:
        try: app.total_shots = int(str(config["N° of Shots"]).strip())
        except: pass
    app.current_shot = 0
    app.capture_state = "IDLE"
    app.update_hardware_requested = True

    def draw_frame(y_data_A, y_data_B, tInt_ns, pre_trig_samples, max_mv_A, max_mv_B, noSamples, time_str):
        x_data_ns = np.arange(noSamples) * tInt_ns
        x_data_sec = x_data_ns * 1e-9

        if y_data_A is not None:
            app.latest_y_A = y_data_A
            app.latest_x_sec = x_data_sec
            ax1.cla()
            ax1.set_facecolor("#adb4ce")
            for spine in ax1.spines.values():
                spine.set_color("#2b303a")
                spine.set_linewidth(1.0)
            ax1.grid(True, color="#989ebb", linestyle="-", linewidth=0.7)
            ax1.axhline(0, color="#1e293b", linewidth=1.0)
            ax1.plot(x_data_sec, y_data_A, color="#0055ff", linewidth=1.2)
            ax1.set_ylabel(f"{app.ch1_type}[{app.unit_A}]", color="black", fontsize=8.5, fontweight="bold", labelpad=2)
            ax1.set_ylim(y_limits_v)
            ax1.set_yticks(y_ticks_v)
            ax1.set_yticklabels(y_labels_v, color="black", fontsize=7.5, fontweight="bold")
            xticks = np.linspace(0, x_max, 11)
            ax1.set_xlim(0, x_max)
            ax1.set_xticks(xticks)
            xlabels = ["0.0E+0"] + [f"{x*1e6:.1f}E-6" for x in xticks[1:]]
            ax1.set_xticklabels(xlabels, color="black", fontsize=7.5, fontweight="bold")
            ax1.tick_params(axis='both', colors="black", direction='in', length=4, pad=3)
            canvas1.draw()

        if y_data_B is not None:
            app.latest_y_B = y_data_B
            ax2.cla()
            ax2.set_facecolor("#adb4ce")
            for spine in ax2.spines.values():
                spine.set_color("#2b303a")
                spine.set_linewidth(1.0)
            ax2.grid(True, color="#989ebb", linestyle="-", linewidth=0.7)
            ax2.axhline(0, color="#1e293b", linewidth=1.0)
            ax2.plot(x_data_sec, y_data_B, color="#0055ff", linewidth=1.2)
            ax2.set_ylabel(f"{app.ch2_type}[{app.unit_B}]", color="black", fontsize=8.5, fontweight="bold", labelpad=2)
            ax2.set_ylim(y_limits_i)
            ax2.set_yticks(y_ticks_i)
            ax2.set_yticklabels(y_labels_i, color="black", fontsize=7.5, fontweight="bold")
            xticks = np.linspace(0, x_max, 11)
            ax2.set_xlim(0, x_max)
            ax2.set_xticks(xticks)
            xlabels = ["0.0E+0"] + [f"{x*1e6:.1f}E-6" for x in xticks[1:]]
            ax2.set_xticklabels(xlabels, color="black", fontsize=7.5, fontweight="bold")
            ax2.tick_params(axis='both', colors="black", direction='in', length=4, pad=3)
            canvas2.draw()

        app.current_x_data = x_data_sec
        app.current_y_data_A = y_data_A
        app.current_y_data_B = y_data_B

        # Refresh in-line sidebar parameters if visible
        try:
            if hasattr(param_panel_ch1, 'winfo_ismapped') and param_panel_ch1.winfo_ismapped():
                render_parameters_content(param_panel_ch1, "CH1")
            if hasattr(param_panel_ch2, 'winfo_ismapped') and param_panel_ch2.winfo_ismapped():
                render_parameters_content(param_panel_ch2, "CH2")
        except Exception:
            pass

        # Save shot data to disk
        save_folder = getattr(app, 'config', {}).get('test_path') or os.path.join(os.getcwd(), "captured_data")
        os.makedirs(save_folder, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        shot_num = getattr(app, 'current_shot', 1)
        filename = os.path.join(save_folder, f"shot_{shot_num}_{ts}.txt")
        try:
            with open(filename, 'w') as f:
                f.write(f"Time[s]\tCH1_{app.ch1_type}\tCH2_{app.ch2_type}\n")
                for x, ya, yb in zip(x_data_sec, y_data_A if y_data_A is not None else np.zeros_like(x_data_sec), y_data_B if y_data_B is not None else np.zeros_like(x_data_sec)):
                    f.write(f"{x:.8e}\t{ya:.4f}\t{yb:.4f}\n")
        except: pass

        if hasattr(app, 'spin_wave'):
            try:
                app.spin_wave.delete(0, "end")
                app.spin_wave.insert(0, str(shot_num))
            except: pass

    def update_graph():
        if app.capture_state != "IDLE": return
        if not app.chandle:
            app.waveform_job = parent_frame.after(500, update_graph)
            return

        try:
            total_time_ns = parse_time_to_ns(time_str)
            range_enum_A = get_voltage_range_enum(1000)
            range_enum_B = get_voltage_range_enum(1000)
            timebase, noSamples = calc_tb(total_time_ns)

            success = run_hardware_block(
                app, config, total_time_ns, 1000, 1000, time_str,
                range_enum_A, range_enum_B, timebase, noSamples, "14 bits"
            )

            if not success:
                app.capture_state = "IDLE"
                app.waveform_job = parent_frame.after(100, update_graph)
                return

            app.capture_state = "WAITING"

            def poll_ready():
                if not getattr(app, 'chandle', None) or app.capture_state != "WAITING": return

                if not is_hardware_ready(app):
                    app.waveform_job = parent_frame.after(10, poll_ready)
                    return
                else:
                    app.capture_state = "READY"
                    fetch_and_draw()

            def fetch_and_draw():
                if not getattr(app, 'chandle', None) or app.capture_state != "READY": return
                try:
                    y_data_A, y_data_B, tInt, pre_trig_samples, mx_mv_A, mx_mv_B, nSamp, t_str = fetch_hardware_data(app, config)
                    app.current_shot += 1
                    draw_frame(y_data_A, y_data_B, tInt, pre_trig_samples, mx_mv_A, mx_mv_B, nSamp, t_str)
                except Exception as e:
                    traceback.print_exc()

                app.capture_state = "IDLE"
                if app.current_shot < app.total_shots:
                    app.waveform_job = parent_frame.after(1000, update_graph)
                else:
                    app.waveform_job = None

            app.waveform_job = parent_frame.after(10, poll_ready)

        except Exception as e:
            traceback.print_exc()
            app.capture_state = "IDLE"
            app.waveform_job = parent_frame.after(100, update_graph)

    if hasattr(app, 'prefetched_data') and app.prefetched_data:
        try:
            data = app.prefetched_data
            app.prefetched_data = None
            app.current_shot += 1
            draw_frame(*data)
            app.capture_state = "IDLE"
            if app.current_shot < app.total_shots:
                app.waveform_job = parent_frame.after(1000, update_graph)
            else:
                app.waveform_job = None
        except Exception as e:
            traceback.print_exc()
            app.waveform_job = parent_frame.after(100, update_graph)
    else:
        app.waveform_job = parent_frame.after(100, update_graph)
