import os
import cv2
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime
import sys
import numpy as np
from PIL import Image, ImageTk

def cv2_imread_unicode(file_path):
    """ Read image from path with unicode characters """
    try:
        raw_data = np.fromfile(file_path, dtype=np.uint8)
        return cv2.imdecode(raw_data, cv2.IMREAD_COLOR)
    except Exception:
        return None

def cv2_imwrite_unicode(file_path, img):
    """ Write image to path with unicode characters """
    try:
        ext = os.path.splitext(file_path)[1]
        result, nparray = cv2.imencode(ext, img)
        if result:
            with open(file_path, mode='wb') as f:
                nparray.tofile(f)
            return True
    except Exception:
        return False
    return False

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def get_base_dir():
    """ Get directory where the app/exe is located """
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

# Standardize path for both dev and production
APP_ROOT = resource_path("")
sys.path.insert(0, APP_ROOT)

from src.core.inspector import ICInspector
from src.utils.config_manager import ConfigManager

class VisualReviewDialog:
    def __init__(self, parent, items, current_idx=0, ng_callback=None):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("🔍 VISUAL REVIEW & ZOOM INSPECTION (PARALLEL ROI VIEW)")
        self.dialog.geometry("1200x800")
        self.dialog.configure(bg="#0f172a")

        self.ng_callback = ng_callback
        self.logged_ng_set = set()
        self.photo_refs = []  # Keep references for images displayed in grid

        # Group items by base PCB name
        self.pcb_groups = self._group_by_pcb(items)
        
        # Determine starting PCB index based on current_idx
        target_filename = items[current_idx][0] if (items and 0 <= current_idx < len(items)) else None
        self.current_pcb_idx = 0
        if target_filename:
            for p_idx, (base_name, rois) in enumerate(self.pcb_groups):
                if any(fn == target_filename for _, fn, _ in rois):
                    self.current_pcb_idx = p_idx
                    break

        self._build_ui()
        self._load_current_pcb()

        # Keyboard shortcuts
        self.dialog.bind("<Left>", lambda e: self._prev_pcb())
        self.dialog.bind("<Right>", lambda e: self._next_pcb())
        self.dialog.bind("a", lambda e: self._prev_pcb())
        self.dialog.bind("d", lambda e: self._next_pcb())

    def _group_by_pcb(self, items):
        groups = {}
        for filename, abs_path in items:
            name_no_ext = os.path.splitext(filename)[0]
            if name_no_ext.startswith("Crop_"):
                parts = name_no_ext[5:].rsplit("_ROI", 1)
                base_pcb = parts[0]
                roi_label = f"ROI #{parts[1]}" if len(parts) > 1 else "ROI"
            else:
                base_pcb = name_no_ext
                roi_label = "ROI"

            if base_pcb not in groups:
                groups[base_pcb] = []
            groups[base_pcb].append((roi_label, filename, abs_path))
        return list(groups.items())

    def _build_ui(self):
        # Top toolbar
        toolbar = tk.Frame(self.dialog, bg="#1e293b", padx=12, pady=10)
        toolbar.pack(fill=tk.X)

        self.prev_btn = tk.Button(toolbar, text="◄ Previous PCB (Left / A)", command=self._prev_pcb,
                                  bg="#334155", fg="white", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=12, pady=6)
        self.prev_btn.pack(side=tk.LEFT, padx=5)

        self.info_lbl = tk.Label(toolbar, text="", bg="#1e293b", fg="#38bdf8", font=("Segoe UI", 11, "bold"))
        self.info_lbl.pack(side=tk.LEFT, expand=True, padx=10)

        self.next_btn = tk.Button(toolbar, text="Next PCB ► (Right / D)", command=self._next_pcb,
                                  bg="#334155", fg="white", font=("Segoe UI", 9, "bold"), relief=tk.FLAT, padx=12, pady=6)
        self.next_btn.pack(side=tk.LEFT, padx=5)

        self.zoom_lbl = tk.Label(toolbar, text="💡 Click any ROI image to Zoom 100%", bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 9, "italic"))
        self.zoom_lbl.pack(side=tk.RIGHT, padx=15)

        # Container for side-by-side ROI columns
        self.roi_container = tk.Frame(self.dialog, bg="#020617")
        self.roi_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        self.roi_container.bind("<Configure>", lambda e: self._load_current_pcb())

    def _load_current_pcb(self):
        if not self.pcb_groups: return
        base_pcb, rois = self.pcb_groups[self.current_pcb_idx]
        self.info_lbl.config(text=f"[ PCB {self.current_pcb_idx + 1} / {len(self.pcb_groups)} ] {base_pcb} ({len(rois)} ROIs)")

        # Clear existing ROI cards
        for widget in self.roi_container.winfo_children():
            widget.destroy()
        self.photo_refs.clear()

        # Grid configuration for side-by-side columns
        n_cols = len(rois)
        for c in range(n_cols):
            self.roi_container.columnconfigure(c, weight=1)
        self.roi_container.rowconfigure(0, weight=1)

        container_w = max(self.roi_container.winfo_width(), 800)
        container_h = max(self.roi_container.winfo_height(), 500)
        card_w = max(200, (container_w - (n_cols + 1) * 10) // n_cols)
        card_h = max(280, container_h - 90)

        for col_idx, (roi_label, filename, abs_path) in enumerate(rois):
            card_frame = tk.Frame(self.roi_container, bg="#1e293b", padx=8, pady=8,
                                  highlightthickness=2, highlightbackground="#334155")
            card_frame.grid(row=0, column=col_idx, padx=6, pady=6, sticky="nsew")

            # Header of Card
            is_ng = filename in self.logged_ng_set
            header_text = f"{roi_label} [🔴 NG SAVED]" if is_ng else roi_label
            header_color = "#ef4444" if is_ng else "#38bdf8"

            hdr_lbl = tk.Label(card_frame, text=header_text, bg="#1e293b", fg=header_color, font=("Segoe UI", 10, "bold"))
            hdr_lbl.pack(pady=(0, 4))

            # Bottom Add NG button for this ROI (Prominent & Easy to Click)
            ng_btn = tk.Button(card_frame, text=f"➕ ADD NG ({roi_label})",
                               command=lambda f=filename, p=abs_path: self._mark_ng(f, p),
                               bg="#ef4444", fg="white", font=("Segoe UI", 11, "bold"),
                               activebackground="#dc2626", activeforeground="white",
                               relief=tk.FLAT, pady=10, cursor="hand2")
            ng_btn.pack(side=tk.BOTTOM, fill=tk.X, pady=(6, 2))

            # Image display canvas
            img = cv2_imread_unicode(abs_path)
            if img is not None:
                h, w = img.shape[:2]
                scale = min(card_w / w, card_h / h)
                nw, nh = max(1, int(w * scale)), max(1, int(h * scale))

                rgb = cv2.cvtColor(cv2.resize(img, (nw, nh)), cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(rgb)
                photo = ImageTk.PhotoImage(pil_img)
                self.photo_refs.append(photo)

                canvas = tk.Canvas(card_frame, bg="#020617", width=card_w, height=card_h, highlightthickness=0, cursor="hand2")
                canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

                x_pos = max(0, (card_w - nw) // 2)
                y_pos = max(0, (card_h - nh) // 2)
                canvas.create_image(x_pos, y_pos, anchor="nw", image=photo)
                canvas.bind("<Button-1>", lambda e, p=abs_path, fn=filename: self._zoom_fullsize(fn, p))

    def _prev_pcb(self):
        if self.current_pcb_idx > 0:
            self.current_pcb_idx -= 1
            self._load_current_pcb()

    def _next_pcb(self):
        if self.current_pcb_idx < len(self.pcb_groups) - 1:
            self.current_pcb_idx += 1
            self._load_current_pcb()

    def _mark_ng(self, filename, abs_path):
        if self.ng_callback:
            self.logged_ng_set.add(filename)
            self.ng_callback(filename, abs_path)
            self._load_current_pcb()

    def _zoom_fullsize(self, filename, abs_path):
        img = cv2_imread_unicode(abs_path)
        if img is None: return

        zoom_win = tk.Toplevel(self.dialog)
        zoom_win.title(f"🔍 FULLSIZE ZOOM 100%: {filename}")
        zoom_win.geometry("1000x800")
        zoom_win.configure(bg="#000000")

        z_canvas = tk.Canvas(zoom_win, bg="#000000", highlightthickness=0)
        s_y = ttk.Scrollbar(zoom_win, orient=tk.VERTICAL, command=z_canvas.yview)
        s_x = ttk.Scrollbar(zoom_win, orient=tk.HORIZONTAL, command=z_canvas.xview)

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb)
        full_photo = ImageTk.PhotoImage(pil_img)

        z_canvas.create_image(0, 0, anchor="nw", image=full_photo)
        z_canvas.config(scrollregion=(0, 0, img.shape[1], img.shape[0]), xscrollcommand=s_x.set, yscrollcommand=s_y.set)

        # Mouse wheel scrolling bindings (vertical scroll & Shift+scroll horizontal)
        def _on_v_scroll(event):
            z_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_h_scroll(event):
            z_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")

        zoom_win.bind("<MouseWheel>", _on_v_scroll)
        zoom_win.bind("<Shift-MouseWheel>", _on_h_scroll)

        s_y.pack(side=tk.RIGHT, fill=tk.Y)
        s_x.pack(side=tk.BOTTOM, fill=tk.X)
        z_canvas.pack(fill=tk.BOTH, expand=True)
        z_canvas.photo_ref = full_photo


class ICInspectorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("IC Pin Inspector Pro v1.0")
        self.root.geometry("1100x780")
        self.root.configure(bg="#0f172a")
        
        # Set app icon using bundled resource
        icon_path = resource_path(os.path.join("Logo", "tool.png"))
        if os.path.exists(icon_path):
            try:
                icon = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(True, icon)
            except Exception:
                pass

        self.is_running = False
        config_path = os.path.join(get_base_dir(), 'config', 'config.json')
        self.config_mgr = ConfigManager(config_path)
        self.config = self.config_mgr.load_config()
        self.inspector = ICInspector(self.config)

        self.cropped_items = []         # list of tuples: (filename, abs_path)
        self.thumbnail_images = []      # Keep references to ImageTk.PhotoImage
        self.thumbnail_widgets = []     # Keep track of item_frame widgets for highlighting
        self.selected_item = None       # (filename, abs_path, item_frame)

        self._build_ui()

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#0f172a")
        style.configure("TLabel", background="#0f172a", foreground="#cbd5e1", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#f8fafc")

        main_container = ttk.Frame(self.root, padding="15")
        main_container.pack(fill=tk.BOTH, expand=True)

        # Header Frame with Title, ROI setting, and ADD NG Button
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill=tk.X, pady=(0, 15))

        header = ttk.Label(header_frame, text="IC PIN INSPECTOR SYSTEM", style="Header.TLabel")
        header.pack(side=tk.LEFT, anchor=tk.W)

        # Setting ROI count
        ttk.Label(header_frame, text="ROI Count:").pack(side=tk.LEFT, padx=(20, 5))
        self.num_rois_var = tk.IntVar(value=self.config.get("num_rois", 4))
        self.roi_spinbox = tk.Spinbox(header_frame, from_=1, to=20, textvariable=self.num_rois_var, width=5,
                                     bg="#1e293b", fg="#f8fafc", buttonbackground="#334155", insertbackground="white")
        self.roi_spinbox.pack(side=tk.LEFT, padx=5)

        # Add NG Button at top
        self.add_ng_btn = tk.Button(header_frame, text="➕ ADD NG", command=self._add_ng_log,
                                    bg="#ef4444", fg="white", font=("Segoe UI", 10, "bold"),
                                    activebackground="#dc2626", activeforeground="white",
                                    relief=tk.FLAT, padx=16, pady=6)
        self.add_ng_btn.pack(side=tk.RIGHT, padx=5)

        # Folder paths frame
        input_frame = ttk.Frame(main_container)
        input_frame.pack(fill=tk.X, pady=4)
        
        ttk.Label(input_frame, text="Input Folder:").pack(side=tk.LEFT, padx=5)
        self.path_var = tk.StringVar()
        self.path_entry = tk.Entry(input_frame, textvariable=self.path_var, bg="#1e293b", fg="white", insertbackground="white", borderwidth=0)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, ipady=5)
        
        self.browse_btn = tk.Button(input_frame, text="Browse", command=self._browse_input, bg="#334155", fg="white", relief=tk.FLAT, padx=15)
        self.browse_btn.pack(side=tk.LEFT, padx=5)

        # Output Folder Section
        out_frame = ttk.Frame(main_container)
        out_frame.pack(fill=tk.X, pady=4)
        
        ttk.Label(out_frame, text="Output Folder:").pack(side=tk.LEFT, padx=5)
        self.out_path_var = tk.StringVar()
        self.out_entry = tk.Entry(out_frame, textvariable=self.out_path_var, bg="#1e293b", fg="white", insertbackground="white", borderwidth=0)
        self.out_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5, ipady=5)
        
        self.out_browse_btn = tk.Button(out_frame, text="Browse", command=self._browse_output, bg="#334155", fg="white", relief=tk.FLAT, padx=15)
        self.out_browse_btn.pack(side=tk.LEFT, padx=5)

        stats_frame = ttk.Frame(main_container)
        stats_frame.pack(fill=tk.X, pady=10)
        
        self.total_lbl = self._create_stat_box(stats_frame, "TOTAL IMAGES", 0)
        self.ok_lbl = self._create_stat_box(stats_frame, "CROPPED ROIS", 1, color="#10b981")
        self.ng_lbl = self._create_stat_box(stats_frame, "NG ITEMS", 2, color="#ef4444")
        self.prog_lbl = self._create_stat_box(stats_frame, "PROGRESS", 3)

        for i in range(4): stats_frame.columnconfigure(i, weight=1)

        btn_frame = ttk.Frame(main_container)
        btn_frame.pack(fill=tk.X, pady=10)
        btn_frame.columnconfigure(0, weight=1)
        btn_frame.columnconfigure(1, weight=1)
        btn_frame.columnconfigure(2, weight=1)

        self.setup_btn = tk.Button(btn_frame, text="1. SET ROI POSITION", command=self._setup_position, 
                                   bg="#2563eb", fg="white", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, pady=10)
        self.setup_btn.grid(row=0, column=0, sticky="nsew", padx=3)

        self.action_btn = tk.Button(btn_frame, text="2. RUN INSPECTION", command=self._toggle_action, 
                                   bg="#d97706", fg="white", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, pady=10)
        self.action_btn.grid(row=0, column=1, sticky="nsew", padx=3)

        self.view_btn = tk.Button(btn_frame, text="3. VISUAL REVIEW", command=self._open_view_dialog, 
                                 bg="#059669", fg="white", font=("Segoe UI", 10, "bold"), relief=tk.FLAT, pady=10)
        self.view_btn.grid(row=0, column=2, sticky="nsew", padx=3)

        # Mid Content Split (Thumbnail Preview Gallery & Live Log)
        content_frame = ttk.Frame(main_container)
        content_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        content_frame.columnconfigure(0, weight=3)
        content_frame.columnconfigure(1, weight=2)

        # Left Column: Thumbnail Preview Gallery
        left_box = ttk.Frame(content_frame)
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 5))

        ttk.Label(left_box, text="Cropped ROI Preview Gallery (Click to Select, Double-Click to Review):").pack(anchor=tk.W, pady=(0, 4))
        
        gallery_container = tk.Frame(left_box, bg="#020617")
        gallery_container.pack(fill=tk.BOTH, expand=True)

        self.gallery_canvas = tk.Canvas(gallery_container, bg="#020617", highlightthickness=0)
        gallery_scroll = ttk.Scrollbar(gallery_container, orient=tk.VERTICAL, command=self.gallery_canvas.yview)
        
        self.gallery_inner_frame = tk.Frame(self.gallery_canvas, bg="#020617")
        self.gallery_inner_frame.bind("<Configure>", lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all")))
        
        self.gallery_canvas.create_window((0, 0), window=self.gallery_inner_frame, anchor="nw")
        self.gallery_canvas.configure(yscrollcommand=gallery_scroll.set)

        gallery_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.gallery_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Right Column: Live Log
        right_box = ttk.Frame(content_frame)
        right_box.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        ttk.Label(right_box, text="Live System Log:").pack(anchor=tk.W, pady=(0, 4))
        log_scroll = ttk.Scrollbar(right_box, orient=tk.VERTICAL)
        self.log_text = tk.Text(right_box, bg="#020617", fg="#22c55e", font=("Consolas", 9), borderwidth=0)
        log_scroll.config(command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        self._log("Ready.")

    def _create_stat_box(self, parent, label, col, color="#ffffff"):
        frame = tk.Frame(parent, bg="#1e293b", padx=10, pady=10, highlightthickness=1, highlightbackground="#334155")
        frame.grid(row=0, column=col, sticky="nsew", padx=5)
        tk.Label(frame, text=label, bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 8, "bold")).pack()
        val_lbl = tk.Label(frame, text="0", bg="#1e293b", fg=color, font=("Segoe UI", 18, "bold"))
        val_lbl.pack()
        return val_lbl

    def _log(self, msg):
        now = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{now}] {msg}\n")
        self.log_text.see(tk.END)

    def _browse_input(self):
        folder = filedialog.askdirectory()
        if folder:
            self.path_var.set(os.path.abspath(folder))
            if not self.out_path_var.get():
                self.out_path_var.set(os.path.join(os.path.abspath(folder), "Cropped_Results"))

    def _browse_output(self):
        folder = filedialog.askdirectory()
        if folder:
            self.out_path_var.set(os.path.abspath(folder))

    def _setup_position(self):
        folder = self.path_var.get()
        if not folder or not os.path.exists(folder):
            messagebox.showwarning("Warning", "Please select a folder first!")
            return
        
        files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        valid_files = [f for f in files if "_ocr" not in f.lower()]
        
        if not valid_files:
            messagebox.showerror("Error", "No valid original images found (excluding _OCR files)!")
            return
        
        try:
            num_rois = int(self.num_rois_var.get())
            if num_rois < 1:
                num_rois = 1
        except ValueError:
            num_rois = 4
            self.num_rois_var.set(4)

        self.config["num_rois"] = num_rois
        self.config_mgr.save_config(self.config)

        sample_path = os.path.join(folder, valid_files[0])
        self._log(f"Setting up ROI for {num_rois} regions on {valid_files[0]}...")
        
        from src.tools.setup_roi import setup_roi
        try:
            setup_roi(sample_path, num_rois=num_rois)
            self._log("Setup completed.")
            self.config = self.config_mgr.load_config()
            messagebox.showinfo("Success", f"Position saved for {num_rois} ROIs!")
        except Exception as e:
            self._log(f"Error: {str(e)}")
            messagebox.showerror("Error", str(e))

    def _add_thumbnail_to_gallery(self, crop_filename, crop_save_path, img_crop):
        """ Render thumbnail image in gallery GUI """
        try:
            rgb = cv2.cvtColor(img_crop, cv2.COLOR_BGR2RGB)
            pil_img = Image.fromarray(rgb)
            pil_img.thumbnail((110, 110), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(pil_img)
            self.thumbnail_images.append(photo)

            col_count = 3
            idx = len(self.thumbnail_widgets)
            row = idx // col_count
            col = idx % col_count

            item_frame = tk.Frame(self.gallery_inner_frame, bg="#1e293b", padx=5, pady=5,
                                  highlightthickness=2, highlightbackground="#334155")
            item_frame.grid(row=row, column=col, padx=4, pady=4, sticky="nsew")

            img_lbl = tk.Label(item_frame, image=photo, bg="#1e293b", cursor="hand2")
            img_lbl.pack()

            short_name = crop_filename if len(crop_filename) <= 18 else crop_filename[:15] + "..."
            text_lbl = tk.Label(item_frame, text=short_name, bg="#1e293b", fg="#cbd5e1",
                                font=("Segoe UI", 8), cursor="hand2")
            text_lbl.pack(pady=(2, 0))

            for widget in (item_frame, img_lbl, text_lbl):
                widget.bind("<Button-1>", lambda e, f=crop_filename, p=crop_save_path, frm=item_frame: self._select_thumbnail(frm, f, p))
                widget.bind("<Double-Button-1>", lambda e, f=crop_filename, p=crop_save_path, frm=item_frame: self._open_view_dialog(f))

            self.thumbnail_widgets.append(item_frame)

            if self.selected_item is None:
                self._select_thumbnail(item_frame, crop_filename, crop_save_path)

        except Exception as e:
            print(f"Error creating thumbnail: {e}")

    def _select_thumbnail(self, item_frame, filename, abs_path):
        """ Highlight selected thumbnail frame and mark as selected item """
        for frm in self.thumbnail_widgets:
            frm.configure(highlightbackground="#334155")
        
        item_frame.configure(highlightbackground="#ef4444")
        self.selected_item = (filename, abs_path, item_frame)
        self._log(f"🎯 Selected image: {filename}")

    def _open_view_dialog(self, target_filename=None):
        """ Open Visual Review dialog to view large images """
        if not self.cropped_items:
            messagebox.showwarning("Warning", "No cropped ROI images to review! Run RUN INSPECTION first.")
            return

        current_idx = 0
        if target_filename:
            for idx, (fn, _) in enumerate(self.cropped_items):
                if fn == target_filename:
                    current_idx = idx
                    break
        elif self.selected_item:
            sel_fn = self.selected_item[0]
            for idx, (fn, _) in enumerate(self.cropped_items):
                if fn == sel_fn:
                    current_idx = idx
                    break

        def ng_cb(filename, abs_path):
            self._write_ng_record(filename, abs_path)

        VisualReviewDialog(self.root, self.cropped_items, current_idx=current_idx, ng_callback=ng_cb)

    def _write_ng_record(self, filename, abs_path):
        """ Non-blocking NG logging with separate NG folder and image copy """
        out_folder = self.out_path_var.get()
        if not out_folder:
            out_folder = os.path.join(self.path_var.get() or ".", "Cropped_Results")
        
        ng_dir = os.path.join(out_folder, "NG_Images")
        os.makedirs(ng_dir, exist_ok=True)

        dst_img_path = os.path.join(ng_dir, filename)
        
        try:
            # Copy faulty image to NG_Images folder
            img = cv2_imread_unicode(abs_path)
            if img is not None:
                cv2_imwrite_unicode(dst_img_path, img)

            log_file_path = os.path.join(ng_dir, "NG_log.txt")
            log_entry = f"{dst_img_path} - {filename}\n"

            with open(log_file_path, "a", encoding="utf-8") as f:
                f.write(log_entry)
            
            if self.selected_item and self.selected_item[0] == filename:
                self.selected_item[2].configure(highlightbackground="#ef4444")

            self._log(f"🔴 NG Logged & Image Saved: {filename} -> {ng_dir}")
            current_ng = int(self.ng_lbl.cget("text"))
            self.ng_lbl.config(text=str(current_ng + 1))
        except Exception as e:
            self._log(f"❌ Error writing NG log: {str(e)}")

    def _add_ng_log(self):
        """ Log currently selected image thumbnail as NG to logfile """
        if not self.selected_item:
            messagebox.showwarning("Warning", "Please select a thumbnail image to Add NG!")
            return

        filename, abs_path, _ = self.selected_item
        self._write_ng_record(filename, abs_path)

    def _toggle_action(self):
        if self.is_running:
            self.is_running = False
            self.action_btn.configure(text="STOPPING...", bg="#555555")
        else:
            folder = self.path_var.get()
            if not folder or not os.path.exists(folder):
                messagebox.showerror("Error", "Select a valid folder!")
                return
            
            self.is_running = True
            self.action_btn.configure(text="STOP", bg="#c0392b")
            threading.Thread(target=self._run_inspection, args=(folder,), daemon=True).start()

    def _run_inspection(self, folder):
        from concurrent.futures import ThreadPoolExecutor

        try:
            folder = os.path.abspath(folder)
            out_folder = self.out_path_var.get()
            if not out_folder:
                out_folder = os.path.join(folder, "Cropped_Results")
            
            out_folder = os.path.abspath(out_folder)
            os.makedirs(out_folder, exist_ok=True)
            
            self._log(f"Target Folder: {folder}")
            self._log(f"Output Folder: {out_folder}")

            rois = self.config.get("rois", [])
            if not rois:
                messagebox.showerror("Error", "No ROIs defined! Run SET POSITION first.")
                self.is_running = False
                self.root.after(0, lambda: self.action_btn.config(text="START INSPECTION", bg="#e67e22"))
                return

            files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            valid_files = [f for f in files if "_ocr" not in f.lower() and not f.startswith("Crop_")]
            
            self.root.after(0, lambda: self.total_lbl.config(text=str(len(valid_files))))
            self._log(f"Starting ROI crop for {len(valid_files)} images ({len(rois)} ROIs each)...")

            def clear_gallery():
                for widget in self.gallery_inner_frame.winfo_children():
                    widget.destroy()
                self.cropped_items.clear()
                self.thumbnail_images.clear()
                self.thumbnail_widgets.clear()
                self.selected_item = None
            self.root.after(0, clear_gallery)

            stats = {"processed": 0, "total_crops": 0}
            lock = threading.Lock()

            def process_single_file(filename):
                if not self.is_running: return
                
                img_path = os.path.join(folder, filename)
                img = cv2_imread_unicode(img_path)
                if img is None:
                    self._log(f"⚠️ Could not read image: {filename}")
                    return

                base_name, ext = os.path.splitext(filename)

                for roi_idx, roi in enumerate(rois):
                    if not self.is_running: break
                    rx, ry, rw, rh = roi
                    if ry+rh > img.shape[0] or rx+rw > img.shape[1]: continue
                        
                    ic_crop = img[ry:ry+rh, rx:rx+rw]
                    crop_filename = f"Crop_{base_name}_ROI{roi_idx+1}{ext}"
                    crop_save_path = os.path.join(out_folder, crop_filename)

                    success = cv2_imwrite_unicode(crop_save_path, ic_crop)
                    if success:
                        with lock:
                            stats["total_crops"] += 1
                            item = (crop_filename, crop_save_path)
                            self.cropped_items.append(item)
                            self.root.after(0, lambda fn=crop_filename, p=crop_save_path, c=ic_crop.copy(): 
                                            self._add_thumbnail_to_gallery(fn, p, c))
                
                with lock:
                    stats["processed"] += 1
                    p = int((stats["processed"]/len(valid_files))*100)
                    self.root.after(0, lambda crops=stats["total_crops"], perc=p: self._update_stats(crops, perc))

            with ThreadPoolExecutor(max_workers=4) as executor:
                executor.map(process_single_file, valid_files)

            self._log(f"Done. Processed {stats['processed']} images, generated {stats['total_crops']} cropped ROIs.")
            messagebox.showinfo("Finished", f"Process Complete\nProcessed Images: {len(valid_files)}\nTotal Cropped ROIs: {stats['total_crops']}")

        except Exception as e:
            self._log(f"Error: {str(e)}")
            messagebox.showerror("Error", str(e))
        
        finally:
            self.is_running = False
            self.root.after(0, lambda: self.action_btn.config(text="START INSPECTION", bg="#e67e22"))

    def _update_stats(self, crops, perc):
        self.ok_lbl.config(text=str(crops))
        self.prog_lbl.config(text=f"{perc}%")

if __name__ == "__main__":
    root = tk.Tk()
    app = ICInspectorGUI(root)
    root.mainloop()
