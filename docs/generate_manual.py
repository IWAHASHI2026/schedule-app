"""
シフトスケジューラー 取扱説明書 PDF生成スクリプト
ReportLab を使用して日本語PDFを生成する
"""

import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.cidfonts import UnicodeCIDFont

# --- フォント設定 ---
FONT_DIR = "C:/Windows/Fonts"
# BIZ UDゴシックを使用（見やすい日本語フォント）
FONT_REGULAR = os.path.join(FONT_DIR, "BIZ-UDGothicR.ttc")
FONT_BOLD = os.path.join(FONT_DIR, "BIZ-UDGothicB.ttc")

if os.path.exists(FONT_REGULAR):
    pdfmetrics.registerFont(TTFont("JP", FONT_REGULAR, subfontIndex=0))
    pdfmetrics.registerFont(TTFont("JP-Bold", FONT_BOLD, subfontIndex=0))
else:
    # フォールバック: MS Gothic
    pdfmetrics.registerFont(TTFont("JP", os.path.join(FONT_DIR, "msgothic.ttc"), subfontIndex=0))
    pdfmetrics.registerFont(TTFont("JP-Bold", os.path.join(FONT_DIR, "msgothic.ttc"), subfontIndex=0))

# --- カラー定義 ---
PRIMARY = HexColor("#2563EB")       # Blue
PRIMARY_LIGHT = HexColor("#EFF6FF") # Light blue background
ACCENT = HexColor("#3B82F6")
DARK = HexColor("#1E293B")
GRAY = HexColor("#64748B")
LIGHT_GRAY = HexColor("#F1F5F9")
BORDER_COLOR = HexColor("#CBD5E1")

# --- スタイル定義 ---
styles = getSampleStyleSheet()

style_title = ParagraphStyle(
    "Title_JP",
    fontName="JP-Bold",
    fontSize=28,
    leading=36,
    alignment=TA_CENTER,
    textColor=DARK,
    spaceAfter=6*mm,
)

style_subtitle = ParagraphStyle(
    "Subtitle_JP",
    fontName="JP",
    fontSize=14,
    leading=20,
    alignment=TA_CENTER,
    textColor=GRAY,
    spaceAfter=20*mm,
)

style_h1 = ParagraphStyle(
    "H1_JP",
    fontName="JP-Bold",
    fontSize=18,
    leading=26,
    textColor=PRIMARY,
    spaceBefore=8*mm,
    spaceAfter=4*mm,
    borderPadding=(0, 0, 2, 0),
)

style_h2 = ParagraphStyle(
    "H2_JP",
    fontName="JP-Bold",
    fontSize=14,
    leading=20,
    textColor=DARK,
    spaceBefore=5*mm,
    spaceAfter=3*mm,
)

style_h3 = ParagraphStyle(
    "H3_JP",
    fontName="JP-Bold",
    fontSize=11,
    leading=16,
    textColor=DARK,
    spaceBefore=3*mm,
    spaceAfter=2*mm,
)

style_body = ParagraphStyle(
    "Body_JP",
    fontName="JP",
    fontSize=10,
    leading=16,
    textColor=DARK,
    spaceAfter=2*mm,
)

style_body_indent = ParagraphStyle(
    "BodyIndent_JP",
    parent=style_body,
    leftIndent=8*mm,
)

style_bullet = ParagraphStyle(
    "Bullet_JP",
    fontName="JP",
    fontSize=10,
    leading=16,
    textColor=DARK,
    leftIndent=10*mm,
    firstLineIndent=-5*mm,
    spaceAfter=1*mm,
)

style_note = ParagraphStyle(
    "Note_JP",
    fontName="JP",
    fontSize=9,
    leading=14,
    textColor=GRAY,
    leftIndent=5*mm,
    rightIndent=5*mm,
    spaceBefore=2*mm,
    spaceAfter=2*mm,
    backColor=LIGHT_GRAY,
    borderPadding=8,
)

style_step = ParagraphStyle(
    "Step_JP",
    fontName="JP-Bold",
    fontSize=10,
    leading=16,
    textColor=PRIMARY,
    leftIndent=5*mm,
    spaceAfter=1*mm,
)

style_caption = ParagraphStyle(
    "Caption_JP",
    fontName="JP",
    fontSize=9,
    leading=14,
    alignment=TA_CENTER,
    textColor=GRAY,
    spaceBefore=2*mm,
    spaceAfter=4*mm,
)

style_footer = ParagraphStyle(
    "Footer_JP",
    fontName="JP",
    fontSize=8,
    textColor=GRAY,
    alignment=TA_CENTER,
)

# --- パス設定 ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
IMG_DIR = PROJECT_DIR  # スクリーンショットがルートにある

OUTPUT_PDF = os.path.join(SCRIPT_DIR, "シフトスケジューラー取扱説明書.pdf")


def get_image(filename, max_width=160*mm):
    """画像を読み込み、幅に合わせてリサイズ"""
    path = os.path.join(IMG_DIR, filename)
    if not os.path.exists(path):
        print(f"  Warning: Image not found: {path}")
        return Spacer(1, 10*mm)
    img = Image(path)
    aspect = img.imageHeight / img.imageWidth
    img.drawWidth = min(max_width, img.drawWidth)
    img.drawHeight = img.drawWidth * aspect
    # 最大高さ制限
    max_height = 100*mm
    if img.drawHeight > max_height:
        img.drawHeight = max_height
        img.drawWidth = img.drawHeight / aspect
    img.hAlign = "CENTER"
    return img


def make_section_header(number, title):
    """セクション番号付きヘッダーを生成"""
    return Paragraph(
        f'<font color="{PRIMARY.hexval()}">{number}.</font> {title}',
        style_h1,
    )


def section_divider():
    """セクション区切り線"""
    return HRFlowable(
        width="100%", thickness=0.5, color=BORDER_COLOR,
        spaceBefore=2*mm, spaceAfter=2*mm,
    )


def build_cover_page():
    """表紙ページ"""
    elements = []
    elements.append(Spacer(1, 50*mm))
    elements.append(Paragraph("シフトスケジューラー", style_title))
    elements.append(Paragraph("取扱説明書", ParagraphStyle(
        "TitleSub", fontName="JP-Bold", fontSize=22, leading=30,
        alignment=TA_CENTER, textColor=DARK, spaceAfter=10*mm,
    )))
    elements.append(Spacer(1, 10*mm))
    elements.append(HRFlowable(
        width="40%", thickness=2, color=PRIMARY,
        spaceBefore=5*mm, spaceAfter=5*mm,
    ))
    elements.append(Spacer(1, 10*mm))
    elements.append(Paragraph(
        "月間シフトの自動生成・管理・出力を行う<br/>Webアプリケーション",
        style_subtitle,
    ))

    # バージョン情報テーブル
    info_data = [
        ["バージョン", "1.0"],
        ["作成日", "2026年3月"],
    ]
    info_table = Table(info_data, colWidths=[35*mm, 40*mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "JP"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TEXTCOLOR", (0, 0), (0, -1), GRAY),
        ("TEXTCOLOR", (1, 0), (1, -1), DARK),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    info_table.hAlign = "CENTER"
    elements.append(info_table)

    elements.append(PageBreak())
    return elements


def build_toc():
    """目次ページ"""
    elements = []
    elements.append(Paragraph("目次", ParagraphStyle(
        "TOC_Title", fontName="JP-Bold", fontSize=20, leading=28,
        textColor=DARK, spaceAfter=8*mm,
    )))
    elements.append(section_divider())

    toc_items = [
        ("1", "システム概要", "アプリの目的と全体像"),
        ("2", "画面構成", "メニューと各画面の役割"),
        ("3", "基本操作フロー", "シフト作成の手順"),
        ("4", "スタッフ管理", "スタッフの登録・編集"),
        ("5", "希望入力", "休み希望・出勤希望の入力"),
        ("6", "必要人数設定", "日別の必要人数を設定"),
        ("7", "シフト自動生成", "AIによる最適なシフト生成"),
        ("8", "シフト表", "生成結果の確認・手動調整"),
        ("9", "集計・レポート", "スタッフ別集計・充足コメント"),
        ("10", "シフト出力", "CSV / Excel / PDFの出力"),
    ]

    for num, title, desc in toc_items:
        elements.append(Paragraph(
            f'<font color="{PRIMARY.hexval()}"><b>{num}.</b></font>　'
            f'<b>{title}</b>　'
            f'<font color="{GRAY.hexval()}">{desc}</font>',
            ParagraphStyle(
                f"TOC_{num}", fontName="JP", fontSize=11, leading=22,
                textColor=DARK, leftIndent=5*mm,
            ),
        ))

    elements.append(PageBreak())
    return elements


def build_section_1():
    """1. システム概要"""
    elements = []
    elements.append(make_section_header("1", "システム概要"))
    elements.append(section_divider())
    elements.append(Paragraph(
        "シフトスケジューラーは、約20名のスタッフの月間シフトを自動で生成・管理するWebアプリケーションです。",
        style_body,
    ))
    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("主な特徴", style_h2))
    features = [
        ("自動最適化", "AI（Google OR-Tools）がスタッフの希望や制約を考慮して最適なシフトを自動生成します。"),
        ("希望反映", "スタッフの休み希望・出勤希望を入力し、シフトに自動反映します。"),
        ("自然言語調整", "「Aさんの職人を増やして」のように自然な言葉でシフトを微調整できます。"),
        ("集計・レポート", "出勤日数・業種別の配分・公平性などを自動で集計します。"),
        ("多形式出力", "完成したシフトをCSV・Excel・PDFで出力できます。"),
    ]
    for title, desc in features:
        elements.append(Paragraph(
            f'<b>・{title}</b>：{desc}', style_bullet,
        ))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("対応する業種（ジョブタイプ）", style_h2))
    job_types = [
        ("職人", "メインの職種。1日1名配置"),
        ("サブ職人", "サブの職種。1日1名配置"),
        ("lkデータ", "データ入力業務"),
        ("uv/cpデータ", "データ入力業務"),
        ("手紙", "手紙業務"),
        ("その他", "上記以外の業務"),
    ]
    jt_data = [["業種名", "説明"]]
    for name, desc in job_types:
        jt_data.append([name, desc])

    jt_table = Table(jt_data, colWidths=[40*mm, 110*mm])
    jt_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "JP"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (-1, 0), "JP-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    jt_table.hAlign = "LEFT"
    elements.append(jt_table)

    elements.append(PageBreak())
    return elements


def build_section_2():
    """2. 画面構成"""
    elements = []
    elements.append(make_section_header("2", "画面構成"))
    elements.append(section_divider())
    elements.append(Paragraph(
        "画面左側のサイドバーから各機能にアクセスします。以下の8つのメニューがあります。",
        style_body,
    ))
    elements.append(Spacer(1, 3*mm))

    menu_data = [
        ["メニュー", "機能概要"],
        ["ダッシュボード", "システム全体の状況を一覧表示。アラートや統計情報を確認できます"],
        ["スタッフ管理", "スタッフの登録・編集・削除。担当可能な業種の設定を行います"],
        ["希望入力", "スタッフごとの休み希望・出勤希望・週間上限を入力します"],
        ["必要人数設定", "日別・業種別に必要な人数を設定します"],
        ["シフト自動生成", "AIが制約を考慮してシフトを自動生成。自然言語での調整も可能"],
        ["シフト表", "生成されたシフトをマトリクス表示。手動編集も可能です"],
        ["集計・レポート", "スタッフ別の出勤日数・業種配分・希望充足状況を確認"],
        ["シフト出力", "CSV / Excel / PDF形式でダウンロード。共有URLの発行も可能"],
    ]

    menu_table = Table(menu_data, colWidths=[35*mm, 120*mm])
    menu_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "JP"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (-1, 0), "JP-Bold"),
        ("FONTNAME", (0, 1), (0, -1), "JP-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [white, LIGHT_GRAY]),
    ]))
    menu_table.hAlign = "LEFT"
    elements.append(menu_table)

    elements.append(PageBreak())
    return elements


def build_section_3():
    """3. 基本操作フロー"""
    elements = []
    elements.append(make_section_header("3", "基本操作フロー"))
    elements.append(section_divider())
    elements.append(Paragraph(
        "シフトを作成する基本的な流れは以下のとおりです。",
        style_body,
    ))
    elements.append(Spacer(1, 3*mm))

    steps = [
        ("Step 1: スタッフ登録", "「スタッフ管理」画面でスタッフ情報と担当可能な業種を登録します。"),
        ("Step 2: 希望入力", "「希望入力」画面でスタッフの休み希望・出勤上限などを入力します。"),
        ("Step 3: 必要人数設定", "「必要人数設定」画面で日ごと・業種ごとの必要人数を設定します。"),
        ("Step 4: シフト自動生成", "「シフト自動生成」画面で対象月を選び「生成」ボタンを押します。"),
        ("Step 5: 確認・調整", "生成結果を確認し、必要に応じて手動編集や自然言語で調整します。"),
        ("Step 6: 確定・公開", "シフト表を「確定」→「公開」してスタッフに共有します。"),
        ("Step 7: 出力", "「シフト出力」画面からCSV・Excel・PDFで出力します。"),
    ]

    # フロー図をテーブルで表現
    for i, (step_title, step_desc) in enumerate(steps):
        elements.append(Paragraph(
            f'<font color="{PRIMARY.hexval()}"><b>{step_title}</b></font>',
            style_step,
        ))
        elements.append(Paragraph(step_desc, style_body_indent))
        if i < len(steps) - 1:
            elements.append(Paragraph(
                '<font color="#94A3B8">　　　↓</font>',
                ParagraphStyle("Arrow", fontName="JP", fontSize=12,
                               leading=16, leftIndent=15*mm, spaceAfter=1*mm),
            ))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph(
        "※ Step 1〜3は初回のみ必要です。2回目以降は前月のデータをもとに必要な箇所のみ更新してください。",
        style_note,
    ))

    elements.append(PageBreak())
    return elements


def build_section_4():
    """4. スタッフ管理"""
    elements = []
    elements.append(make_section_header("4", "スタッフ管理"))
    elements.append(section_divider())
    elements.append(Paragraph(
        "スタッフの登録・編集・削除を行います。各スタッフに担当可能な業種を設定します。",
        style_body,
    ))
    elements.append(Spacer(1, 3*mm))

    elements.append(Paragraph("スタッフの登録", style_h2))
    elements.append(Paragraph(
        '・画面上部の入力欄にスタッフ名を入力し「追加」ボタンをクリックします。',
        style_bullet,
    ))
    elements.append(Paragraph(
        '・追加後、スタッフ名をクリックすると編集ダイアログが開きます。',
        style_bullet,
    ))

    elements.append(Paragraph("設定項目", style_h2))
    items = [
        ("スタッフ名", "表示名を設定します"),
        ("雇用形態", "「常勤」または「扶養内」を選択します。常勤が優先的に配置されます"),
        ("担当業種", "チェックボックスで担当可能な業種を選択します"),
        ("表示順", "ドラッグ&ドロップでスタッフの並び順を変更できます"),
    ]
    for item_name, item_desc in items:
        elements.append(Paragraph(f'・<b>{item_name}</b>：{item_desc}', style_bullet))

    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph(
        "※ 雇用形態が「常勤」のスタッフは「扶養内」のスタッフよりも優先的にシフトに配置されます。",
        style_note,
    ))

    elements.append(PageBreak())
    return elements


def build_section_5():
    """5. 希望入力"""
    elements = []
    elements.append(make_section_header("5", "希望入力"))
    elements.append(section_divider())
    elements.append(Paragraph(
        "スタッフごとの休み希望・出勤希望・週間上限を設定します。",
        style_body,
    ))
    elements.append(Spacer(1, 3*mm))

    elements.append(Paragraph("入力手順", style_h2))
    steps = [
        "画面上部で対象の年月を選択します。",
        "スタッフを選択します。",
        "カレンダー上で希望休の日をクリックして「希望休」を設定します。",
        "出勤希望（上限日数 or 「なるべく多く」）を設定します。",
        "週間上限がある場合は「週○日以内」を設定します。",
        "「保存」ボタンで確定します。",
    ]
    for i, step in enumerate(steps, 1):
        elements.append(Paragraph(
            f'<font color="{PRIMARY.hexval()}"><b>{i}.</b></font> {step}',
            style_body_indent,
        ))

    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("希望休の種類", style_h2))
    elements.append(Paragraph('・<b>希望休</b>：その日は必ず休みになります（絶対ルール）。', style_bullet))
    elements.append(Paragraph('・<b>出勤希望</b>：出勤上限日数を指定、または「なるべく多く」を選択できます。', style_bullet))
    elements.append(Paragraph('・<b>週間上限</b>：1週間あたりの最大出勤日数を制限します。', style_bullet))

    elements.append(PageBreak())
    return elements


def build_section_6():
    """6. 必要人数設定"""
    elements = []
    elements.append(make_section_header("6", "必要人数設定"))
    elements.append(section_divider())
    elements.append(Paragraph(
        "日ごと・業種ごとに必要な人数を設定します。テンプレート機能で一括設定も可能です。",
        style_body,
    ))
    elements.append(Spacer(1, 3*mm))

    # スクリーンショット
    elements.append(get_image("222.jpg", max_width=165*mm))
    elements.append(Paragraph("【必要人数設定画面】テンプレート一括設定と日別必要人数", style_caption))

    elements.append(Paragraph("テンプレート一括設定", style_h2))
    elements.append(Paragraph(
        "画面上部の「曜日テンプレート一括設定」で、曜日ごとの基本パターンを設定できます。"
        "「テンプレートを全営業日に適用」ボタンを押すと、該当月のすべての営業日に一括反映されます。",
        style_body,
    ))

    elements.append(Paragraph("日別必要人数", style_h2))
    elements.append(Paragraph(
        "画面下部で日付ごとに個別の調整が可能です。各業種の必要人数を入力し「保存」ボタンで確定します。",
        style_body,
    ))
    elements.append(Paragraph(
        "・土日・祝日は自動的に非営業日（必要人数0）となります。",
        style_bullet,
    ))
    elements.append(Paragraph(
        "・合計欄でその日の総必要人数を確認できます。",
        style_bullet,
    ))

    elements.append(PageBreak())
    return elements


def build_section_7():
    """7. シフト自動生成"""
    elements = []
    elements.append(make_section_header("7", "シフト自動生成"))
    elements.append(section_divider())
    elements.append(Paragraph(
        "AIがスタッフの希望と必要人数を考慮して、最適なシフトを自動生成します。",
        style_body,
    ))
    elements.append(Spacer(1, 3*mm))

    elements.append(Paragraph("生成手順", style_h2))
    steps = [
        "対象月を選択します。",
        "「シフト生成」ボタンをクリックします。",
        "最大30秒で最適なシフトが生成されます。",
        "生成結果がプレビュー表示されます。",
        "制約違反（人数不足など）がある場合は警告が表示されます。",
    ]
    for i, step in enumerate(steps, 1):
        elements.append(Paragraph(
            f'<font color="{PRIMARY.hexval()}"><b>{i}.</b></font> {step}',
            style_body_indent,
        ))

    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("自然言語による調整", style_h2))
    elements.append(Paragraph(
        "生成後、テキスト欄に自然な言葉で指示を入力してシフトを微調整できます。",
        style_body,
    ))
    elements.append(Paragraph("入力例：", style_h3))
    examples = [
        "「Aさんの職人シフトを2日増やして」",
        "「3月10日のlkデータをBさんに変更」",
        "「CさんとDさんの出勤日を入れ替えて」",
    ]
    for ex in examples:
        elements.append(Paragraph(f'・{ex}', style_bullet))

    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("生成ルール（主な制約）", style_h2))
    elements.append(Paragraph("<b>絶対ルール（必ず守る）</b>", style_h3))
    hard = [
        "希望休は必ず休みにする",
        "1日に同一スタッフには1つの業種のみ",
        "土日・祝日は休み",
        "資格のない業種は割り当てない",
        "職人・サブ職人は1日1名ずつ",
    ]
    for h in hard:
        elements.append(Paragraph(f'・{h}', style_bullet))

    elements.append(Paragraph("<b>できるだけルール（優先順に考慮）</b>", style_h3))
    soft = [
        "必要人数をできるだけ満たす",
        "出勤希望上限を守る",
        "常勤を優先的に配置",
        "同じ業種が連続しないようにする",
        "業種配分を均等にする",
    ]
    for s in soft:
        elements.append(Paragraph(f'・{s}', style_bullet))

    elements.append(PageBreak())
    return elements


def build_section_8():
    """8. シフト表"""
    elements = []
    elements.append(make_section_header("8", "シフト表"))
    elements.append(section_divider())
    elements.append(Paragraph(
        "生成されたシフトをマトリクス形式で確認・編集します。",
        style_body,
    ))
    elements.append(Spacer(1, 3*mm))

    elements.append(Paragraph("マトリクス表示", style_h2))
    elements.append(Paragraph(
        "縦軸にスタッフ、横軸に日付を配置したマトリクス表で、各セルに業種が色分け表示されます。",
        style_body,
    ))

    # 色分け説明テーブル
    color_data = [
        ["業種", "表示色"],
        ["職人", "赤"],
        ["サブ職人", "青"],
        ["lkデータ", "緑"],
        ["uv/cpデータ", "紫"],
        ["手紙", "オレンジ"],
        ["その他", "黄"],
        ["休み", "グレー"],
    ]
    color_table = Table(color_data, colWidths=[40*mm, 40*mm])
    color_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "JP"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (-1, 0), "JP-Bold"),
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_LIGHT),
        ("TEXTCOLOR", (0, 0), (-1, 0), PRIMARY),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    color_table.hAlign = "LEFT"
    elements.append(color_table)

    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("手動編集", style_h2))
    elements.append(Paragraph(
        "各セルをクリックすると業種を変更できます。ドロップダウンから業種を選択してください。",
        style_body,
    ))

    elements.append(Paragraph("ステータス管理", style_h2))
    status_items = [
        ("下書き", "生成直後の状態。自由に編集できます"),
        ("確定", "内容が確定した状態。公開前の最終確認用"),
        ("公開済み", "スタッフに公開された状態。共有URLからアクセス可能"),
    ]
    for name, desc in status_items:
        elements.append(Paragraph(f'・<b>{name}</b>：{desc}', style_bullet))

    elements.append(PageBreak())
    return elements


def build_section_9():
    """9. 集計・レポート"""
    elements = []
    elements.append(make_section_header("9", "集計・レポート"))
    elements.append(section_divider())
    elements.append(Paragraph(
        "生成されたシフトの集計情報やスタッフ別の統計を確認できます。",
        style_body,
    ))
    elements.append(Spacer(1, 3*mm))

    elements.append(Paragraph("スタッフ別集計", style_h2))
    elements.append(Paragraph(
        "各スタッフの出勤日数・休日数・業種ごとの配分を一覧で確認できます。",
        style_body,
    ))
    # スクリーンショット
    elements.append(get_image("444.jpg", max_width=165*mm))
    elements.append(Paragraph("【スタッフ別集計画面】出勤日数・業種配分の一覧", style_caption))

    elements.append(Paragraph(
        "表の見方：出勤日数、休日数、希望出勤（上限）、週間上限に加え、"
        "右側に業種別（職人・サブ職人・lkデータ・uv/cpデータ・手紙・その他）の配分が表示されます。",
        style_body,
    ))

    elements.append(Spacer(1, 5*mm))
    elements.append(Paragraph("希望充足コメント", style_h2))
    elements.append(Paragraph(
        "各スタッフの希望がどの程度反映されたかを確認できます。",
        style_body,
    ))
    elements.append(get_image("333.jpg", max_width=140*mm))
    elements.append(Paragraph("【希望充足コメント】スタッフごとの達成状況", style_caption))

    elements.append(Paragraph(
        "コメントには、出勤上限の達成状況、調整休の有無、希望休の反映数、"
        "週間制約の状態が表示されます。",
        style_body,
    ))

    elements.append(PageBreak())
    return elements


def build_section_10():
    """10. シフト出力"""
    elements = []
    elements.append(make_section_header("10", "シフト出力"))
    elements.append(section_divider())
    elements.append(Paragraph(
        "完成したシフトをさまざまな形式で出力できます。",
        style_body,
    ))
    elements.append(Spacer(1, 3*mm))

    elements.append(Paragraph("出力形式", style_h2))
    formats = [
        ("CSV", "テキスト形式のデータ。他システムへの取り込みに便利です"),
        ("Excel", "書式付きのExcelファイル。印刷にも適しています"),
        ("PDF", "レイアウト済みのPDFファイル。そのまま配布可能です"),
    ]
    for fmt, desc in formats:
        elements.append(Paragraph(f'・<b>{fmt}</b>：{desc}', style_bullet))

    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("共有URL", style_h2))
    elements.append(Paragraph(
        "「共有URLを発行」ボタンでスタッフ向けの閲覧専用URLを生成できます。"
        "URLを知っている人は誰でもシフトを確認できます（編集不可）。",
        style_body,
    ))

    elements.append(Spacer(1, 3*mm))
    elements.append(Paragraph("出力手順", style_h2))
    steps = [
        "対象月を選択します。",
        "ステータスが「確定」または「公開済み」であることを確認します。",
        "希望の出力形式のボタンをクリックします。",
        "ファイルが自動的にダウンロードされます。",
    ]
    for i, step in enumerate(steps, 1):
        elements.append(Paragraph(
            f'<font color="{PRIMARY.hexval()}"><b>{i}.</b></font> {step}',
            style_body_indent,
        ))

    return elements


def add_page_number(canvas, doc):
    """ページ番号をフッターに追加"""
    page_num = canvas.getPageNumber()
    if page_num > 1:  # 表紙以外
        canvas.saveState()
        canvas.setFont("JP", 8)
        canvas.setFillColor(GRAY)
        canvas.drawCentredString(
            A4[0] / 2, 12*mm,
            f"- {page_num - 1} -"
        )
        # ヘッダー
        canvas.setFont("JP", 7)
        canvas.drawString(20*mm, A4[1] - 12*mm, "シフトスケジューラー 取扱説明書")
        canvas.setStrokeColor(BORDER_COLOR)
        canvas.setLineWidth(0.5)
        canvas.line(20*mm, A4[1] - 14*mm, A4[0] - 20*mm, A4[1] - 14*mm)
        canvas.restoreState()


def main():
    print("シフトスケジューラー取扱説明書を生成中...")

    doc = SimpleDocTemplate(
        OUTPUT_PDF,
        pagesize=A4,
        topMargin=20*mm,
        bottomMargin=18*mm,
        leftMargin=20*mm,
        rightMargin=20*mm,
    )

    elements = []

    # 各セクションを構築
    print("  表紙を生成...")
    elements.extend(build_cover_page())

    print("  目次を生成...")
    elements.extend(build_toc())

    print("  1. システム概要...")
    elements.extend(build_section_1())

    print("  2. 画面構成...")
    elements.extend(build_section_2())

    print("  3. 基本操作フロー...")
    elements.extend(build_section_3())

    print("  4. スタッフ管理...")
    elements.extend(build_section_4())

    print("  5. 希望入力...")
    elements.extend(build_section_5())

    print("  6. 必要人数設定...")
    elements.extend(build_section_6())

    print("  7. シフト自動生成...")
    elements.extend(build_section_7())

    print("  8. シフト表...")
    elements.extend(build_section_8())

    print("  9. 集計・レポート...")
    elements.extend(build_section_9())

    print("  10. シフト出力...")
    elements.extend(build_section_10())

    # PDF生成
    print("  PDFを書き出し中...")
    doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"\n完成！ => {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
