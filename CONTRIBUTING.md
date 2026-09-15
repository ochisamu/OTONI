# 開発する

Python 3.12、FFmpeg、IPA Pゴシックを用意し、`requirements-test.txt` でGPUなしのテスト環境を作れます。詳しくは [再現性](docs/REPRODUCIBILITY.md) を参照してください。

- `app.py`：API、ジョブキュー、入力支援の接続
- `schemas.py` / `album_schemas.py`：リクエストと生成案の検証
- `worker*.py`：隔離したモデル実行プロセス
- `codex_bridge.py` / `codex_tasks.py`：Codex App Server
- `albums.py`：構成と順次生成、再開
- `album_video.py` / `video_artwork.py`：動画と曲名描画
- `web/`：ビルド不要のHTML/CSS/JavaScript

変更後は `python -m pytest -q`。モデル関連の変更は短い実音声生成も別途確認し、GPU、依存バージョン、固定入力、実行時間、失敗条件を記録してください。CIの成功だけでは音声品質やGPU実行の検証になりません。

公開されるIssue・PRにトークン、個人のデータ、外部モデル重みを含めないでください。OTONIへのコードの貢献は、本プロジェクトの [MIT License](LICENSE) に従って提供してください。第三者コードを含める場合は、その出典と利用条件を明記してください。
