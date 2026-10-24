"""配布用の exe (ffmpeg 同梱) をビルドして zip にまとめる。

事前準備:
    python -m venv .venv
    .venv\\Scripts\\python -m pip install pyinstaller==6.11.1
    vendor\\ffmpeg\\ に ffmpeg.exe / ffprobe.exe / LICENSE を置く (https://www.gyan.dev/ffmpeg/builds/)

実行:
    .venv\\Scripts\\python build.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
NAME = "X動画変換"
VENDOR = ROOT / "vendor" / "ffmpeg"
DIST = ROOT / "dist"


def main():
    for f in ("ffmpeg.exe", "ffprobe.exe", "LICENSE"):
        if not (VENDOR / f).exists():
            sys.exit(f"{VENDOR / f} がありません。")

    subprocess.run(
        [
            sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--console",
            "--name", NAME,
            "--add-binary", f"{VENDOR / 'ffmpeg.exe'};ffmpeg",
            "--add-binary", f"{VENDOR / 'ffprobe.exe'};ffmpeg",
            str(ROOT / "tw.py"),
        ],
        check=True, cwd=ROOT,
    )

    app = DIST / NAME
    shutil.copy(ROOT / "使い方.txt", app / "使い方.txt")
    shutil.copy(VENDOR / "LICENSE", app / "FFmpeg-LICENSE.txt")
    archive = shutil.make_archive(str(DIST / NAME), "zip", DIST, NAME)
    print(f"できました: {archive}")


if __name__ == "__main__":
    main()
