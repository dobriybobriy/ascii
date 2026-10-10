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
├── build_exe.py             # PyInstaller standalone packaging script (.exe builder)
├── build.bat                # Windows one-click batch compiler
├── app.py                   # Main graphical user interface (CustomTkinter, PIL, OpenCV, Thread-Safe Queue)
├── ascii_engine.py          # High-performance vectorized ASCII art engine (NumPy, OpenCV SIMD blitting)
├── main.py                  # Entry point for CLI runner, terminal viewer, and interactive menu
├── test_runner.py           # Autonomous end-to-end user simulation and regression test suite
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

### 🖥️ GUI Features & Animations (`app.py`)
- **Smooth Splash Screen:**
  - Modern frameless splash window with glowing logo (`assets/icon.png`), real-time initialization progress bar, and automatic smooth fade/transition into maximized workspace.
- **Side Panel & Tab Animations:**
  - Smooth multi-step animated sliding transition for expanding and collapsing sidebar settings panels.
  - Animated switching between Photo, Video, and Webcam navigation views.
- **Non-Blocking Background Rendering & Loading Spinner:**
  - All heavy ASCII generation tasks are offloaded to background worker threads (`threading.Thread`).
  - Thread-safe UI task queue (`queue.Queue`) safely marshals canvas and widget updates back to the CustomTkinter mainloop without freezing or lag.
  - Animated neon circular spinner (`LoadingSpinner`) displayed during high-resolution processing.
- **Photo Processing & Visual Effects:**
  - Load images across formats (PNG, JPG, JPEG, BMP, WEBP, TIFF, ICO) with Unicode-safe path support on Windows.
  - **Floyd-Steinberg Dithering:** Error-diffusion dithering preventing color banding on gradients, faces, and skies.
  - **Edge Contour Accents (Sobel):** Directional stroke detection (`|`, `-`, `/`, `\`) along sharp object contours for architectural and comic-style sketches.
  - **CRT Scanlines Effect:** Authentic retro phosphor monitor scanlines overlay.
  - **Color Palettes:** Full Color (RGB), Monochrome, Matrix, Retro Amber, Cyberpunk Neon, Vintage Sepia, **Vaporwave Sunset**, and **Game Boy 1989**.
  - Interactive pan and zoom canvas (mouse wheel zoom, left-click drag to pan, double-click fit, 1:1 button).
  - Multiple preview tabs: *ASCII Render*, *Plain Text* (with Ctrl+Wheel font scaling), and *Original Image*.
  - Export capabilities: Programmatic or dialog-driven export as high-resolution PNG image, **Animated GIF**, plain `.txt`, styled standalone `.html`, or direct clipboard copy.
- **Video Processing:**
  - Open video files (MP4, AVI, MOV, etc.) with Unicode-safe path support (`open_video_unicode`).
  - Playback controls: Play, Pause, Resume, Stop, and Loop toggle.
  - Snapshot tool: Grab current video frame into Photo tab or export directly to disk.
  - Thread-safe settings access preventing GUI widget contention during streaming.
- **Webcam Processing:**
  - Real-time live camera capture with camera index selector (`CAP_DSHOW` backend fallback).
  - Live ASCII streaming with dynamic FPS tracking.
  - Snapshot tool: Capture camera frame directly into Photo tab.
- **Windows Terminal / CMD Integration:**
  - "Open in CMD" feature for photos, video streams, and webcam feeds.
  - Spawns independent Windows Command Prompt windows with full 24-bit TrueColor ANSI color support.
  - Automatically resolves `python.exe` when GUI is launched under `pythonw.exe`.
- **Standalone Desktop Packaging (`build_exe.py` / `build.bat`):**
  - PyInstaller automated compilation with embedded icon, assets, hidden imports, `sys._MEIPASS` dynamic path resolution, and top-level crash logging against silent `--noconsole` exits.

### ⚡ Engine Optimizations (`ascii_engine.py`)
- **Vectorized Character Glyph Masks:** Precomputed character font masks stored as binary `uint8` matrices (0 and 255).
- **Early Palette Computation:** Sepia, Matrix, Cyberpunk, Monochrome, Vaporwave, and Game Boy color mappings are vectorized across the low-resolution `(target_h, target_w)` grid before upscaling, resulting in an ~80x reduction in pixel arithmetic.
- **SIMD Nearest-Neighbor Upscaling & Blitting:** Frame upscaling performed via `cv2.resize(..., INTER_NEAREST)` and glyph composition accelerated with `cv2.copyTo`.
- **Streamlined Video/Webcam Pipeline:** Added `generate_text=False` flag to eliminate redundant string concatenations during live video/camera rendering.
- **Benchmark Performance:** Render times dropped from >50ms down to **~22 ms per frame** at 200+ character widths.

### 🧪 Autonomous Testing Suite (`test_runner.py`)
- Fully automated E2E test runner executing 9 sequential phases:
  1. Engine core vectorization & mask blitting benchmark (200 chars).
  2. Main window initialization without mainloop lockup.
  3. Image loading & background worker synchronization.
  4. ZoomableCanvas interactive gestures (zoom in/out, pan drag, fit, 100%, expand/collapse animations).
  5. Settings adjustments (width, contrast, brightness sliders) via async rendering.
  6. File exports (TXT, PNG, HTML).
  7. Video navigation, playback, pause, and snapshot export.
  8. Bilingual localization and appearance mode toggling (Dark/Light).
  9. Graceful shutdown verifying zero resource leaks (`cv2.VideoCapture` release, timer cancellation).

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
3. **Non-Standard Codec Support:**
   - Videos requiring proprietary or exotic codecs may fail to open if system DirectShow / Media Foundation / FFmpeg backend codecs are not available to OpenCV.
