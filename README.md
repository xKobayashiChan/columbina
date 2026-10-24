# columbina

撮った動画を X(Twitter) 向けにエンコードし直す CLI です。

X はアップロードされた動画を必ず再エンコードします。高fps・HEVC・HDR などの仕様外の動画は特に荒れやすいので、
先に X の推奨形式に揃えておくことで劣化を抑えます。

## 配布用 exe（PC に詳しくない人向け）

[Releases](https://github.com/xKobayashiChan/columbina/releases/latest) から `X-video-converter-setup-<バージョン>.exe` をダウンロードして開くだけで使えます。
管理者権限はいりません。インストールすると、デスクトップのショートカットと、右クリックの「送る」メニューに「X動画変換」が追加されます。
動画をショートカットにドラッグ&ドロップするか、動画を右クリック →「送る」→「X動画変換」で変換できます。
インストールしたくない人向けに zip 版もあります。

Python と ffmpeg は同梱しているので、相手の PC には何も入れる必要はありません。説明は同梱の `使い方.txt` に書いてあります。

### リリース方法 (GitHub Actions)

`main` への push と PR では毎回、exe・zip・setup.exe のビルドと動作確認（サイレントインストールしてテスト動画を変換）を行います。
できたファイルは Actions の実行結果ページの Artifacts からダウンロードできます。

新しいバージョンを配るときは、タグを push するだけです。ビルド後に GitHub Release が自動で作られ、setup.exe と zip が載ります。

```
git tag v1.1.0
git push origin v1.1.0
```

### ローカルでビルドする場合

```
python -m venv .venv
.venv\Scripts\python -m pip install pyinstaller==6.11.1
winget install JRSoftware.InnoSetup
# vendor\ffmpeg\ に ffmpeg.exe / ffprobe.exe / LICENSE を置く（https://www.gyan.dev/ffmpeg/builds/ の essentials）
.venv\Scripts\python build.py --version 1.1.0   # → dist\ に zip と setup.exe
```

同梱している FFmpeg は GPL v3 です。配布物に入っている `FFmpeg-LICENSE.txt` は消さないでください。

## コマンドラインで使う場合の必要なもの

- Python 3.10 以上（追加パッケージなし）
- ffmpeg / ffprobe（PATH 上、または `C:\ffmpeg\bin`、または `--ffmpeg` で指定）

## 使い方

```
python tw.py 動画.mp4                 # 動画と同じ場所に 動画_x.mp4 ができる
python tw.py a.mp4 b.mov -o out       # まとめて変換、out フォルダに出力
python tw.py clip.mp4 --trim 0:10-1:30  # 切り出し
python tw.py long.mp4 --cut           # 2:20 を超える分を切る
python tw.py dark.mp4 --denoise       # 暗所・ノイズの多い映像
python tw.py clip.mp4 --fast          # NVENC (GPU) で高速エンコード ※新しい ffmpeg が必要
```

## 出力される形式

| 項目 | 内容 |
|---|---|
| 映像 | H.264 High, yuv420p 8bit, BT.709, 2-pass (libx264 slow) |
| 解像度 | 横 ≤1920x1080 / 縦 ≤1080x1920（拡大はしない） |
| fps | 60 を超える場合は 60 に（120/144/240fps の録画など） |
| ビットレート | 1080p: 8Mbps (≤30fps) / 12Mbps (>30fps)、720p: 5 / 7.5Mbps |
| 音声 | AAC 192kbps 48kHz ステレオ |
| その他 | faststart、HDR は SDR にトーンマップ、回転メタデータは映像に反映済み |

無料アカウントの上限（2分20秒・512MB）を超える場合は警告して止まります（`--cut` で自動カット）。

## ffmpeg の PATH について

環境変数 PATH に `C:ffmpeg\bin`（`\` 抜け）のような誤ったエントリがあると ffmpeg が見つかりません。
`C:\ffmpeg\bin` に直すと、どこからでも `ffmpeg` が使えるようになります（このツールは直さなくても `C:\ffmpeg\bin` を自動で探します）。

## --fast (NVENC) について

NVIDIA の GPU で高速にエンコードします。ffmpeg 4.x などの古い ffmpeg は最近のドライバで NVENC が使えないので、
新しい ffmpeg（https://www.gyan.dev/ffmpeg/builds/ など）を使ってください。
