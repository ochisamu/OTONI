# GitHub公開前チェック

公開先は https://github.com/ochisamu/OTONI です。以下は更新を公開するときのチェック手順です。

1. OTONI独自コードのMIT LICENSEと第三者コンポーネントの通知が含まれることを確認する。著作権表示は「2026 OTONI contributors」。モデルの条件は各配布元を参照する方針を維持する。
2. `python3 scripts/export_source.py --output dist/otoni-source` で公開専用のコピーを作る。既存の出力先には上書きしない。
3. `release-manifest.json` とファイル一覧を確認する。allowlistに新しく公開したいファイルがあれば、内容を確認して追加する。
4. コピー先で新しいvenvを作り、requirements-test.txtとpytestを実行する。
5. 別PCまたは新しいWSL環境でREADMEどおりに導入し、GPUで短い曲を生成する。実施していなければ、その旨を残す。
6. コピー先でGitを初期化してステージ内容をレビューし、公開する。

`.gitignore`だけに頼らず、公開コピーは `release-files.txt` の完全なファイル一覧から作成します。未知のファイルを自動で含めません。簡易トークン・個人パス検査も行いますが、すべての秘密情報を検知する保証はないため、最終一覧のレビューは必要です。

モデルrevisionを更新するときはlockを意図的に更新し、同じ入力・seedで新旧を比較してください。READMEのclone先は公開リポジトリを指定しています。
