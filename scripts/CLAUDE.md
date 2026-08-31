## Build Scripts

プロジェクトのビルドとデプロイを補助するスクリプト群。

## Scripts

```
scripts/
└── build-layer.sh    # Lambda Layer ビルドスクリプト
```

## build-layer.sh

Lambda用のPython依存関係レイヤーをビルドする。

### Usage

```bash
./scripts/build-layer.sh
```

### What It Does

1. **クリーンアップ**: 以前のビルド成果物を削除
2. **ディレクトリ作成**: `lambda/layer-dist/python/` 構造を作成
3. **依存関係インストール**: `uv pip install --target` で依存関係をインストール
4. **最適化**: 不要ファイル削除（`__pycache__`、`.dist-info`、`.pyc`、`.pyo`）
5. **確認**: レイヤーサイズとインストール済みパッケージを表示

### Output

```
lambda/
└── layer-dist/           # ビルド出力（gitignore）
    └── python/           # Lambda Layer構造
        ├── linebot/
        ├── openai/
        ├── boto3/
        ├── pytz/
        └── ...
```

### Dependencies Source

`pyproject.toml` の依存関係を使用:

```toml
dependencies = [
    "line-bot-sdk>=3.17.1",
    "openai>=1.0.0",
    "boto3>=1.28.0",
    "pytz>=2023.3",
    "xai-sdk>=1.0.0",
]
```

### Lambda Layer Structure

AWS Lambdaが認識するレイヤー構造:
```
python/
└── {packages}
```

CDKで参照:
```typescript
new lambda.LayerVersion(this, 'DependenciesLayer', {
  code: lambda.Code.fromAsset(path.join(__dirname, '../../lambda/layer-dist')),
  compatibleRuntimes: [PYTHON_RUNTIME],
});
```

### Requirements

- **uv**: Astral社製の高速Pythonパッケージマネージャー
- **bash**: シェルスクリプト実行環境

### Execution Context

- CI/CD（GitHub Actions）とローカル開発の両方で使用
- プロジェクトルートから実行することを想定

### Error Handling

`set -e` により、エラー発生時はスクリプトが即座に終了。

## Adding New Scripts

新しいスクリプトを追加する際のガイドライン:

1. **実行権限**: `chmod +x scripts/new-script.sh`
2. **Shebang**: `#!/bin/bash` を先頭に
3. **エラーハンドリング**: `set -e` で厳格モード
4. **相対パス**: `SCRIPT_DIR` パターンを使用
5. **ログ出力**: 進捗を分かりやすく表示

```bash
#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔨 Starting process..."
# ...
echo "✅ Done!"
```
