import os
import sys
import time
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk
import cv2
import numpy as np

from ascii_engine import AsciiEngine, CHAR_PRESETS, COLOR_MODES
from zoom_canvas import ZoomableImageFrame


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


class AsciiStudioApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("ASCII Studio Pro — Відео, Фото та Вебкамера")
        self.geometry("1300x850")
        self.minsize(980, 680)

        # Автоматичне розгортання вікна на весь екран при запуску
        self.after(60, lambda: self.state("zoomed"))

        # Двигунець рендерингу
        self.engine = AsciiEngine(font_size=12)

        # Стан додатку
        self.current_mode = "image"  # 'image', 'video', 'webcam'
        self.text_font_size = 10
        self.is_expanded = False
        self.is_fullscreen = False

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

        # Обробка закриття програми
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        # Головна сітка: зліва навігація, по центру робоча зона, праворуч панель налаштувань
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
            text="Art & Video Generator",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.sub_logo_label.grid(row=1, column=0, padx=20, pady=(0, 20))

        # Кнопки навігації
        self.btn_nav_image = ctk.CTkButton(
            self.sidebar_frame,
            text="🖼️  Фото",
            height=40,
            anchor="w",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self.switch_mode("image"),
        )
        self.btn_nav_image.grid(row=2, column=0, padx=15, pady=6, sticky="ew")

        self.btn_nav_video = ctk.CTkButton(
            self.sidebar_frame,
            text="🎬  Відео",
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
            text="📹  Вебкамера",
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
            text="💻  Консоль (CMD)",
            height=36,
            anchor="w",
            font=ctk.CTkFont(size=13),
            fg_color="#2c3e50",
            hover_color="#34495e",
            command=self.launch_cmd_interactive,
        )
        self.btn_sidebar_cmd.grid(row=5, column=0, padx=15, pady=(15, 6), sticky="ew")

        # Нижня частина сайдбару
        self.appearance_label = ctk.CTkLabel(self.sidebar_frame, text="Тема оформлення:", font=ctk.CTkFont(size=11))
        self.appearance_label.grid(row=7, column=0, padx=20, pady=(10, 0), sticky="w")

        self.appearance_menu = ctk.CTkOptionMenu(
            self.sidebar_frame,
            values=["Темна", "Світла", "Системна"],
            command=self.change_appearance_mode,
            height=28,
        )
        self.appearance_menu.grid(row=8, column=0, padx=15, pady=(4, 20), sticky="ew")

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
        self.settings_frame = ctk.CTkScrollableFrame(self, width=280, label_text="⚙️ Параметри ASCII")
        self.settings_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 15), pady=15)
        self.settings_frame.grid_columnconfigure(0, weight=1)

        # 1. Ширина в символах
        self.lbl_width = ctk.CTkLabel(
            self.settings_frame,
            text="Ширина: 100 символів",
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
        ctk.CTkLabel(
            self.settings_frame,
            text="Набір символів:",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 2))

        preset_names = list(CHAR_PRESETS.keys()) + ["Власний набір..."]
        self.combo_presets = ctk.CTkOptionMenu(
            self.settings_frame,
            values=preset_names,
            command=self._on_preset_changed,
        )
        self.combo_presets.set(preset_names[0])
        self.combo_presets.pack(fill="x", padx=10, pady=(0, 5))

        self.entry_custom_chars = ctk.CTkEntry(
            self.settings_frame,
            placeholder_text="Введіть власні символи...",
        )
        self.entry_custom_chars.insert(0, CHAR_PRESETS["Стандартний (10 символів)"])
        self.entry_custom_chars.bind("<KeyRelease>", lambda e: self._on_setting_changed())
        self.entry_custom_chars.pack(fill="x", padx=10, pady=(0, 15))

        # 3. Колірний режим
        ctk.CTkLabel(
            self.settings_frame,
            text="Колірна палітра:",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).pack(fill="x", padx=10, pady=(0, 2))

        self.combo_colors = ctk.CTkOptionMenu(
            self.settings_frame,
            values=COLOR_MODES,
            command=lambda val: self._on_setting_changed(),
        )
        self.combo_colors.set(COLOR_MODES[0])
        self.combo_colors.pack(fill="x", padx=10, pady=(0, 15))

        # 4. Перемикач інверсії
        self.switch_invert = ctk.CTkSwitch(
            self.settings_frame,
            text="Інвертувати яскравість",
            command=self._on_setting_changed,
        )
        self.switch_invert.pack(fill="x", padx=10, pady=(0, 15))

        # 5. Контрастність
        self.lbl_contrast = ctk.CTkLabel(
            self.settings_frame,
            text="Контраст: 1.0x",
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
            text="Яскравість: 0",
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
            text="Скинути налаштування",
            fg_color="gray30",
            hover_color="gray40",
            command=self._reset_settings,
        )
        self.btn_reset_settings.pack(fill="x", padx=10, pady=(10, 10))

    def _reset_settings(self):
        self.slider_width.set(100)
        self.lbl_width.configure(text="Ширина: 100 символів")
        self.combo_presets.set(list(CHAR_PRESETS.keys())[0])
        self.entry_custom_chars.delete(0, "end")
        self.entry_custom_chars.insert(0, CHAR_PRESETS["Стандартний (10 символів)"])
        self.combo_colors.set(COLOR_MODES[0])
        self.switch_invert.deselect()
        self.slider_contrast.set(1.0)
        self.lbl_contrast.configure(text="Контраст: 1.0x")
        self.slider_brightness.set(0)
        self.lbl_brightness.configure(text="Яскравість: 0")
        self._on_setting_changed()

    def _on_width_changed(self, value):
        val = int(value)
        self.lbl_width.configure(text=f"Ширина: {val} символів")
        self._on_setting_changed()

    def _on_contrast_changed(self, value):
        self.lbl_contrast.configure(text=f"Контраст: {value:.2f}x")
        self._on_setting_changed()

    def _on_brightness_changed(self, value):
        self.lbl_brightness.configure(text=f"Яскравість: {int(value)}")
        self._on_setting_changed()

    def _on_preset_changed(self, choice):
        if choice in CHAR_PRESETS:
            self.entry_custom_chars.delete(0, "end")
            self.entry_custom_chars.insert(0, CHAR_PRESETS[choice])
        self._on_setting_changed()

    def _on_setting_changed(self):
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

    # ==========================
    # РОЗШИРЕННЯ ТА ПОВНИЙ ЕКРАН
    # ==========================
    def toggle_expand_view(self):
        """Розгортає область перегляду на всю ширину вікна, приховуючи бічні панелі."""
        self.is_expanded = not self.is_expanded

        if self.is_expanded:
            self.sidebar_frame.grid_remove()
            self.settings_frame.grid_remove()
            self.main_container.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=8, pady=8)
            btn_text = "↩️ Показати панелі"
        else:
            self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
            self.main_container.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
            self.settings_frame.grid(row=0, column=2, sticky="nsew", padx=(0, 15), pady=15)
            btn_text = "⛶ Розширити область"

        # Оновлюємо текст на кнопках розширення у всіх полотнах
        for canvas_frame in (self.ascii_canvas, self.orig_canvas, self.video_canvas, self.webcam_canvas):
            if hasattr(canvas_frame, "set_expand_btn_text"):
                canvas_frame.set_expand_btn_text(btn_text)

        # Оновлюємо розміри полотен
        self.after(50, self._refit_current_canvas)

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
        cmd_list = [sys.executable, script_path, "--cli", "--mode", "menu"]
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10) if sys.platform == "win32" else 0
        try:
            subprocess.Popen(cmd_list, creationflags=creationflags)
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося відкрити CMD:\n{e}")

    def launch_cmd_process(self, mode: str, path: str = "", camera: int = 0):
        """Запускає конкретний режим (фото, відео, вебку) у новому вікні CMD."""
        opts = self.get_current_settings()
        script_path = str((Path(__file__).parent / "main.py").resolve())

        is_color = 1 if opts["color_mode"] != "Монохромний (Білий)" else 0
        cmd_list = [
            sys.executable,
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

        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x10) if sys.platform == "win32" else 0
        try:
            subprocess.Popen(cmd_list, creationflags=creationflags)
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося запустити CMD:\n{e}")

    def open_image_in_cmd(self):
        if self.current_orig_image is None:
            messagebox.showwarning("Увага", "Спочатку відкрийте зображення!")
            return

        target_path = self.current_image_path
        # Якщо файл не існує або це знімок, зберігаємо тимчасовий PNG через imencode
        if not target_path or not Path(target_path).exists():
            temp_path = str((Path(__file__).parent / "_cmd_preview.png").resolve())
            _, buf = cv2.imencode(".png", self.current_orig_image)
            buf.tofile(temp_path)
            target_path = temp_path

        self.launch_cmd_process(mode="image", path=target_path)

    def open_video_in_cmd(self):
        if not self.current_video_path or not Path(self.current_video_path).exists():
            messagebox.showwarning("Увага", "Спочатку відкрийте відеофайл!")
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

        btn_open = ctk.CTkButton(
            top_bar,
            text="📂 Відкрити фото",
            width=135,
            command=self.open_image_dialog,
        )
        btn_open.pack(side="left", padx=(10, 4), pady=8)

        self.btn_open_cmd = ctk.CTkButton(
            top_bar,
            text="💻 Відкрити в CMD",
            width=140,
            state="disabled",
            fg_color="#34495e",
            hover_color="#2c3e50",
            command=self.open_image_in_cmd,
        )
        self.btn_open_cmd.pack(side="left", padx=4, pady=8)

        self.btn_save_png = ctk.CTkButton(
            top_bar,
            text="🖼️ Зберегти PNG",
            width=125,
            state="disabled",
            command=self.save_as_png,
        )
        self.btn_save_png.pack(side="left", padx=4, pady=8)

        self.btn_save_txt = ctk.CTkButton(
            top_bar,
            text="📄 Зберегти TXT",
            width=125,
            state="disabled",
            command=self.save_as_txt,
        )
        self.btn_save_txt.pack(side="left", padx=4, pady=8)

        self.btn_save_html = ctk.CTkButton(
            top_bar,
            text="🌐 Експорт в HTML",
            width=135,
            state="disabled",
            command=self.save_as_html,
        )
        self.btn_save_html.pack(side="left", padx=4, pady=8)

        self.btn_copy_text = ctk.CTkButton(
            top_bar,
            text="📋 Копіювати текст",
            width=135,
            state="disabled",
            fg_color="gray30",
            hover_color="gray40",
            command=self.copy_ascii_to_clipboard,
        )
        self.btn_copy_text.pack(side="left", padx=4, pady=8)

        # Кнопка розгортання вікна на повний екран
        self.btn_fullscreen_img = ctk.CTkButton(
            top_bar,
            text="⛶ Повний екран (F11)",
            width=150,
            fg_color="gray25",
            hover_color="gray35",
            command=self.toggle_fullscreen,
        )
        self.btn_fullscreen_img.pack(side="right", padx=10, pady=8)

        # Таби попереднього перегляду (Графіка / Текст / Оригінал)
        self.image_tabs = ctk.CTkTabview(self.image_view_frame)
        self.image_tabs.grid(row=1, column=0, sticky="nsew")

        tab_render = self.image_tabs.add("🎨 ASCII Рендер (Зум)")
        tab_text = self.image_tabs.add("📝 Чистий Текст")
        tab_orig = self.image_tabs.add("🔍 Оригінал (Зум)")

        # 1. ASCII Рендер таб із зумованим полотном
        tab_render.grid_columnconfigure(0, weight=1)
        tab_render.grid_rowconfigure(0, weight=1)
        self.ascii_canvas = ZoomableImageFrame(
            tab_render,
            placeholder_text="Натисніть «Відкрити фото», щоб розпочати 🖼️",
            on_expand_toggle=self.toggle_expand_view,
        )
        self.ascii_canvas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # 2. Чистий текст таб з масштабуванням шрифту
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
            text=f"Шрифт: {self.text_font_size} pt",
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

        ctk.CTkButton(
            text_zoom_bar,
            text="Скинути (10 pt)",
            width=110,
            height=26,
            fg_color="gray30",
            hover_color="gray40",
            command=lambda: self._set_text_font_size(10),
        ).pack(side="left", padx=4, pady=4)

        ctk.CTkLabel(
            text_zoom_bar,
            text="💡 Ctrl + Коліщатко миші змінює розмір шрифту",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        ).pack(side="right", padx=12, pady=4)

        self.txt_ascii_display = ctk.CTkTextbox(
            tab_text,
            font=ctk.CTkFont(family="Consolas", size=self.text_font_size),
            wrap="none",
        )
        self.txt_ascii_display.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.txt_ascii_display.bind("<Control-MouseWheel>", self._on_text_wheel_zoom)

        # 3. Оригінал таб із зумованим полотном
        tab_orig.grid_columnconfigure(0, weight=1)
        tab_orig.grid_rowconfigure(0, weight=1)
        self.orig_canvas = ZoomableImageFrame(
            tab_orig,
            placeholder_text="Оригінальне фото з'явиться тут",
            on_expand_toggle=self.toggle_expand_view,
        )
        self.orig_canvas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

    def _change_text_font_size(self, delta: int):
        new_size = max(5, min(36, self.text_font_size + delta))
        self._set_text_font_size(new_size)

    def _set_text_font_size(self, size: int):
        self.text_font_size = size
        self.lbl_text_font.configure(text=f"Шрифт: {self.text_font_size} pt")
        self.txt_ascii_display.configure(font=ctk.CTkFont(family="Consolas", size=self.text_font_size))

    def _on_text_wheel_zoom(self, event):
        delta = 1 if event.delta > 0 else -1
        self._change_text_font_size(delta)
        return "break"

    def open_image_dialog(self):
        filetypes = [
            ("Зображення", "*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.ico"),
            ("Всі файли", "*.*"),
        ]
        file_path = filedialog.askopenfilename(title="Оберіть зображення", filetypes=filetypes)
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
                messagebox.showerror("Помилка", f"Не вдалося відкрити зображення:\n{e}")
                return

        self.current_image_path = file_path
        self.current_orig_image = frame

        orig_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        orig_pil = Image.fromarray(orig_rgb)
        self.orig_canvas.set_image(orig_pil, reset_fit=True)

        # Активуємо кнопки збереження та CMD
        self.btn_open_cmd.configure(state="normal")
        self.btn_save_png.configure(state="normal")
        self.btn_save_txt.configure(state="normal")
        self.btn_save_html.configure(state="normal")
        self.btn_copy_text.configure(state="normal")

        # Рендеримо
        self.render_current_image(reset_fit=True)

    def render_current_image(self, reset_fit: bool = False):
        if self.current_orig_image is None:
            return

        opts = self.get_current_settings()
        rendered_pil, plain_text, rgb_grid, text_grid = self.engine.process_frame(
            self.current_orig_image,
            width=opts["width"],
            char_set=opts["char_set"],
            color_mode=opts["color_mode"],
            contrast=opts["contrast"],
            brightness=opts["brightness"],
            invert=opts["invert"],
        )

        self.last_rendered_pil = rendered_pil
        self.last_rendered_text = plain_text
        self.last_rgb_grid = rgb_grid
        self.last_text_grid = text_grid

        # Відображення тексту
        self.txt_ascii_display.delete("1.0", "end")
        self.txt_ascii_display.insert("1.0", plain_text)

        # Відображаємо в зумованому полотні
        self.ascii_canvas.set_image(rendered_pil, reset_fit=reset_fit)

    def save_as_png(self):
        if self.last_rendered_pil is None:
            return
        default_name = "ascii_art.png"
        if self.current_image_path:
            default_name = f"{Path(self.current_image_path).stem}_ascii.png"
        path = filedialog.asksaveasfilename(
            title="Зберегти ASCII як зображення",
            defaultextension=".png",
            initialfile=default_name,
            filetypes=[("PNG Image", "*.png"), ("JPEG Image", "*.jpg")],
        )
        if path:
            self.last_rendered_pil.save(path)
            messagebox.showinfo("Успіх", f"Зображення збережено в:\n{path}")

    def save_as_txt(self):
        if not self.last_rendered_text:
            return
        default_name = "ascii_art.txt"
        if self.current_image_path:
            default_name = f"{Path(self.current_image_path).stem}_ascii.txt"
        path = filedialog.asksaveasfilename(
            title="Зберегти ASCII текст",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("Текстовий файл", "*.txt")],
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.last_rendered_text)
            messagebox.showinfo("Успіх", f"Текст збережено в:\n{path}")

    def save_as_html(self):
        if self.last_text_grid is None or self.last_rgb_grid is None:
            return
        default_name = "ascii_art.html"
        if self.current_image_path:
            default_name = f"{Path(self.current_image_path).stem}_ascii.html"
        path = filedialog.asksaveasfilename(
            title="Експортувати в HTML",
            defaultextension=".html",
            initialfile=default_name,
            filetypes=[("HTML вебсторінка", "*.html")],
        )
        if path:
            title = Path(path).stem
            AsciiEngine.export_html(self.last_text_grid, self.last_rgb_grid, path, title=title)
            messagebox.showinfo("Успіх", f"Кольоровий HTML файл збережено:\n{path}")

    def copy_ascii_to_clipboard(self):
        if self.last_rendered_text:
            self.clipboard_clear()
            self.clipboard_append(self.last_rendered_text)
            messagebox.showinfo("Скопійовано", "ASCII текст скопійовано в буфер обміну!")

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

        btn_open = ctk.CTkButton(
            top_bar,
            text="📂 Відкрити відео",
            width=135,
            command=self.open_video_dialog,
        )
        btn_open.pack(side="left", padx=8, pady=8)

        self.btn_video_cmd = ctk.CTkButton(
            top_bar,
            text="💻 Відкрити в CMD",
            width=140,
            state="disabled",
            fg_color="#34495e",
            hover_color="#2c3e50",
            command=self.open_video_in_cmd,
        )
        self.btn_video_cmd.pack(side="left", padx=4, pady=8)

        self.btn_play_pause = ctk.CTkButton(
            top_bar,
            text="▶️ Відтворити",
            width=120,
            state="disabled",
            fg_color="#2ecc71",
            hover_color="#27ae60",
            command=self.toggle_video_play,
        )
        self.btn_play_pause.pack(side="left", padx=4, pady=8)

        self.btn_stop_video = ctk.CTkButton(
            top_bar,
            text="⏹️ Зупинити",
            width=100,
            state="disabled",
            fg_color="gray30",
            hover_color="gray40",
            command=self.stop_video,
        )
        self.btn_stop_video.pack(side="left", padx=4, pady=8)

        self.switch_loop = ctk.CTkSwitch(top_bar, text="Зациклити")
        self.switch_loop.select()
        self.switch_loop.pack(side="left", padx=10, pady=8)

        self.btn_snapshot_video = ctk.CTkButton(
            top_bar,
            text="📸 Зберегти кадр",
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
            placeholder_text="Відкрийте відеофайл (MP4, AVI, MOV...), щоб переглянути його в ASCII 🎬",
            on_expand_toggle=self.toggle_expand_view,
        )
        self.video_canvas.grid(row=2, column=0, sticky="nsew")

    def open_video_dialog(self):
        filetypes = [
            ("Відеофайли", "*.mp4 *.avi *.mkv *.mov *.wmv *.webm *.flv"),
            ("Всі файли", "*.*"),
        ]
        file_path = filedialog.askopenfilename(title="Оберіть відео", filetypes=filetypes)
        if not file_path:
            return

        self.load_video(file_path)

    def load_video(self, file_path: str):
        self.stop_video()

        self.video_cap = open_video_unicode(file_path)
        if not self.video_cap.isOpened():
            messagebox.showerror("Помилка", f"Не вдалося відкрити відео:\n{file_path}")
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

        # Читаємо та рендеримо перший кадр
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
        self.btn_play_pause.configure(text="⏸️ Пауза", fg_color="#e67e22", hover_color="#d35400")

        if self.video_thread is None or not self.video_thread.is_alive():
            self.video_thread = threading.Thread(target=self._video_worker, daemon=True)
            self.video_thread.start()

    def pause_video(self):
        self.is_video_playing = False
        self.btn_play_pause.configure(text="▶️ Продовжити", fg_color="#2ecc71", hover_color="#27ae60")

    def stop_video(self):
        self.is_video_playing = False
        if self.video_cap is not None:
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        self.btn_play_pause.configure(text="▶️ Відтворити", fg_color="#2ecc71", hover_color="#27ae60")
        self.slider_timeline.set(0)
        self.lbl_video_time.configure(text="00:00 / 00:00")

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
                if self.switch_loop.get():
                    self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    self.after(0, self.stop_video)
                    break

            curr_frame_idx = int(self.video_cap.get(cv2.CAP_PROP_POS_FRAMES))

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

            fps_counter += 1
            if time.time() - fps_tracker_t >= 1.0:
                cur_fps = fps_counter / (time.time() - fps_tracker_t)
                fps_tracker_t = time.time()
                fps_counter = 0
                self.after(0, lambda f=cur_fps: self.lbl_video_fps.configure(text=f"FPS: {f:.1f}"))

            self.after(0, lambda img=pil_img, idx=curr_frame_idx: self._update_video_ui(img, idx))

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

    def save_video_snapshot(self):
        if hasattr(self, "last_video_frame_pil") and self.last_video_frame_pil:
            path = filedialog.asksaveasfilename(
                title="Зберегти поточний кадр",
                defaultextension=".png",
                initialfile="video_frame_ascii.png",
                filetypes=[("PNG Image", "*.png")],
            )
            if path:
                self.last_video_frame_pil.save(path)
                messagebox.showinfo("Збережено", f"Кадр збережено:\n{path}")

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

        ctk.CTkLabel(top_bar, text="Камера:").pack(side="left", padx=(10, 5), pady=8)

        self.combo_camera_idx = ctk.CTkOptionMenu(
            top_bar,
            values=["Камера 0", "Камера 1", "Камера 2"],
            width=110,
            command=self._on_camera_select,
        )
        self.combo_camera_idx.set("Камера 0")
        self.combo_camera_idx.pack(side="left", padx=5, pady=8)

        self.btn_toggle_webcam = ctk.CTkButton(
            top_bar,
            text="🟢 Запустити камеру",
            width=165,
            fg_color="#2ecc71",
            hover_color="#27ae60",
            command=self.toggle_webcam,
        )
        self.btn_toggle_webcam.pack(side="left", padx=6, pady=8)

        self.btn_webcam_cmd = ctk.CTkButton(
            top_bar,
            text="💻 Відкрити в CMD",
            width=140,
            fg_color="#34495e",
            hover_color="#2c3e50",
            command=self.open_webcam_in_cmd,
        )
        self.btn_webcam_cmd.pack(side="left", padx=4, pady=8)

        self.btn_snapshot_webcam = ctk.CTkButton(
            top_bar,
            text="📸 Зробити знімок",
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
            placeholder_text="Натисніть «Запустити камеру» для ASCII стрімінгу в реальному часі 📹",
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
                messagebox.showerror("Помилка", f"Не вдалося відкрити вебкамеру #{self.camera_index}!")
                return

        self.is_webcam_running = True
        self.btn_toggle_webcam.configure(
            text="🔴 Зупинити камеру",
            fg_color="#e74c3c",
            hover_color="#c0392b",
        )
        self.btn_snapshot_webcam.configure(state="normal")
        self.webcam_canvas.canvas.is_fit = True

        self.webcam_thread = threading.Thread(target=self._webcam_worker, daemon=True)
        self.webcam_thread.start()

    def stop_webcam(self):
        self.is_webcam_running = False
        if self.webcam_cap is not None:
            self.webcam_cap.release()
            self.webcam_cap = None
        self.btn_toggle_webcam.configure(
            text="🟢 Запустити камеру",
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

            opts = self.get_current_settings()
            pil_img, plain_text, rgb_grid, text_grid = self.engine.process_frame(
                frame,
                width=opts["width"],
                char_set=opts["char_set"],
                color_mode=opts["color_mode"],
                contrast=opts["contrast"],
                brightness=opts["brightness"],
                invert=opts["invert"],
            )

            fps_counter += 1
            if time.time() - fps_tracker_t >= 1.0:
                cur_fps = fps_counter / (time.time() - fps_tracker_t)
                fps_tracker_t = time.time()
                fps_counter = 0
                self.after(0, lambda f=cur_fps: self.lbl_webcam_fps.configure(text=f"FPS: {f:.1f}"))

            self.after(0, lambda img=pil_img: self._update_webcam_ui(img))
            time.sleep(0.015)

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
        messagebox.showinfo("Знімок готовий", "Знімок з вебкамери успішно перенесено у вкладку «Фото»! Тепер його можна масштабувати, налаштувати, зберегти або відкрити в CMD.")

    # ==========================
    # ПЕРЕМИКАННЯ РЕЖИМІВ
    # ==========================
    def switch_mode(self, mode: str):
        self.current_mode = mode

        # Оновлення кнопок сайдбару
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

        # Ховаємо всі контейнери
        self.image_view_frame.grid_forget()
        self.video_view_frame.grid_forget()
        self.webcam_view_frame.grid_forget()

        # Показуємо обраний
        if mode == "image":
            self.image_view_frame.grid(row=0, column=0, sticky="nsew")
        elif mode == "video":
            self.video_view_frame.grid(row=0, column=0, sticky="nsew")
        elif mode == "webcam":
            self.webcam_view_frame.grid(row=0, column=0, sticky="nsew")

    def change_appearance_mode(self, mode: str):
        mode_map = {"Темна": "Dark", "Світла": "Light", "Системна": "System"}
        chosen = mode_map.get(mode, "Dark")
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
        self.stop_video()
        self.stop_webcam()
        self.destroy()


def main():
    app = AsciiStudioApp()
    app.mainloop()


if __name__ == "__main__":
    main()
