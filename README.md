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

## デプロイ (Vercel + Railway)

### Vercel（フロントエンド）

1. [Vercel](https://vercel.com) で New Project → GitHub から `schedule-app` を選択
2. **Root Directory** を `frontend` に設定
3. **Framework Preset** を `Next.js` に設定
4. **Output Directory** は**空のまま**（Next.js は自動で `.next` を使用）
5. 環境変数 `NEXT_PUBLIC_API_URL` に Railway の API URL を設定（例: `https://xxx.railway.app`）
6. Deploy

### Railway（バックエンド）

1. [Railway](https://railway.app) で New Project → GitHub から `schedule-app` を選択
2. **Root Directory** を `backend` に設定
3. 環境変数を設定:
   - `FRONTEND_URL`: Vercel の URL（例: `https://schedule-app-xxx.vercel.app`）
   - `ANTHROPIC_API_KEY`: 自然言語修正機能を使う場合
4. Deploy → 生成された URL を `NEXT_PUBLIC_API_URL` に設定して Vercel を再デプロイ

> **注意**: Railway の無料プランでは SQLite のデータは再デプロイ時にリセットされます。本番運用では PostgreSQL 等の推奨。

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
