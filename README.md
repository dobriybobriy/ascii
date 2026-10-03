# 🎬 ASCII Studio Pro

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/GUI-CustomTkinter-blueviolet?style=for-the-badge" alt="CustomTkinter">
  <img src="https://img.shields.io/badge/Engine-OpenCV%20%2B%20NumPy-orange?style=for-the-badge&logo=opencv&logoColor=white" alt="OpenCV & NumPy">
  <img src="https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License MIT">
</p>

<p align="center">
  <b>A high-performance modern desktop application to convert Images, Videos, and Live Webcam feeds into color ASCII art in real time, featuring interactive zoom & pan and 1-click native Windows CMD streaming.</b>
</p>

---

## ✨ Features

### 🖼️ Image Converter
- **Multi-Format Support:** Load `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, and `.ico` files (including full Unicode/Cyrillic paths).
- **Three Preview Modes:**
  - 🎨 **ASCII Render:** High-definition rendered graphical ASCII with TrueColor RGB support.
  - 📝 **Plain Text:** Monospaced text view with font scaling (`A+` / `A-` / `Ctrl + Mouse Wheel`).
  - 🔍 **Original View:** Side-by-side or tabbed comparison with the original input.
- **Export Options:**
  - 🖼️ **Save PNG:** Export the crisp rendered ASCII artwork as a high-resolution image.
  - 📄 **Save TXT:** Export pure plain-text ASCII art.
  - 🌐 **Export HTML:** Self-contained colored HTML webpage with styled character spans.
  - 📋 **Copy to Clipboard:** Instantly copy ASCII characters to clipboard.

### 🎬 Video Player & Converter
- **Real-Time Playback:** Smooth playback at source FPS without lag or stutters.
- **Interactive Timeline:** Scrub to any second of the video with progress slider.
- **Loop Toggle:** Seamless loop playback option.
- **Snapshot Extractor:** 1-click button to capture any video frame directly into the Image tab for tweaking and export.

### 📹 Live Webcam Streamer
- **Real-Time 30+ FPS Streaming:** Hardware-accelerated live ASCII camera feed.
- **Camera Index Selector:** Switch between external or built-in cameras (`Camera 0`, `Camera 1`...).
- **Mirrored Display:** Natural selfie mirroring for live video chatting and demos.
- **1-Click Snapshot:** Snap photos directly from your webcam into the editor with instant export capabilities.

### 🔍 Interactive Zoom & Pan Engine
- **Mouse Wheel Zoom:** Zoom from **5% up to 3000%** with pinpoint focus centered at your mouse cursor.
- **Drag & Pan:** Hold Left, Right, or Middle Mouse Button to smoothly pan around large images.
- **Fit & 1:1 Buttons:** 1-click auto-fit to container (`↔️ Fit`) or 100% pixel-to-pixel view (`1:1`).
- **Double-Click Reset:** Instantly resets zoom and centers the artwork.
- **Viewport-Cropped Rendering:** Only visible on-screen pixels are processed, ensuring blazingly fast 60+ FPS rendering even at extreme zoom levels.

### 💻 Native Windows CMD Terminal Integration
- **1-Click Launch in CMD:** Open any loaded photo, video, or webcam stream inside an authentic **Windows Command Prompt** window.
- **24-Bit ANSI TrueColor:** Supports full RGB color rendering directly in the terminal (`\033[38;2;R;G;Bm`).
- **Auto-Buffer Sizing:** Automatically adjusts terminal columns and lines (`mode con`) to eliminate ugly text wrapping.
- **Zero-Flicker Screen Sync:** Cursor home addressing (`\033[H`) for smooth video playback.

### ⛶ Window Expansion & Fullscreen
- **Auto-Maximize:** Opens maximized to fill your monitor automatically.
- **Expand Viewport:** 1-click button (or `ESC`) to collapse the left sidebar and settings panel, giving **100% of your screen width and height** to the preview canvas!
- **True Fullscreen (`F11`):** Borderless fullscreen mode for immersive presentation.

---

## ⚙️ Customization & Presets

- **Width Slider:** Adjust resolution dynamically from 30 to 240 characters.
- **Character Set Presets:**
  - `Standard (10 chars)`: ` .:-=+*#%@`
  - `Detailed (70 chars)`: ` .'`^",:;Il!i><~+_-?][}{1)(|\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$`
  - `Blocks (Pseudographics)`: ` ░▒▓█`
  - `Binary`: ` 01`
  - `Matrix Code`: ` 0123456789ABCDEF$#*`
  - `Minimalist`: ` .oO@`
  - `Custom`: Enter any sequence of custom symbols in real time!
- **Color Palettes:**
  - 🌈 **Full Color (RGB)** — Original pixel hues
  - ⚪ **Monochrome (White)** — Classic terminal grayscale
  - 🟢 **Matrix (Phosphor Green)** — Retro hacker terminal glow
  - 🟠 **Retro Amber** — Vintage amber CRT aesthetic
  - 🟣 **Cyberpunk (Neon)** — High-contrast neon tint
  - 🟤 **Sepia** — Warm vintage photograph look
- **Image Adjustments:** Real-time brightness offset (-80 to +80), contrast multiplier (0.5x to 2.5x), and brightness inversion.

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
| :--- | :--- |
| **`Mouse Wheel`** | Zoom In / Zoom Out (centered at cursor) |
| **`LMB / RMB Drag`** | Pan / move around the image |
| **`Double Click`** | Reset zoom to Fit |
| **`Ctrl + Mouse Wheel`** | Zoom text font size (Text tab) |
| **`F11`** | Toggle Fullscreen mode |
| **`ESC`** | Exit Fullscreen or restore collapsed sidebars |
| **`q`** (in CMD mode) | Stop & exit terminal playback |

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10 or newer** installed on Windows.
- Make sure Python is added to your system `PATH`.

### 2. Clone the Repository
```bash
git clone https://github.com/<your-username>/ascii-studio-pro.git
cd ascii-studio-pro
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Application
- **Double-click:** [run.bat](run.bat)
- **Or via terminal:**
```bash
python app.py
```
*(You can also run `python main.py` directly, which launches the GUI by default)*

---

## 💻 CLI / Terminal Mode

If you prefer using the command line or want to automate ASCII rendering in scripts:

```bash
# Interactive menu
python main.py --cli

# Render an image in terminal
python main.py --cli --mode image --path "photo.jpg" --width 100 --color 1

# Play a video in terminal
python main.py --cli --mode video --path "video.mp4" --width 90 --color 1

# Stream webcam in terminal
python main.py --cli --mode webcam --camera 0 --width 90 --color 1
```

---

## 🏗️ Project Architecture

```
ascii/
├── app.py              # Main CustomTkinter desktop GUI application
├── ascii_engine.py     # High-speed vectorized NumPy glyph atlas rendering engine
├── zoom_canvas.py      # Interactive viewport-cropped zoom & pan canvas widget
├── main.py             # Dual entry point: CLI runner & GUI launcher
├── run.bat             # 1-click Windows launcher script
├── requirements.txt    # Python dependencies list
├── .gitignore          # Git ignore configuration
└── README.md           # Documentation
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) — free for personal and commercial use.
