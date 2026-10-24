"""X(Twitter) 用に動画をエンコードし直す CLI。

動画を exe にドラッグ&ドロップ (またはダブルクリックしてファイルを選択) しても使える。

X はアップロードされた動画を必ず再エンコードする。仕様から外れた動画
(高fps・HEVC・HDR・高すぎる/低すぎるビットレートなど) は劣化しやすいので、
あらかじめ X の推奨形式 (H.264 High / yuv420p / AAC / faststart) に揃えておく。
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from fractions import Fraction
from pathlib import Path

MAX_DURATION = 140  # 無料アカウントの上限 (2分20秒)
MAX_SIZE = 512 * 1024 * 1024
SIZE_BUDGET = 480 * 1024 * 1024  # 512MB に収めるための余裕を持った目標サイズ
MAX_FPS = 60
AUDIO_BITRATE = 192_000
FALLBACK_FFMPEG_DIRS = [r"C:\ffmpeg\bin"]
# exe 化したときに同梱した ffmpeg を置く場所 (PyInstaller の展開先)
BUNDLED_FFMPEG_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "ffmpeg"
HDR_TRANSFERS = {"smpte2084", "arib-std-b67"}


def find_tool(name, ffmpeg_arg):
    if ffmpeg_arg:
        p = Path(ffmpeg_arg)
        d = p if p.is_dir() else p.parent
        cand = d / f"{name}.exe" if os.name == "nt" else d / name
        if cand.exists():
            return str(cand)
    bundled = BUNDLED_FFMPEG_DIR / f"{name}.exe"
    if bundled.exists():
        return str(bundled)
    found = shutil.which(name)
    if found:
        return found
    for d in FALLBACK_FFMPEG_DIRS:
        cand = Path(d) / f"{name}.exe"
        if cand.exists():
            return str(cand)
    raise RuntimeError(f"{name} が見つかりません。--ffmpeg で場所を指定してください。")


def launched_from_explorer():
    """ダブルクリックやドラッグ&ドロップで起動された (専用のコンソールを持っている) か。"""
    if os.name != "nt":
        return False
    import ctypes

    procs = (ctypes.c_uint * 2)()
    return ctypes.windll.kernel32.GetConsoleProcessList(procs, 2) == 1


def pick_files():
    """ファイル選択ダイアログで入力動画を選ばせる。"""
    import tkinter
    from tkinter import filedialog

    root = tkinter.Tk()
    root.withdraw()
    paths = filedialog.askopenfilenames(
        title="X 用に変換する動画を選んでください",
        filetypes=[("動画", "*.mp4 *.mov *.mkv *.webm *.avi *.m4v *.ts"), ("すべてのファイル", "*.*")],
    )
    root.destroy()
    return [Path(p) for p in paths]


def ask_yes(question):
    answer = input(f"  {question} [y/n]: ")
    # 日本語入力がオンのままだと全角の「ｙ」になるので、半角に揃えてから判定する
    answer = unicodedata.normalize("NFKC", answer).strip().lower()
    return answer in ("y", "yes", "はい")


def parse_time(s):
    """'90' / '1:30' / '0:01:30.5' を秒に変換する。"""
    secs = 0.0
    for part in s.strip().split(":"):
        secs = secs * 60 + float(part)
    return secs


def parse_trim(s):
    start, _, end = s.partition("-")
    start = parse_time(start) if start else 0.0
    end = parse_time(end) if end else None
    if end is not None and end <= start:
        raise argparse.ArgumentTypeError(f"--trim の終了が開始より前です: {s}")
    return start, end


def probe(ffprobe, path):
    out = subprocess.run(
        [ffprobe, "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)],
        capture_output=True, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe 失敗: {out.stderr.strip()}")
    return json.loads(out.stdout)


def rotation_of(stream):
    rot = stream.get("tags", {}).get("rotate")
    if rot is None:
        for sd in stream.get("side_data_list", []):
            if "rotation" in sd:
                rot = sd["rotation"]
    return int(float(rot or 0)) % 360


def parse_rate(s):
    try:
        r = Fraction(s)
    except (ValueError, ZeroDivisionError):
        return None
    return r if r > 0 else None


def even(x):
    return max(2, int(round(x / 2)) * 2)


def fit_size(w, h):
    """横は 1920x1080、縦は 1080x1920、正方形は 1080x1080 に収める (拡大はしない)。"""
    if w > h:
        box = (1920, 1080)
    elif h > w:
        box = (1080, 1920)
    else:
        box = (1080, 1080)
    s = min(1.0, box[0] / w, box[1] / h)
    return even(w * s), even(h * s)


def pick_bitrate(w, h, fps, duration, has_audio):
    short = min(w, h)
    if short >= 1080:
        base = 8_000_000
    elif short >= 720:
        base = 5_000_000
    else:
        base = 3_000_000
    if fps > 30:
        base = int(base * 1.5)
    # 512MB を超えそうなら長さから逆算して下げる
    audio = AUDIO_BITRATE if has_audio else 0
    cap = int(SIZE_BUDGET * 8 / max(duration, 1) / 1.05) - audio
    return min(base, cap)


def build_filters(vs, out_w, out_h, out_fps, denoise):
    filters = [f"fps={out_fps}"]
    transfer = vs.get("color_transfer")
    if transfer in HDR_TRANSFERS:
        filters.append(
            f"zscale=tin={transfer}:min=bt2020nc:pin=bt2020:t=linear:npl=100,"
            "format=gbrpf32le,zscale=p=bt709,tonemap=hable:desat=0,"
            "zscale=t=bt709:m=bt709:r=tv"
        )
    if denoise:
        filters.append("hqdn3d=1.5:1.5:6:6")
    filters.append(f"scale={out_w}:{out_h}:flags=lanczos:out_color_matrix=bt709:out_range=tv")
    filters.append("setsar=1")
    filters.append("format=yuv420p")
    # 新しい ffmpeg はフレームの色情報を優先するので、フィルター側でも bt709 を明示する
    filters.append("setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv")
    return ",".join(filters)


def fmt_time(secs):
    m, s = divmod(secs, 60)
    return f"{int(m)}:{s:05.2f}"


def convert(src, args, ffmpeg, ffprobe):
    info = probe(ffprobe, src)
    streams = info.get("streams", [])
    vs = next((s for s in streams if s.get("codec_type") == "video"), None)
    if vs is None:
        raise RuntimeError("映像トラックがありません")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    w, h = int(vs["width"]), int(vs["height"])
    if rotation_of(vs) in (90, 270):
        w, h = h, w
    out_w, out_h = fit_size(w, h)

    src_fps = parse_rate(vs.get("avg_frame_rate")) or parse_rate(vs.get("r_frame_rate")) or Fraction(30)
    out_fps = min(src_fps, Fraction(MAX_FPS)).limit_denominator(1001)

    total = float(info.get("format", {}).get("duration") or vs.get("duration") or 0)
    start, end = args.trim or (0.0, None)
    end = min(end, total) if end is not None and total else (end or total)
    duration = end - start
    if duration <= 0:
        raise RuntimeError("切り出し範囲が動画の長さを超えています")
    if duration > MAX_DURATION:
        over = f"長さ {fmt_time(duration)} が上限の 2:20 を超えています。最初の 2:20 だけ使いますか？"
        if not args.cut and not (args.interactive and ask_yes(over)):
            raise RuntimeError(
                f"長さ {fmt_time(duration)} が無料アカウントの上限 2:20 を超えています。"
                " --cut で 2:20 に切るか、--trim で範囲を指定してください。"
            )
        print(f"  長さ {fmt_time(duration)} → 2:20 に切ります")
        duration = MAX_DURATION

    bitrate = pick_bitrate(out_w, out_h, float(out_fps), duration, has_audio)
    hdr = vs.get("color_transfer") in HDR_TRANSFERS

    out_dir = Path(args.out) if args.out else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{src.stem}_x.mp4"
    if dst.resolve() == src.resolve():
        raise RuntimeError("出力先が入力と同じファイルです")

    print(
        f"  入力: {w}x{h} {float(src_fps):.2f}fps {vs.get('codec_name')}"
        f"{' HDR' if hdr else ''} {fmt_time(duration)}"
    )
    print(f"  出力: {out_w}x{out_h} {float(out_fps):.2f}fps H.264 {bitrate / 1e6:.1f}Mbps"
          f"{' (HDR→SDR)' if hdr else ''}")

    vf = build_filters(vs, out_w, out_h, out_fps, args.denoise)
    gop = str(max(1, round(float(out_fps) * 2)))
    head = [ffmpeg, "-hide_banner", "-loglevel", "error", "-stats", "-y"]
    if start:
        head += ["-ss", f"{start:.3f}"]
    head += ["-i", str(src), "-t", f"{duration:.3f}", "-map", "0:v:0", "-vf", vf]
    color = ["-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv"]
    rate = ["-b:v", str(bitrate), "-maxrate", str(int(bitrate * 1.5)), "-bufsize", str(bitrate * 2)]
    audio = ["-map", "0:a:0", "-c:a", "aac", "-b:a", str(AUDIO_BITRATE), "-ar", "48000", "-ac", "2"] if has_audio else ["-an"]
    tail = ["-metadata:s:v:0", "rotate=0", "-movflags", "+faststart", "-sn", "-dn", str(dst)]

    try:
        encode(args.fast, head, gop, rate, color, audio, tail)
    except RuntimeError:
        dst.unlink(missing_ok=True)  # 途中までの壊れたファイルを残さない
        if args.fast:
            raise RuntimeError(
                "NVENC でのエンコードに失敗しました。ffmpeg が古いと最近の GPU ドライバで NVENC が使えません。"
                " ffmpeg を新しくするか、--fast なしで実行してください。"
            ) from None
        raise

    size = dst.stat().st_size
    print(f"  完了: {dst} ({size / 1024 / 1024:.1f}MB)")
    if size > MAX_SIZE:
        print("  警告: 512MB を超えています。X にアップロードできません。")
    return dst


def encode(fast, head, gop, rate, color, audio, tail):
    if fast:
        video = ["-c:v", "h264_nvenc", "-preset", "p6", "-tune", "hq", "-rc", "vbr", "-multipass", "fullres",
                 "-profile:v", "high", "-spatial-aq", "1", "-rc-lookahead", "32", "-bf", "2", "-g", gop, *rate]
        run(head + video + color + audio + tail)
        return
    video = ["-c:v", "libx264", "-preset", "slow", "-profile:v", "high", "-level", "4.2",
             "-bf", "2", "-g", gop, *rate]
    with tempfile.TemporaryDirectory() as tmp:
        log = os.path.join(tmp, "pass")
        print("  [1/2] 解析中...")
        run(head + video + ["-pass", "1", "-passlogfile", log] + color + ["-an", "-f", "null", os.devnull])
        print("  [2/2] エンコード中...")
        run(head + video + ["-pass", "2", "-passlogfile", log] + color + audio + tail)


def run(cmd):
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg がエラーで終了しました (code {r.returncode})")


def main():
    ap = argparse.ArgumentParser(description="動画を X(Twitter) 向けにエンコードし直します。")
    ap.add_argument("inputs", nargs="*", type=Path, help="入力動画 (省略するとファイル選択画面を開く)")
    ap.add_argument("-o", "--out", help="出力先フォルダ (デフォルト: 入力と同じ場所に <名前>_x.mp4)")
    ap.add_argument("--fast", action="store_true", help="NVENC で高速エンコード (画質はやや落ちる)")
    ap.add_argument("--trim", type=parse_trim, metavar="START-END", help="切り出し (例: 0:10-1:30, 5-)")
    ap.add_argument("--cut", action="store_true", help="2:20 を超える分を自動で切る")
    ap.add_argument("--denoise", action="store_true", help="軽いノイズ除去 (暗所・粗い映像向け)")
    ap.add_argument("--ffmpeg", help="ffmpeg.exe またはそのフォルダの場所")
    args = ap.parse_args()
    args.interactive = launched_from_explorer()

    try:
        failed = run_all(args)
    except Exception as e:  # ウィンドウが閉じる前にエラーを読めるようにする
        print(f"エラー: {e}")
        failed = 1
    if args.interactive:
        input("\nEnter キーで閉じます...")
    sys.exit(1 if failed else 0)


def run_all(args):
    ffmpeg = find_tool("ffmpeg", args.ffmpeg)
    ffprobe = find_tool("ffprobe", args.ffmpeg)

    inputs = args.inputs or pick_files()
    if not inputs:
        print("動画が選ばれませんでした。")
        return 1

    failed = 0
    done = []
    for src in inputs:
        print(f"{src}")
        if not src.is_file():
            print("  エラー: ファイルがありません")
            failed += 1
            continue
        try:
            done.append(convert(src, args, ffmpeg, ffprobe))
        except RuntimeError as e:
            print(f"  エラー: {e}")
            failed += 1
    if args.interactive and done:
        # 変換したファイルをエクスプローラーで選択した状態で開く
        subprocess.run(["explorer", f"/select,{done[-1]}"])
    return failed


if __name__ == "__main__":
    main()
