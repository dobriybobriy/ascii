"""
ASCII Studio Pro — Standalone Executable Packaging Script (.exe)
Adheres to the desktop-app-packaging engineering standard:
- Bundles application assets (assets/icon.ico, assets/icon.png)
- Sets standalone executable metadata, icon, and windowed mode
- Ensures safe runtime asset resolution via sys._MEIPASS
- Verifies build output integrity
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def main():
    project_dir = Path(__file__).parent.resolve()
    assets_dir = project_dir / "assets"
    icon_ico = assets_dir / "icon.ico"
    icon_png = assets_dir / "icon.png"

    print("=================================================================")
    print("📦 [BUILD] Packaging ASCII Studio Pro into Standalone .exe")
    print("=================================================================")

    # 1. Check prerequisites
    try:
        import PyInstaller
        print(f"✓ PyInstaller detected (version {PyInstaller.__version__})")
    except ImportError:
        print("⚡ PyInstaller not found. Installing via pip...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✓ PyInstaller installed successfully.")

    # 2. Check assets
    if not icon_ico.exists():
        print(f"⚠️ Warning: {icon_ico} not found. Icon might be skipped.")
    else:
        print(f"✓ Application icon: {icon_ico}")

    # 3. Clean prior build artifacts
    for folder in ["build", "dist"]:
        p = project_dir / folder
        if p.exists():
            print(f"🧹 Cleaning prior {folder}/ directory...")
            shutil.rmtree(p, ignore_errors=True)

    # 4. Assemble PyInstaller command
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name=ASCII_Studio_Pro",
        "--onefile",
        "--noconsole",
        f"--add-data={assets_dir};assets",
        "--clean",
    ]

    if icon_ico.exists():
        cmd.append(f"--icon={icon_ico}")

    # Specify hidden imports for CustomTkinter, PIL, cv2
    cmd.extend([
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageTk",
        "--hidden-import=cv2",
        "--hidden-import=numpy",
        "--hidden-import=customtkinter",
    ])

    cmd.append("app.py")

    print("\n🚀 Executing build command:")
    print(" ".join(cmd))
    print("-----------------------------------------------------------------")

    ret = subprocess.call(cmd, cwd=str(project_dir))
    if ret != 0:
        print(f"\n❌ Build failed with exit code: {ret}")
        sys.exit(ret)

    # 5. Verify output binary
    dist_exe = project_dir / "dist" / "ASCII_Studio_Pro.exe"
    if dist_exe.exists():
        size_mb = dist_exe.stat().st_size / (1024 * 1024)
        print("=================================================================")
        print(f"🎉 [BUILD SUCCESS] Executable created successfully!")
        print(f"📍 Location: {dist_exe}")
        print(f"📊 Binary Size: {size_mb:.2f} MB")
        print("=================================================================")
    else:
        print(f"❌ Output binary not found at expected location: {dist_exe}")
        sys.exit(1)


if __name__ == "__main__":
    main()
