# OTONI（オトニ）

[English](README.md) | **日本語**

日本語で曲のイメージを考え、ローカルGPUで生成し、アルバムとして聴くための音楽生成支援ツールです。YuE2・ACE-Step・Stable Audioを同じライブラリで扱います。OTONI自体は音楽生成モデルを提供せず、各モデルの入力・実行・生成物の管理を支援します。

**Windows + WSL2 + NVIDIA GPU向けの実験的な個人用アプリです。** 音声生成はローカルで動きます。Codexによる作詞・構成・参考情報の調査・ジャケット生成には、ネット接続とChatGPTでのCodexログインが必要です。完全オフラインのAI作詞ツールではありません。

## できること

- 単曲とアルバムの生成。曲ごとにモデルを選ぶ「おまかせ混在」も利用可能
- ジャンル・BPM・歌声・長さを指定し、Codexでモデル別のプロンプトを設計
- 日本語、英語、中国語、日本語中心＋短い英語フレーズの歌詞
- インスト、生成済みの曲からの派生、生成条件・歌詞の閲覧
- M4A/FLAC保存、共通プレイヤー、シャッフル、スマホ対応、ダークテーマ
- ジャケットと曲名が切り替わるYouTube用動画の作成、任意のYouTube接続

## モデルと動作範囲

| モデル | アプリでの用途 | 曲長の指定 | 追加環境 |
|---|---|---|---|
| YuE2-3B | 歌声・実験的なインスト、ABC譜面による構成 | 目安。秒数の保証なし | `.venv` |
| ACE-Step 1.5 XL Turbo | 歌声・インスト、音源からの派生 | 固定10〜180秒／おまかせ30〜180秒 | `.venv-ace` |
| Stable Audio 3 Medium | インスト専用 | 固定10〜180秒／おまかせ30〜180秒 | `.venv-stable` |
| DiffSynth Music | 通常生成・ビート・音声制御 | 固定10〜180秒／おまかせ30〜180秒 | `.venv-diffsynth` |
| MuLaCover | 完成曲からカバー | 10〜180秒の生成上限 | `.venv-mulacover` |

上限はアプリ側の設定です。モデル本来の最大長とは異なります。GPU処理は全モデル共通で**1曲ずつ**進みます。入力したBPM・声質・ジャンル・歌詞が期待どおり音に反映される保証はありません。

## 最初のセットアップ

動作確認環境は **WSL2 Ubuntu 22.04、RTX 5060 Ti 16GB、Windows側ドライバー591.86、Python 3.12.11** です。macOS、AMD、CPUのみ、Windowsネイティブでは検証していません。別GPUでの最低VRAMも未検証です。

次のコマンドでリポジトリを取得し、そのディレクトリで実行します。

```bash
git clone https://github.com/ochisamu/OTONI.git
cd OTONI
```

WSLのLinuxファイルシステム上（例：`~/workspace/otoni`）を使用してください。以下の手順は最初に共通環境とYuE2を導入します。ACE/Stableだけを使う場合でも、現状のセットアップには共通のYuE2環境が必要です。

```bash
sudo apt update
sudo apt install -y git curl ffmpeg fonts-ipafont-gothic
# uvを公式手順でインストールしてから続けます。
nvidia-smi
cp .env.example .env
./scripts/setup.sh
./scripts/start.sh
```

[uvのインストール手順](https://docs.astral.sh/uv/getting-started/installation/)を参照してください。WSL内へLinux用ディスプレイドライバーを追加する手順は含めていません。

ブラウザで **http://localhost:7860** を開きます。ターミナルを閉じると停止します。バックグラウンド起動、追加モデル、Codexログインは **[導入ガイド](docs/SETUP.md)** を参照してください。

最初は単曲生成で「生成前にCodexで整える」をOFFにして英語サンプルを入力し、YuE2で1曲作ると、認証とGPUの問題を分けて確認できます。アルバムの自動構成にはCodexが必要です。

## 追加モデルとCodex（任意）

共通セットアップの後、使いたいモデルだけを追加します。最初に `./scripts/start.sh` で起動している場合は、生成終了後にCtrl+Cで停止してから実行してください。

```bash
# ACE-Step 1.5 XL Turbo
./scripts/setup_ace.sh

# Stable Audio 3 Medium：先に公式モデルページでアクセス条件に同意
.venv/bin/hf auth login
./scripts/setup_stable.sh
```

Stable Audioの同意先は [公式モデルページ](https://huggingface.co/stabilityai/stable-audio-3-medium) です。同じアカウントのトークンをHF CLIの対話入力へ渡します。コードやIssueには記載しません。

Codex支援を使う場合は [公式導入案内](https://learn.chatgpt.com/docs/quickstart) に従ってLinux/WSLで動くCodexを用意し、`codex --version` と `codex app-server --help` を確認してください。PATHにない場合は `.env` の `YUE_CODEX_BIN` に実行ファイルの絶対パスを指定します。アプリ上部のChatGPT接続ボタンからログインできます。作詞・構成・画像生成などにはCodexの利用枠を使います。検証済みCLIは `0.154.0-alpha.6.2` です。

## 起動して最初の1曲を作る

セットアップ後、取得したディレクトリで実行します。新しいターミナルなら、まず配置先へ移動してください。

```bash
# 配置先の例。別の場所へcloneした場合は読み替えてください。
cd ~/workspace/OTONI
./scripts/start.sh
```

Uvicornの起動表示が出たら、Windowsのブラウザで **http://localhost:7860** を開きます。起動したターミナルは開いたままにします。

1. 「曲をつくる」で導入済みのモデルを選びます。
2. 最初のYuE2動作確認では英語サンプルを入力し、「生成前にCodexでメロディー・構成を整える」をOFFにします。この方法ではChatGPTログインは不要です。
3. 「曲を生成」を押します。GPU処理は1曲ずつです。初回はモデルの読み込みなどで時間がかかる場合があります。
4. 「すべての曲」で完成した曲を再生します。詳細から歌詞や生成条件も確認できます。

Codexで作詞・入力支援する場合やアルバムを自動構成する場合は、ChatGPTへ接続してから使います。Stable Audioはインスト専用です。

**停止はCtrl+C**です。生成中の停止は曲を中断するため、完了後に停止してください。再び起動するときは同じコマンドを実行します。ブラウザだけ閉じてもサーバーや生成キューは停止しません。

### バックグラウンドで起動する場合

WSLのユーザーsystemdが使える環境では、上の起動方法の代わりに以下を使えます。二重起動は避けてください。

```bash
./scripts/service.sh start
./scripts/service.sh status
./scripts/service.sh logs
# 生成が終わってから停止・再起動
./scripts/service.sh stop
./scripts/service.sh restart
```

現在の配置先でユーザーサービスを生成・有効化します。unit名は `yue2-studio.service` です。WSL自体の起動やユーザーサービスの起動条件は端末設定に依存します。自動起動の解除は `systemctl --user disable --now yue2-studio.service` です。systemdが使えなければ `./scripts/start.sh` を使ってください。

## 容量と再現性

モデル・仮想環境・ダウンロードキャッシュで数十GBを使用します。目安はYuE2の重み約7.3GB、ACE追加約21GB、Stable追加約9.8GB。さらに各Python環境、キャッシュ、曲、動画の空き容量が必要です。DiffSynthは約34GB、MuLaCoverと付属モデルは約17GBをさらに使います。5モデルすべてでは150〜200GB程度の空きを計画上の目安にし、キャッシュも含めた実際の消費量を確認してください。

ソース・重みのrevision、Python依存関係の記録、テスト方法、再現できない部分は **[再現性と検証](docs/REPRODUCIBILITY.md)** にまとめています。既存PCでの動作確認と、別PCでのクリーンインストール確認を区別しています。同じseedでも別環境やCodexによる再提案で同一音声になるとは限りません。

## データ・接続・利用条件

生成した音声・歌詞・設定は通常 `data/`、モデルは `models/`、一時ファイルは `work/` に置きます。リポジトリには含めません。バックアップするときは音声だけでなく `data/` を保存してください（YouTube接続情報も含まれるため取扱いに注意）。M4A/FLACへの変換後は検証を経て重複WAVを削除します。削除操作には元に戻す機能がありません。

LAN公開は任意です。複数ユーザーのログイン・権限分離を備えていないため、インターネットへ直接公開するサーバー用途は想定していません。詳細は [接続とデータ](docs/SECURITY.md) を参照してください。

OTONIは生成支援ツールです。**モデルの利用条件は、利用する各モデルの公式ライセンス・モデルカード・付属通知を参照してください。** モデル重み・推論wheel・外部リポジトリは同梱せず、導入時に公式配布元から取得します。参照先は [第三者コンポーネント](THIRD_PARTY_NOTICES.md) にまとめています。

生成した音楽の公開・商用利用などについて、OTONIが一律に許可や保証を与えるものではありません。利用するモデルや関連サービスの条件、入力素材・生成物に関する権利を利用者が確認してください。モデルのライセンスがそのまま生成物へ適用されると一律に扱うものでもありません。

OTONI独自コードは **[MIT License](LICENSE)** で公開します。モデル・外部コンポーネントの利用条件とは別です。

## 開発・報告

[開発ガイド](CONTRIBUTING.md) ／ [公開前チェック](docs/RELEASE.md)

不具合報告には、OS・GPU・モデル・エラーの再現手順を記載してください。`.env`、認証ファイル、個人の歌詞や生成物を丸ごと添付しないでください。

## DiffSynth Music / MuLaCover

DiffSynth Musicの通常生成・音声制御と、MuLaCoverの元曲からのカバー生成に対応。[導入と操作・利用条件](docs/CONTROL_MODELS.md)を参照してください。
