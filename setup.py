import tkinter as tk
from tkinter import ttk
import json
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "setup_config.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(config):
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
    except:
        pass

def build_setup_ui(parent_frame, app=None):
    saved_config = load_config()
    
    def trigger_save(*args):
        try:
            sb_volt.get()
            sb_curr.get()
            sb_shots.get()
        except NameError:
            return
            
        if not hasattr(parent_frame, 'channels_info') or len(parent_frame.channels_info) < 2:
            return
            
        save_dict = {
            "Impulse Type": cb_impulse.get(),
            "Polarity": cb_polarity.get(),
            "Expected Voltage [kV]": sb_volt.get(),
            "Expected Current [A]": sb_curr.get(),
            "N° of Shots": sb_shots.get(),
            "Window Time": cb_window.get()
        }
            
        c1 = parent_frame.channels_info[0]
        save_dict["ch1_active"] = (c1['btn']["text"] == "Active")
        save_dict["ch1_type"] = c1['type_cb'].get()
        save_dict["ch1_int"] = c1['int_att'].get()
        save_dict["ch1_ext"] = c1['ext_att'].get()
        
        c2 = parent_frame.channels_info[1]
        save_dict["ch2_active"] = (c2['btn']["text"] == "Active")
        save_dict["ch2_type"] = c2['type_cb'].get()
        save_dict["ch2_int"] = c2['int_att'].get()
        save_dict["ch2_ext"] = c2['ext_att'].get()
        
        save_config(save_dict)

    # Clear previous widgets
    for widget in parent_frame.winfo_children():
        widget.destroy()
        
    parent_frame.configure(bg="#8c97a8")
    parent_frame.rowconfigure(0, weight=0)
    parent_frame.input_widgets = []
        
    # Top tab bar
    tab_frame = tk.Frame(parent_frame, bg="#333333")
    tab_frame.grid(row=0, column=0, sticky="new")
    
    tk.Label(tab_frame, text="Setup", bg="#e53935", fg="white", width=10, font=("Segoe UI", 10, "bold"), pady=5).pack(side="left")
    
    lbl_view = tk.Label(tab_frame, text="View", bg="#555555", fg="white", width=10, font=("Segoe UI", 10), pady=5, cursor="hand2")
    lbl_view.pack(side="left", padx=1)
    
    lbl_review = tk.Label(tab_frame, text="Review", bg="#555555", fg="white", width=10, font=("Segoe UI", 10), pady=5, cursor="hand2")
    lbl_review.pack(side="left", padx=1)
    
    lbl_analysis = tk.Label(tab_frame, text="Analysis", bg="#555555", fg="white", width=10, font=("Segoe UI", 10), pady=5, cursor="hand2")
    lbl_analysis.pack(side="left", padx=1)
    
    if app:
        lbl_view.bind("<Button-1>", lambda e: show_empty_tab_page(parent_frame, app, "View"))
        lbl_review.bind("<Button-1>", lambda e: show_empty_tab_page(parent_frame, app, "Review"))
        lbl_analysis.bind("<Button-1>", lambda e: show_empty_tab_page(parent_frame, app, "Analysis"))
    
    def perform_app_exit():
        if app and hasattr(app, 'exit_app'):
            app.exit_app()
        else:
            try:
                parent_frame.winfo_toplevel().destroy()
            except Exception:
                pass
            import os
            os._exit(0)

    # Exit Button
    if app:
        exit_btn = tk.Button(tab_frame, text="EXIT", bg="#facc15", fg="black", font=("Segoe UI", 10, "bold"), relief="raised", borderwidth=2, width=12, height=1, pady=0, cursor="hand2", command=perform_app_exit)
        exit_btn.pack(side="right", padx=10, pady=2)

    # Status LED & Label
    status_frame = tk.Frame(tab_frame, bg="#333333")
    status_frame.pack(side="right", padx=20, pady=5)
    
    parent_frame.status_canvas = tk.Canvas(status_frame, width=16, height=16, bg="#333333", highlightthickness=0)
    parent_frame.status_canvas.pack(side="left")
    parent_frame.led = parent_frame.status_canvas.create_oval(2, 2, 14, 14, fill="#32cd32", outline="white")
    
    parent_frame.status_label = tk.Label(status_frame, text="Scope Connected", bg="#333333", fg="#32cd32", font=("Segoe UI", 10, "bold"))
    parent_frame.status_label.pack(side="left", padx=5)
    
    # Main content area wrapper for centering
    center_wrapper = tk.Frame(parent_frame, bg="#8c97a8")
    center_wrapper.grid(row=1, column=0, sticky="nsew")
    parent_frame.rowconfigure(1, weight=1)
    
    # The centered block (placed safely below the top logos using fixed y offset)
    main_frame = tk.Frame(center_wrapper, bg="#8c97a8")
    main_frame.place(relx=0.5, y=190, anchor="n")
    
    # Logo
    try:
        from PIL import Image, ImageTk
        import os
        # Loading from images folder to restore the original Carona Power logo
        img_path = os.path.join(BASE_DIR, "images", "carona_transparent.png")
        if os.path.exists(img_path):
            img = Image.open(img_path)
            img.thumbnail((390, 130)) # Resize to fit nicely (Increased by 30%)
            parent_frame.logo_img = ImageTk.PhotoImage(img)
            logo_label = tk.Label(center_wrapper, image=parent_frame.logo_img, bg="#8c97a8")
            logo_label.place(relx=0.02, rely=0.02, anchor="nw")
    except Exception as e:
        print(f"Error loading logo: {e}")
    
    # IAAS Logo
    try:
        iaas_img_path = os.path.join(BASE_DIR, "images", "iaas_logo.png")
        if os.path.exists(iaas_img_path):
            iaas_img = Image.open(iaas_img_path)
            iaas_img.thumbnail((450, 150)) # Resize to fit nicely (increased by 50%)
            parent_frame.iaas_logo_img = ImageTk.PhotoImage(iaas_img)
            iaas_logo_label = tk.Label(center_wrapper, image=parent_frame.iaas_logo_img, bg="#8c97a8")
            iaas_logo_label.place(relx=0.5, rely=0.02, anchor="n")
    except Exception as e:
        print(f"Error loading IAAS logo: {e}")

    # Removed Main title ("Setup") per request

    # Two-column layout
    content_frame = tk.Frame(main_frame, bg="#8c97a8")
    content_frame.pack(fill="both", expand=True, pady=0)
    content_frame.columnconfigure(0, weight=1, uniform="panels")
    content_frame.columnconfigure(1, weight=1, uniform="panels")

    # Left panel (Channels)
    left_panel = tk.Frame(content_frame, bg="#8c97a8")
    left_panel.grid(row=0, column=0, sticky="new", padx=(0, 25), pady=0)
    
    # Right panel (General settings)
    right_panel = tk.Frame(content_frame, bg="#8c97a8")
    right_panel.grid(row=0, column=1, sticky="new", padx=(25, 0), pady=0)
    
    # --- Right Panel Elements ---
    settings_frame = tk.Frame(right_panel, bg="#8c97a8", relief="groove", borderwidth=2)
    settings_frame.pack(fill="x", pady=0, padx=10)
    
    settings_inner = tk.Frame(settings_frame, bg="#8c97a8")
    settings_inner.pack(fill="both", expand=True, padx=20, pady=20)

    def validate_numeric(P):
        if P == "" or P == ".":
            return True
        try:
            float(P)
            if "." in P:
                parts = P.split(".")
                if len(parts) > 1 and len(parts[1]) > 2:
                    return False
            return True
        except ValueError:
            return False
            
    vcmd = (parent_frame.register(validate_numeric), '%P')
    
    def enforce_min_1(event):
        w = event.widget
        try:
            val = float(w.get())
            max_v = getattr(w, 'max_val', float('inf'))
            if val <= 0:
                if "." in w.get():
                    w.delete(0, "end")
                    w.insert(0, "1.0")
                else:
                    w.delete(0, "end")
                    w.insert(0, "1")
            elif val > max_v:
                is_float = "." in w.get()
                w.delete(0, "end")
                if is_float or max_v == float('inf'):
                    w.insert(0, str(float(max_v)))
                else:
                    w.insert(0, str(int(max_v)))
        except ValueError:
            w.delete(0, "end")
            w.insert(0, "1")

    def add_right_row(parent, label_text, widget_class, **kwargs):
        row = tk.Frame(parent, bg="#8c97a8")
        row.pack(fill="x", pady=12)
        tk.Label(row, text=label_text, bg="#8c97a8", fg="white", width=22, anchor="w", font=("Segoe UI", 10)).pack(side="left")
        w = widget_class(row, **kwargs)
        w.pack(side="right", fill="x", expand=True)
        parent_frame.input_widgets.append(w)
        return w

    cb_impulse = add_right_row(settings_inner, "Impulse Type", ttk.Combobox, values=["Lightning", "Switching", "Steep front", "Current"], state="readonly")
    cb_impulse.set(saved_config.get("Impulse Type", "Lightning"))
    
    cb_polarity = add_right_row(settings_inner, "Polarity", ttk.Combobox, values=["Negative", "Positive"], state="readonly")
    cb_polarity.set(saved_config.get("Polarity", "Negative"))
    cb_polarity.bind("<<ComboboxSelected>>", trigger_save, add="+")
    
    def make_spinbox(parent, label_text, default_val, max_val=float('inf')):
        row = tk.Frame(parent, bg="#8c97a8")
        row.pack(fill="x", pady=12)
        tk.Label(row, text=label_text, bg="#8c97a8", fg="white", width=22, anchor="w", font=("Segoe UI", 10)).pack(side="left")
        var = tk.StringVar(value=default_val)
        var.trace_add("write", trigger_save)
        w = tk.Spinbox(row, from_=0, to=max_val, increment=1, textvariable=var, font=("Segoe UI", 10), validate="key", validatecommand=vcmd)
        w.var = var
        w.max_val = max_val
        w.bind("<FocusOut>", enforce_min_1)
        w.pack(side="right", fill="x", expand=True)
        parent_frame.input_widgets.append(w)
        return w

    sb_volt = make_spinbox(settings_inner, "Expected Voltage [kV]", saved_config.get("Expected Voltage [kV]", "150.0"))
    sb_curr = make_spinbox(settings_inner, "Expected Current [A]", saved_config.get("Expected Current [A]", "300.0"))
    sb_shots = make_spinbox(settings_inner, "N° of Shots", saved_config.get("N° of Shots", "1"), max_val=10)
    
    window_time_options = [
        "2 ns", "4 ns", "10 ns", "20 ns", "40 ns", "100 ns", "200 ns", "400 ns",
        "1 us", "2 us", "4 us", "10 us", "20 us", "40 us", "100 us", "200 us", "400 us",
        "1 ms", "2 ms", "4 ms", "10 ms", "20 ms", "40 ms", "100 ms", "200 ms", "400 ms",
        "1 s", "2 s"
    ]
    cb_window = add_right_row(settings_inner, "Window Time", ttk.Combobox, values=window_time_options, state="readonly")
    cb_window.set(saved_config.get("Window Time", "100 us"))
    
    warning_row = tk.Frame(settings_inner, bg="#8c97a8")
    warning_row.pack(fill="x", pady=0)
    lbl_warning = tk.Label(warning_row, text="", bg="#8c97a8", fg="#ff4c4c", font=("Segoe UI", 9, "bold"), anchor="e")
    lbl_warning.pack(side="right")

    def update_window_options(*args):
        impulse = cb_impulse.get()
        if impulse in ["Lightning", "Current"]:
            options = ["4 us", "10 us", "20 us", "40 us", "100 us", "200 us", "400 us"]
            default = "100 us"
        elif impulse == "Switching":
            options = ["200 us", "400 us", "1 ms", "2 ms", "4 ms", "10 ms", "20 ms", "40 ms"]
            default = "4 ms"
        elif impulse == "Steep front":
            options = ["400 ns", "1 us", "2 us", "4 us", "10 us", "20 us"]
            default = "4 us"
        else:
            options = window_time_options
            default = "100 us"

        cb_window['values'] = options
        if cb_window.get() not in options:
            cb_window.set(default)
            
    # Call it initially to set correct options
    update_window_options()

    def validate_window_time(event=None):
        update_window_options()
        impulse_type = cb_impulse.get()
        time_str = cb_window.get()
        parts = time_str.split()
        if len(parts) == 2:
            val = float(parts[0])
            unit = parts[1]
            if unit == "ns": us_val = val * 0.001
            elif unit == "us": us_val = val
            elif unit == "ms": us_val = val * 1000.0
            elif unit == "s": us_val = val * 1000000.0
            else: us_val = val
        else:
            us_val = 0
            
        valid = True
        msg = ""
        if impulse_type == "Lightning":
            if us_val < 4 or us_val > 400:
                valid, msg = False, "Warning: Valid range is 4 us to 400 us"
        elif impulse_type == "Switching":
            if us_val < 200 or us_val > 40000:
                valid, msg = False, "Warning: Valid range is 200 us to 40 ms"
        elif impulse_type == "Steep front":
            if us_val < 0.4 or us_val > 20:
                valid, msg = False, "Warning: Valid range is 400 ns to 20 us"
        elif impulse_type == "Current":
            if us_val < 4 or us_val > 400:
                valid, msg = False, "Warning: Valid range is 4 us to 400 us"
                
        if not valid:
            lbl_warning.config(text=msg)
        else:
            lbl_warning.config(text="")
            
        if event:
            trigger_save()

    cb_window.bind("<<ComboboxSelected>>", validate_window_time, add="+")
    cb_impulse.bind("<<ComboboxSelected>>", validate_window_time, add="+")
    validate_window_time()
    
    def on_enter_click():
        from tkinter import messagebox
        impulse_type = cb_impulse.get()
        time_str = cb_window.get()
        
        parts = time_str.split()
        if len(parts) == 2:
            val = float(parts[0])
            unit = parts[1]
            if unit == "ns": us_val = val * 0.001
            elif unit == "us": us_val = val
            elif unit == "ms": us_val = val * 1000.0
            elif unit == "s": us_val = val * 1000000.0
            else: us_val = val
        else:
            us_val = 0
            
        valid = True
        msg = ""
        if impulse_type == "Lightning":
            if us_val < 4 or us_val > 400:
                valid, msg = False, "Window Time incompatible with Lightning impulse.\nPlease select a value between 4 us and 400 us."
        elif impulse_type == "Switching":
            if us_val < 200 or us_val > 40000:
                valid, msg = False, "Window Time incompatible with Switching impulse.\nPlease select a value between 200 us and 40 ms."
        elif impulse_type == "Steep front":
            if us_val < 0.4 or us_val > 20:
                valid, msg = False, "Window Time incompatible with Steep front impulse.\nPlease select a value between 400 ns and 20 us."
        elif impulse_type == "Current":
            if us_val < 4 or us_val > 400:
                valid, msg = False, "Window Time incompatible with Current impulse.\nPlease select a value between 4 us and 400 us."
                
        if not valid:
            messagebox.showinfo(f"{impulse_type}: Incompatible Window Time", msg)
            return
            
        save_dict = {
            "Impulse Type": impulse_type,
            "Polarity": cb_polarity.get(),
            "Expected Voltage [kV]": sb_volt.get(),
            "Expected Current [A]": sb_curr.get(),
            "N° of Shots": sb_shots.get(),
            "Window Time": time_str
        }
            
        if app:
            if not hasattr(app, 'config'):
                app.config = {}
                
            app.config['impulse_type'] = impulse_type
            app.config['polarity'] = cb_polarity.get()
            app.config['time_str'] = time_str
            app.config['Expected Voltage [kV]'] = sb_volt.get()
            app.config['Expected Current [A]'] = sb_curr.get()
            app.config['N° of Shots'] = sb_shots.get()
            
            # Save Channel 1
            c1 = parent_frame.channels_info[0]
            app.config['ch1_active'] = (c1['btn']["text"] == "Active")
            app.config['ch1_type'] = c1['type_cb'].get()
            app.config['ch1_int'] = c1['int_att'].get()
            app.config['ch1_ext'] = c1['ext_att'].get()
            
            # Save Channel 2
            c2 = parent_frame.channels_info[1]
            app.config['ch2_active'] = (c2['btn']["text"] == "Active")
            app.config['ch2_type'] = c2['type_cb'].get()
            app.config['ch2_int'] = c2['int_att'].get()
            app.config['ch2_ext'] = c2['ext_att'].get()
            
            save_dict["ch1_active"] = app.config['ch1_active']
            save_dict["ch1_type"] = app.config['ch1_type']
            save_dict["ch1_int"] = app.config['ch1_int']
            save_dict["ch1_ext"] = app.config['ch1_ext']
            
            save_dict["ch2_active"] = app.config['ch2_active']
            save_dict["ch2_type"] = app.config['ch2_type']
            save_dict["ch2_int"] = app.config['ch2_int']
            save_dict["ch2_ext"] = app.config['ch2_ext']
            
            t_path = getattr(app, 'config', {}).get('test_path') or saved_config.get('test_path', os.path.join(BASE_DIR, 'Capture Data'))
            if hasattr(app, 'config'):
                app.config['test_path'] = t_path
            save_dict['test_path'] = t_path
            
            save_config(save_dict)
            
            parent_frame.is_acquiring = True
            if hasattr(parent_frame, 'enter_btn'):
                parent_frame.enter_btn.config(state="disabled", bg="#555555")
            
            def show_niscope_dialog():
                ni_dialog = tk.Toplevel(parent_frame)
                ni_dialog.overrideredirect(True)
                ni_dialog.configure(bg="#8c97a8")
                
                box = tk.Frame(ni_dialog, bg="#8c97a8", bd=2, relief="groove")
                box.pack(fill="both", expand=True, padx=2, pady=2)
                
                top_row = tk.Frame(box, bg="#8c97a8")
                top_row.pack(fill="both", expand=True, padx=12, pady=(10, 4))
                
                left_f = tk.Frame(top_row, bg="#8c97a8", width=90)
                left_f.pack(side="left", fill="y", padx=(0, 10))
                left_f.pack_propagate(False)
                
                hg_path = os.path.join(BASE_DIR, "images", "hourglass_exact.png")
                if os.path.exists(hg_path):
                    try:
                        from PIL import Image, ImageTk
                        img = Image.open(hg_path)
                        img = img.resize((50, 65), Image.Resampling.LANCZOS)
                        ni_dialog.img_tk = ImageTk.PhotoImage(img)
                        lbl_img = tk.Label(left_f, image=ni_dialog.img_tk, bg="#8c97a8")
                        lbl_img.pack(side="top", pady=(4, 2))
                    except Exception as e:
                        print("Error loading hourglass image:", e)
                        
                lbl_niscope = tk.Label(left_f, text="NI-SCOPE", font=("Segoe UI", 8, "bold italic"), bg="#8c97a8", fg="black")
                lbl_niscope.pack(side="top")
                
                sunken_panel = tk.Frame(top_row, bg="#8590a1", bd=2, relief="sunken")
                sunken_panel.pack(side="right", fill="both", expand=True)
                
                ch1_v = save_dict.get("Expected Voltage [kV]", "100")
                ch1_t = save_dict.get("ch1_type", "Voltage")
                ch1_u = "kV" if ch1_t == "Voltage" else "A"
                
                ch2_c = save_dict.get("Expected Current [A]", "300")
                ch2_t = save_dict.get("ch2_type", "Current")
                ch2_u = "A" if ch2_t == "Current" else "kV"
                
                pol = save_dict.get("Polarity", "Negative")
                
                tk.Label(sunken_panel, text=f"CH1: {ch1_v} {ch1_u}", font=("Segoe UI", 9, "bold"), fg="white", bg="#8590a1").pack(pady=(6, 1))
                tk.Label(sunken_panel, text=f"CH2: {ch2_c} {ch2_u}", font=("Segoe UI", 9, "bold"), fg="white", bg="#8590a1").pack(pady=1)
                tk.Label(sunken_panel, text=f"Polarity: {pol}", font=("Segoe UI", 9, "bold"), fg="white", bg="#8590a1").pack(pady=1)
                
                lbl_status = tk.Label(sunken_panel, text="Waiting Waves......", font=("Segoe UI", 9, "bold"), fg="white", bg="#8590a1")
                lbl_status.pack(pady=(1, 4))
                
                prog_bar = ttk.Progressbar(sunken_panel, orient="horizontal", length=220, mode="determinate", maximum=100)
                
                bot_row = tk.Frame(box, bg="#8c97a8")
                bot_row.pack(fill="x", side="bottom", pady=(0, 6))
                
                lbl_abort = tk.Label(bot_row, text="Double Click to Abort Acquisition", font=("Segoe UI", 9, "bold"), fg="#ffff00", bg="#8c97a8")
                lbl_abort.pack(anchor="center")
                
                # Position centered on main screen
                nw, nh = 480, 175
                sw = parent_frame.winfo_screenwidth()
                sh = parent_frame.winfo_screenheight()
                nx = (sw - nw) // 2
                ny = (sh - nh) // 2
                ni_dialog.geometry(f"{nw}x{nh}+{nx}+{ny}")
                ni_dialog.attributes("-topmost", True)
                ni_dialog.lift()
                ni_dialog.focus_force()
                try:
                    ni_dialog.grab_set()
                except Exception:
                    pass
                
                # Double click abort handler
                last_click_time = [0.0]
                def abort_acquisition(event=None):
                    parent_frame.is_acquiring = False
                    if hasattr(ni_dialog, 'poll_job') and ni_dialog.poll_job:
                        parent_frame.after_cancel(ni_dialog.poll_job)
                        ni_dialog.poll_job = None
                    if hasattr(ni_dialog, 'prog_job') and ni_dialog.prog_job:
                        parent_frame.after_cancel(ni_dialog.prog_job)
                        ni_dialog.prog_job = None
                    if not is_demo and app and getattr(app, 'chandle', None):
                        try:
                            scope_m = read_control_info().get('Scope', 'ps5000a')
                            ps_stop = PicoScopeProxy(scope_m)
                            ps_stop.ps5000aStop(app.chandle)
                        except Exception:
                            pass
                    try:
                        ni_dialog.grab_release()
                    except Exception:
                        pass
                    try:
                        ni_dialog.destroy()
                    except:
                        pass
                    if hasattr(parent_frame, 'enter_btn'):
                        parent_frame.enter_btn.config(state="normal", bg="#32cd32", text="ENTER")
                    print("[NI-SCOPE] Acquisition aborted by user.")
                    
                def on_single_click(event=None):
                    import time
                    now = time.time()
                    if now - last_click_time[0] < 0.45:
                        abort_acquisition(event)
                    last_click_time[0] = now
                    
                def bind_recursive_abort(widget):
                    widget.bind("<Double-Button-1>", abort_acquisition)
                    widget.bind("<Button-1>", on_single_click, add="+")
                    for child in widget.winfo_children():
                        bind_recursive_abort(child)
                        
                bind_recursive_abort(ni_dialog)
                
                # Waveform arrival transition handler
                def on_wave_arrived():
                    parent_frame.is_acquiring = False
                    try:
                        ni_dialog.grab_release()
                    except Exception:
                        pass
                    try:
                        ni_dialog.destroy()
                    except:
                        pass
                    if hasattr(parent_frame, 'enter_btn'):
                        parent_frame.enter_btn.config(state="normal", bg="#32cd32", text="ENTER")
                    if hasattr(parent_frame, 'setup_poll_job') and parent_frame.setup_poll_job:
                        parent_frame.after_cancel(parent_frame.setup_poll_job)
                        parent_frame.setup_poll_job = None
                    if app and hasattr(app, 'show_waveform_screen'):
                        app.show_waveform_screen()

                # Progress bar animation (0% -> 100%)
                def animate_progress(val=0):
                    if not ni_dialog.winfo_exists():
                        return
                    if val <= 100:
                        prog_bar['value'] = val
                        ni_dialog.prog_job = parent_frame.after(15, lambda: animate_progress(val + 4))
                    else:
                        ni_dialog.prog_job = parent_frame.after(100, on_wave_arrived)

                def on_wave_captured():
                    if not ni_dialog.winfo_exists():
                        return
                    if hasattr(ni_dialog, 'poll_job') and ni_dialog.poll_job:
                        parent_frame.after_cancel(ni_dialog.poll_job)
                        ni_dialog.poll_job = None
                    lbl_status.config(text="Waveform Captured", fg="#32cd32")
                    prog_bar.pack(pady=(2, 6))
                    animate_progress(0)

                # Polling for waveform trigger: does NOT navigate until wave is actually captured
                from waveform_hw import init_scope, run_hardware_block, is_hardware_ready, fetch_hardware_data
                from waveform_utils import parse_time_to_ns, get_voltage_range_enum, calc_tb
                
                is_demo = getattr(app, 'is_demo_mode', False) if app else True
                
                # If physical hardware is connected, arm the hardware block!
                if not is_demo and app and getattr(app, 'is_scope_connected', False):
                    try:
                        if getattr(app, 'chandle', None) is None:
                            init_scope(app, app.config)
                            
                        time_str = save_dict.get("Window Time", "100 us")
                        total_time_ns = parse_time_to_ns(time_str)
                        timebase, noSamples = calc_tb(total_time_ns)
                        
                        ch1_att = float(save_dict.get('ch1_int', 1)) * float(save_dict.get('ch1_ext', 1))
                        ch2_att = float(save_dict.get('ch2_int', 1)) * float(save_dict.get('ch2_ext', 1))
                        exp_v1 = float(save_dict.get('Expected Voltage [kV]', 100)) * 1000.0 if save_dict.get('ch1_type') == 'Voltage' else float(save_dict.get('Expected Current [A]', 300))
                        exp_v2 = float(save_dict.get('Expected Voltage [kV]', 100)) * 1000.0 if save_dict.get('ch2_type') == 'Voltage' else float(save_dict.get('Expected Current [A]', 300))
                        
                        max_mv_A = abs((exp_v1 / ch1_att if ch1_att != 0 else exp_v1) * 1000.0)
                        max_mv_B = abs((exp_v2 / ch2_att if ch2_att != 0 else exp_v2) * 1000.0)
                        
                        range_enum_A = get_voltage_range_enum(max(1000, max_mv_A * 1.2))
                        range_enum_B = get_voltage_range_enum(max(1000, max_mv_B * 1.2))
                        
                        app.capture_state = "WAITING"
                        armed = run_hardware_block(
                            app, app.config, total_time_ns, max_mv_A, max_mv_B, time_str,
                            range_enum_A, range_enum_B, timebase, noSamples, "14 bits"
                        )
                        print(f"[NI-SCOPE] Hardware block armed: {armed}")
                    except Exception as e:
                        print(f"[NI-SCOPE] Hardware arm error: {e}")

                poll_count = [0]
                def poll_trigger():
                    if not ni_dialog.winfo_exists():
                        return
                    
                    poll_count[0] += 1
                    if is_demo:
                        # In demo mode, simulate waiting for trigger pulse (3000ms)
                        if poll_count[0] >= 60: # ~1800ms
                            print("[NI-SCOPE] Simulated trigger fired!")
                            on_wave_captured()
                            return
                    else:
                        # Real physical scope: wait for hardware trigger to fire
                        if poll_count[0] % 30 == 0:
                            print("[NI-SCOPE] Scope armed and waiting for trigger...")
                        if is_hardware_ready(app):
                            print("[NI-SCOPE] Hardware trigger detected! Capturing waveform...")
                            try:
                                if app and hasattr(app, 'config'):
                                    app.prefetched_data = fetch_hardware_data(app, app.config)
                            except Exception as e:
                                print(f"[NI-SCOPE] Fetch error: {e}")
                            on_wave_captured()
                            return
                        # Strict hardware trigger only: NO blind timeout capture!
                            
                    ni_dialog.poll_job = parent_frame.after(30, poll_trigger)

                ni_dialog.poll_job = parent_frame.after(30, poll_trigger)
                
                # Universal Force Trigger: Pressing Space, Enter, or Right-Click immediately captures
                def force_trigger(event=None):
                    print("[NI-SCOPE] Force trigger requested by user!")
                    if not is_demo and app and getattr(app, 'chandle', None):
                        try:
                            scope_m = read_control_info().get('Scope', 'ps5000a')
                            ps = PicoScopeProxy(scope_m)
                            ps.ps5000aStop(app.chandle)
                            app.prefetched_data = fetch_hardware_data(app, app.config)
                        except Exception as e:
                            print(f"[NI-SCOPE] Force fetch: {e}")
                    on_wave_captured()

                ni_dialog.bind("<space>", force_trigger)
                ni_dialog.bind("<Return>", force_trigger)
                ni_dialog.focus_set()

            def show_winding_dialog():
                win_dlg = tk.Toplevel(parent_frame)
                win_dlg.overrideredirect(True)
                win_dlg.configure(bg="#8c97a8")
                win_dlg.attributes("-topmost", True)
                
                box = tk.Frame(win_dlg, bg="#8c97a8", bd=2, relief="groove")
                box.pack(fill="both", expand=True, padx=2, pady=2)
                
                f_inputs = tk.Frame(box, bg="#8c97a8")
                f_inputs.pack(fill="x", padx=12, pady=(10, 4))
                
                tk.Label(f_inputs, text="Winding Definition", font=("Segoe UI", 9, "bold"), bg="#8c97a8", fg="#1e293b").grid(row=0, column=0, sticky="w", pady=4)
                e_wind = tk.Entry(f_inputs, font=("Segoe UI", 9), bg="#cbd5e1", fg="#1e293b", bd=2, relief="sunken", width=18)
                e_wind.grid(row=0, column=1, sticky="e", padx=(12, 0), pady=4)
                e_wind.insert(0, saved_config.get("winding_definition", ""))
                
                tk.Label(f_inputs, text="Phase", font=("Segoe UI", 9, "bold"), bg="#8c97a8", fg="#1e293b").grid(row=1, column=0, sticky="w", pady=4)
                e_phase = tk.Entry(f_inputs, font=("Segoe UI", 9), bg="#cbd5e1", fg="#1e293b", bd=2, relief="sunken", width=18)
                e_phase.grid(row=1, column=1, sticky="e", padx=(12, 0), pady=4)
                e_phase.insert(0, saved_config.get("phase", ""))
                
                tk.Label(f_inputs, text="Tap Changer Pos", font=("Segoe UI", 9, "bold"), bg="#8c97a8", fg="#1e293b").grid(row=2, column=0, sticky="w", pady=4)
                e_tap = tk.Entry(f_inputs, font=("Segoe UI", 9), bg="#cbd5e1", fg="#1e293b", bd=2, relief="sunken", width=18)
                e_tap.grid(row=2, column=1, sticky="e", padx=(12, 0), pady=4)
                e_tap.insert(0, saved_config.get("tap_changer_pos", ""))
                
                div = tk.Frame(box, height=2, bd=1, relief="groove", bg="#8c97a8")
                div.pack(fill="x", padx=8, pady=(4, 6))
                
                def do_winding_ok():
                    w_val = e_wind.get().strip()
                    p_val = e_phase.get().strip()
                    t_val = e_tap.get().strip()
                    
                    saved_config["winding_definition"] = w_val
                    saved_config["phase"] = p_val
                    saved_config["tap_changer_pos"] = t_val
                    save_dict["winding_definition"] = w_val
                    save_dict["phase"] = p_val
                    save_dict["tap_changer_pos"] = t_val
                    
                    if app and hasattr(app, 'config'):
                        app.config["winding_definition"] = w_val
                        app.config["phase"] = p_val
                        app.config["tap_changer_pos"] = t_val
                        
                    save_config(saved_config)
                    try:
                        win_dlg.grab_release()
                    except Exception:
                        pass
                    win_dlg.destroy()
                    show_niscope_dialog()
                    
                def cancel_winding(event=None):
                    parent_frame.is_acquiring = False
                    try:
                        win_dlg.grab_release()
                    except Exception:
                        pass
                    try:
                        win_dlg.destroy()
                    except:
                        pass
                    if hasattr(parent_frame, 'enter_btn'):
                        parent_frame.enter_btn.config(state="normal", bg="#32cd32", text="ENTER")
                        
                win_dlg.bind("<Escape>", cancel_winding)
                
                btn_row = tk.Frame(box, bg="#8c97a8")
                btn_row.pack(fill="x", padx=10, pady=(0, 6))
                btn_ok = tk.Button(btn_row, text="Ok", bg="#32cd32", fg="black", font=("Segoe UI", 9, "bold"), relief="raised", bd=2, width=8, cursor="hand2", command=do_winding_ok)
                btn_ok.pack(side="right")
                
                # Position beside enter button
                dw, dh = 310, 150
                bx = enter_btn.winfo_rootx()
                by = enter_btn.winfo_rooty()
                bw = enter_btn.winfo_width()
                bh = enter_btn.winfo_height()
                
                x = bx - dw - 10
                y = by + bh - dh
                if x < 10:
                    x = bx + bw + 10
                if y < 10:
                    y = 10
                    
                win_dlg.geometry(f"{dw}x{dh}+{x}+{y}")
                win_dlg.lift()
                win_dlg.focus_force()
                try:
                    win_dlg.grab_set()
                except Exception:
                    pass
                e_wind.focus_set()

            if hasattr(parent_frame, 'enter_btn'):
                parent_frame.enter_btn.config(state="disabled")
                
            show_winding_dialog()
            
    def open_test_path_dialog():
        from tkinter import filedialog, simpledialog, messagebox
        
        default_dir = saved_config.get("test_path", os.path.join(BASE_DIR, "Capture Data"))
        os.makedirs(default_dir, exist_ok=True)
        
        dialog = tk.Toplevel(parent_frame)
        dialog.title("Configure Test Path")
        dialog.geometry("480x160")
        dialog.configure(bg="#8c97a8")
        dialog.resizable(False, False)
        dialog.transient(parent_frame.winfo_toplevel())
        dialog.grab_set()
        
        try:
            dialog.update_idletasks()
            pw = parent_frame.winfo_toplevel()
            x = pw.winfo_rootx() + (pw.winfo_width() - 480) // 2
            y = pw.winfo_rooty() + (pw.winfo_height() - 160) // 2
            dialog.geometry(f"+{x}+{y}")
        except:
            pass
            
        box = tk.Frame(dialog, bg="#8c97a8", bd=2, relief="groove")
        box.pack(fill="both", expand=True, padx=8, pady=8)
        
        tk.Label(box, text="Configure Test Path", bg="#8c97a8", fg="#1e293b",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(8, 4))
                 
        entry_frame = tk.Frame(box, bg="#adb4ce", bd=2, relief="sunken")
        entry_frame.pack(fill="x", padx=10, pady=(2, 12))
        
        path_var = tk.StringVar(value=default_dir)
        path_entry = tk.Entry(entry_frame, textvariable=path_var, font=("Segoe UI", 9),
                              bg="#adb4ce", fg="#1e293b", relief="flat", bd=0)
        path_entry.pack(side="left", fill="x", expand=True, padx=6, pady=4)
        
        def do_new():
            parent_dir = path_var.get().strip()
            if not os.path.exists(parent_dir):
                parent_dir = os.getcwd()
            name = simpledialog.askstring("New Folder", "Enter new test folder name:", parent=dialog)
            if name:
                new_folder = os.path.join(parent_dir, name.strip())
                try:
                    os.makedirs(new_folder, exist_ok=True)
                    path_var.set(os.path.normpath(new_folder))
                except Exception as e:
                    messagebox.showerror("Error", f"Could not create folder: {e}", parent=dialog)
                    
        def do_choose():
            cur = path_var.get().strip()
            initial = cur if os.path.exists(cur) else os.getcwd()
            selected = filedialog.askdirectory(title="Choose Test Path", initialdir=initial, parent=dialog)
            if selected:
                path_var.set(os.path.normpath(selected))
                
        def do_ok():
            chosen = path_var.get().strip()
            if chosen:
                os.makedirs(chosen, exist_ok=True)
                saved_config["test_path"] = chosen
                save_config(saved_config)
                if app and hasattr(app, 'config'):
                    app.config['test_path'] = chosen
            dialog.destroy()
            
        btn_row = tk.Frame(box, bg="#8c97a8")
        btn_row.pack(side="bottom", pady=(0, 10))
        
        btn_new = tk.Button(btn_row, text="New", bg="#e53935", fg="black", font=("Segoe UI", 9, "bold"),
                            relief="raised", bd=2, width=8, cursor="hand2", command=do_new)
        btn_new.pack(side="left", padx=6)
        
        btn_choose = tk.Button(btn_row, text="Choose", bg="#facc15", fg="black", font=("Segoe UI", 9, "bold"),
                               relief="raised", bd=2, width=8, cursor="hand2", command=do_choose)
        btn_choose.pack(side="left", padx=6)
        
        btn_ok = tk.Button(btn_row, text="Ok", bg="#32cd32", fg="black", font=("Segoe UI", 9, "bold"),
                           relief="raised", bd=2, width=8, cursor="hand2", command=do_ok)
        btn_ok.pack(side="left", padx=6)

    test_path_btn = tk.Button(right_panel, text="Test Path", bg="#d1d5db", fg="black", font=("Segoe UI", 10, "bold"), relief="raised", borderwidth=2, width=12, height=1, pady=0, cursor="hand2", command=open_test_path_dialog)
    test_path_btn.pack(pady=(10, 5), padx=10, anchor="e")
    parent_frame.test_path_btn = test_path_btn
    parent_frame.input_widgets.append(test_path_btn)

    enter_btn = tk.Button(right_panel, text="ENTER", bg="#32cd32", fg="black", font=("Segoe UI", 10, "bold"), relief="raised", borderwidth=2, width=12, height=1, pady=0, cursor="hand2", command=on_enter_click)
    enter_btn.pack(pady=(0, 0), padx=10, anchor="e")
    parent_frame.enter_btn = enter_btn

    # --- Left Panel Elements (Channels) ---
    channels_frame = tk.Frame(left_panel, bg="#8c97a8", relief="groove", borderwidth=2)
    channels_frame.pack(fill="x", pady=0, padx=10)
    channels_frame.columnconfigure(0, weight=1)
    channels_frame.columnconfigure(1, weight=1)
    
    parent_frame.ch_buttons = []
    parent_frame.channels_info = []
    def create_channel(parent, col, title, default_active, default_type, default_int, default_ext):
        ch_frame = tk.LabelFrame(parent, text=title, bg="#8c97a8", fg="white", font=("Segoe UI", 10))
        ch_frame.grid(row=0, column=col, sticky="nsew", padx=20, pady=20)
        
        btn_frame = tk.Frame(ch_frame, bg="#8c97a8")
        btn_frame.pack(pady=10)
        
        def toggle_active():
            if btn["text"] == "Active":
                btn.config(text="Inactive", bg="#555555") 
            else:
                btn.config(text="Active", bg="#32cd32")
                
            if hasattr(parent_frame, 'enter_btn'):
                any_active = any(b["text"] == "Active" for b in parent_frame.ch_buttons)
                if any_active:
                    parent_frame.enter_btn.config(state="normal", bg="#32cd32")
                else:
                    parent_frame.enter_btn.config(state="disabled", bg="#555555")
            
            trigger_save()
                
        btn = tk.Button(btn_frame, text="Active" if default_active else "Inactive", bg="#32cd32" if default_active else "#555555", fg="black", font=("Segoe UI", 10, "bold"), relief="raised", borderwidth=2, width=12, height=1, pady=0, cursor="hand2", command=toggle_active)
        btn.pack()
        parent_frame.ch_buttons.append(btn)
        parent_frame.input_widgets.append(btn)
        
        row1 = tk.Frame(ch_frame, bg="#8c97a8")
        row1.pack(fill="x", pady=8, padx=10)
        tk.Label(row1, text="Type", bg="#8c97a8", fg="white", width=10, anchor="w", font=("Segoe UI", 9)).pack(side="left")
        cb = ttk.Combobox(row1, values=["Voltage", "Current"], width=12, state="readonly")
        cb.set(default_type)
        cb.bind("<<ComboboxSelected>>", trigger_save, add="+")
        cb.pack(side="right")
        parent_frame.input_widgets.append(cb)
        
        row2 = tk.Frame(ch_frame, bg="#8c97a8")
        row2.pack(fill="x", pady=8, padx=10)
        tk.Label(row2, text="Internal Att.", bg="#8c97a8", fg="white", width=10, anchor="w", font=("Segoe UI", 9)).pack(side="left")
        var_int = tk.StringVar(value=default_int)
        var_int.trace_add("write", trigger_save)
        sp1 = tk.Spinbox(row2, from_=0, to=float('inf'), textvariable=var_int, width=13, validate="key", validatecommand=vcmd)
        sp1.var = var_int
        sp1.bind("<FocusOut>", enforce_min_1)
        sp1.pack(side="right")
        parent_frame.input_widgets.append(sp1)
        
        row3 = tk.Frame(ch_frame, bg="#8c97a8")
        row3.pack(fill="x", pady=8, padx=10)
        tk.Label(row3, text="External Att.", bg="#8c97a8", fg="white", width=10, anchor="w", font=("Segoe UI", 9)).pack(side="left")
        var_ext = tk.StringVar(value=default_ext)
        var_ext.trace_add("write", trigger_save)
        sp2 = tk.Spinbox(row3, from_=0, to=float('inf'), textvariable=var_ext, width=13, validate="key", validatecommand=vcmd)
        sp2.var = var_ext
        sp2.bind("<FocusOut>", enforce_min_1)
        sp2.pack(side="right")
        parent_frame.input_widgets.append(sp2)
        
        parent_frame.channels_info.append({
            "btn": btn,
            "type_cb": cb,
            "int_att": sp1,
            "ext_att": sp2
        })

    c1_active = saved_config.get("ch1_active", True)
    c1_type = saved_config.get("ch1_type", "Voltage")
    c1_int = saved_config.get("ch1_int", "200.0")
    c1_ext = saved_config.get("ch1_ext", "557.0")
    create_channel(channels_frame, 0, "Channel 1", c1_active, c1_type, c1_int, c1_ext)

    c2_active = saved_config.get("ch2_active", False)
    c2_type = saved_config.get("ch2_type", "Current")
    c2_int = saved_config.get("ch2_int", "200.0")
    c2_ext = saved_config.get("ch2_ext", "10.0")
    create_channel(channels_frame, 1, "Channel 2", c2_active, c2_type, c2_int, c2_ext)
    
    def poll_hardware_setup():
        if getattr(parent_frame, 'is_acquiring', False):
            if hasattr(parent_frame, 'winfo_exists') and parent_frame.winfo_exists():
                parent_frame.setup_poll_job = parent_frame.after(1500, poll_hardware_setup)
            return
        if app and not getattr(app, 'is_demo_mode', False):
            try:
                conn = app.try_connect_scope()
                if conn != app.is_scope_connected:
                    app.is_scope_connected = conn
                    update_status(parent_frame, conn)
            except Exception:
                pass
        if hasattr(parent_frame, 'winfo_exists') and parent_frame.winfo_exists():
            parent_frame.setup_poll_job = parent_frame.after(1500, poll_hardware_setup)
            
    poll_hardware_setup()

def update_status(parent_frame, is_connected):
    if getattr(parent_frame, 'is_acquiring', False): return
    if not hasattr(parent_frame, 'status_canvas'): return
    if is_connected:
        parent_frame.status_canvas.itemconfig(parent_frame.led, fill="#32cd32")
        parent_frame.status_label.config(text="Scope Connected", fg="#32cd32")
        state = "normal"
    else:
        parent_frame.status_canvas.itemconfig(parent_frame.led, fill="#ff4c4c")
        parent_frame.status_label.config(text="Scope Disconnected", fg="#ff4c4c")
        state = "disabled"
        
    for w in parent_frame.input_widgets:
        try:
            from tkinter import ttk
            if hasattr(w, 'winfo_exists') and w.winfo_exists():
                if isinstance(w, ttk.Combobox):
                    w.config(state="readonly" if is_connected else "disabled")
                else:
                    w.config(state="normal" if is_connected else "disabled")
        except Exception:
            pass
            
    if is_connected and hasattr(parent_frame, 'enter_btn') and hasattr(parent_frame, 'ch_buttons'):
        try:
            any_active = any(b.winfo_exists() and b["text"] == "Active" for b in parent_frame.ch_buttons)
            if not any_active:
                if hasattr(parent_frame.enter_btn, 'winfo_exists') and parent_frame.enter_btn.winfo_exists():
                    parent_frame.enter_btn.config(state="disabled", bg="#555555")
        except: pass

def show_empty_tab_page(parent_frame, app, active_tab):
    if active_tab == "View":
        if hasattr(app, 'show_waveform_screen'):
            app.show_waveform_screen()
        else:
            import waveform
            waveform.build_waveform_ui(parent_frame, app)
        return

    if active_tab == "Review":
        import review
        review.build_review_ui(parent_frame, app)
        return

    for widget in parent_frame.winfo_children():
        widget.destroy()

    bg_color = "#8c97a8"
    parent_frame.configure(bg=bg_color)
    
    import tkinter as tk
    tab_frame = tk.Frame(parent_frame, bg="#333333")
    tab_frame.pack(side="top", fill="x")
    
    def go_setup(e):
        build_setup_ui(parent_frame, app)
        update_status(parent_frame, getattr(app, 'is_scope_connected', False))

    def go_tab(t_name):
        show_empty_tab_page(parent_frame, app, t_name)

    tabs = ["Setup", "View", "Review", "Analysis"]
    for t in tabs:
        if t == active_tab:
            lbl = tk.Label(tab_frame, text=t, bg="#e53935", fg="white", width=10, font=("Segoe UI", 10, "bold"), pady=5)
        else:
            lbl = tk.Label(tab_frame, text=t, bg="#555555", fg="white", width=10, font=("Segoe UI", 10), pady=5, cursor="hand2")
            if t == "Setup":
                lbl.bind("<Button-1>", go_setup)
            else:
                lbl.bind("<Button-1>", lambda e, name=t: go_tab(name))
        lbl.pack(side="left", padx=1 if t != "Setup" else 0)

    # Status LED & Label
    status_frame = tk.Frame(tab_frame, bg="#333333")
    status_frame.pack(side="right", padx=10)
    
    is_conn = getattr(app, 'is_scope_connected', False)
    status_text = "Scope Connected" if is_conn else "Scope Disconnected"
    status_color = "#32cd32" if is_conn else "#ff4c4c"
    tk.Label(status_frame, text=status_text, bg="#333333", fg=status_color, font=("Segoe UI", 10, "bold")).pack(side="left", padx=5)

    # Empty content area with one wave
    content = tk.Frame(parent_frame, bg=bg_color)
    content.pack(fill="both", expand=True, padx=20, pady=20)
    
    tk.Label(content, text=f"{active_tab} Module (Placeholder)", bg=bg_color, fg="white", font=("Segoe UI", 16, "bold")).pack(pady=(0, 10))
    
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import numpy as np

    fig = Figure(figsize=(8, 4), facecolor="#1e1e1e")
    ax = fig.add_subplot(111)
    ax.set_facecolor("#000000")
    ax.tick_params(colors="white")
    for spine in ax.spines.values():
        spine.set_color("white")
    
    t = np.linspace(0, 10, 100)
    y = np.sin(t)
    ax.plot(t, y, color="#32cd32", linewidth=2)
    ax.set_title("Sample Wave", color="white")
    ax.grid(True, color="#555555", linestyle="--")

    canvas = FigureCanvasTkAgg(fig, master=content)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)
