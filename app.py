import os
import sys
import time
import queue
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk
import cv2
import numpy as np

from ascii_engine import (
    AsciiEngine,
    PRESETS_EN,
    PRESETS_UK,
    COLOR_MODES_EN,
    COLOR_MODES_UK,
)
from zoom_canvas import ZoomableImageFrame
from translations import TRANSLATIONS, LANGUAGES


# 1. Приховуємо вікно консолі (CMD), якщо програма запущена в графічному режимі
if sys.platform == "win32":
    try:
        import ctypes
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 0)  # 0 = SW_HIDE
    except Exception:
        pass

# 2. Налаштовуємо AppUserModelID для відображення власної іконки на панелі завдань Windows (Taskbar)
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("antigravity.asciistudio.pro.1.0")
    except Exception:
        pass

# Налаштування теми CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")


def open_video_unicode(video_source):
    """Надійно відкриває відео навіть якщо шлях містить кирилицю або пробіли."""
    if isinstance(video_source, int):
        return cv2.VideoCapture(video_source)
    clean_path = str(video_source).strip('"')
    cap = cv2.VideoCapture(clean_path)
    if cap.isOpened():
        return cap
    try:
        import win32api
        short_path = win32api.GetShortPathName(clean_path)
        cap = cv2.VideoCapture(short_path)
        if cap.isOpened():
            return cap
    except Exception:
        pass
    return cap


def get_console_python():
    """Повертає шлях до консольного python.exe (якщо застосунок запущено через pythonw.exe)."""
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        cand = exe[:-5] + ".exe"
        if os.path.exists(cand):
            return cand
    elif "pythonw" in exe.lower():
        cand = exe.lower().replace("pythonw.exe", "python.exe")
        if os.path.exists(cand):
            return cand
    import shutil
    py = shutil.which("python.exe") or shutil.which("python")
    if py:
        return py
    return exe


class SplashScreen(ctk.CTkToplevel):
    """
    Плавний стильний Splash Screen під час завантаження та прогріву рушія.
    """
    def __init__(self, parent, on_complete=None):
        super().__init__(parent)
        self.on_complete = on_complete
        self.overrideredirect(True)
        self.configure(fg_color="#0e1117")
        self.attributes("-topmost", True)

        width, height = 440, 310
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Контейнер картки
        card = ctk.CTkFrame(self, fg_color="#141822", corner_radius=16, border_width=1, border_color="#262f45")
        card.pack(fill="both", expand=True, padx=4, pady=4)

        # Логотип
        assets_dir = Path(__file__).parent / "assets"
        png_path = assets_dir / "icon.png"
        self.logo_img = None
        if png_path.exists():
            try:
                pil_logo = Image.open(png_path).resize((72, 72), Image.Resampling.LANCZOS)
                self.logo_img = ctk.CTkImage(pil_logo, size=(72, 72))
            except Exception:
                pass

        if self.logo_img:
            self.lbl_logo = ctk.CTkLabel(card, image=self.logo_img, text="")
            self.lbl_logo.pack(pady=(24, 6))
        else:
            self.lbl_logo = ctk.CTkLabel(card, text="⚡", font=ctk.CTkFont(size=40))
            self.lbl_logo.pack(pady=(24, 6))

        self.lbl_title = ctk.CTkLabel(
            card,
            text="ASCII STUDIO PRO",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#ffffff",
        )
        self.lbl_title.pack(pady=(0, 2))

        self.lbl_sub = ctk.CTkLabel(
            card,
            text="High-Performance Art & Video Engine",
            font=ctk.CTkFont(size=12),
            text_color="#7aa2f7",
        )
        self.lbl_sub.pack(pady=(0, 16))

        # Індикатор прогресу
        self.progress = ctk.CTkProgressBar(card, width=280, height=8, corner_radius=4, progress_color="#3b82f6")
        self.progress.pack(pady=(0, 8))
        self.progress.set(0.0)

        self.lbl_status = ctk.CTkLabel(
            card,
            text="Initializing engine & assets...",
            font=ctk.CTkFont(size=11),
            text_color="#94a3b8",
        )
        self.lbl_status.pack(pady=(0, 16))

        self._step = 0
        self._animate_progress()

    def _animate_progress(self):
        self._step += 1
        pct = min(1.0, self._step / 14.0)
        self.progress.set(pct)

        if self._step == 4:
            self.lbl_status.configure(text="Loading fonts & presets...")
        elif self._step == 8:
            self.lbl_status.configure(text="Precomputing character masks...")
        elif self._step == 12:
            self.lbl_status.configure(text="Engine ready!")

        if self._step < 14:
            self.after(30, self._animate_progress)
        else:
            self.after(80, self._finish)

    def _finish(self):
        try:
            self.destroy()
        except Exception:
            pass
        if self.on_complete:
            self.on_complete()


class LoadingSpinner(ctk.CTkFrame):
    """
    Сучасний анімований спінер (індикатор завантаження) для важких операцій рендерингу.
    """
    def __init__(self, parent, size: int = 54, text: str = "⚡ Rendering ASCII..."):
        super().__init__(
            parent,
            fg_color=("#181c24", "#12151d"),
            corner_radius=14,
            border_width=1,
            border_color="#2b3447",
        )
        self.size = size
        self.angle = 0
        self._is_active = False

        self.canvas = tk.Canvas(
            self,
            width=size,
            height=size,
            bg="#12151d",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(padx=20, pady=(14, 4))

        self.lbl_text = ctk.CTkLabel(
            self,
            text=text,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#93c5fd",
        )
        self.lbl_text.pack(padx=20, pady=(0, 12))

    def set_text(self, text: str):
        self.lbl_text.configure(text=text)

    def show(self):
        if not self._is_active:
            self._is_active = True
            self.place(relx=0.5, rely=0.5, anchor="center")
            self.lift()
            self._animate()

    def hide(self):
        self._is_active = False
        self.place_forget()

    def _animate(self):
        if not self._is_active:
            return
        self.canvas.delete("all")
        pad = 6
        x0, y0 = pad, pad
        x1, y1 = self.size - pad, self.size - pad

        # Фоновий тонкий контур
        self.canvas.create_oval(x0, y0, x1, y1, outline="#1f293d", width=3)
        # Обертова неонова дуга
        self.canvas.create_arc(
            x0, y0, x1, y1,
            start=self.angle,
            extent=110,
            outline="#3b82f6",
            width=3.5,
            style="arc",
        )
        self.angle = (self.angle + 16) % 360
        self.after(25, self._animate)


class AsciiStudioApp(ctk.CTk):
    def __init__(self, show_splash: bool = True):
        super().__init__()
        self.show_splash = show_splash

        # Мова за замовчуванням — Англійська ("en")
        self.current_lang = "en"

        self.title(self.t("app_title"))
        self.geometry("1300x850")
        self.minsize(980, 680)

        # Встановлення власної іконки застосунку для вікна та панелі завдань
        assets_dir = Path(__file__).parent / "assets"
        ico_path = assets_dir / "icon.ico"
        png_path = assets_dir / "icon.png"

        if ico_path.exists():
            try:
                self.iconbitmap(str(ico_path.resolve()))
            except Exception:
                pass

        if png_path.exists():
            try:
                self._app_icon_photo = ImageTk.PhotoImage(file=str(png_path.resolve()))
                self.iconphoto(True, self._app_icon_photo)
            except Exception:
                pass

        # Двигунець рендерингу
        self.engine = AsciiEngine(font_size=12)

        # Стан додатку та асинхронного рендерингу
        self.current_mode = "image"  # 'image', 'video', 'webcam'
        self.text_font_size = 10
        self.is_expanded = False
        self.is_fullscreen = False
        self._is_animating_panel = False
        self._render_generation = 0
        self._is_rendering = False

        # Стан фото
        self.current_image_path = None
        self.current_orig_image = None
        self.last_rendered_pil = None
        self.last_rendered_text = ""
        self.last_rgb_grid = None
        self.last_text_grid = None

        # Стан відео
        self.current_video_path = None
        self.video_cap = None
        self.is_video_playing = False
        self.video_thread = None
        self.video_total_frames = 0
        self.video_fps = 30.0
        self.video_loop = True

        # Стан вебкамери
        self.webcam_cap = None
        self.is_webcam_running = False
        self.webcam_thread = None
        self.camera_index = 0
        self.last_webcam_raw_frame = None

        # Гарячі клавіші для розширення та повного екрану
        self.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.bind("<Escape>", lambda e: self.on_escape_pressed())

        # Побудова інтерфейсу
        self._build_ui()
        self.cached_settings = self.get_current_settings()

        # Стан життєвого циклу програми
        self._is_closing = False
        self._poll_timer_id = None

        # Черга завдань для безпечного потокового оновлення UI (Thread-Safe UI Queue)
        self._ui_queue = queue.Queue()
        self._poll_timer_id = self.after(15, self._poll_ui_queue)

        # Обробка закриття програми
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        if self.show_splash:
            self.withdraw()
            self.splash = SplashScreen(self, on_complete=self._on_splash_done)
        else:
            self.after(60, lambda: self.state("zoomed"))

    def _post_ui_task(self, func, *args, **kwargs):
        """Безпечно відправляє завдання для виконання в головному UI-потоці через чергу."""
        self._ui_queue.put((func, args, kwargs))

    def _poll_ui_queue(self):
        """Періодично вичитує чергу повідомлень та виконує оновлення UI."""
        if getattr(self, "_is_closing", False):
            return
        try:
            while not self._ui_queue.empty():
                func, args, kwargs = self._ui_queue.get_nowait()
                try:
                    func(*args, **kwargs)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if hasattr(self, "tk") and not getattr(self, "_is_closing", False):
                self._poll_timer_id = self.after(15, self._poll_ui_queue)
        except Exception:
            pass

    def _on_splash_done(self):
        try:
            self.deiconify()
            self.after(50, lambda: self.state("zoomed"))
        except Exception:
            pass

    def t(self, key: str, **kwargs) -> str:
        """Повертає перекладений рядок відповідно до поточної мови."""
        trans = TRANSLATIONS.get(self.current_lang, TRANSLATIONS["en"])
        val = trans.get(key, key)
        if kwargs:
            val = val.format(**kwargs)
        return val

    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. ЛІВА ПАНЕЛЬ НАВІГАЦІЇ
        self.sidebar_frame = ctk.CTkFrame(self, width=210, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="✨ ASCII Studio",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 4))

        self.sub_logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text=self.t("sub_logo"),
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.sub_logo_label.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Кнопки навігації
        self.btn_nav_image = ctk.CTkButton(
            self.sidebar_frame,
            text=self.t("nav_photo"),
            height=40,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self.switch_mode("image"),
        )
        self.btn_nav_image.grid(row=2, column=0, padx=15, pady=6, sticky="ew")

        self.btn_nav_video = ctk.CTkButton(
            self.sidebar_frame,
            text=self.t("nav_video"),
            height=40,
            anchor="w",
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            command=lambda: self.switch_mode("video"),
        )
        self.btn_nav_video.grid(row=3, column=0, padx=15, pady=6, sticky="ew")

        self.btn_nav_webcam = ctk.CTkButton(
            self.sidebar_frame,
            text=self.t("nav_webcam"),
            height=40,
            anchor="w",
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            text_color=("gray10", "gray90"),
            command=lambda: self.switch_mode("webcam"),
        )
        self.btn_nav_webcam.grid(row=4, column=0, padx=15, pady=6, sticky="ew")

        # Швидкий запуск консолі CMD
        self.btn_sidebar_cmd = ctk.CTkButton(
            self.sidebar_frame,
            text=self.t("nav_cmd"),
            height=36,
            anchor="w",
            font=ctk.CTkFont(size=13),
            fg_color="#2c3e50",
            hover_color="#34495e",
            command=self.launch_cmd_interactive,
        )
        self.btn_sidebar_cmd.grid(row=5, column=0, padx=15, pady=(15, 6), sticky="ew")

        # Перемикач мови (English / Українська)
        self.lang_label = ctk.CTkLabel(self.sidebar_frame, text=self.t("lang_label"), font=ctk.CTkFont(size=11))
        self.lang_label.grid(row=7, column=0, padx=20, pady=(10, 0), sticky="w")

        self.lang_menu = ctk.CTkOptionMenu(
            self.sidebar_frame,
            values=["English", "Українська"],
            command=self.change_language,
            height=28,
        )
        self.lang_menu.set("English")
        self.lang_menu.grid(row=8, column=0, padx=15, pady=(4, 10), sticky="ew")

        # Перемикач теми
        self.appearance_label = ctk.CTkLabel(self.sidebar_frame, text=self.t("theme_label"), font=ctk.CTkFont(size=11))
        self.appearance_label.grid(row=9, column=0, padx=20, pady=(0, 0), sticky="w")

        self.appearance_menu = ctk.CTkOptionMenu(
            self.sidebar_frame,
            values=[self.t("theme_dark"), self.t("theme_light"), self.t("theme_system")],
            command=self.change_appearance_mode,
            height=28,
        )
        self.appearance_menu.grid(row=10, column=0, padx=15, pady=(4, 20), sticky="ew")

        # 2. ЦЕНТРАЛЬНА ЗОНА (КОНТЕНТ)
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        # Контейнери для трьох режимів
        self._build_image_view()
        self._build_video_view()
        self._build_webcam_view()

        # 3. ПРАВА ПАНЕЛЬ НАЛАШТУВАНЬ РЕНДЕРУ
        self._build_settings_panel()

        # За замовчуванням активуємо Фото
        self.switch_mode("image")

    # ==========================
    # ПАНЕЛЬ НАЛАШТУВАНЬ
    # ==========================
    def _build_settings_panel(self):
        self.settings_frame = ctk.CTkScrollableFrame(self, width=280, label_text=self.t("settings_title"))
        self.settings_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 15), pady=15)
        self.settings_frame.grid_columnconfigure(0, weight=1)

        # 1. Ширина в символах
        self.lbl_width = ctk.CTkLabel(
            self.settings_frame,
            text=self.t("lbl_width", val=100),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        self.lbl_width.pack(fill="x", padx=10, pady=(10, 2))

        self.slider_width = ctk.CTkSlider(
            self.settings_frame,
            from_=30,
            to=240,
            number_of_steps=210,
            command=self._on_width_changed,
        )
        self.slider_width.set(100)
        self.slider_width.pack(fill="x", padx=10, pady=(0, 15))

        # 2. Пресет символів
        self.lbl_charset_title = ctk.CTkLabel(
            self.settings_frame,
            text=self.t("lbl_charset"),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        self.lbl_charset_title.pack(fill="x", padx=10, pady=(0, 2))

        presets_dict = PRESETS_EN if self.current_lang == "en" else PRESETS_UK
        preset_names = list(presets_dict.keys()) + [self.t("preset_custom")]
        self.combo_presets = ctk.CTkOptionMenu(
            self.settings_frame,
            values=preset_names,
            command=self._on_preset_changed,
        )
        self.combo_presets.set(preset_names[0])
        self.combo_presets.pack(fill="x", padx=10, pady=(0, 5))

        self.entry_custom_chars = ctk.CTkEntry(
            self.settings_frame,
            placeholder_text=self.t("placeholder_custom_chars"),
        )
        self.entry_custom_chars.insert(0, presets_dict[preset_names[0]])
        self.entry_custom_chars.bind("<KeyRelease>", lambda e: self._on_setting_changed())
        self.entry_custom_chars.pack(fill="x", padx=10, pady=(0, 15))

        # 3. Колірний режим
        self.lbl_palette_title = ctk.CTkLabel(
            self.settings_frame,
            text=self.t("lbl_palette"),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        )
        self.lbl_palette_title.pack(fill="x", padx=10, pady=(0, 2))

        modes_list = COLOR_MODES_EN if self.current_lang == "en" else COLOR_MODES_UK
        self.combo_colors = ctk.CTkOptionMenu(
            self.settings_frame,
            values=modes_list,
            command=lambda val: self._on_setting_changed(),
        )
        self.combo_colors.set(modes_list[0])
        self.combo_colors.pack(fill="x", padx=10, pady=(0, 15))

        # 4. Перемикач інверсії
        self.switch_invert = ctk.CTkSwitch(
            self.settings_frame,
            text=self.t("switch_invert"),
            command=self._on_setting_changed,
        )
        self.switch_invert.pack(fill="x", padx=10, pady=(0, 15))

        # 5. Контрастність
        self.lbl_contrast = ctk.CTkLabel(
            self.settings_frame,
            text=self.t("lbl_contrast", val=1.0),
            anchor="w",
            font=ctk.CTkFont(size=13),
        )
        self.lbl_contrast.pack(fill="x", padx=10, pady=(0, 2))

        self.slider_contrast = ctk.CTkSlider(
            self.settings_frame,
            from_=0.5,
            to=2.5,
            number_of_steps=40,
            command=self._on_contrast_changed,
        )
        self.slider_contrast.set(1.0)
        self.slider_contrast.pack(fill="x", padx=10, pady=(0, 15))

        # 6. Яскравість
        self.lbl_brightness = ctk.CTkLabel(
            self.settings_frame,
            text=self.t("lbl_brightness", val=0),
            anchor="w",
            font=ctk.CTkFont(size=13),
        )
        self.lbl_brightness.pack(fill="x", padx=10, pady=(0, 2))

        self.slider_brightness = ctk.CTkSlider(
            self.settings_frame,
            from_=-80,
            to=80,
            number_of_steps=160,
            command=self._on_brightness_changed,
        )
        self.slider_brightness.set(0)
        self.slider_brightness.pack(fill="x", padx=10, pady=(0, 15))

        # Кнопка скидання налаштувань
        self.btn_reset_settings = ctk.CTkButton(
            self.settings_frame,
            text=self.t("btn_reset_settings"),
            fg_color="gray30",
            hover_color="gray40",
            command=self._reset_settings,
        )
        self.btn_reset_settings.pack(fill="x", padx=10, pady=(10, 10))

    def _reset_settings(self):
        self.slider_width.set(100)
        self.lbl_width.configure(text=self.t("lbl_width", val=100))
        presets_dict = PRESETS_EN if self.current_lang == "en" else PRESETS_UK
        first_preset = list(presets_dict.keys())[0]
        self.combo_presets.set(first_preset)
        self.entry_custom_chars.delete(0, "end")
        self.entry_custom_chars.insert(0, presets_dict[first_preset])
        modes_list = COLOR_MODES_EN if self.current_lang == "en" else COLOR_MODES_UK
        self.combo_colors.set(modes_list[0])
        self.switch_invert.deselect()
        self.slider_contrast.set(1.0)
        self.lbl_contrast.configure(text=self.t("lbl_contrast", val=1.0))
        self.slider_brightness.set(0)
        self.lbl_brightness.configure(text=self.t("lbl_brightness", val=0))
        self._on_setting_changed()

    def _on_width_changed(self, value):
        val = int(value)
        self.lbl_width.configure(text=self.t("lbl_width", val=val))
        self._on_setting_changed()

    def _on_contrast_changed(self, value):
        self.lbl_contrast.configure(text=self.t("lbl_contrast", val=value))
        self._on_setting_changed()

    def _on_brightness_changed(self, value):
        self.lbl_brightness.configure(text=self.t("lbl_brightness", val=int(value)))
        self._on_setting_changed()

    def _on_preset_changed(self, choice):
        presets_dict = PRESETS_EN if self.current_lang == "en" else PRESETS_UK
        if choice in presets_dict:
            self.entry_custom_chars.delete(0, "end")
            self.entry_custom_chars.insert(0, presets_dict[choice])
        self._on_setting_changed()

    def _on_setting_changed(self):
        self.cached_settings = self.get_current_settings()
        if self.current_mode == "image" and self.current_orig_image is not None:
            self.render_current_image(reset_fit=False)

    def get_current_settings(self):
        return {
            "width": int(self.slider_width.get()),
            "char_set": self.entry_custom_chars.get() or " .:-=+*#%@",
            "color_mode": self.combo_colors.get(),
            "contrast": float(self.slider_contrast.get()),
            "brightness": int(self.slider_brightness.get()),
            "invert": bool(self.switch_invert.get()),
        }

    def get_thread_safe_settings(self):
        """Безпечний доступ до актуальних налаштувань для фонових потоків (відео/вебкамера)."""
        if hasattr(self, "cached_settings") and self.cached_settings:
            return self.cached_settings.copy()
        return self.get_current_settings()

    # ==========================
    # ПЕРЕМИКАННЯ МОВИ
    # ==========================
    def change_language(self, lang_name: str):
        self.current_lang = LANGUAGES.get(lang_name, "en")

        # 1. Заголовок і сайдбар
        self.title(self.t("app_title"))
        self.sub_logo_label.configure(text=self.t("sub_logo"))
        self.btn_nav_image.configure(text=self.t("nav_photo"))
        self.btn_nav_video.configure(text=self.t("nav_video"))
        self.btn_nav_webcam.configure(text=self.t("nav_webcam"))
        self.btn_sidebar_cmd.configure(text=self.t("nav_cmd"))
        self.lang_label.configure(text=self.t("lang_label"))
        self.appearance_label.configure(text=self.t("theme_label"))
        self.appearance_menu.configure(values=[self.t("theme_dark"), self.t("theme_light"), self.t("theme_system")])

        # 2. Панель налаштувань
        self.settings_frame.configure(label_text=self.t("settings_title"))
        self.lbl_width.configure(text=self.t("lbl_width", val=int(self.slider_width.get())))
        self.lbl_charset_title.configure(text=self.t("lbl_charset"))

        presets_dict = PRESETS_EN if self.current_lang == "en" else PRESETS_UK
        cur_preset_idx = 0
        preset_names = list(presets_dict.keys()) + [self.t("preset_custom")]
        self.combo_presets.configure(values=preset_names)
        self.combo_presets.set(preset_names[cur_preset_idx])
        self.entry_custom_chars.configure(placeholder_text=self.t("placeholder_custom_chars"))

        self.lbl_palette_title.configure(text=self.t("lbl_palette"))
        modes_list = COLOR_MODES_EN if self.current_lang == "en" else COLOR_MODES_UK
        self.combo_colors.configure(values=modes_list)
        self.combo_colors.set(modes_list[0])

        self.switch_invert.configure(text=self.t("switch_invert"))
        self.lbl_contrast.configure(text=self.t("lbl_contrast", val=float(self.slider_contrast.get())))
        self.lbl_brightness.configure(text=self.t("lbl_brightness", val=int(self.slider_brightness.get())))
        self.btn_reset_settings.configure(text=self.t("btn_reset_settings"))

        # 3. Фото вкладка
        self.btn_open_img.configure(text=self.t("btn_open_photo"))
        self.btn_open_cmd.configure(text=self.t("btn_open_cmd"))
        self.btn_save_png.configure(text=self.t("btn_save_png"))
        self.btn_save_txt.configure(text=self.t("btn_save_txt"))
        self.btn_save_html.configure(text=self.t("btn_save_html"))
        self.btn_copy_text.configure(text=self.t("btn_copy_text"))
        self.btn_fullscreen_img.configure(text=self.t("btn_fullscreen"))

        self.lbl_text_font.configure(text=self.t("lbl_font_size", val=self.text_font_size))
        self.btn_reset_font.configure(text=self.t("btn_reset_font"))
        self.lbl_hint_text_font.configure(text=self.t("hint_text_font"))

        # 4. Відео вкладка
        self.btn_open_video.configure(text=self.t("btn_open_video"))
        self.btn_video_cmd.configure(text=self.t("btn_open_cmd"))
        play_btn_txt = self.t("btn_play") if not self.is_video_playing else self.t("btn_pause")
        self.btn_play_pause.configure(text=play_btn_txt)
        self.btn_stop_video.configure(text=self.t("btn_stop"))
        self.switch_loop.configure(text=self.t("switch_loop"))
        self.btn_snapshot_video.configure(text=self.t("btn_snapshot_video"))

        # 5. Вебкамера вкладка
        self.lbl_webcam_cam.configure(text=self.t("lbl_camera"))
        self.combo_camera_idx.configure(values=[self.t("camera_name", idx=0), self.t("camera_name", idx=1), self.t("camera_name", idx=2)])
        cam_btn_txt = self.t("btn_start_webcam") if not self.is_webcam_running else self.t("btn_stop_webcam")
        self.btn_toggle_webcam.configure(text=cam_btn_txt)
        self.btn_webcam_cmd.configure(text=self.t("btn_open_cmd"))
        self.btn_snapshot_webcam.configure(text=self.t("btn_snapshot_webcam"))

        # 6. Оновлення полотен
        expand_txt = self.t("btn_collapse") if self.is_expanded else self.t("btn_expand")
        for canvas_frame in (self.ascii_canvas, self.orig_canvas, self.video_canvas, self.webcam_canvas):
            if hasattr(canvas_frame, "update_ui_texts"):
                canvas_frame.update_ui_texts(
                    btn_fit=self.t("btn_fit"),
                    btn_100=self.t("btn_100"),
                    btn_expand=expand_txt,
                    hint=self.t("hint_canvas"),
                )

        self.ascii_canvas.canvas.placeholder_text = self.t("placeholder_photo")
        self.orig_canvas.canvas.placeholder_text = self.t("placeholder_orig")
        self.video_canvas.canvas.placeholder_text = self.t("placeholder_video")
        self.webcam_canvas.canvas.placeholder_text = self.t("placeholder_webcam")
        self._refit_current_canvas()
        self.cached_settings = self.get_current_settings()

    # ==========================
    # РОЗШИРЕННЯ ТА ПОВНИЙ ЕКРАН
    # ==========================
    def toggle_expand_view(self):
        """Розгортає область перегляду на всю ширину вікна, приховуючи бічні панелі з плавною анімацією."""
        if getattr(self, "_is_animating_panel", False):
            return

        self.is_expanded = not self.is_expanded
        btn_text = self.t("btn_collapse") if self.is_expanded else self.t("btn_expand")

        for canvas_frame in (self.ascii_canvas, self.orig_canvas, self.video_canvas, self.webcam_canvas):
            if hasattr(canvas_frame, "set_expand_btn_text"):
                canvas_frame.set_expand_btn_text(btn_text)

        self._animate_panels_transition(self.is_expanded)

    def _animate_panels_transition(self, collapsing: bool):
        self._is_animating_panel = True
        steps = [280, 210, 140, 70, 0] if collapsing else [70, 140, 210, 280]

        if not collapsing:
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
            self.main_container.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
            self.settings_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 15), pady=15)

        def _step(i=0):
            if i < len(steps):
                w = steps[i]
                try:
                    self.settings_frame.configure(width=max(10, w))
                except Exception:
                    pass
                self.after(14, lambda: _step(i + 1))
            else:
                if collapsing:
                    self.sidebar_frame.grid_remove()
                    self.settings_frame.grid_remove()
                    self.main_container.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=8, pady=8)
                else:
                    self.settings_frame.configure(width=280)
                self._is_animating_panel = False
                self._refit_current_canvas()

        _step(0)

    def _refit_current_canvas(self):
        if self.current_mode == "image":
            self.ascii_canvas.canvas.redraw()
        elif self.current_mode == "video":
            self.video_canvas.canvas.redraw()
        elif self.current_mode == "webcam":
            self.webcam_canvas.canvas.redraw()

    def toggle_fullscreen(self):
        """Перемикає повноекранний режим (F11)."""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    def on_escape_pressed(self):
        """При натисканні ESC повертаємо панелі або виходимо з повного екрану."""
        if self.is_fullscreen:
            self.toggle_fullscreen()
        elif self.is_expanded:
            self.toggle_expand_view()

    # ==========================
    # ЗАПУСК У КОНСОЛІ (CMD)
    # ==========================
    def launch_cmd_interactive(self):
        """Відкриває інтерактивне меню ASCII у новому вікні Windows CMD."""
        script_path = str((Path(__file__).parent / "main.py").resolve())
        py_exe = get_console_python()
        cmd_list = [py_exe, script_path, "--cli", "--mode", "menu"]
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10) if sys.platform == "win32" else 0
        try:
            subprocess.Popen(cmd_list, creationflags=creationflags)
        except Exception as e:
            messagebox.showerror(self.t("dialog_saved_title"), self.t("dialog_cmd_error", err=e))

    def launch_cmd_process(self, mode: str, path: str = "", camera: int = 0, title: str = ""):
        """Запускає конкретний режим (фото, відео, вебку) у новому вікні CMD."""
        opts = self.get_current_settings()
        script_path = str((Path(__file__).parent / "main.py").resolve())
        py_exe = get_console_python()

        is_color = 1 if opts["color_mode"] not in ("Monochrome (White)", "Монохромний (Білий)") else 0
        cmd_list = [
            py_exe,
            script_path,
            "--cli",
            "--mode", mode,
            "--width", str(opts["width"]),
            "--color", str(is_color),
            "--charset", opts["char_set"],
            "--invert", "1" if opts["invert"] else "0",
        ]

        if mode in ("image", "video") and path:
            cmd_list.extend(["--path", str(path)])
        elif mode == "webcam":
            cmd_list.extend(["--camera", str(camera)])

        if title:
            cmd_list.extend(["--title", str(title)])

        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10) if sys.platform == "win32" else 0
        try:
            subprocess.Popen(cmd_list, creationflags=creationflags)
        except Exception as e:
            messagebox.showerror("Error", self.t("dialog_cmd_error", err=e))

    def open_image_in_cmd(self):
        if self.current_orig_image is None:
            messagebox.showwarning("Notice", self.t("dialog_warn_no_img"))
            return

        temp_path = str((Path(__file__).parent / "_cmd_preview.png").resolve())
        try:
            _, buf = cv2.imencode(".png", self.current_orig_image)
            buf.tofile(temp_path)
            target_path = temp_path
        except Exception:
            target_path = self.current_image_path or temp_path

        orig_name = Path(self.current_image_path).name if self.current_image_path else "Photo"
        self.launch_cmd_process(mode="image", path=target_path, title=orig_name)

    def open_video_in_cmd(self):
        if not self.current_video_path or not Path(self.current_video_path).exists():
            messagebox.showwarning("Notice", self.t("dialog_warn_no_vid"))
            return

        self.pause_video()
        self.launch_cmd_process(mode="video", path=self.current_video_path)

    def open_webcam_in_cmd(self):
        if self.is_webcam_running:
            self.stop_webcam()

        self.launch_cmd_process(mode="webcam", camera=self.camera_index)

    # ==========================
    # 1. РЕЖИМ ФОТО
    # ==========================
    def _build_image_view(self):
        self.image_view_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.image_view_frame.grid_columnconfigure(0, weight=1)
        self.image_view_frame.grid_rowconfigure(1, weight=1)

        # Верхня панель дій
        top_bar = ctk.CTkFrame(self.image_view_frame, height=50)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.btn_open_img = ctk.CTkButton(
            top_bar,
            text=self.t("btn_open_photo"),
            width=135,
            command=self.open_image_dialog,
        )
        self.btn_open_img.pack(side="left", padx=(10, 4), pady=8)

        self.btn_open_cmd = ctk.CTkButton(
            top_bar,
            text=self.t("btn_open_cmd"),
            width=140,
            state="disabled",
            fg_color="#34495e",
            hover_color="#2c3e50",
            command=self.open_image_in_cmd,
        )
        self.btn_open_cmd.pack(side="left", padx=4, pady=8)

        self.btn_save_png = ctk.CTkButton(
            top_bar,
            text=self.t("btn_save_png"),
            width=125,
            state="disabled",
            command=self.save_as_png,
        )
        self.btn_save_png.pack(side="left", padx=4, pady=8)

        self.btn_save_txt = ctk.CTkButton(
            top_bar,
            text=self.t("btn_save_txt"),
            width=125,
            state="disabled",
            command=self.save_as_txt,
        )
        self.btn_save_txt.pack(side="left", padx=4, pady=8)

        self.btn_save_html = ctk.CTkButton(
            top_bar,
            text=self.t("btn_save_html"),
            width=135,
            state="disabled",
            command=self.save_as_html,
        )
        self.btn_save_html.pack(side="left", padx=4, pady=8)

        self.btn_copy_text = ctk.CTkButton(
            top_bar,
            text=self.t("btn_copy_text"),
            width=135,
            state="disabled",
            fg_color="gray30",
            hover_color="gray40",
            command=self.copy_ascii_to_clipboard,
        )
        self.btn_copy_text.pack(side="left", padx=4, pady=8)

        self.btn_fullscreen_img = ctk.CTkButton(
            top_bar,
            text=self.t("btn_fullscreen"),
            width=150,
            fg_color="gray25",
            hover_color="gray35",
            command=self.toggle_fullscreen,
        )
        self.btn_fullscreen_img.pack(side="right", padx=10, pady=8)

        # Таби попереднього перегляду
        self.image_tabs = ctk.CTkTabview(self.image_view_frame)
        self.image_tabs.grid(row=1, column=0, sticky="nsew")

        tab_render = self.image_tabs.add(self.t("tab_ascii_render"))
        tab_text = self.image_tabs.add(self.t("tab_plain_text"))
        tab_orig = self.image_tabs.add(self.t("tab_original"))

        # 1. ASCII Render tab
        tab_render.grid_columnconfigure(0, weight=1)
        tab_render.grid_rowconfigure(0, weight=1)
        self.ascii_canvas = ZoomableImageFrame(
            tab_render,
            placeholder_text=self.t("placeholder_photo"),
            on_expand_toggle=self.toggle_expand_view,
        )
        self.ascii_canvas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Спінер завантаження / рендерингу поверх полотна
        self.spinner = LoadingSpinner(tab_render, text=self.t("status_rendering"))

        # 2. Plain Text tab
        tab_text.grid_columnconfigure(0, weight=1)
        tab_text.grid_rowconfigure(1, weight=1)

        text_zoom_bar = ctk.CTkFrame(tab_text, height=36, corner_radius=8, fg_color=("gray85", "#1e222a"))
        text_zoom_bar.grid(row=0, column=0, sticky="ew", padx=10, pady=(5, 5))

        ctk.CTkButton(
            text_zoom_bar,
            text="A➖",
            width=36,
            height=26,
            command=lambda: self._change_text_font_size(-1),
        ).pack(side="left", padx=(8, 4), pady=4)

        self.lbl_text_font = ctk.CTkLabel(
            text_zoom_bar,
            text=self.t("lbl_font_size", val=self.text_font_size),
            width=90,
            font=ctk.CTkFont(size=12, weight="bold"),
        )
        self.lbl_text_font.pack(side="left", padx=2, pady=4)

        ctk.CTkButton(
            text_zoom_bar,
            text="A➕",
            width=36,
            height=26,
            command=lambda: self._change_text_font_size(+1),
        ).pack(side="left", padx=(2, 8), pady=4)

        self.btn_reset_font = ctk.CTkButton(
            text_zoom_bar,
            text=self.t("btn_reset_font"),
            width=110,
            height=26,
            fg_color="gray30",
            hover_color="gray40",
            command=lambda: self._set_text_font_size(10),
        )
        self.btn_reset_font.pack(side="left", padx=4, pady=4)

        self.lbl_hint_text_font = ctk.CTkLabel(
            text_zoom_bar,
            text=self.t("hint_text_font"),
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self.lbl_hint_text_font.pack(side="right", padx=12, pady=4)

        self.txt_ascii_display = ctk.CTkTextbox(
            tab_text,
            font=ctk.CTkFont(family="Consolas", size=self.text_font_size),
            wrap="none",
        )
        self.txt_ascii_display.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.txt_ascii_display.bind("<Control-MouseWheel>", self._on_text_wheel_zoom)

        # 3. Original tab
        tab_orig.grid_columnconfigure(0, weight=1)
        tab_orig.grid_rowconfigure(0, weight=1)
        self.orig_canvas = ZoomableImageFrame(
            tab_orig,
            placeholder_text=self.t("placeholder_orig"),
            on_expand_toggle=self.toggle_expand_view,
        )
        self.orig_canvas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    def _change_text_font_size(self, delta: int):
        new_size = max(5, min(36, self.text_font_size + delta))
        self._set_text_font_size(new_size)

    def _set_text_font_size(self, size: int):
        self.text_font_size = size
        self.lbl_text_font.configure(text=self.t("lbl_font_size", val=self.text_font_size))
        self.txt_ascii_display.configure(font=ctk.CTkFont(family="Consolas", size=self.text_font_size))

    def _on_text_wheel_zoom(self, event):
        delta = 1 if event.delta > 0 else -1
        self._change_text_font_size(delta)
        return "break"

    def open_image_dialog(self):
        filetypes = [
            (self.t("filetypes_img"), "*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.ico"),
            (self.t("filetypes_all"), "*.*"),
        ]
        file_path = filedialog.askopenfilename(title=self.t("btn_open_photo"), filetypes=filetypes)
        if not file_path:
            return

        self.load_image(file_path)

    def load_image(self, file_path: str):
        frame = None
        try:
            data = np.fromfile(str(file_path).strip('"'), dtype=np.uint8)
            if data.size > 0:
                frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
        except Exception:
            pass

        if frame is None:
            try:
                pil_img = Image.open(file_path).convert("RGB")
                frame = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
            except Exception as e:
                messagebox.showerror("Error", self.t("dialog_img_error", err=e))
                return

        self.current_image_path = file_path
        self.current_orig_image = frame

        orig_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        orig_pil = Image.fromarray(orig_rgb)
        self.orig_canvas.set_image(orig_pil, reset_fit=True)

        self.btn_open_cmd.configure(state="normal")
        self.btn_save_png.configure(state="normal")
        self.btn_save_txt.configure(state="normal")
        self.btn_save_html.configure(state="normal")
        self.btn_copy_text.configure(state="normal")

        self.render_current_image(reset_fit=True)

    def render_current_image(self, reset_fit: bool = False, on_complete=None):
        if self.current_orig_image is None:
            if on_complete:
                on_complete()
            return

        self._render_generation += 1
        gen = self._render_generation
        self._is_rendering = True

        if hasattr(self, "spinner") and self.spinner:
            self.spinner.show()

        opts = self.get_current_settings()
        frame_copy = self.current_orig_image.copy()

        def _worker():
            try:
                rendered_pil, plain_text, rgb_grid, text_grid = self.engine.process_frame(
                    frame_copy,
                    width=opts["width"],
                    char_set=opts["char_set"],
                    color_mode=opts["color_mode"],
                    contrast=opts["contrast"],
                    brightness=opts["brightness"],
                    invert=opts["invert"],
                    generate_text=True,
                )
            except Exception as e:
                rendered_pil, plain_text, rgb_grid, text_grid = None, f"Error: {e}", None, None

            self._post_ui_task(self._apply_rendered_image, gen, rendered_pil, plain_text, rgb_grid, text_grid, reset_fit, on_complete)

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _apply_rendered_image(self, gen, rendered_pil, plain_text, rgb_grid, text_grid, reset_fit, on_complete=None):
        if gen != self._render_generation:
            return

        self._is_rendering = False
        if hasattr(self, "spinner") and self.spinner:
            self.spinner.hide()

        if rendered_pil is not None:
            self.last_rendered_pil = rendered_pil
            self.last_rendered_text = plain_text
            self.last_rgb_grid = rgb_grid
            self.last_text_grid = text_grid

            self.txt_ascii_display.delete("1.0", "end")
            self.txt_ascii_display.insert("1.0", plain_text)

            self.ascii_canvas.set_image(rendered_pil, reset_fit=reset_fit)

        if on_complete:
            try:
                on_complete()
            except Exception:
                pass

    def save_as_png(self, export_path: str = None):
        if self.last_rendered_pil is None:
            return None
        default_name = "ascii_art.png"
        if self.current_image_path:
            default_name = f"{Path(self.current_image_path).stem}_ascii.png"
        path = export_path
        if not path:
            path = filedialog.asksaveasfilename(
                title=self.t("btn_save_png"),
                defaultextension=".png",
                initialfile=default_name,
                filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg")],
            )
        if path:
            self.last_rendered_pil.save(path)
            if not export_path:
                messagebox.showinfo(self.t("dialog_saved_title"), self.t("dialog_saved_msg", path=path))
            return path
        return None

    def save_as_txt(self, export_path: str = None):
        if not self.last_rendered_text:
            return None
        default_name = "ascii_art.txt"
        if self.current_image_path:
            default_name = f"{Path(self.current_image_path).stem}_ascii.txt"
        path = export_path
        if not path:
            path = filedialog.asksaveasfilename(
                title=self.t("btn_save_txt"),
                defaultextension=".txt",
                initialfile=default_name,
                filetypes=[("Text File", "*.txt")],
            )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.last_rendered_text)
            if not export_path:
                messagebox.showinfo(self.t("dialog_saved_title"), self.t("dialog_saved_msg", path=path))
            return path
        return None

    def save_as_html(self, export_path: str = None):
        if self.last_text_grid is None or self.last_rgb_grid is None:
            return None
        default_name = "ascii_art.html"
        if self.current_image_path:
            default_name = f"{Path(self.current_image_path).stem}_ascii.html"
        path = export_path
        if not path:
            path = filedialog.asksaveasfilename(
                title=self.t("btn_save_html"),
                defaultextension=".html",
                initialfile=default_name,
                filetypes=[("HTML Webpage", "*.html")],
            )
        if path:
            title = Path(path).stem
            AsciiEngine.export_html(self.last_text_grid, self.last_rgb_grid, path, title=title)
            if not export_path:
                messagebox.showinfo(self.t("dialog_saved_title"), self.t("dialog_saved_msg", path=path))
            return path
        return None

    def copy_ascii_to_clipboard(self):
        if self.last_rendered_text:
            self.clipboard_clear()
            self.clipboard_append(self.last_rendered_text)
            messagebox.showinfo(self.t("dialog_copied_title"), self.t("dialog_copied_msg"))

    # ==========================
    # 2. РЕЖИМ ВІДЕО
    # ==========================
    def _build_video_view(self):
        self.video_view_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.video_view_frame.grid_columnconfigure(0, weight=1)
        self.video_view_frame.grid_rowconfigure(2, weight=1)

        # Верхня панель дій
        top_bar = ctk.CTkFrame(self.video_view_frame, height=50)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.btn_open_video = ctk.CTkButton(
            top_bar,
            text=self.t("btn_open_video"),
            width=135,
            command=self.open_video_dialog,
        )
        self.btn_open_video.pack(side="left", padx=8, pady=8)

        self.btn_video_cmd = ctk.CTkButton(
            top_bar,
            text=self.t("btn_open_cmd"),
            width=140,
            state="disabled",
            fg_color="#34495e",
            hover_color="#2c3e50",
            command=self.open_video_in_cmd,
        )
        self.btn_video_cmd.pack(side="left", padx=4, pady=8)

        self.btn_play_pause = ctk.CTkButton(
            top_bar,
            text=self.t("btn_play"),
            width=120,
            state="disabled",
            fg_color="#2ecc71",
            hover_color="#27ae60",
            command=self.toggle_video_play,
        )
        self.btn_play_pause.pack(side="left", padx=4, pady=8)

        self.btn_stop_video = ctk.CTkButton(
            top_bar,
            text=self.t("btn_stop"),
            width=100,
            state="disabled",
            fg_color="gray30",
            hover_color="gray40",
            command=self.stop_video,
        )
        self.btn_stop_video.pack(side="left", padx=4, pady=8)

        self.switch_loop = ctk.CTkSwitch(top_bar, text=self.t("switch_loop"), command=self._on_loop_switch_changed)
        self.switch_loop.select()
        self.video_loop = True
        self.switch_loop.pack(side="left", padx=10, pady=8)

        self.btn_snapshot_video = ctk.CTkButton(
            top_bar,
            text=self.t("btn_snapshot_video"),
            width=135,
            state="disabled",
            command=self.save_video_snapshot,
        )
        self.btn_snapshot_video.pack(side="right", padx=10, pady=8)

        # Панель таймлайну
        timeline_bar = ctk.CTkFrame(self.video_view_frame, height=35)
        timeline_bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        timeline_bar.grid_columnconfigure(1, weight=1)

        self.lbl_video_time = ctk.CTkLabel(timeline_bar, text="00:00 / 00:00", width=100)
        self.lbl_video_time.grid(row=0, column=0, padx=10, pady=5)

        self.slider_timeline = ctk.CTkSlider(
            timeline_bar,
            from_=0,
            to=100,
            command=self._on_seek_video,
        )
        self.slider_timeline.set(0)
        self.slider_timeline.grid(row=0, column=1, sticky="ew", padx=10, pady=5)

        self.lbl_video_fps = ctk.CTkLabel(timeline_bar, text="FPS: --", width=70)
        self.lbl_video_fps.grid(row=0, column=2, padx=10, pady=5)

        # Дисплей відео з інтерактивним зумом
        self.video_canvas = ZoomableImageFrame(
            self.video_view_frame,
            placeholder_text=self.t("placeholder_video"),
            on_expand_toggle=self.toggle_expand_view,
        )
        self.video_canvas.grid(row=2, column=0, sticky="nsew")

    def _on_loop_switch_changed(self):
        self.video_loop = bool(self.switch_loop.get())

    def open_video_dialog(self):
        filetypes = [
            (self.t("filetypes_vid"), "*.mp4 *.avi *.mkv *.mov *.wmv *.webm *.flv"),
            (self.t("filetypes_all"), "*.*"),
        ]
        file_path = filedialog.askopenfilename(title=self.t("btn_open_video"), filetypes=filetypes)
        if not file_path:
            return

        self.load_video(file_path)

    def load_video(self, file_path: str):
        self.stop_video()

        self.video_cap = open_video_unicode(file_path)
        if not self.video_cap.isOpened():
            messagebox.showerror("Error", self.t("dialog_vid_error", err=file_path))
            return

        self.current_video_path = file_path
        self.video_total_frames = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.video_fps = self.video_cap.get(cv2.CAP_PROP_FPS)
        if self.video_fps <= 0 or np.isnan(self.video_fps):
            self.video_fps = 30.0

        self.slider_timeline.configure(from_=0, to=max(1, self.video_total_frames - 1))
        self.slider_timeline.set(0)

        self.btn_video_cmd.configure(state="normal")
        self.btn_play_pause.configure(state="normal")
        self.btn_stop_video.configure(state="normal")
        self.btn_snapshot_video.configure(state="normal")

        ret, frame = self.video_cap.read()
        if ret:
            self._render_single_video_frame(frame, reset_fit=True)
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    def toggle_video_play(self):
        if self.is_video_playing:
            self.pause_video()
        else:
            self.play_video()

    def play_video(self):
        if self.video_cap is None:
            return
        self.is_video_playing = True
        self.btn_play_pause.configure(text=self.t("btn_pause"), fg_color="#e67e22", hover_color="#d35400")

        if self.video_thread is None or not self.video_thread.is_alive():
            self.video_thread = threading.Thread(target=self._video_worker, daemon=True)
            self.video_thread.start()

    def pause_video(self):
        self.is_video_playing = False
        if self.video_thread is not None and self.video_thread.is_alive():
            try:
                self.video_thread.join(timeout=0.35)
            except Exception:
                pass
            self.video_thread = None
        self.btn_play_pause.configure(text=self.t("btn_resume"), fg_color="#2ecc71", hover_color="#27ae60")

    def stop_video(self):
        self.is_video_playing = False
        if self.video_thread is not None and self.video_thread.is_alive():
            try:
                self.video_thread.join(timeout=0.35)
            except Exception:
                pass
            self.video_thread = None

        if self.video_cap is not None:
            try:
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            except Exception:
                pass
        self.btn_play_pause.configure(text=self.t("btn_play"), fg_color="#2ecc71", hover_color="#27ae60")
        self.slider_timeline.set(0)
        self.lbl_video_time.configure(text="00:00 / 00:00")
        self.lbl_video_fps.configure(text="FPS: --")

    def _on_seek_video(self, value):
        if self.video_cap is not None:
            target_frame = int(value)
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
            if not self.is_video_playing:
                ret, frame = self.video_cap.read()
                if ret:
                    self._render_single_video_frame(frame, reset_fit=False)
                    self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)

    def _video_worker(self):
        target_delay = 1.0 / self.video_fps
        fps_tracker_t = time.time()
        fps_counter = 0

        while self.is_video_playing and self.video_cap is not None and self.video_cap.isOpened():
            start_t = time.time()

            ret, frame = self.video_cap.read()
            if not ret:
                if getattr(self, "video_loop", True):
                    self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    self._post_ui_task(self.stop_video)
                    break

            curr_frame_idx = int(self.video_cap.get(cv2.CAP_PROP_POS_FRAMES))

            opts = self.get_thread_safe_settings()
            pil_img, _, _, _ = self.engine.process_frame(
                frame,
                width=opts["width"],
                char_set=opts["char_set"],
                color_mode=opts["color_mode"],
                contrast=opts["contrast"],
                brightness=opts["brightness"],
                invert=opts["invert"],
                generate_text=False,
            )

            fps_counter += 1
            if time.time() - fps_tracker_t >= 1.0:
                cur_fps = fps_counter / (time.time() - fps_tracker_t)
                fps_tracker_t = time.time()
                fps_counter = 0
                self._post_ui_task(self._set_video_fps_label, cur_fps)

            self._post_ui_task(self._update_video_ui, pil_img, curr_frame_idx)

            elapsed = time.time() - start_t
            sleep_t = target_delay - elapsed
            if sleep_t > 0.001:
                time.sleep(sleep_t)

    def _render_single_video_frame(self, frame, reset_fit: bool = False):
        opts = self.get_current_settings()
        pil_img, _, _, _ = self.engine.process_frame(
            frame,
            width=opts["width"],
            char_set=opts["char_set"],
            color_mode=opts["color_mode"],
            contrast=opts["contrast"],
            brightness=opts["brightness"],
            invert=opts["invert"],
        )
        self.last_video_frame_pil = pil_img
        self.video_canvas.set_image(pil_img, reset_fit=reset_fit)
        frame_idx = int(self.video_cap.get(cv2.CAP_PROP_POS_FRAMES)) if self.video_cap else 0
        self._update_timeline_labels(frame_idx)

    def _update_video_ui(self, pil_img, frame_idx):
        if self.current_mode != "video":
            return

        self.last_video_frame_pil = pil_img
        self.video_canvas.set_image(pil_img, reset_fit=False)
        self._update_timeline_labels(frame_idx)

    def _update_timeline_labels(self, frame_idx):
        self.slider_timeline.set(frame_idx)
        cur_sec = int(frame_idx / max(1.0, self.video_fps))
        tot_sec = int(self.video_total_frames / max(1.0, self.video_fps))
        cur_str = f"{cur_sec // 60:02d}:{cur_sec % 60:02d}"
        tot_str = f"{tot_sec // 60:02d}:{tot_sec % 60:02d}"
        self.lbl_video_time.configure(text=f"{cur_str} / {tot_str}")

    def save_video_snapshot(self, export_path: str = None):
        if hasattr(self, "last_video_frame_pil") and self.last_video_frame_pil:
            path = export_path
            if not path:
                path = filedialog.asksaveasfilename(
                    title=self.t("btn_snapshot_video"),
                    defaultextension=".png",
                    initialfile="video_frame_ascii.png",
                    filetypes=[("PNG Image", "*.png")],
                )
            if path:
                self.last_video_frame_pil.save(path)
                if not export_path:
                    messagebox.showinfo(self.t("dialog_saved_title"), self.t("dialog_saved_msg", path=path))
                return path
        return None

    # ==========================
    # 3. РЕЖИМ ВЕБКАМЕРИ
    # ==========================
    def _build_webcam_view(self):
        self.webcam_view_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.webcam_view_frame.grid_columnconfigure(0, weight=1)
        self.webcam_view_frame.grid_rowconfigure(1, weight=1)

        # Верхня панель дій
        top_bar = ctk.CTkFrame(self.webcam_view_frame, height=50)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        self.lbl_webcam_cam = ctk.CTkLabel(top_bar, text=self.t("lbl_camera"))
        self.lbl_webcam_cam.pack(side="left", padx=(10, 5), pady=8)

        self.combo_camera_idx = ctk.CTkOptionMenu(
            top_bar,
            values=[self.t("camera_name", idx=0), self.t("camera_name", idx=1), self.t("camera_name", idx=2)],
            width=110,
            command=self._on_camera_select,
        )
        self.combo_camera_idx.set(self.t("camera_name", idx=0))
        self.combo_camera_idx.pack(side="left", padx=5, pady=8)

        self.btn_toggle_webcam = ctk.CTkButton(
            top_bar,
            text=self.t("btn_start_webcam"),
            width=165,
            fg_color="#2ecc71",
            hover_color="#27ae60",
            command=self.toggle_webcam,
        )
        self.btn_toggle_webcam.pack(side="left", padx=6, pady=8)

        self.btn_webcam_cmd = ctk.CTkButton(
            top_bar,
            text=self.t("btn_open_cmd"),
            width=140,
            fg_color="#34495e",
            hover_color="#2c3e50",
            command=self.open_webcam_in_cmd,
        )
        self.btn_webcam_cmd.pack(side="left", padx=4, pady=8)

        self.btn_snapshot_webcam = ctk.CTkButton(
            top_bar,
            text=self.t("btn_snapshot_webcam"),
            width=140,
            state="disabled",
            command=self.take_webcam_snapshot,
        )
        self.btn_snapshot_webcam.pack(side="left", padx=4, pady=8)

        self.lbl_webcam_fps = ctk.CTkLabel(top_bar, text="FPS: --", width=80)
        self.lbl_webcam_fps.pack(side="right", padx=15, pady=8)

        # Дисплей вебкамери із зумом
        self.webcam_canvas = ZoomableImageFrame(
            self.webcam_view_frame,
            placeholder_text=self.t("placeholder_webcam"),
            on_expand_toggle=self.toggle_expand_view,
        )
        self.webcam_canvas.grid(row=1, column=0, sticky="nsew")

    def _on_camera_select(self, choice):
        try:
            self.camera_index = int(choice.split()[-1])
        except Exception:
            self.camera_index = 0

        if self.is_webcam_running:
            self.stop_webcam()
            self.start_webcam()

    def toggle_webcam(self):
        if self.is_webcam_running:
            self.stop_webcam()
        else:
            self.start_webcam()

    def start_webcam(self):
        self.webcam_cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not self.webcam_cap.isOpened():
            self.webcam_cap = cv2.VideoCapture(self.camera_index)
            if not self.webcam_cap.isOpened():
                messagebox.showerror("Error", self.t("dialog_cam_error", idx=self.camera_index))
                return

        self.is_webcam_running = True
        self.btn_toggle_webcam.configure(
            text=self.t("btn_stop_webcam"),
            fg_color="#e74c3c",
            hover_color="#c0392b",
        )
        self.btn_snapshot_webcam.configure(state="normal")
        self.webcam_canvas.canvas.is_fit = True

        self.webcam_thread = threading.Thread(target=self._webcam_worker, daemon=True)
        self.webcam_thread.start()

    def stop_webcam(self):
        self.is_webcam_running = False
        if self.webcam_thread is not None and self.webcam_thread.is_alive():
            try:
                self.webcam_thread.join(timeout=0.4)
            except Exception:
                pass
            self.webcam_thread = None

        if self.webcam_cap is not None:
            try:
                self.webcam_cap.release()
            except Exception:
                pass
            self.webcam_cap = None

        self.btn_toggle_webcam.configure(
            text=self.t("btn_start_webcam"),
            fg_color="#2ecc71",
            hover_color="#27ae60",
        )
        self.btn_snapshot_webcam.configure(state="disabled")
        self.lbl_webcam_fps.configure(text="FPS: --")

    def _webcam_worker(self):
        fps_tracker_t = time.time()
        fps_counter = 0

        while self.is_webcam_running and self.webcam_cap is not None and self.webcam_cap.isOpened():
            ret, frame = self.webcam_cap.read()
            if not ret:
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)
            self.last_webcam_raw_frame = frame.copy()

            opts = self.get_thread_safe_settings()
            pil_img, plain_text, rgb_grid, text_grid = self.engine.process_frame(
                frame,
                width=opts["width"],
                char_set=opts["char_set"],
                color_mode=opts["color_mode"],
                contrast=opts["contrast"],
                brightness=opts["brightness"],
                invert=opts["invert"],
                generate_text=False,
            )

            fps_counter += 1
            if time.time() - fps_tracker_t >= 1.0:
                cur_fps = fps_counter / (time.time() - fps_tracker_t)
                fps_tracker_t = time.time()
                fps_counter = 0
                self._post_ui_task(self._set_webcam_fps_label, cur_fps)

            self._post_ui_task(self._update_webcam_ui, pil_img)
            time.sleep(0.015)

    def _set_video_fps_label(self, val: float):
        try:
            self.lbl_video_fps.configure(text=f"FPS: {val:.1f}")
        except Exception:
            pass

    def _set_webcam_fps_label(self, val: float):
        try:
            self.lbl_webcam_fps.configure(text=f"FPS: {val:.1f}")
        except Exception:
            pass

    def _update_webcam_ui(self, pil_img):
        if self.current_mode != "webcam":
            return

        self.last_webcam_frame_pil = pil_img
        self.webcam_canvas.set_image(pil_img, reset_fit=False)

    def take_webcam_snapshot(self):
        if not hasattr(self, "last_webcam_raw_frame") or self.last_webcam_raw_frame is None:
            return

        self.current_orig_image = self.last_webcam_raw_frame.copy()
        self.current_image_path = "webcam_snapshot.png"

        orig_rgb = cv2.cvtColor(self.current_orig_image, cv2.COLOR_BGR2RGB)
        orig_pil = Image.fromarray(orig_rgb)
        self.orig_canvas.set_image(orig_pil, reset_fit=True)

        self.btn_open_cmd.configure(state="normal")
        self.btn_save_png.configure(state="normal")
        self.btn_save_txt.configure(state="normal")
        self.btn_save_html.configure(state="normal")
        self.btn_copy_text.configure(state="normal")

        self.switch_mode("image")
        self.render_current_image(reset_fit=True)
        messagebox.showinfo(self.t("dialog_snap_title"), self.t("dialog_snap_msg"))

    # ==========================
    # ПЕРЕМИКАННЯ РЕЖИМІВ
    # ==========================
    def switch_mode(self, mode: str):
        prev_mode = getattr(self, "current_mode", None)
        self.current_mode = mode

        # Безпечне призупинення/завершення попереднього фонового режиму
        if prev_mode == "video" and mode != "video":
            self.pause_video()
        elif prev_mode == "webcam" and mode != "webcam":
            self.stop_webcam()

        self.btn_nav_image.configure(
            fg_color=("gray75", "gray25") if mode == "image" else "transparent",
            font=ctk.CTkFont(size=14, weight="bold" if mode == "image" else "normal"),
        )
        self.btn_nav_video.configure(
            fg_color=("gray75", "gray25") if mode == "video" else "transparent",
            font=ctk.CTkFont(size=14, weight="bold" if mode == "video" else "normal"),
        )
        self.btn_nav_webcam.configure(
            fg_color=("gray75", "gray25") if mode == "webcam" else "transparent",
            font=ctk.CTkFont(size=14, weight="bold" if mode == "webcam" else "normal"),
        )

        target_frame = self.image_view_frame
        if mode == "video":
            target_frame = self.video_view_frame
        elif mode == "webcam":
            target_frame = self.webcam_view_frame

        # Плавний перехід між вкладками
        for frame in (self.image_view_frame, self.video_view_frame, self.webcam_view_frame):
            if frame != target_frame:
                frame.grid_forget()

        target_frame.grid(row=0, column=0, sticky="nsew")
        self.after(25, self._refit_current_canvas)

    def change_appearance_mode(self, mode_text: str):
        # Визначаємо вибраний режим за значенням
        dark_keys = (self.t("theme_dark"), "Dark", "Темна")
        light_keys = (self.t("theme_light"), "Light", "Світла")
        if mode_text in dark_keys:
            chosen = "Dark"
        elif mode_text in light_keys:
            chosen = "Light"
        else:
            chosen = "System"

        ctk.set_appearance_mode(chosen)
        is_dark = (chosen == "Dark")
        if hasattr(self, "ascii_canvas"):
            self.ascii_canvas.set_theme(is_dark)
        if hasattr(self, "orig_canvas"):
            self.orig_canvas.set_theme(is_dark)
        if hasattr(self, "video_canvas"):
            self.video_canvas.set_theme(is_dark)
        if hasattr(self, "webcam_canvas"):
            self.webcam_canvas.set_theme(is_dark)

    def on_close(self):
        self._is_closing = True
        if getattr(self, "_poll_timer_id", None):
            try:
                self.after_cancel(self._poll_timer_id)
            except Exception:
                pass
            self._poll_timer_id = None
        try:
            self.stop_video()
            if self.video_cap is not None:
                self.video_cap.release()
                self.video_cap = None
        except Exception:
            pass
        try:
            self.stop_webcam()
            if self.webcam_cap is not None:
                self.webcam_cap.release()
                self.webcam_cap = None
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass


def main(show_splash: bool = True):
    app = AsciiStudioApp(show_splash=show_splash)
    app.mainloop()


if __name__ == "__main__":
    main()
