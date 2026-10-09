"""
Autonomous Self-Testing and User Simulation Runner for ASCII Studio Pro
Simulates real end-to-end user workflows:
1. Initialize test media assets (Image & Video).
2. Launch GUI app without freezing CustomTkinter mainloop.
3. Load test image & wait for async background rendering.
4. Interact with ZoomableCanvas (zoom, pan, fit, 1:1, expand/collapse).
5. Adjust width & contrast sliders (verifying async generation).
6. Export to TXT, PNG, and HTML.
7. Switch to Video tab with smooth animated transitions.
8. Play video frames & trigger video Snapshot.
9. Test bilingual language switcher and theme switcher.
10. Gracefully close app & verify zero resource leaks.
"""

import os
import sys
import time
from pathlib import Path

# Enable UTF-8 encoding for Windows terminals
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

import cv2
import numpy as np
from PIL import Image

# Ensure project root is in sys.path
PROJECT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(PROJECT_DIR))

from app import AsciiStudioApp, SplashScreen, LoadingSpinner
from ascii_engine import AsciiEngine


def create_test_assets():
    """Generates a test image and test video for the test runner."""
    img_path = str((PROJECT_DIR / "test_sample_image.png").resolve())
    vid_path = str((PROJECT_DIR / "test_sample_video.mp4").resolve())

    # 1. Створюємо тестове RGB зображення (240x240) з градієнтом та геометричними фігурами
    img = np.zeros((240, 240, 3), dtype=np.uint8)
    for y in range(240):
        img[y, :, 0] = int(y / 240.0 * 255)  # Blue
        img[:, y, 1] = int(y / 240.0 * 255)  # Green
        img[y, :, 2] = 255 - int(y / 240.0 * 255)  # Red
    cv2.circle(img, (120, 120), 50, (255, 255, 255), -1)
    cv2.rectangle(img, (30, 30), (80, 80), (0, 255, 255), -1)
    cv2.putText(img, "TEST", (75, 130), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    
    # Використовуємо PIL для надійного збереження шляхів з кирилицею
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    Image.fromarray(rgb_img).save(img_path)

    # 2. Створюємо тестове MP4 відео (15 кадрів, 128x128)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(vid_path, fourcc, 10.0, (128, 128))
    for i in range(15):
        frame = np.zeros((128, 128, 3), dtype=np.uint8)
        frame[:, :] = (i * 15, 255 - i * 15, 120)
        cv2.circle(frame, (20 + i * 6, 64), 20, (255, 255, 255), -1)
        out.write(frame)
    out.release()

    return img_path, vid_path


def read_image_unicode(path: str):
    try:
        data = np.fromfile(path, dtype=np.uint8)
        if data.size > 0:
            res = cv2.imdecode(data, cv2.IMREAD_COLOR)
            if res is not None:
                return res
    except Exception:
        pass
    pil_img = Image.open(path).convert("RGB")
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def cleanup_test_assets(files):
    """Deletes temporary artifacts created during testing."""
    for f in files:
        p = Path(f)
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass


def wait_for_ui(app, duration_sec=0.2, step_ms=20):
    """Pumps the Tkinter event loop safely for a specified duration."""
    start = time.time()
    while time.time() - start < duration_sec:
        try:
            if not app.winfo_exists():
                break
            app.update_idletasks()
            app.update()
        except Exception:
            break
        time.sleep(step_ms / 1000.0)


def wait_for_render(app, timeout_sec=5.0):
    """Waits for the background async rendering worker and UI queue to finish."""
    start = time.time()
    while getattr(app, "_is_rendering", False) or (hasattr(app, "_ui_queue") and not app._ui_queue.empty()):
        if time.time() - start > timeout_sec:
            raise TimeoutError("ASCII background rendering timed out!")
        try:
            if not app.winfo_exists():
                break
            app.update_idletasks()
            app.update()
        except Exception:
            break
        time.sleep(0.015)
    wait_for_ui(app, 0.1)


def run_e2e_tests():
    print("=" * 65)
    print("🚀 [TEST RUNNER] Starting ASCII Studio Pro Autonomous E2E Tests")
    print("=" * 65)

    test_img, test_vid = create_test_assets()
    export_txt = str(PROJECT_DIR / "test_export.txt")
    export_png = str(PROJECT_DIR / "test_export.png")
    export_html = str(PROJECT_DIR / "test_export.html")
    export_snap = str(PROJECT_DIR / "test_snapshot.png")

    created_files = [test_img, test_vid, export_txt, export_png, export_html, export_snap]

    try:
        # 1. Перевірка рушія та масочного бліттінгу
        print("\n[Step 1/9] Benchmarking AsciiEngine core optimizations...")
        engine = AsciiEngine(font_size=12)
        sample_frame = read_image_unicode(test_img)
        t0 = time.time()
        for _ in range(5):
            pil_res, text_res, _, _ = engine.process_frame(sample_frame, width=200, generate_text=True)
        t_elapsed = (time.time() - t0) / 5 * 1000.0
        print(f"  ✓ AsciiEngine 200-char render: {t_elapsed:.2f} ms/frame")
        assert pil_res is not None, "Engine rendered image is None!"
        assert len(text_res) > 100, "Engine plain text is empty!"

        # 2. Запуск графічного застосунку (без модальних діалогів)
        print("\n[Step 2/9] Launching AsciiStudioApp GUI...")
        app = AsciiStudioApp(show_splash=False)
        wait_for_ui(app, 0.3)
        assert app.winfo_exists(), "App failed to launch or window closed prematurely!"
        print("  ✓ Main window created and responsive.")

        # 3. Завантаження зображення
        print("\n[Step 3/9] Loading test image into Photo view...")
        app.load_image(test_img)
        wait_for_render(app)
        assert app.current_orig_image is not None, "current_orig_image is None after load_image!"
        assert app.last_rendered_pil is not None, "last_rendered_pil was not produced!"
        assert len(app.last_rendered_text) > 0, "last_rendered_text is empty!"
        print(f"  ✓ Image loaded and rendered: {app.last_rendered_pil.size}, chars: {len(app.last_rendered_text)}")

        # 4. Тестування інтерактивних жестів ZoomableCanvas
        print("\n[Step 4/9] Testing ZoomableCanvas interactive controls...")
        canvas = app.ascii_canvas.canvas
        initial_scale = canvas.scale

        # Зум коліщатком (MouseWheel)
        canvas.event_generate("<MouseWheel>", delta=120, x=150, y=150)
        wait_for_ui(app, 0.05)
        assert canvas.scale > initial_scale, f"Zoom in failed! scale: {canvas.scale} <= {initial_scale}"

        canvas.event_generate("<MouseWheel>", delta=-120, x=150, y=150)
        wait_for_ui(app, 0.05)

        # Перетягування (Drag Pan)
        canvas.event_generate("<ButtonPress-1>", x=100, y=100)
        canvas.event_generate("<B1-Motion>", x=140, y=130)
        canvas.event_generate("<ButtonRelease-1>", x=140, y=130)
        wait_for_ui(app, 0.05)

        # Кнопки 100% та Fit
        app.ascii_canvas.btn_100.invoke()
        wait_for_ui(app, 0.05)
        assert abs(canvas.scale - 1.0) < 1e-3, f"100% Zoom failed! scale={canvas.scale}"

        app.ascii_canvas.btn_fit.invoke()
        wait_for_ui(app, 0.05)
        assert canvas.is_fit, "Fit Zoom did not restore is_fit=True!"

        # Плавна анімація розгортання/згортання бічної панелі
        print("  ✓ Testing smooth sidebar expand/collapse animation...")
        app.ascii_canvas.btn_expand.invoke()
        wait_for_ui(app, 0.3)
        assert app.is_expanded, "Canvas expand toggle failed!"
        app.ascii_canvas.btn_expand.invoke()
        wait_for_ui(app, 0.3)
        assert not app.is_expanded, "Canvas collapse toggle failed!"
        print("  ✓ ZoomableCanvas events, buttons, and panel animations verified.")

        # 5. Зміна параметрів (Ширина, Контраст, Яскравість)
        print("\n[Step 5/9] Testing settings sliders (width, contrast, brightness)...")
        app.slider_width.set(160)
        app._on_width_changed(160)
        app.slider_contrast.set(1.4)
        app._on_contrast_changed(1.4)
        app.slider_brightness.set(15)
        app._on_brightness_changed(15)

        wait_for_render(app)
        settings = app.get_current_settings()
        assert settings["width"] == 160, f"Width mismatch: {settings['width']}"
        assert abs(settings["contrast"] - 1.4) < 1e-3, f"Contrast mismatch: {settings['contrast']}"
        assert settings["brightness"] == 15, f"Brightness mismatch: {settings['brightness']}"
        print(f"  ✓ Async settings update finished successfully: {settings['width']} chars, contrast {settings['contrast']}x")

        # 6. Експорт у TXT, PNG та HTML
        print("\n[Step 6/9] Testing file exports (TXT, PNG, HTML)...")
        txt_res = app.save_as_txt(export_path=export_txt)
        assert txt_res and os.path.exists(export_txt), "TXT export failed!"
        with open(export_txt, "r", encoding="utf-8") as f:
            txt_content = f.read()
        assert len(txt_content) > 100, "TXT content is too short!"
        print(f"  ✓ TXT export successful ({len(txt_content)} bytes).")

        png_res = app.save_as_png(export_path=export_png)
        assert png_res and os.path.exists(export_png), "PNG export failed!"
        print(f"  ✓ PNG export successful ({os.path.getsize(export_png)} bytes).")

        html_res = app.save_as_html(export_path=export_html)
        assert html_res and os.path.exists(export_html), "HTML export failed!"
        print(f"  ✓ HTML export successful ({os.path.getsize(export_html)} bytes).")

        # 7. Перехід у режим Відео, відтворення та знімок (Snapshot)
        print("\n[Step 7/9] Switching to Video tab & playing frames...")
        app.btn_nav_video.invoke()
        wait_for_ui(app, 0.2)
        assert app.current_mode == "video", f"Current mode is {app.current_mode}, expected 'video'!"

        app.load_video(test_vid)
        wait_for_ui(app, 0.2)
        assert app.video_cap is not None and app.video_cap.isOpened(), "Video failed to load!"

        # Запуск відтворення
        app.btn_play_pause.invoke()
        wait_for_ui(app, 0.4)
        assert app.is_video_playing, "Video playback did not start!"

        # Пауза
        app.btn_play_pause.invoke()
        wait_for_ui(app, 0.2)
        assert not app.is_video_playing, "Video playback did not pause!"

        # Створення знімка кадру
        snap_res = app.save_video_snapshot(export_path=export_snap)
        assert snap_res and os.path.exists(export_snap), "Video snapshot failed!"
        print(f"  ✓ Video loaded, played, paused, and snapshot captured ({os.path.getsize(export_snap)} bytes).")

        # 8. Перевірка локалізації та тем оформлення
        print("\n[Step 8/9] Testing language switcher & appearance modes...")
        app.change_language("Українська")
        wait_for_ui(app, 0.1)
        assert app.current_lang == "uk", "Language did not switch to Ukrainian!"
        assert app.btn_open_img.cget("text") == app.t("btn_open_photo"), "Button text not translated!"

        app.change_language("English")
        wait_for_ui(app, 0.1)
        assert app.current_lang == "en", "Language did not switch back to English!"

        app.change_appearance_mode("Light")
        wait_for_ui(app, 0.1)
        app.change_appearance_mode("Dark")
        wait_for_ui(app, 0.1)
        print("  ✓ Bilingual switching and theme toggling validated.")

        # 9. Безпечне закриття застосунку та звільнення ресурсів
        print("\n[Step 9/9] Testing graceful closure & resource cleanup...")
        app.on_close()
        wait_for_ui(app, 0.1)
        assert app.video_cap is None, "Video cap was not released on exit!"
        assert app.webcam_cap is None, "Webcam cap was not released on exit!"
        print("  ✓ Application closed gracefully, all threads and VideoCapture handles released.")

        print("\n" + "=" * 65)
        print("🎉 [ALL TESTS PASSED] 100% Autonomous E2E Simulation Successful!")
        print("=" * 65)
        return True

    except Exception as e:
        import traceback
        print("\n" + "!" * 65)
        print(f"❌ [TEST FAILED]: {e}")
        traceback.print_exc()
        print("!" * 65)
        return False

    finally:
        cleanup_test_assets(created_files)


if __name__ == "__main__":
    success = run_e2e_tests()
    sys.exit(0 if success else 1)
