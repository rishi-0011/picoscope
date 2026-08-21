import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import numpy as np
import os

def build_review_ui(parent_frame, app=None):
    # Clear previous contents
    for widget in parent_frame.winfo_children():
        widget.destroy()

    bg_color = "#8c97a8"
    parent_frame.configure(bg=bg_color)
    parent_frame.rowconfigure(0, weight=0)
    parent_frame.rowconfigure(1, weight=1)
    parent_frame.columnconfigure(0, weight=1)

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
    # Main Review Content Area
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
    main_split.columnconfigure(0, weight=1)  # Plots area
    main_split.columnconfigure(1, weight=0)  # Sidebar
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

    def draw_plots(mode="Channel 1&2"):
        fig.clear()
        
        if mode == "Channel 1&2":
            ax1 = fig.add_subplot(211)
            ax2 = fig.add_subplot(212)
            
            # Top Plot Ch1
            ax1.set_facecolor("#dce2ee")
            ax1.grid(True, color="#a0a8b8", linestyle="-", linewidth=0.7)
            ax1.set_ylabel("Voltage [kV]", fontsize=9, fontweight="bold")
            ax1.set_xlabel("Time [s]", fontsize=9, fontweight="bold")
            ax1.tick_params(labelsize=8)
            ax1.set_xlim(0, 200)
            ax1.set_ylim(-110, 10)
            
            # Bottom Plot Ch2
            ax2.set_facecolor("#dce2ee")
            ax2.grid(True, color="#a0a8b8", linestyle="-", linewidth=0.7)
            ax2.set_ylabel("Voltage [kV]", fontsize=9, fontweight="bold")
            ax2.set_xlabel("Time [s]", fontsize=9, fontweight="bold")
            ax2.tick_params(labelsize=8)
            ax2.set_xlim(0, 100)
            ax2.set_ylim(-90, 1200)

        elif mode == "Channel 1":
            ax1 = fig.add_subplot(111)
            ax1.set_facecolor("#dce2ee")
            ax1.grid(True, color="#a0a8b8", linestyle="-", linewidth=0.7)
            ax1.set_ylabel("Voltage [kV]", fontsize=9, fontweight="bold")
            ax1.set_xlabel("Time [s]", fontsize=9, fontweight="bold")
            ax1.tick_params(labelsize=8)
            ax1.set_xlim(0, 200)
            ax1.set_ylim(-110, 10)
            ax1.set_title("Review - Channel 1", fontsize=10, fontweight="bold")

        elif mode == "Channel 2":
            ax2 = fig.add_subplot(111)
            ax2.set_facecolor("#dce2ee")
            ax2.grid(True, color="#a0a8b8", linestyle="-", linewidth=0.7)
            ax2.set_ylabel("Voltage [kV]", fontsize=9, fontweight="bold")
            ax2.set_xlabel("Time [s]", fontsize=9, fontweight="bold")
            ax2.tick_params(labelsize=8)
            ax2.set_xlim(0, 100)
            ax2.set_ylim(-90, 1200)
            ax2.set_title("Review - Channel 2", fontsize=10, fontweight="bold")

        fig.tight_layout()
        canvas.draw()

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

    # Initial plot rendering
    set_subtab("Channel 1&2")

    # ----------------------------------------------------
    # Right Control Sidebar (Review Ch1 & Review Ch2 controls)
    # ----------------------------------------------------
    sidebar = tk.Frame(main_split, bg="#8c97a8", bd=2, relief="groove", padx=10, pady=8)
    sidebar.grid(row=0, column=1, sticky="ns")
    sidebar.columnconfigure(0, weight=1)

    # Button click handler placeholder
    def on_btn_click(btn_name):
        print(f"Review Tab Action: {btn_name}")

    # Helper function to create styled sidebar buttons
    def make_btn(parent, text, bg_color, fg_color="black"):
        btn = tk.Button(parent, text=text, bg=bg_color, fg=fg_color,
                        font=("Segoe UI", 9, "bold"), relief="raised", bd=2,
                        cursor="hand2", width=18, pady=2,
                        command=lambda t=text: on_btn_click(t))
        btn.pack(fill="x", pady=3)
        return btn

    # Helper function to create mini toolbars under Ch1 / Ch2
    def make_mini_toolbar(parent):
        tb_frame = tk.Frame(parent, bg="#8c97a8")
        tb_frame.pack(fill="x", pady=(2, 6))
        
        icons = ["+", "🔍", "⌂", "X", "Y", "MK"]
        for icon in icons:
            b = tk.Button(tb_frame, text=icon, bg="#d1d5db", fg="black",
                          font=("Segoe UI", 8, "bold"), width=3, relief="raised", bd=1,
                          command=lambda i=icon: on_btn_click(f"Tool {i}"))
            b.pack(side="left", padx=1)

    # --- SECTION 1: Review Ch1 ---
    ch1_sec = tk.Frame(sidebar, bg="#8c97a8")
    ch1_sec.pack(fill="x", pady=(0, 5))

    tk.Label(ch1_sec, text="Review Ch1", bg="#8c97a8", fg="#facc15",
             font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 4))

    make_btn(ch1_sec, "Load...", bg_color="#facc15", fg_color="black")
    make_btn(ch1_sec, "Remove Wave", bg_color="#f97316", fg_color="black")
    make_btn(ch1_sec, "Parameters", bg_color="#881337", fg_color="white")

    make_mini_toolbar(ch1_sec)

    # Separator
    ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=6)

    # --- SECTION 2: Active Wave Row ---
    active_wave_frame = tk.Frame(sidebar, bg="#8c97a8")
    active_wave_frame.pack(fill="x", pady=4)

    tk.Label(active_wave_frame, text="Active Wave", bg="#8c97a8", fg="#1e293b",
             font=("Segoe UI", 9, "bold")).pack(side="left", padx=(0, 5))

    # Blue indicator box
    blue_box = tk.Label(active_wave_frame, bg="#0000ff", width=2, height=1, relief="solid", bd=1)
    blue_box.pack(side="left", padx=(0, 5))

    # Spinbox / Entry for Wave Number
    spin_wave = tk.Spinbox(active_wave_frame, from_=1, to=99, width=4, font=("Segoe UI", 9, "bold"), justify="center")
    spin_wave.pack(side="left")

    # Separator
    ttk.Separator(sidebar, orient="horizontal").pack(fill="x", pady=6)

    # --- SECTION 3: Review Ch2 ---
    ch2_sec = tk.Frame(sidebar, bg="#8c97a8")
    ch2_sec.pack(fill="x", pady=(0, 5))

    tk.Label(ch2_sec, text="Review Ch2", bg="#8c97a8", fg="#2563eb",
             font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 4))

    make_btn(ch2_sec, "Load...", bg_color="#facc15", fg_color="black")
    make_btn(ch2_sec, "Remove Wave", bg_color="#f97316", fg_color="black")
    make_btn(ch2_sec, "Parameters", bg_color="#881337", fg_color="white")
    make_btn(ch2_sec, "Save All as...", bg_color="#2563eb", fg_color="white")
    make_btn(ch2_sec, "Export", bg_color="#facc15", fg_color="black")
    make_btn(ch2_sec, "Print", bg_color="#60a5fa", fg_color="black")

    make_mini_toolbar(ch2_sec)
