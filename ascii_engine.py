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
    "Vaporwave (Sunset)",
    "Game Boy (1989)",
]

COLOR_MODES_UK = [
    "Повний колір (RGB)",
    "Монохромний (Білий)",
    "Матриця (Зелений)",
    "Ретро (Бурштиновий)",
    "Кіберпанк (Неон)",
    "Сепія (Вінтаж)",
    "Вейпорвейв (Захід)",
    "Геймбой (1989)",
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

    def _prepare_masks(self, char_set: str, include_edges: bool = False):
        full_set = char_set + "|-/\\" if include_edges else char_set
        if self._current_char_set == full_set and self._masks is not None:
            return

        self._current_char_set = full_set
        masks = []
        for ch in full_set:
            img = Image.new("L", (self._char_w, self._char_h), 0)
            draw = ImageDraw.Draw(img)
            draw.text((0, 0), ch, fill=255, font=self._font)
            arr = np.array(img, dtype=np.uint8)
            # 8-бітний бінарний масив (0 або 255) для миттєвого blit через cv2.copyTo
            mask = np.where(arr > 70, np.uint8(255), np.uint8(0))
            masks.append(mask)

        self._masks = np.array(masks, dtype=np.uint8)

    @staticmethod
    def _apply_dithering(gray_f32: np.ndarray, num_chars: int) -> np.ndarray:
        """
        Floyd-Steinberg error diffusion for ASCII character quantization.
        """
        h, w = gray_f32.shape
        arr = gray_f32.copy()
        max_idx = num_chars - 1
        scale = max_idx / 255.0
        inv_scale = 255.0 / max_idx if max_idx > 0 else 1.0

        indices = np.zeros((h, w), dtype=np.int32)
        for y in range(h):
            for x in range(w):
                old_val = arr[y, x]
                idx = int(np.clip(np.round(old_val * scale), 0, max_idx))
                indices[y, x] = idx
                err = old_val - (idx * inv_scale)

                if x + 1 < w:
                    arr[y, x + 1] += err * (7.0 / 16.0)
                if y + 1 < h:
                    if x > 0:
                        arr[y + 1, x - 1] += err * (3.0 / 16.0)
                    arr[y + 1, x] += err * (5.0 / 16.0)
                    if x + 1 < w:
                        arr[y + 1, x + 1] += err * (1.0 / 16.0)

        return indices

    @staticmethod
    def _detect_edges(gray_u8: np.ndarray, threshold: float = 55.0):
        """
        Detects directional contour lines using Sobel filters.
        Returns (edge_mask, edge_types) where edge_types: 0=vert, 1=horiz, 2=diag1 (/), 3=diag2 (\\)
        """
        gx = cv2.Sobel(gray_u8, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray_u8, cv2.CV_32F, 0, 1, ksize=3)
        mag = cv2.magnitude(gx, gy)
        edge_mask = mag > threshold

        angle = np.degrees(np.arctan2(gy, gx))
        abs_angle = np.abs(angle)

        edge_types = np.zeros(gray_u8.shape, dtype=np.int32)
        vert = (abs_angle < 22.5) | (abs_angle > 157.5)
        horiz = (abs_angle >= 67.5) & (abs_angle <= 112.5)
        diag1 = ((angle >= 22.5) & (angle < 67.5)) | ((angle >= -157.5) & (angle < -112.5))
        diag2 = ((angle >= 112.5) & (angle < 157.5)) | ((angle >= -67.5) & (angle < -22.5))

        edge_types[vert] = 0
        edge_types[horiz] = 1
        edge_types[diag1] = 2
        edge_types[diag2] = 3

        return edge_mask, edge_types

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
        dither: bool = False,
        edges: bool = False,
        crt: bool = False,
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

        self._prepare_masks(char_set, include_edges=edges)
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

        # 4. Швидкий розрахунок індексів символів (з підтримкою Floyd-Steinberg Dithering)
        if dither:
            indices = self._apply_dithering(gray.astype(np.float32), num_chars)
        else:
            indices = (gray.astype(np.float32) * ((num_chars - 1) / 255.0)).astype(np.int32).clip(0, num_chars - 1)

        # 4b. Опціональне накладання контурних ліній (Edge Detection)
        if edges:
            edge_mask, edge_types = self._detect_edges(gray)
            base_edge_idx = num_chars
            indices[edge_mask & (edge_types == 0)] = base_edge_idx      # |
            indices[edge_mask & (edge_types == 1)] = base_edge_idx + 1  # -
            indices[edge_mask & (edge_types == 2)] = base_edge_idx + 2  # /
            indices[edge_mask & (edge_types == 3)] = base_edge_idx + 3  # \

        # 5. Опціональна генерація текстового рядка (економить час під час стрімінгу відео)
        plain_text = ""
        text_grid = None
        full_char_list = list(char_set + "|-/\\" if edges else char_set)
        char_arr = np.array(full_char_list)
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
        elif "Vaporwave" in color_mode or "Вейпорвейв" in color_mode or "Sunset" in color_mode or "Захід" in color_mode:
            r = np.clip(gray.astype(np.float32) * 1.3, 0, 255).astype(np.uint8)
            g = (gray * 0.25).astype(np.uint8)
            b = np.clip(gray.astype(np.float32) * 1.45, 0, 255).astype(np.uint8)
            palette_small = np.stack([r, g, b], axis=-1)
        elif "Game Boy" in color_mode or "Геймбой" in color_mode or "1989" in color_mode:
            gb_palette = np.array([
                [15, 56, 15],
                [48, 98, 48],
                [139, 172, 15],
                [155, 188, 15]
            ], dtype=np.uint8)
            gb_idx = (gray.astype(np.float32) / 255.0 * 3.99).astype(np.int32).clip(0, 3)
            palette_small = gb_palette[gb_idx]
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

        # 10. Опціональний CRT Scanlines ефект
        if crt:
            rendered_img[::3] = (rendered_img[::3].astype(np.float32) * 0.65).astype(np.uint8)

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
