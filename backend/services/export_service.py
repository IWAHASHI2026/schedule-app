import csv
import io
from datetime import date
from openpyxl import Workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy.orm import Session
from database import Schedule, ShiftAssignment, Employee, JobType
import calendar
import os


JOB_TYPE_COLORS = {
    "職人": "FF6B6B",
    "サブ職人": "4DABF7",
    "データ": "51CF66",
    "その他": "FFD43B",
}


def _get_schedule_data(db: Session, month: str):
    schedule = (
        db.query(Schedule)
        .filter(Schedule.target_month == month)
        .order_by(Schedule.id.desc())
        .first()
    )
    if not schedule:
        raise ValueError("No schedule found for the specified month")

    employees = db.query(Employee).order_by(Employee.id).all()
    job_types = db.query(JobType).all()
    jt_map = {jt.id: jt.name for jt in job_types}

    assignments = (
        db.query(ShiftAssignment)
        .filter(ShiftAssignment.schedule_id == schedule.id)
        .order_by(ShiftAssignment.employee_id, ShiftAssignment.date)
        .all()
    )

    year, mon = map(int, month.split("-"))
    days_in_month = calendar.monthrange(year, mon)[1]
    dates = [date(year, mon, d) for d in range(1, days_in_month + 1)]

    # Build matrix: emp_id -> date -> job_type_name
    matrix: dict[int, dict[date, str]] = {}
    for a in assignments:
        if a.employee_id not in matrix:
            matrix[a.employee_id] = {}
        if a.job_type_id and a.work_type != "off":
            name = jt_map.get(a.job_type_id, "")
            if a.work_type == "morning_half":
                name += "(午前)"
            elif a.work_type == "afternoon_half":
                name += "(午後)"
            matrix[a.employee_id][a.date] = name
        else:
            matrix[a.employee_id][a.date] = "休"

    return employees, dates, matrix, jt_map


def generate_csv(db: Session, month: str) -> str:
    employees, dates, matrix, _ = _get_schedule_data(db, month)

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    header = ["スタッフ"] + [d.strftime("%m/%d(%a)") for d in dates]
    writer.writerow(header)

    for emp in employees:
        row = [emp.name]
        for d in dates:
            row.append(matrix.get(emp.id, {}).get(d, ""))
        writer.writerow(row)

    return output.getvalue()


def generate_excel(db: Session, month: str) -> bytes:
    employees, dates, matrix, _ = _get_schedule_data(db, month)

    wb = Workbook()
    ws = wb.active
    ws.title = f"シフト表 {month}"

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin'),
    )

    # Header row
    ws.cell(row=1, column=1, value="スタッフ").font = Font(bold=True)
    ws.cell(row=1, column=1).border = thin_border
    ws.column_dimensions['A'].width = 12

    weekday_names = ["月", "火", "水", "木", "金", "土", "日"]
    for col_idx, d in enumerate(dates, start=2):
        cell = ws.cell(row=1, column=col_idx)
        cell.value = f"{d.day}\n{weekday_names[d.weekday()]}"
        cell.font = Font(bold=True, size=8)
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        cell.border = thin_border
        ws.column_dimensions[cell.column_letter].width = 6
        if d.weekday() >= 5:
            cell.fill = PatternFill(start_color="D9D9D9", fill_type="solid")

    # Data rows
    for row_idx, emp in enumerate(employees, start=2):
        ws.cell(row=row_idx, column=1, value=emp.name).border = thin_border
        for col_idx, d in enumerate(dates, start=2):
            cell = ws.cell(row=row_idx, column=col_idx)
            val = matrix.get(emp.id, {}).get(d, "")
            cell.value = val
            cell.alignment = Alignment(horizontal='center')
            cell.border = thin_border
            cell.font = Font(size=8)

            if d.weekday() >= 5:
                cell.fill = PatternFill(start_color="D9D9D9", fill_type="solid")
            elif val != "休":
                for jt_name, color in JOB_TYPE_COLORS.items():
                    if jt_name in val:
                        cell.fill = PatternFill(start_color=color, fill_type="solid")
                        break

    output = io.BytesIO()
    wb.save(output)
    return output.getvalue()


def generate_pdf(db: Session, month: str) -> bytes:
    employees, dates, matrix, _ = _get_schedule_data(db, month)

    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=landscape(A3),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    # Try to register a Japanese font
    _try_register_japanese_font()

    weekday_names = ["月", "火", "水", "木", "金", "土", "日"]

    # Build table data
    header = [""] + [f"{d.day}\n{weekday_names[d.weekday()]}" for d in dates]
    data = [header]

    for emp in employees:
        row = [emp.name]
        for d in dates:
            row.append(matrix.get(emp.id, {}).get(d, ""))
        data.append(row)

    # Column widths
    name_width = 50
    day_width = max(10, (landscape(A3)[0] - 20 * mm - name_width) / len(dates))
    col_widths = [name_width] + [day_width] * len(dates)

    table = Table(data, colWidths=col_widths, repeatRows=1)

    style_cmds = [
        ('FONTSIZE', (0, 0), (-1, -1), 6),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.9, 0.9, 0.9)),
    ]

    # Color weekend columns
    for col_idx, d in enumerate(dates):
        if d.weekday() >= 5:
            style_cmds.append(
                ('BACKGROUND', (col_idx + 1, 0), (col_idx + 1, -1),
                 colors.Color(0.85, 0.85, 0.85))
            )

    # Color job type cells
    jt_colors_rgb = {
        "職人": colors.Color(1.0, 0.42, 0.42),
        "サブ職人": colors.Color(0.3, 0.67, 0.97),
        "データ": colors.Color(0.32, 0.81, 0.4),
        "その他": colors.Color(1.0, 0.83, 0.23),
    }
    for row_idx, emp in enumerate(employees, start=1):
        for col_idx, d in enumerate(dates):
            val = matrix.get(emp.id, {}).get(d, "")
            for jt_name, color in jt_colors_rgb.items():
                if jt_name in val:
                    style_cmds.append(
                        ('BACKGROUND', (col_idx + 1, row_idx), (col_idx + 1, row_idx), color)
                    )
                    break

    table.setStyle(TableStyle(style_cmds))
    doc.build([table])
    return output.getvalue()


def _try_register_japanese_font():
    """Try to register a Japanese font for PDF generation."""
    font_paths = [
        # Windows
        "C:/Windows/Fonts/msgothic.ttc",
        "C:/Windows/Fonts/meiryo.ttc",
        # macOS
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        # Linux
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                pdfmetrics.registerFont(TTFont("JapaneseFont", path))
                return
            except Exception:
                continue
