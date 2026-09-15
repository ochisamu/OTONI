# 導入ガイド

すべてリポジトリ直下で実行します。サポート対象の基準はWSL2 + Ubuntu + NVIDIA CUDAです。動作確認環境はREADMEに記載しています。

## 1. 共通環境とYuE2

READMEのOSパッケージ、uv、`nvidia-smi`の確認後：

```bash
cp .env.example .env
./scripts/setup.sh
./scripts/start.sh
```

既に `.env` がある場合は上書きせず、例との差分を確認します。setupはPython 3.12の仮想環境、CUDA 12.8用PyTorch、ハッシュ検証付きYuE2 wheelと固定revisionの重みを取得します。GPUが見えない場合は、先にWindows側ドライバーとWSL GPUの設定を確認してください。

## 2. 追加モデル

### ACE-Step

```bash
./scripts/setup_ace.sh
```

別の `.venv-ace` へ公式ソースの固定commitと、そのcommitのuv.lockから導入します。標準はXL Turbo・BF16・CPU退避・8ステップ・追加5Hz LMなしです。初回はダウンロードに時間と容量が必要です。

### Stable Audio

まず [公式モデルページ](https://huggingface.co/stabilityai/stable-audio-3-medium)で、利用するアカウントでアクセス条件を確認・同意します。その後、共通環境のHF CLIでログインします。まだ存在しない `.venv-stable` のCLIを使う必要はありません。

```bash
.venv/bin/hf auth login
./scripts/setup_stable.sh
```

トークンはCLIの対話入力へ渡し、コード・`.env.example`・Issueへ書きません。アカウントのアクセスが承認されていない場合、ダウンロードは失敗します。公式の重みと付属T5Gemmaを固定revisionで取得し、`.venv-stable` で実行します。LargeのクラウドAPIを使用する機能ではありません。

モデル導入後は画面を再読み込みします。状態が更新されない場合は生成終了後にサーバーを再起動します。

## 3. Codex / ChatGPT

[公式Codex導入案内](https://learn.chatgpt.com/docs/quickstart)に従ってLinux/WSLから実行できるCodexを用意します。`codex --version` と `codex app-server --help` を確認してください。CLIがPATHにない場合は `.env` の `YUE_CODEX_BIN` にLinux実行ファイルの絶対パスを指定します。

同じOSユーザー・設定ディレクトリのCodexログインを使います。必要な場合だけ `CODEX_HOME` で既存設定の場所を指定してください。他人の認証ファイルをコピーする手順はありません。

アプリ上部のChatGPT接続ボタンからログインできます。本アプリはApp ServerのChatGPTアカウントを利用し、APIキー方式の作詞は実装していません。ログイン方式と資格情報管理は [公式認証ガイド](https://learn.chatgpt.com/docs/auth)、プロトコルは [公式App Serverドキュメント](https://learn.chatgpt.com/docs/app-server)を参照してください。

曲の説明・歌詞・スタイル・参考作品などをCodexへ送ります。利用枠を消費します。ジャケット生成、Web検索、モデル一覧はCodex側のバージョン・アカウント・利用可能な機能にも依存します。検証済みCLIは `0.154.0-alpha.6.2` で、すべての公開CLI版での互換性を保証していません。

## 4. バックグラウンド起動

WSLでユーザーsystemdが使える場合：

```bash
./scripts/service.sh start
./scripts/service.sh status
./scripts/service.sh logs
# 生成中ではないことを確認してから
./scripts/service.sh restart
./scripts/service.sh stop
```

現在の配置先を使ってユーザーunitを生成し、有効化します。unit名は旧名の `yue2-studio.service` を継続使用します。ユーザーsystemdの起動条件やWSLの起動そのものはWindows側の設定に依存します。不要なら `systemctl --user disable --now yue2-studio.service` で自動起動を解除してください。

systemdが使えない環境では `./scripts/start.sh` を使います。リポジトリを移動した場合は停止後にstartしてunitを再生成します。空白を含むパスの仮想環境・外部ツール互換性は未検証のため、単純なLinuxパスを推奨します。

## 5. 任意のLAN接続

`.env` を `YUE_HOST=0.0.0.0` にし、必要なら `YUE_ALLOWED_HOSTS` にアクセスするホスト名を追加して再起動します。WSLのネットワーク方式によってはWindows側転送が必要です。

管理者PowerShellで、**自分のPCのLANアドレスと許可するサブネット**を指定して `scripts/enable-lan.ps1 -LanAddress <PCのIPv4> -Subnet <許可CIDR>` を実行します。このスクリプトはWindowsのportproxyとファイアウォールを変更します。ルーターのポート開放は行いません。WSLのIPが変わったら再設定が必要です。

YouTubeの認証・投稿はlocalhostの認証済みブラウザに限定します。設定手順は稼働画面の `/static/youtube-setup.html` を参照してください。動画の生成・ダウンロード自体にGoogleアカウントは不要です。

## よくある問題

- GPU不足：他のGPUアプリを終了し、短い曲で試します。複数workerの同時起動は避けます。
- HF 401/403：利用条件の同意とCLIのアカウントを確認。トークンをログへ出さないでください。
- Codex接続失敗：Linux実行可能ファイル、設定ディレクトリ、ChatGPTログインとCLI版を確認。
- 動画の文字描画失敗：`fonts-ipafont-gothic`を導入。FFmpeg/ffprobeも必要です。
- 終了・再起動：生成中の曲は中断します。アルバムは完成済み曲を保って再開できますが、途中音声からの再開ではありません。
