import os
import sys
import time
import argparse
from pathlib import Path
import cv2
import numpy as np

# Налаштовуємо UTF-8 для виводу в консоль Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Увімкнення UTF-8 та ANSI-кольорів у терміналі Windows
os.system("chcp 65001 > nul 2>&1")
os.system("")

# Градієнт символів за замовчуванням
ASCII_CHARS = " .:-=+*#%@"


def read_image_unicode(image_path: str):
    """
    Надійно зчитує зображення з шляхів, що містять пробіли або кирилицю (наприклад, 'Робочий стіл').
    """
    clean_path = str(image_path).strip('"')
    try:
        data = np.fromfile(clean_path, dtype=np.uint8)
        if data.size > 0:
            img = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if img is not None:
                return img
    except Exception:
        pass

    img = cv2.imread(clean_path)
    if img is not None:
        return img

    try:
        from PIL import Image
        pil_img = Image.open(clean_path).convert("RGB")
        return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception:
        return None


def open_video_unicode(video_source):
    """
    Надійно відкриває відео або вебкамеру навіть якщо шлях містить кирилицю.
    """
    if isinstance(video_source, int):
        return cv2.VideoCapture(video_source)

    clean_path = str(video_source).strip('"')
    cap = cv2.VideoCapture(clean_path)
    if cap.isOpened():
        return cap

    # Спроба отримати коротке ім'я Windows 8.3 (GetShortPathName)
    try:
        import win32api
        short_path = win32api.GetShortPathName(clean_path)
        cap = cv2.VideoCapture(short_path)
        if cap.isOpened():
            return cap
    except Exception:
        pass

    return cap


def frame_to_ascii(frame, width: int = 100, color: bool = True, char_set: str = ASCII_CHARS, invert: bool = False):
    """
    Конвертує один кадр зображення у рядок з ASCII-символів.
    Повертає (арт_рядок, розрахована_висота).
    """
    if not char_set:
        char_set = ASCII_CHARS

    h, w, _ = frame.shape
    aspect_ratio = h / w
    height = int(width * aspect_ratio * 0.5)
    if height < 1:
        height = 1

    resized = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    if invert:
        gray = 255 - gray

    num_chars = len(char_set)
    char_indices = (gray.astype(np.float32) / 255.0 * (num_chars - 1)).clip(0, num_chars - 1).astype(np.int32)

    lines = []
    for y in range(height):
        line_chars = []
        for x in range(width):
            char = char_set[char_indices[y, x]]
            if color:
                b, g, r = resized[y, x]
                line_chars.append(f"\033[38;2;{r};{g};{b}m{char}")
            else:
                line_chars.append(char)

        if color:
            line_chars.append("\033[0m")
        lines.append("".join(line_chars))

    return "\n".join(lines), height


def setup_console_size(width: int, height: int):
    """Підганяє розмір вікна CMD під розмір ASCII арту, щоб не було розривів рядків."""
    try:
        cols = max(90, width + 4)
        lines = max(30, height + 8)
        os.system(f"mode con: cols={cols} lines={lines} > nul 2>&1")
    except Exception:
        pass


def convert_image(
    image_path: str,
    width: int = 100,
    color: bool = True,
    char_set: str = ASCII_CHARS,
    invert: bool = False,
    output_txt: str = "ascii_photo.txt",
    display_title: str = "",
):
    """Converts a photo to ASCII and displays it in the console."""
    frame = read_image_unicode(image_path)
    if frame is None:
        print(f"[!] Could not open image: {image_path}")
        print("Press Enter to exit...")
        try:
            input()
        except Exception:
            pass
        return

    ascii_art, height = frame_to_ascii(frame, width=width, color=color, char_set=char_set, invert=invert)
    setup_console_size(width, height)

    title_name = display_title if display_title else Path(image_path).name
    print("\033[2J\033[H", end="")
    print(f"=== ASCII PHOTO: {title_name} (Width: {width}, Color: {'ON' if color else 'OFF'}) ===")
    print("-" * min(width, 80))
    print(ascii_art)
    print("-" * min(width, 80))

    # Save clean text to file
    plain_art, _ = frame_to_ascii(frame, width=width, color=False, char_set=char_set, invert=invert)
    try:
        with open(output_txt, "w", encoding="utf-8") as f:
            f.write(plain_art)
        print(f"[OK] Result also saved to: {output_txt}")
    except Exception as e:
        print(f"[!] Failed to save text file: {e}")

    print("\nPress Enter to close window...")
    try:
        input()
    except (KeyboardInterrupt, EOFError):
        pass


def play_video(
    video_path,
    width: int = 90,
    color: bool = True,
    char_set: str = ASCII_CHARS,
    invert: bool = False,
    is_webcam: bool = False,
):
    """Plays video or webcam feed in the terminal using ASCII characters."""
    import msvcrt

    cap = open_video_unicode(video_path)
    if not cap.isOpened():
        src_name = "webcam" if is_webcam else f"video: {video_path}"
        print(f"[!] Could not open {src_name}")
        print("Press Enter to exit...")
        try:
            input()
        except Exception:
            pass
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0 or np.isnan(fps) or is_webcam:
        fps = 30.0
    frame_time = 1.0 / fps

    ret, sample_frame = cap.read()
    if not ret:
        print("[!] Could not read initial frame.")
        cap.release()
        return

    if is_webcam:
        sample_frame = cv2.flip(sample_frame, 1)

    _, height = frame_to_ascii(sample_frame, width=width, color=color, char_set=char_set, invert=invert)
    setup_console_size(width, height)

    if not is_webcam:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    title_str = "LIVE WEBCAM" if is_webcam else f"VIDEO: {Path(str(video_path)).name}"
    print(f"\033[2J\033[H=== {title_str} (FPS: {fps:.1f}) ===")
    print("Press 'q' or Ctrl + C to stop")
    time.sleep(1)

    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        while True:
            start_t = time.time()
            ret, frame = cap.read()
            if not ret:
                if not is_webcam:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                else:
                    break

            if is_webcam:
                frame = cv2.flip(frame, 1)

            ascii_frame, _ = frame_to_ascii(frame, width=width, color=color, char_set=char_set, invert=invert)

            sys.stdout.write("\033[H" + ascii_frame)
            sys.stdout.flush()

            if msvcrt.kbhit():
                key = msvcrt.getch().lower()
                if key in (b'q', b'\x1b', b'\x03'):
                    break

            elapsed = time.time() - start_t
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        pass
    finally:
        cap.release()
        sys.stdout.write("\033[?25h\033[0m\n")
        sys.stdout.flush()
        print("\nPlayback stopped. Press Enter to exit...")
        try:
            input()
        except (KeyboardInterrupt, EOFError):
            pass


def run_cli_interactive():
    print("=" * 60)
    print("       ASCII STUDIO — CONSOLE MODE (CMD)       ")
    print("=" * 60)
    print("1. Play VIDEO in terminal as ASCII")
    print("2. Convert PHOTO to ASCII (+ save to .txt)")
    print("3. Stream WEBCAM in real-time")
    print("4. Launch Graphical Application (GUI)")

    choice = input("\nSelect action (1, 2, 3 or 4) [1]: ").strip() or "1"

    if choice == "4":
        from app import main as start_gui
        start_gui()
        return

    color_input = input("Enable 24-bit ANSI colors? (y/n) [y]: ").strip().lower()
    is_color = color_input != 'n'

    w_input = input("Width in characters (70-160) [100]: ").strip()
    try:
        width = int(w_input)
    except ValueError:
        width = 100

    if choice == "1":
        file_path = input("Enter video file path: ").strip().strip('"')
        play_video(file_path, width=width, color=is_color)
    elif choice == "2":
        file_path = input("Enter photo file path: ").strip().strip('"')
        convert_image(file_path, width=width, color=is_color)
    elif choice == "3":
        cam_idx = input("Camera index [0]: ").strip()
        try:
            cam_idx = int(cam_idx)
        except ValueError:
            cam_idx = 0
        play_video(cam_idx, width=width, color=is_color, is_webcam=True)


def parse_and_run_cli():
    try:
        # Якщо запущено без консолі (наприклад, через pythonw), примусово створюємо її
        if sys.platform == "win32":
            try:
                import ctypes
                if ctypes.windll.kernel32.GetConsoleWindow() == 0 and (sys.stdin is None or not hasattr(sys.stdin, "fileno")):
                    ctypes.windll.kernel32.AllocConsole()
                    sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
                    sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
                    sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
            except Exception:
                pass

        parser = argparse.ArgumentParser(description="ASCII Studio CLI Runner")
        parser.add_argument("--cli", action="store_true", help="Запустити в консольному режимі")
        parser.add_argument("--mode", choices=["image", "video", "webcam", "menu"], default="menu")
        parser.add_argument("--path", type=str, default="")
        parser.add_argument("--width", type=int, default=100)
        parser.add_argument("--color", type=int, default=1)
        parser.add_argument("--camera", type=int, default=0)
        parser.add_argument("--charset", type=str, default=ASCII_CHARS)
        parser.add_argument("--invert", type=int, default=0)
        parser.add_argument("--title", type=str, default="")

        args, _ = parser.parse_known_args()

        if sys.platform == "win32":
            try:
                import ctypes
                mode_str = args.title or args.mode.upper()
                ctypes.windll.kernel32.SetConsoleTitleW(f"ASCII Studio CMD — {mode_str}")
            except Exception:
                pass

        if args.mode == "menu":
            run_cli_interactive()
        elif args.mode == "image":
            if not args.path:
                print("[!] Не вказано шлях до зображення!")
                input("Натисніть Enter...")
                return
            convert_image(
                args.path,
                width=args.width,
                color=bool(args.color),
                char_set=args.charset,
                invert=bool(args.invert),
                display_title=args.title,
            )
        elif args.mode == "video":
            if not args.path:
                print("[!] Не вказано шлях до відео!")
                input("Натисніть Enter...")
                return
            play_video(
                args.path,
                width=args.width,
                color=bool(args.color),
                char_set=args.charset,
                invert=bool(args.invert),
                is_webcam=False,
            )
        elif args.mode == "webcam":
            play_video(
                args.camera,
                width=args.width,
                color=bool(args.color),
                char_set=args.charset,
                invert=bool(args.invert),
                is_webcam=True,
            )
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"\n[!] Виникла помилка: {e}")
        input("Натисніть Enter для виходу...")


if __name__ == "__main__":
    if "--cli" in sys.argv:
        parse_and_run_cli()
    else:
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = ctypes.windll.kernel32.GetConsoleWindow()
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 0)
            except Exception:
                pass
        from app import main as start_gui
        start_gui()