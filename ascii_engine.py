import cv2
import numpy as np
from PIL import Image, ImageFont, ImageDraw
import html

# Пресети символів (English & Ukrainian)
PRESETS_EN = {
    "Standard (10 chars)": " .:-=+*#%@",
    "Detailed (70 chars)": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "Blocks (Pseudographics)": " ░▒▓█",
    "Binary (0 and 1)": " 01",
    "Matrix (Digits & Code)": " 0123456789ABCDEF$#*",
    "Minimalist": " .oO@",
}

PRESETS_UK = {
    "Стандартний (10 символів)": " .:-=+*#%@",
    "Детальний (70 символів)": " .'`^\",:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
    "Блоки (Символи псевдографіки)": " ░▒▓█",
    "Бінарний (0 та 1)": " 01",
    "Матриця (Цифри та код)": " 0123456789ABCDEF$#*",
    "Мінімалістичний": " .oO@",
}

# За замовчуванням — англійська
CHAR_PRESETS = PRESETS_EN

COLOR_MODES_EN = [
    "Full Color (RGB)",
    "Monochrome (White)",
    "Matrix (Green)",
    "Retro (Amber)",
    "Cyberpunk (Neon)",
    "Sepia (Vintage)",
]

COLOR_MODES_UK = [
    "Повний колір (RGB)",
    "Монохромний (Білий)",
    "Матриця (Зелений)",
    "Ретро (Бурштиновий)",
    "Кіберпанк (Неон)",
    "Сепія (Вінтаж)",
]

# За замовчуванням — англійська
COLOR_MODES = COLOR_MODES_EN


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
            arr = np.array(img, dtype=np.uint8)
            # 8-бітний бінарний масив (0 або 255) для миттєвого blit через cv2.copyTo
            mask = np.where(arr > 70, np.uint8(255), np.uint8(0))
            masks.append(mask)

        self._masks = np.array(masks, dtype=np.uint8)

    def process_frame(
        self,
        frame_bgr: np.ndarray,
        width: int = 100,
        char_set: str = " .:-=+*#%@",
        color_mode: str = "Full Color (RGB)",
        contrast: float = 1.0,
        brightness: int = 0,
        invert: bool = False,
        bg_color: tuple = (16, 16, 20),
        generate_text: bool = True,
    ):
        """
        Високопродуктивна обробка кадру з повною SIMD-оптимізацією (cv2, numpy).
        Повертає:
        1. PIL.Image (графічний рендер ASCII арт з вибраним кольоровим режимом)
        2. str (чистий текст або порожній рядок, якщо generate_text=False)
        3. np.ndarray (RGB сітка для кожного символу)
        4. np.ndarray (сітка символів для експорту в HTML)
        """
        if not char_set:
            char_set = " .:-=+*#%@"

        self._prepare_masks(char_set)
        num_chars = len(char_set)

        orig_h, orig_w = frame_bgr.shape[:2]
        char_ratio = self._char_h / self._char_w
        target_w = max(10, width)
        target_h = max(5, int(target_w * (orig_h / orig_w) / char_ratio))

        # 1. Зменшуємо кадр під сітку символів
        small_bgr = cv2.resize(frame_bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)

        # 2. Корекція яскравості та контрасту
        if contrast != 1.0 or brightness != 0:
            small_bgr = np.clip(contrast * small_bgr.astype(np.float32) + brightness, 0, 255).astype(np.uint8)

        # 3. Конвертація в RGB та Gray
        small_rgb = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2GRAY)

        if invert:
            gray = 255 - gray

        # 4. Швидкий розрахунок індексів символів
        indices = (gray.astype(np.float32) * ((num_chars - 1) / 255.0)).astype(np.int32).clip(0, num_chars - 1)

        # 5. Опціональна генерація текстового рядка (економить час під час стрімінгу відео)
        plain_text = ""
        text_grid = None
        char_arr = np.array(list(char_set))
        if generate_text:
            text_grid = char_arr[indices]
            text_lines = ["".join(row) for row in text_grid]
            plain_text = "\n".join(text_lines)
        else:
            text_grid = char_arr[indices]

        # 6. Розрахунок колірної палітри на МАЛІЙ сітці (у 80+ разів швидше, ніж на розгорнутій)
        if "Color" in color_mode or "Колір" in color_mode or "RGB" in color_mode:
            palette_small = small_rgb
        elif "Monochrome" in color_mode or "Монохром" in color_mode or "White" in color_mode or "Білий" in color_mode:
            palette_small = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        elif "Matrix" in color_mode or "Матриця" in color_mode or "Green" in color_mode or "Зелен" in color_mode:
            g = np.clip(gray.astype(np.int16) + 40, 0, 255).astype(np.uint8)
            r = (gray * 0.15).astype(np.uint8)
            b = (gray * 0.25).astype(np.uint8)
            palette_small = np.stack([r, g, b], axis=-1)
        elif "Retro" in color_mode or "Amber" in color_mode or "Ретро" in color_mode or "Бурштин" in color_mode:
            r = gray
            g = (gray * 0.7).astype(np.uint8)
            b = (gray * 0.1).astype(np.uint8)
            palette_small = np.stack([r, g, b], axis=-1)
        elif "Cyberpunk" in color_mode or "Neon" in color_mode or "Кіберпанк" in color_mode or "Неон" in color_mode:
            r = np.clip(gray.astype(np.float32) * 1.1, 0, 255).astype(np.uint8)
            g = (gray * 0.3).astype(np.uint8)
            b = np.clip(gray.astype(np.float32) * 1.3, 0, 255).astype(np.uint8)
            palette_small = np.stack([r, g, b], axis=-1)
        elif "Sepia" in color_mode or "Сепія" in color_mode or "Vintage" in color_mode or "Вінтаж" in color_mode:
            r = np.clip(gray.astype(np.float32) * 1.1, 0, 255).astype(np.uint8)
            g = np.clip(gray.astype(np.float32) * 0.9, 0, 255).astype(np.uint8)
            b = np.clip(gray.astype(np.float32) * 0.7, 0, 255).astype(np.uint8)
            palette_small = np.stack([r, g, b], axis=-1)
        else:
            palette_small = small_rgb

        # 7. Швидке масштабування кольорів через апаратний SIMD (INTER_NEAREST)
        out_h = target_h * self._char_h
        out_w = target_w * self._char_w
        grid_colors = cv2.resize(palette_small, (out_w, out_h), interpolation=cv2.INTER_NEAREST)

        # 8. Складання маски символів
        grid_masks = np.ascontiguousarray(self._masks[indices].transpose(0, 2, 1, 3).reshape(out_h, out_w))

        # 9. Миттєвий бліттінг через оптимізований cv2.copyTo
        rendered_img = np.empty((out_h, out_w, 3), dtype=np.uint8)
        rendered_img[:] = bg_color
        cv2.copyTo(grid_colors, grid_masks, rendered_img)

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
