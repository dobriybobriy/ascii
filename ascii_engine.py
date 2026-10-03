import cv2
import numpy as np
from PIL import Image, ImageFont, ImageDraw
import html

# Пресети символів
CHAR_PRESETS = {
    "Стандартний (10 символів)": " .:-=+*#%@",
    "Детальний (70 символів)": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "Блоки (Символи псевдографіки)": " ░▒▓█",
    "Бінарний (0 та 1)": " 01",
    "Матриця (Цифри та код)": " 0123456789ABCDEF$#*",
    "Мінімалістичний": " .oO@",
}

COLOR_MODES = [
    "Повний колір (RGB)",
    "Монохромний (Білий)",
    "Матриця (Зелений)",
    "Ретро (Бурштиновий)",
    "Кіберпанк (Неон)",
    "Сепія (Вінтаж)",
]


class AsciiEngine:
    def __init__(self, font_size: int = 12):
        self.font_size = font_size
        self._current_char_set = ""
        self._font = None
        self._char_w = 7
        self._char_h = 12
        self._masks = None  # numpy boolean array (num_chars, char_h, char_w)
        self._init_font()

    def _init_font(self):
        # Намагаємося завантажити Consolas, Lucida Console або дефолтний моноширинний
        for font_name in ["consola.ttf", "consolab.ttf", "lucon.ttf", "cour.ttf"]:
            try:
                self._font = ImageFont.truetype(font_name, self.font_size)
                break
            except Exception:
                continue

        if self._font is None:
            self._font = ImageFont.load_default()

        # Визначаємо розміри символу
        bbox = self._font.getbbox("M")
        self._char_w = max(6, bbox[2] - bbox[0])
        self._char_h = max(10, bbox[3] - bbox[1] + 2)

    def _prepare_masks(self, char_set: str):
        if self._current_char_set == char_set and self._masks is not None:
            return

        self._current_char_set = char_set
        masks = []
        for ch in char_set:
            img = Image.new("L", (self._char_w, self._char_h), 0)
            draw = ImageDraw.Draw(img)
            draw.text((0, 0), ch, fill=255, font=self._font)
            mask = np.array(img) > 70
            masks.append(mask)

        self._masks = np.array(masks, dtype=bool)

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        width: int = 100,
        char_set: str = CHAR_PRESETS["Стандартний (10 символів)"],
        color_mode: str = "Повний колір (RGB)",
        contrast: float = 1.0,
        brightness: int = 0,
        invert: bool = False,
        bg_color: tuple = (16, 16, 20),
    ):
        """
        Обробляє BGR кадр OpenCV і повертає:
        1. PIL.Image (графічний рендер ASCII арт з вибраним кольоровим режимом)
        2. str (чистий текст)
        3. np.ndarray (RGB кольори для кожного символу для HTML експорту)
        """
        if not char_set:
            char_set = " .:-=+*#%@"

        self._prepare_masks(char_set)
        num_chars = len(char_set)

        orig_h, orig_w = frame_bgr.shape[:2]
        # Символи витягнуті вертикально (~1.7:1), тому коригуємо aspect ratio
        char_ratio = self._char_h / self._char_w  # приблизно 1.6 - 1.8
        target_w = max(10, width)
        target_h = max(5, int(target_w * (orig_h / orig_w) / char_ratio))

        # Зменшуємо кадр під сітку символів
        small_bgr = cv2.resize(frame_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)

        # Корекція яскравості та контрасту
        if contrast != 1.0 or brightness != 0:
            small_bgr = np.clip(contrast * small_bgr.astype(np.float32) + brightness, 0, 255).astype(np.uint8)

        # Конвертація в RGB
        small_rgb = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2RGB)

        # Отримуємо яскравість (Grayscale)
        gray = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2GRAY)

        if invert:
            gray = 255 - gray

        # Розрахунок індексів символів
        indices = (gray.astype(np.float32) / 255.0 * (num_chars - 1)).clip(0, num_chars - 1).astype(np.int32)

        # 1. Формуємо текстовий рядок
        char_arr = np.array(list(char_set))
        text_grid = char_arr[indices]
        text_lines = ["".join(row) for row in text_grid]
        plain_text = "\n".join(text_lines)

        # 2. Рендеримо зображення через векторизований масочний бліттінг
        out_h = target_h * self._char_h
        out_w = target_w * self._char_w

        # Розгортаємо маски під кожну позицію
        grid_masks = self._masks[indices].transpose(0, 2, 1, 3).reshape(out_h, out_w)

        # Визначаємо колірні шари
        rendered_img = np.full((out_h, out_w, 3), bg_color, dtype=np.uint8)

        if color_mode == "Повний колір (RGB)":
            grid_colors = np.repeat(np.repeat(small_rgb, self._char_h, axis=0), self._char_w, axis=1)
            rendered_img[grid_masks] = grid_colors[grid_masks]

        elif color_mode == "Монохромний (Білий)":
            # Робимо колір тексту залежним від яскравості або суцільним білим
            val = np.repeat(np.repeat(gray, self._char_h, axis=0), self._char_w, axis=1)
            rendered_img[grid_masks] = np.stack([val, val, val], axis=-1)[grid_masks]

        elif color_mode == "Матриця (Зелений)":
            val = np.repeat(np.repeat(gray, self._char_h, axis=0), self._char_w, axis=1)
            g = np.clip(val.astype(np.int16) + 40, 0, 255).astype(np.uint8)
            r = (val * 0.15).astype(np.uint8)
            b = (val * 0.25).astype(np.uint8)
            rendered_img[grid_masks] = np.stack([r, g, b], axis=-1)[grid_masks]

        elif color_mode == "Ретро (Бурштиновий)":
            val = np.repeat(np.repeat(gray, self._char_h, axis=0), self._char_w, axis=1)
            r = val
            g = (val * 0.7).astype(np.uint8)
            b = (val * 0.1).astype(np.uint8)
            rendered_img[grid_masks] = np.stack([r, g, b], axis=-1)[grid_masks]

        elif color_mode == "Кіберпанк (Неон)":
            val = np.repeat(np.repeat(gray, self._char_h, axis=0), self._char_w, axis=1)
            r = np.clip(val * 1.1, 0, 255).astype(np.uint8)
            g = (val * 0.3).astype(np.uint8)
            b = np.clip(val * 1.3, 0, 255).astype(np.uint8)
            rendered_img[grid_masks] = np.stack([r, g, b], axis=-1)[grid_masks]

        elif color_mode == "Сепія (Вінтаж)":
            val = np.repeat(np.repeat(gray, self._char_h, axis=0), self._char_w, axis=1)
            r = np.clip(val * 1.1, 0, 255).astype(np.uint8)
            g = np.clip(val * 0.9, 0, 255).astype(np.uint8)
            b = np.clip(val * 0.7, 0, 255).astype(np.uint8)
            rendered_img[grid_masks] = np.stack([r, g, b], axis=-1)[grid_masks]

        pil_image = Image.fromarray(rendered_img)
        return pil_image, plain_text, small_rgb, text_grid

    @staticmethod
    def export_html(text_grid: np.ndarray, rgb_grid: np.ndarray, file_path: str, title: str = "ASCII Art"):
        """
        Експортує ASCII у стильний автономний HTML файл з кольоровими символами.
        """
        h, w = text_grid.shape
        html_lines = [
            "<!DOCTYPE html>",
            "<html lang='uk'>",
            "<head>",
            "  <meta charset='utf-8'>",
            f"  <title>{html.escape(title)}</title>",
            "  <style>",
            "    body { background-color: #0d0f12; color: #f0f0f0; margin: 0; padding: 20px; font-family: 'Consolas', 'Courier New', monospace; font-size: 10px; line-height: 10px; letter-spacing: 0px; user-select: text; }",
            "    pre { margin: 0; white-space: pre; font-size: 11px; line-height: 0.95; }",
            "    .card { background: #181b20; border: 1px solid #2a2e39; border-radius: 12px; padding: 24px; display: inline-block; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }",
            "    h2 { font-family: sans-serif; font-size: 16px; color: #7aa2f7; margin-top: 0; }",
            "  </style>",
            "</head>",
            "<body>",
            "  <div class='card'>",
            f"    <h2>🎨 {html.escape(title)}</h2>",
            "    <pre>",
        ]

        for y in range(h):
            row_html = []
            for x in range(w):
                ch = html.escape(text_grid[y, x])
                r, g, b = rgb_grid[y, x]
                row_html.append(f"<span style='color:rgb({r},{g},{b})'>{ch}</span>")
            html_lines.append("".join(row_html))

        html_lines.extend([
            "    </pre>",
            "  </div>",
            "</body>",
            "</html>",
        ])

        with open(file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(html_lines))
