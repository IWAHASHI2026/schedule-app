# シフト管理システム (Shift Scheduler)

約20名のスタッフに対して、月間のシフト表を自動生成するWebアプリケーションです。

## 技術スタック

- **フロントエンド**: Next.js 15 (App Router) + TypeScript + shadcn/ui + Tailwind CSS
- **バックエンド**: Python + FastAPI
- **最適化エンジン**: Google OR-Tools (CP-SAT ソルバー)
- **自然言語修正**: Claude API (Anthropic)
- **データベース**: SQLite

## セットアップ

### 1. バックエンド

```bash
cd backend
pip install -r requirements.txt
```

`.env` ファイルに Anthropic API キーを設定（自然言語修正機能を使う場合）:

```
ANTHROPIC_API_KEY=your-api-key-here
```

起動:

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

### 2. フロントエンド

```bash
cd frontend
npm install
npm run dev
```

### アクセス

- フロントエンド: http://localhost:3000
- バックエンド API: http://localhost:8000
- API ドキュメント: http://localhost:8000/docs

## 画面構成

| パス | 画面名 | 説明 |
|------|--------|------|
| `/` | ダッシュボード | シフト生成状況・アラート表示 |
| `/staff` | スタッフ管理 | スタッフの登録・編集・担当業務設定 |
| `/requests` | 希望入力 | スタッフの希望休日・出勤日数の代理入力 |
| `/requirements` | 必要人数設定 | 日別・業務種別ごとの必要人数設定 |
| `/generate` | シフト自動生成 | 最適化エンジンによる自動生成・自然言語修正 |
| `/schedule` | シフト表 | マトリクス表示・手動調整・確定/公開 |
| `/reports` | 集計・レポート | スタッフ別集計・公平性グラフ |
| `/export` | シフト出力 | CSV/Excel/PDF出力 |
