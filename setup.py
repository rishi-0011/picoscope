import tkinter as tk
from tkinter import ttk
import json
import os

CONFIG_FILE = r"c:\Users\MaharshiM\Music\Picoscope\setup_config.json"

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
    
    # Status LED & Label
    status_frame = tk.Frame(tab_frame, bg="#333333")
    status_frame.place(relx=0.8, rely=0.5, anchor="center")
    
    parent_frame.status_canvas = tk.Canvas(status_frame, width=16, height=16, bg="#333333", highlightthickness=0)
    parent_frame.status_canvas.pack(side="left")
    parent_frame.led = parent_frame.status_canvas.create_oval(2, 2, 14, 14, fill="#32cd32", outline="white")
    
    parent_frame.status_label = tk.Label(status_frame, text="Scope Connected", bg="#333333", fg="#32cd32", font=("Segoe UI", 10, "bold"))
    parent_frame.status_label.pack(side="left", padx=5)
    
    # Exit Button
    if app:
        exit_btn = tk.Button(tab_frame, text="EXIT", bg="#facc15", fg="black", font=("Segoe UI", 10, "bold"), relief="raised", borderwidth=2, width=12, height=1, pady=0, cursor="hand2", command=app.root.quit)
        exit_btn.pack(side="right", padx=10, pady=2)
    
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
        img_path = r"c:\Users\MaharshiM\Music\Picoscope\images\extracted_logo.png"
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
        iaas_img_path = r"c:\Users\MaharshiM\Music\Picoscope\extracted_logo.png"
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
            
            save_config(save_dict)
            
            if hasattr(app, 'show_waveform_screen'):
                app.show_waveform_screen()
            
    enter_btn = tk.Button(right_panel, text="ENTER", bg="#32cd32", fg="black", font=("Segoe UI", 10, "bold"), relief="raised", borderwidth=2, width=12, height=1, pady=0, cursor="hand2", command=on_enter_click)
    enter_btn.pack(pady=(10, 0), padx=10, anchor="e")
    parent_frame.enter_btn = enter_btn
    parent_frame.input_widgets.append(enter_btn)

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

def update_status(parent_frame, is_connected):
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
            if isinstance(w, ttk.Combobox):
                w.config(state="readonly" if is_connected else "disabled")
            else:
                w.config(state="normal" if is_connected else "disabled")
        except Exception:
            pass
            
    if is_connected and hasattr(parent_frame, 'enter_btn') and hasattr(parent_frame, 'ch_buttons'):
        any_active = any(b["text"] == "Active" for b in parent_frame.ch_buttons)
        if not any_active:
            parent_frame.enter_btn.config(state="disabled", bg="#555555")

def show_empty_tab_page(parent_frame, app, active_tab):
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
