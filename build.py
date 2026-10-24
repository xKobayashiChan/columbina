"""配布用の exe (ffmpeg 同梱) をビルドして、zip とインストーラー (setup.exe) を作る。

事前準備:
    python -m venv .venv
    .venv\\Scripts\\python -m pip install pyinstaller==6.11.1
    vendor\\ffmpeg\\ に ffmpeg.exe / ffprobe.exe / LICENSE を置く (https://www.gyan.dev/ffmpeg/builds/)
    Inno Setup 6 を入れる (winget install JRSoftware.InnoSetup)

実行:
    .venv\\Scripts\\python build.py --version 1.1.0
"""

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
NAME = "X動画変換"
VENDOR = ROOT / "vendor" / "ffmpeg"
DIST = ROOT / "dist"
ISCC_CANDIDATES = [
    Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Inno Setup 6" / "ISCC.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Inno Setup 6" / "ISCC.exe",
]


def find_iscc():
    found = shutil.which("iscc")
    if found:
        return found
    for cand in ISCC_CANDIDATES:
        if cand.exists():
            return str(cand)
    sys.exit("Inno Setup (ISCC.exe) が見つかりません。winget install JRSoftware.InnoSetup で入れてください。")


def build_exe():
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
    return app


def build_installer(app, version):
    subprocess.run(
        [
            find_iscc(), "/Q",
            f"/DAppVersion={version}", f"/DSourceDir={app}", f"/DOutputDir={DIST}",
            str(ROOT / "installer" / "setup.iss"),
        ],
        check=True,
    )
    return DIST / f"X-video-converter-setup-{version}.exe"


def main():
    ap = argparse.ArgumentParser(description="配布用の zip と setup.exe を作ります。")
    ap.add_argument("--version", default="0.0.0-dev", help="バージョン (例: 1.1.0)")
    ap.add_argument("--no-installer", action="store_true", help="setup.exe を作らない")
    args = ap.parse_args()

    app = build_exe()
    archive = shutil.make_archive(str(DIST / f"X-video-converter-{args.version}-windows"), "zip", DIST, NAME)
    print(f"zip: {archive}")
    if not args.no_installer:
        print(f"setup: {build_installer(app, args.version)}")


if __name__ == "__main__":
    main()
