import os
import json
from pathlib import Path
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def parse_modification(input_text: str, current_summary: str, schedule_detail: str = "") -> list[dict]:
    """
    Use Claude API to parse a natural language shift modification request
    into structured constraint data.

    schedule_detail: per-employee daily schedule (e.g. "若生亜紀子: 3/2=データ, 3/3=休み, ...")
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your-api-key-here":
        raise ValueError("ANTHROPIC_API_KEY が設定されていません。backend/.env ファイルを確認してください。")

    client = Anthropic(api_key=api_key)

    prompt = f"""あなたはシフト修正指示を解析するアシスタントです。
ユーザーの指示を読み、必要最小限の変更だけをJSON配列で出力してください。

## ユーザーの修正指示
{input_text}

## 現在のシフト概要
{current_summary}

## 現在の日別スケジュール
{schedule_detail}

## 出力形式

2種類の変更タイプがあります。指示内容に応じて適切なタイプを選んでください。

### タイプ1: pin（特定日の直接変更）— 最も一般的
特定のスタッフの特定日を変更する場合に使います。
{{
  "type": "pin",
  "employee_name": "スタッフ名",
  "date": "YYYY-MM-DD",
  "new_job_type": "職人" / "サブ職人" / "データ" / "その他" / "休み"
}}

### タイプ2: adjust（集計的な変更）
「もっとデータを増やして」のような日付を指定しない調整に使います。
{{
  "type": "adjust",
  "employee_name": "スタッフ名",
  "job_type": "職人" / "サブ職人" / "データ" / "その他",
  "action": "increase" / "decrease" / "set",
  "amount": 数値またはnull
}}

## 重要なルール
- employee_nameは現在のシフト情報に含まれるスタッフ名と正確に一致させてください
- 「休みにして」「休日にして」「オフにして」→ new_job_type は "休み"
- 指示された変更だけを出力してください。指示されていない変更は絶対に含めないでください
- 「それ以外は変更しない」等の指示がある場合は特に注意してください
- JSON配列のみを出力してください。説明文は不要です。"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        error_msg = str(e)
        if "credit balance" in error_msg.lower():
            raise ValueError("Anthropic APIのクレジット残高が不足しています。Plans & Billing でチャージしてください。")
        elif "authentication" in error_msg.lower() or "invalid.*key" in error_msg.lower():
            raise ValueError("Anthropic APIキーが無効です。backend/.env のキーを確認してください。")
        raise

    response_text = message.content[0].text.strip()

    # Extract JSON from response (handle ```json ... ``` blocks)
    if "```" in response_text:
        lines = response_text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```") and not in_block:
                in_block = True
                continue
            elif line.strip().startswith("```") and in_block:
                break
            elif in_block:
                json_lines.append(line)
        response_text = "\n".join(json_lines)

    # Extract JSON array even if surrounded by extra text
    start = response_text.find("[")
    end = response_text.rfind("]")
    if start != -1 and end != -1:
        response_text = response_text[start:end + 1]

    # Remove trailing commas before ] or } (common LLM output issue)
    import re
    response_text = re.sub(r",\s*([}\]])", r"\1", response_text)

    return json.loads(response_text)
