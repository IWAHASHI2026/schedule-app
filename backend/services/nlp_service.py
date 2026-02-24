import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


def parse_modification(input_text: str, current_summary: str) -> list[dict]:
    """
    Use Claude API to parse a natural language shift modification request
    into structured constraint data.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "your-api-key-here":
        raise ValueError("ANTHROPIC_API_KEY is not configured")

    client = Anthropic(api_key=api_key)

    prompt = f"""以下のシフト修正指示を、JSON形式の構造化データに変換してください。

入力: {input_text}

現在のシフト情報:
{current_summary}

出力形式（JSON配列）:
[
  {{
    "employee_name": "スタッフ名",
    "job_type": "仕事種類名（職人/サブ職人/データ/その他）",
    "action": "increase" または "decrease" または "set",
    "amount": 数値またはnull（具体的な数値が指定されていない場合はnull）
  }}
]

注意:
- employee_nameは現在のシフト情報に含まれるスタッフ名と正確に一致させてください
- job_typeは「職人」「サブ職人」「データ」「その他」のいずれかを使用してください
- amountがnullの場合、increase/decreaseは現在の値から±2として扱われます
- JSON配列のみを出力してください。説明文は不要です。"""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    response_text = message.content[0].text.strip()

    # Extract JSON from response
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            elif line.startswith("```") and in_block:
                break
            elif in_block:
                json_lines.append(line)
        response_text = "\n".join(json_lines)

    return json.loads(response_text)
