# 第三者コンポーネント

OTONIは各モデルを利用するための生成支援ツールです。モデルを独自に再配布したり、その利用条件を置き換えたりするものではありません。利用するモデルの公式ライセンス・モデルカード・付属通知を参照してください。

OTONI独自コードは [MIT License](LICENSE) です。第三者のコード・モデル・フォント・サービスに一括でアプリのライセンスを適用するものではありません。

本リポジトリにモデル重み、外部の推論wheel、外部リポジトリ本体、フォント本体は含めません。セットアップで取得するものは取得先のLICENSE・モデルカード・付属通知を確認してください。生成物の公開可否や第三者作品との関係を、この一覧だけで判定することはできません。

| コンポーネント | 公式配布元・確認先 | 固定情報 |
|---|---|---|
| YuE2モデル・推論wheel・VAE | https://huggingface.co/m-a-p/YuE2-3B / https://huggingface.co/m-a-p/YuE2-Vae | models.lock.json / vendor/SHA256SUMS |
| ACE-Step | https://github.com/ace-step/ACE-Step-1.5 / https://huggingface.co/ACE-Step/acestep-v15-xl-turbo | ace.lock.json |
| Stable Audio 3 / 付属T5Gemma | https://github.com/Stability-AI/stable-audio-3 / https://huggingface.co/stabilityai/stable-audio-3-medium | stable.lock.json。アクセス条件への同意が必要 |
| IPAフォント | OSパッケージ fonts-ipafont-gothic の著作権・ライセンス通知 | OSパッケージ管理 |
| FFmpeg / Python依存 | 各配布元およびインストール済みパッケージのLICENSE | requirements / locks |
| Codex | https://learn.chatgpt.com/docs/app-server | サービスとCLIの利用条件を確認 |

プロンプトガイドには参照した公式文書・revisionと、アプリ側の作曲方針を記載しています。上流の変更を取り込む場合は、技術的な互換性だけでなく通知・利用条件も再確認してください。
