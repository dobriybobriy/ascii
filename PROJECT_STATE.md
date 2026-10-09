# Project State: ASCII Studio Pro

**Date:** 2026-10-09  
**Platform:** Windows (Python 3.10+)  
**Repository:** `ascii`

---

## 1. File Structure

```text
ascii/
├── assets/
│   ├── icon.ico             # Application icon for Windows executable / window / taskbar
│   └── icon.png             # High-resolution PNG logo and UI icon
├── app.py                   # Main graphical user interface (CustomTkinter, PIL, OpenCV)
├── ascii_engine.py          # Vectorized ASCII art generation engine (NumPy, PIL, OpenCV)
├── main.py                  # Entry point for CLI runner, terminal viewer, and interactive menu
├── translations.py          # Internationalization dictionary (English default, Ukrainian)
├── zoom_canvas.py           # Interactive pan & zoom canvas widget (Tkinter Canvas)
├── run.bat                  # Windows batch launcher (runs pythonw app.py without CMD window)
├── requirements.txt         # Python package dependencies
├── LICENSE                  # MIT License
├── README.md                # Project overview and user instructions (English)
├── PROJECT_STATE.md         # Current project state, features, schema, and status documentation
└── .gitignore               # Git ignore rules for virtual environments, caches, and temp files
```

---

## 2. Implemented Commands and Features

### 🖥️ GUI Features (`app.py`)
- **Photo Processing:**
  - Load images across formats (PNG, JPG, JPEG, BMP, WEBP, TIFF, ICO).
  - Real-time ASCII rendering preview.
  - Interactive pan and zoom canvas (mouse wheel zoom, left-click drag to pan, double-click fit).
  - Multiple preview tabs: *ASCII Render*, *Plain Text* (with Ctrl+Wheel font scaling), and *Original Image*.
  - Export capabilities: Export as high-resolution PNG image, plain `.txt`, styled standalone `.html`, or direct clipboard copy.
- **Video Processing:**
  - Open video files (MP4, AVI, MOV, etc.).
  - Playback controls: Play, Pause, Resume, Stop, Loop toggle.
  - Snapshot tool: Grab current video frame into Photo tab for further inspection or export.
- **Webcam Processing:**
  - Real-time live camera capture with camera index selector.
  - Live ASCII streaming.
  - Snapshot tool: Capture camera frame directly into Photo tab.
- **Windows Terminal / CMD Integration:**
  - "Open in CMD" feature for photos, video streams, and webcam feeds.
  - Spawns independent Windows Command Prompt windows with full 24-bit TrueColor ANSI color support.
  - Automatically resolves `python.exe` when GUI is launched under `pythonw.exe`.
- **Customization & Controls:**
  - Charset selection: Standard, Dense, Minimal, Blocks, Binary, Math, Matrix, and Custom input.
  - Color palettes: TrueColor (RGB), Monochrome (White), Grayscale, Cyberpunk, Amber Phosphor, Matrix Green.
  - Sliders for ASCII width (characters), contrast adjustment, brightness adjustment, and invert toggle.
  - Fullscreen mode (F11) and distraction-free canvas expansion toggle (Esc to collapse).
  - Bilingual UI switcher: English (default) and Ukrainian.

### ⌨️ CLI Commands (`main.py`)
Run via `python main.py --cli [options]`:

| Option | Values | Default | Description |
|---|---|---|---|
| `--cli` | Flag | `False` | Run in console mode |
| `--mode` | `image`, `video`, `webcam`, `menu` | `menu` | Execution mode |
| `--path` | `<file_path>` | `""` | File path to image or video |
| `--camera` | `<int>` | `0` | Camera device index |
| `--width` | `<int>` | `100` | Output width in ASCII characters |
| `--color` | `0` or `1` | `1` | Enable/disable 24-bit ANSI color rendering |
| `--charset` | `<string>` | ` .:-=+*#%@` | Custom character set gradient |
| `--invert` | `0` or `1` | `0` | Invert brightness values |
| `--title` | `<string>` | `""` | Custom console window title |

---

## 3. Database Schema

- **Status:** **None (Stateless Application)**
- This project operates entirely client-side without a persistent database (SQL or NoSQL).
- Settings, presets, and translation dictionaries are maintained in-memory in `translations.py` and `ascii_engine.py`. Temporary preview artifacts (e.g., `_cmd_preview.png`) are managed ephemerally on the local filesystem.

---

## 4. List of Unresolved Bugs & Known Limitations

1. **No Audio Playback in Video Mode:**
   - Video playback is handled via OpenCV (`cv2.VideoCapture`), which processes visual frames only. Audio tracks are not decoded or played back.
2. **Terminal ANSI Color Compatibility on Legacy Windows:**
   - TrueColor ANSI escape sequences require Windows 10/11 or modern terminal emulators. Older Windows releases without Virtual Terminal sequences support will display raw escape codes or uncolored text.
3. **High Resolution / Extreme Width Performance Impact:**
   - Rendering ASCII video/webcam at widths exceeding 200–250 characters on standard CPUs can cause framerate drops due to terminal output throughput limits and frame resizing overhead.
4. **Non-Standard Codec Support:**
   - Videos requiring proprietary or exotic codecs may fail to open if system DirectShow / Media Foundation / FFmpeg backend codecs are not available to OpenCV.
