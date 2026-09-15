# 再現性と検証

## 検証した環境

2026-09-15時点の開発機：WSL2、Ubuntu 22.04.3 LTS、RTX 5060 Ti 16GB（nvidia-smi: 16311 MiB）、Windowsドライバー591.86、Python 3.12.11。

| 環境 | PyTorch | 固定・記録方法 |
|---|---|---|
| 共通 / YuE2 | 2.10.0 + cu128 | requirements.txt、locks/yue2-constraints.txt、models.lock.json、vendor/SHA256SUMS |
| ACE-Step | 公式ソースのuv.lock参照 | ace.lock.json、上流uv sync --frozen。locks/ace-constraints.txtは開発機の参考記録 |
| Stable Audio | 2.7.1 + cu128 | stable.lock.json、locks/stable-constraints.txt |

YuE2 wheelは公式配布先から取得後SHA-256を照合。YuE2の重みは公式manifestがある場合に照合します。ACEの取得処理は固定revisionのLFSハッシュを検証します。Stableは固定commitから取得しますが、本アプリ独自の全ファイルハッシュ検証は実装していません。

constraintsは動作したPython依存のバージョン記録です。OS、ドライバー、配布サーバーの可用性、wheelの供給まで固定するコンテナイメージではありません。setup_aceは公式lock、他のsetupはconstraintsを使います。開発機へ後から追加した評価用依存が参考記録に含まれることがありますが、constraintsだけでは追加インストールされません。

## 検証済み／未検証

- 既存開発機で3モデルの音声生成を確認。
- 単曲キュー、アルバム、入力支援の配線、ストレージ、実FFmpeg動画、YouTube通信のモックをpytestで検証。
- スマホ幅のUIを開発時にheadless Chromeで確認。iPhoneのDynamic Island実機表示は未検証。
- GPUなしの新規venvと公開用コピーからアプリテストを実施する手順を用意。
- **別PCでの全モデルのクリーンインストールとGPU生成は未検証。** CIでも重みをダウンロードせず、GPU・Codexログイン・実際のYouTube公開をテストしません。

## 追試

```bash
python3 scripts/doctor.py
.venv/bin/python -m pytest -q
```

doctorは環境変数や認証ファイルを表示せず、OS・ツール・GPU・各Python環境とモデルマーカーの有無を報告します。マーカーの存在はモデルの完全性・生成成功の証明ではありません。

GPUなしのアプリテスト：

```bash
uv venv --python 3.12 .venv-test
uv pip install --python .venv-test/bin/python -r requirements-test.txt
.venv-test/bin/python -m pytest -q
```

FFmpegとIPAフォントが必要です。音声はテスト内で短い合成波形を作るため、個人の曲や外部サービスの資格情報は不要です。

実機確認は1モデルずつ行い、まず短い固定入力を使用してください。Codex自動支援をOFFにした入力、seed、モデルrevision、使用環境を保存します。生成後は試聴と保存ファイルの長さを確認します。プロンプト指定BPMと音声の実測BPMは区別してください。

## 同じ曲を再現するとき

`data/songs/<ID>/input.json` が実際のモデル入力です。自動支援前の `submitted.json` と区別します。`assistance.json`、`summary.json`、譜面や保存された生成結果も比較に使います。

同じ元依頼をCodexへもう一度渡すと、タイトル・歌詞・スタイル・秒数が変わり得ます。音声生成だけを比較するなら確定した入力を使い、自動支援をOFFにします。同じseedでもGPU・torch・カーネル・モデルrevisionが異なれば、ビット単位で同じ音になる保証はありません。

### 公開準備時の結果（2026-09-15）

公開対象だけを別ディレクトリへ書き出し、新しく作成したPython 3.12環境へrequirements-test.txtをインストールして既存69テストが成功しました。公開処理・サービスパス用の追加3テストも含め、最終公開コピーで72テストすべてが成功しています。GPU依存を入れずに確認した結果です。セットアップのconstraintsは既存の動作環境に対するdry-run解決も確認しました。モデルの再ダウンロードや別GPUでの追試を意味するものではありません。
