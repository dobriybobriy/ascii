import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk


class ZoomableCanvas(tk.Canvas):
    """
    Потужний інтерактивний віджет полотна з підтримкою:
    - Зум коліщатком миші (з фокусом у точці курсору)
    - Перетягування (панорамування) затиснутою кнопкою миші
    - Кнопки Zoom In / Out / Fit / 100%
    - Оптимізований рендеринг тільки видимої зони (швидко навіть на 10x-20x зумі)
    """

    def __init__(self, master, placeholder_text="Зображення відсутнє", on_zoom_change=None, **kwargs):
        bg = kwargs.pop("bg", "#14171c")
        super().__init__(master, bg=bg, highlightthickness=0, **kwargs)

        self.placeholder_text = placeholder_text
        self.on_zoom_change = on_zoom_change

        self.pil_img = None
        self.photo = None

        self.scale = 1.0
        self.pos_x = 0.0
        self.pos_y = 0.0
        self.is_fit = True

        self.drag_start_x = 0
        self.drag_start_y = 0
        self.is_dragging = False

        # Прив'язка подій
        self.bind("<Configure>", self._on_configure)
        self.bind("<MouseWheel>", self._on_mouse_wheel)
        self.bind("<ButtonPress-1>", self._on_drag_start)
        self.bind("<B1-Motion>", self._on_drag_motion)
        self.bind("<ButtonRelease-1>", self._on_drag_end)

        self.bind("<ButtonPress-2>", self._on_drag_start)
        self.bind("<B2-Motion>", self._on_drag_motion)
        self.bind("<ButtonRelease-2>", self._on_drag_end)
        self.bind("<ButtonPress-3>", self._on_drag_start)
        self.bind("<B3-Motion>", self._on_drag_motion)
        self.bind("<ButtonRelease-3>", self._on_drag_end)

        self.bind("<Double-Button-1>", lambda e: self.zoom_fit())

    def set_theme(self, is_dark: bool):
        bg = "#14171c" if is_dark else "#f0f2f5"
        self.configure(bg=bg)
        self.redraw()

    def set_image(self, pil_image: Image.Image, reset_fit: bool = False):
        self.pil_img = pil_image

        if self.pil_img is None:
            self.redraw()
            return

        if reset_fit or self.is_fit:
            self.zoom_fit()
        else:
            self.redraw()

    def _on_configure(self, event):
        if self.is_fit and self.pil_img is not None:
            self.zoom_fit()
        else:
            self.redraw()

    def zoom_fit(self):
        """Вміщує зображення повністю у межі полотна з центруванням."""
        if self.pil_img is None:
            self.redraw()
            return

        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw <= 1 or ch <= 1:
            cw, ch = 800, 600

        iw, ih = self.pil_img.size
        pad = 20
        avail_w = max(10, cw - pad)
        avail_h = max(10, ch - pad)

        scale = min(avail_w / iw, avail_h / ih, 1.0)
        self.scale = max(0.02, scale)

        disp_w = iw * self.scale
        disp_h = ih * self.scale

        self.pos_x = (cw - disp_w) / 2.0
        self.pos_y = (ch - disp_h) / 2.0
        self.is_fit = True

        self.redraw()
        self._notify_zoom()

    def zoom_100(self):
        """Встановлює реальний масштаб 1:1 (100%) з центруванням."""
        if self.pil_img is None:
            return

        cw = self.winfo_width()
        ch = self.winfo_height()
        iw, ih = self.pil_img.size

        self.scale = 1.0
        self.pos_x = (cw - iw) / 2.0
        self.pos_y = (ch - ih) / 2.0
        self.is_fit = False

        self.redraw()
        self._notify_zoom()

    def zoom_by_factor(self, factor: float):
        """Зумує відносно центру полотна."""
        if self.pil_img is None:
            return
        cw = self.winfo_width() // 2
        ch = self.winfo_height() // 2
        self._zoom_at(cw, ch, factor)

    def _zoom_at(self, cx: float, cy: float, factor: float):
        if self.pil_img is None:
            return

        new_scale = max(0.05, min(30.0, self.scale * factor))
        if abs(new_scale - self.scale) < 1e-4:
            return

        self.pos_x = cx - (cx - self.pos_x) * (new_scale / self.scale)
        self.pos_y = cy - (cy - self.pos_y) * (new_scale / self.scale)
        self.scale = new_scale
        self.is_fit = False

        self.redraw()
        self._notify_zoom()

    def _on_mouse_wheel(self, event):
        if self.pil_img is None:
            return
        factor = 1.18 if event.delta > 0 else (1.0 / 1.18)
        self._zoom_at(event.x, event.y, factor)

    def _on_drag_start(self, event):
        if self.pil_img is None:
            return
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.is_dragging = True
        self.configure(cursor="fleur")

    def _on_drag_motion(self, event):
        if not self.is_dragging or self.pil_img is None:
            return
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.pos_x += dx
        self.pos_y += dy
        self.drag_start_x = event.x
        self.drag_start_y = event.y
        self.is_fit = False
        self.redraw()

    def _on_drag_end(self, event):
        self.is_dragging = False
        self.configure(cursor="")

    def _notify_zoom(self):
        if self.on_zoom_change:
            self.on_zoom_change(self.scale, self.is_fit)

    def redraw(self):
        """Рендерить тільки видиму частину зображення для максимальної швидкості."""
        self.delete("all")

        if self.pil_img is None:
            cw = max(200, self.winfo_width())
            ch = max(200, self.winfo_height())
            self.create_text(
                cw // 2,
                ch // 2,
                text=self.placeholder_text,
                fill="#7e8694",
                font=("Segoe UI", 15),
            )
            return

        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw <= 1 or ch <= 1:
            return

        iw, ih = self.pil_img.size
        disp_w = iw * self.scale
        disp_h = ih * self.scale

        vis_x0 = max(0.0, self.pos_x)
        vis_y0 = max(0.0, self.pos_y)
        vis_x1 = min(float(cw), self.pos_x + disp_w)
        vis_y1 = min(float(ch), self.pos_y + disp_h)

        if vis_x1 <= vis_x0 or vis_y1 <= vis_y0:
            return

        crop_x0 = max(0, int((vis_x0 - self.pos_x) / self.scale))
        crop_y0 = max(0, int((vis_y0 - self.pos_y) / self.scale))
        crop_x1 = min(iw, int((vis_x1 - self.pos_x) / self.scale) + 1)
        crop_y1 = min(ih, int((vis_y1 - self.pos_y) / self.scale) + 1)

        cropped = self.pil_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
        target_w = max(1, int((crop_x1 - crop_x0) * self.scale))
        target_h = max(1, int((crop_y1 - crop_y0) * self.scale))

        resample = Image.Resampling.NEAREST if self.scale >= 1.0 else Image.Resampling.BILINEAR
        scaled = cropped.resize((target_w, target_h), resample)

        self.photo = ImageTk.PhotoImage(scaled)

        paste_x = int(self.pos_x + crop_x0 * self.scale)
        paste_y = int(self.pos_y + crop_y0 * self.scale)
        self.create_image(paste_x, paste_y, anchor="nw", image=self.photo)


class ZoomableImageFrame(ctk.CTkFrame):
    """
    Зручний контейнер з полотном ZoomableCanvas та елегантною панеллю керування:
    [🔍-] [ 100% ] [🔍+] [↔️ За розміром] [1:1] [⛶ Розширити вікно] + підказка
    """

    def __init__(self, master, placeholder_text="Зображення відсутнє", on_expand_toggle=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_expand_toggle = on_expand_toggle
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Полотно для зуму та панорамування
        self.canvas = ZoomableCanvas(
            self,
            placeholder_text=placeholder_text,
            on_zoom_change=self._update_zoom_label,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        # 2. Нижня панель керування зумом
        self.toolbar = ctk.CTkFrame(self, height=36, corner_radius=8, fg_color=("gray85", "#1e222a"))
        self.toolbar.grid(row=1, column=0, sticky="ew", pady=(8, 0))

        # Кнопка зменшити
        self.btn_zoom_out = ctk.CTkButton(
            self.toolbar,
            text="➖",
            width=32,
            height=26,
            command=lambda: self.canvas.zoom_by_factor(0.8),
        )
        self.btn_zoom_out.pack(side="left", padx=(8, 4), pady=4)

        # Відсоток зуму
        self.lbl_zoom = ctk.CTkLabel(
            self.toolbar,
            text="100%",
            width=65,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.lbl_zoom.pack(side="left", padx=2, pady=4)

        # Кнопка збільшити
        self.btn_zoom_in = ctk.CTkButton(
            self.toolbar,
            text="➕",
            width=32,
            height=26,
            command=lambda: self.canvas.zoom_by_factor(1.25),
        )
        self.btn_zoom_in.pack(side="left", padx=(2, 8), pady=4)

        # Кнопка Fit
        self.btn_fit = ctk.CTkButton(
            self.toolbar,
            text="↔️ Fit",
            width=80,
            height=26,
            fg_color="gray30",
            hover_color="gray40",
            command=self.canvas.zoom_fit,
        )
        self.btn_fit.pack(side="left", padx=4, pady=4)

        # Кнопка 100%
        self.btn_100 = ctk.CTkButton(
            self.toolbar,
            text="1:1 (100%)",
            width=85,
            height=26,
            fg_color="gray30",
            hover_color="gray40",
            command=self.canvas.zoom_100,
        )
        self.btn_100.pack(side="left", padx=4, pady=4)

        # Кнопка розширення вікна / приховування бічних панелей
        if self.on_expand_toggle:
            self.btn_expand = ctk.CTkButton(
                self.toolbar,
                text="⛶ Expand Canvas",
                width=140,
                height=26,
                fg_color="#2980b9",
                hover_color="#3498db",
                command=self.on_expand_toggle,
            )
            self.btn_expand.pack(side="left", padx=6, pady=4)

        # Підказка
        self.lbl_hint = ctk.CTkLabel(
            self.toolbar,
            text="💡 Wheel: zoom | Drag LMB: pan | Double-click: Fit",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self.lbl_hint.pack(side="right", padx=12, pady=4)

    def set_expand_btn_text(self, text: str):
        if hasattr(self, "btn_expand"):
            self.btn_expand.configure(text=text)

    def update_ui_texts(self, btn_fit="↔️ Fit", btn_100="1:1 (100%)", btn_expand="⛶ Expand Canvas", hint=None, placeholder=None):
        if hasattr(self, "btn_fit"):
            self.btn_fit.configure(text=btn_fit)
        if hasattr(self, "btn_100"):
            self.btn_100.configure(text=btn_100)
        if hasattr(self, "btn_expand") and btn_expand:
            self.btn_expand.configure(text=btn_expand)
        if hasattr(self, "lbl_hint") and hint:
            self.lbl_hint.configure(text=hint)
        if placeholder:
            self.canvas.placeholder_text = placeholder
            if self.canvas.pil_img is None:
                self.canvas.redraw()

    def set_image(self, pil_image: Image.Image, reset_fit: bool = False):
        self.canvas.set_image(pil_image, reset_fit=reset_fit)

    def set_theme(self, is_dark: bool):
        self.canvas.set_theme(is_dark)

    def _update_zoom_label(self, scale: float, is_fit: bool):
        pct = int(scale * 100)
        fit_suffix = " (Fit)" if is_fit else ""
        self.lbl_zoom.configure(text=f"{pct}%{fit_suffix}")
        fit_suffix = " (Fit)" if is_fit else ""
        self.lbl_zoom.configure(text=f"{pct}%{fit_suffix}")
