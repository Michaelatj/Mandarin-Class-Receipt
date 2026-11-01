"""
services/recap.py - monthly recap for one student: attendance, receipts, what is still unpaid.
Builds the data, a PDF (reportlab) and the WhatsApp message text.
Dates are stored in UTC and shown in WIB (UTC+7) like everywhere else in the app.
"""
import io
import re
from datetime import datetime, timedelta
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import Attendance, Receipt, StudentFee
from .streaks import attendance_streak

WIB = timedelta(hours=7)
MONTHS_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
             "Agustus", "September", "Oktober", "November", "Desember"]
DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

RED = colors.HexColor("#8a1a24")
GOLD = colors.HexColor("#b07d2e")
INK = colors.HexColor("#1a1816")
MUTED = colors.HexColor("#6b655e")
LINE = colors.HexColor("#ddd6c8")
SOFT = colors.HexColor("#faf6ec")


def idr(n):
    return "Rp " + f"{int(n):,}".replace(",", ".")


def parse_month(value, now=None):
    """'2026-10' -> (2026, 10). Falls back to the current WIB month."""
    now = now or (datetime.utcnow() + WIB)
    m = re.fullmatch(r"(\d{4})-(\d{1,2})", (value or "").strip())
    if m and 1 <= int(m.group(2)) <= 12 and 2000 <= int(m.group(1)) <= 2100:
        return int(m.group(1)), int(m.group(2))
    return now.year, now.month


def month_label(year, month):
    return f"{MONTHS_ID[month - 1]} {year}"


def normalize_phone(raw):
    """Indonesian numbers to the international form wa.me expects (62...)."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("0"):
        digits = "62" + digits[1:]
    elif digits.startswith("8"):
        digits = "62" + digits
    return digits if len(digits) >= 9 else ""


def build_recap(teacher, student, year, month):
    # month boundaries are in WIB, rows are stored in UTC
    start_utc = datetime(year, month, 1) - WIB
    end_utc = (datetime(year + (month == 12), (month % 12) + 1, 1)) - WIB

    rows = (Attendance.query
            .filter(Attendance.teacher_id == teacher.id, Attendance.student_id == student.id,
                    Attendance.date >= start_utc, Attendance.date < end_utc)
            .order_by(Attendance.date.asc()).all())
    sessions = [{"wib": r.date + WIB, "note": (r.note or "").strip(), "source": r.source} for r in rows]

    issued = (Receipt.query
              .filter(Receipt.teacher_id == teacher.id, Receipt.student_id == student.id,
                      Receipt.issue_date >= start_utc, Receipt.issue_date < end_utc)
              .order_by(Receipt.issue_date.asc()).all())
    unpaid = (Receipt.query
              .filter(Receipt.teacher_id == teacher.id, Receipt.student_id == student.id, Receipt.paid.is_(False))
              .order_by(Receipt.issue_date.asc()).all())

    fee = StudentFee.query.filter_by(teacher_id=teacher.id, student_id=student.id).first()
    packet = (fee.packet_type if fee and fee.packet_type else "session")
    fee_amount = fee.fee_idr if fee else (teacher.fee_idr or 0)

    return {
        "teacher": teacher, "student": student, "year": year, "month": month,
        "label": month_label(year, month),
        "sessions": sessions,
        "issued": issued, "unpaid": unpaid,
        "outstanding": sum(r.total_fee for r in unpaid),
        "packet": packet, "fee": fee_amount,
        "streak": attendance_streak(student.id),
    }


def whatsapp_text(recap):
    s, t = recap["student"], recap["teacher"]
    lines = [
        f"Halo {s.name()}, ini rekap kelas Mandarin bulan {recap['label']}:",
        f"- Pertemuan: {len(recap['sessions'])} kali",
    ]
    if recap["outstanding"]:
        lines.append(f"- Tagihan belum dibayar: {idr(recap['outstanding'])}")
        if t.bank_account:
            lines.append(f"- Transfer ke {t.bank_name or 'rekening'} {t.bank_account}")
    else:
        lines.append("- Tidak ada tagihan yang tertunda")
    lines.append("Rekap lengkap ada di file PDF terlampir. Terima kasih!")
    lines.append(f"- {t.name()}")
    return "\n".join(lines)


def pdf_filename(recap):
    who = re.sub(r"[^A-Za-z0-9]+", "_", recap["student"].name()).strip("_") or "student"
    return f"Rekap_{who}_{recap['year']}-{recap['month']:02d}.pdf"


def render_pdf(recap):
    t, s = recap["teacher"], recap["student"]
    base = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=base["BodyText"], fontName="Helvetica", fontSize=10, leading=14, textColor=INK)
    small = ParagraphStyle("small", parent=body, fontSize=8.5, leading=11, textColor=MUTED)
    h2 = ParagraphStyle("h2", parent=body, fontName="Helvetica-Bold", fontSize=11.5, leading=15, spaceBefore=14, spaceAfter=6, textColor=RED)
    cell = ParagraphStyle("cell", parent=body, fontSize=9.5, leading=12.5)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Rekap {recap['label']} - {s.name()}", author=t.name())
    width = A4[0] - 36 * mm
    story = []

    # header band
    head = Table([[
        Paragraph('<font color="white" size="17"><b>Rekap Kelas Bulanan</b></font><br/>'
                  f'<font color="#e8c87a" size="10">{escape(recap["label"])}</font>', body),
        Paragraph(f'<font color="white" size="10">{escape(t.name())}</font><br/>'
                  '<font color="#e8c87a" size="8.5">Mandarin class</font>',
                  ParagraphStyle("r", parent=body, alignment=2)),
    ]], colWidths=[width * 0.65, width * 0.35])
    head.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), RED), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story += [head, Spacer(1, 10)]

    packet_txt = "Paket bulanan" if recap["packet"] == "monthly" else "Paket per pertemuan"
    info = Table([
        [Paragraph("<b>Siswa</b>", cell), Paragraph(escape(s.name()), cell),
         Paragraph("<b>Paket</b>", cell), Paragraph(f"{packet_txt}, {idr(recap['fee'])}" if recap["fee"] else packet_txt, cell)],
        [Paragraph("<b>Periode</b>", cell), Paragraph(escape(recap["label"]), cell),
         Paragraph("<b>Pertemuan</b>", cell), Paragraph(f"{len(recap['sessions'])} kali", cell)],
    ], colWidths=[width * 0.14, width * 0.34, width * 0.16, width * 0.36])
    info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(info)

    def grid(data, widths, right_cols=()):
        tbl = Table(data, colWidths=widths, repeatRows=1)
        style = [
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("BACKGROUND", (0, 0), (-1, 0), GOLD),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, SOFT]),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 1), (-1, -1), INK),
        ]
        for c in right_cols:
            style.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
        tbl.setStyle(TableStyle(style))
        return tbl

    # attendance
    story.append(Paragraph("Kehadiran", h2))
    if recap["sessions"]:
        data = [["No", "Tanggal", "Jam (WIB)", "Catatan"]]
        for i, r in enumerate(recap["sessions"], 1):
            d = r["wib"]
            data.append([str(i), f"{DAYS_ID[d.weekday()]}, {d.day} {MONTHS_ID[d.month - 1]} {d.year}",
                         f"{d.hour:02d}:{d.minute:02d}", Paragraph(escape(r["note"]) or "-", cell)])
        story.append(grid(data, [width * 0.08, width * 0.42, width * 0.16, width * 0.34]))
    else:
        story.append(Paragraph("Tidak ada pertemuan yang tercatat bulan ini.", body))

    # receipts
    story.append(Paragraph("Tagihan", h2))
    rows = [["No", "Tanggal terbit", "Jumlah", "Status"]]
    for r in recap["issued"]:
        d = r.issue_date + WIB
        rows.append([f"#{r.receipt_no}", f"{d.day} {MONTHS_ID[d.month - 1]} {d.year}", idr(r.total_fee),
                     "Lunas" if r.paid else "Belum dibayar"])
    if len(rows) > 1:
        story.append(grid(rows, [width * 0.14, width * 0.36, width * 0.26, width * 0.24], right_cols=(2,)))
    else:
        story.append(Paragraph("Tidak ada tagihan baru yang terbit bulan ini.", body))

    # outstanding
    story.append(Spacer(1, 10))
    if recap["outstanding"]:
        pay = [[Paragraph("<b>Total belum dibayar</b>", cell), Paragraph(f"<b>{idr(recap['outstanding'])}</b>",
                ParagraphStyle("amt", parent=cell, alignment=2, textColor=RED, fontSize=12))]]
        if t.bank_account:
            pay.append([Paragraph(f"Transfer ke {escape(t.bank_name or 'rekening')}: <b>{escape(t.bank_account)}</b>", cell), ""])
        box = Table(pay, colWidths=[width * 0.6, width * 0.4])
        box_style = [
            ("BOX", (0, 0), (-1, -1), 0.8, RED), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fdf1f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ]
        if len(pay) > 1:
            box_style.append(("SPAN", (0, 1), (-1, 1)))
        box.setStyle(TableStyle(box_style))
        story.append(box)
    else:
        story.append(Paragraph("Semua tagihan sudah lunas.", body))

    st = recap["streak"]
    if st and st["total"]:
        story.append(Spacer(1, 8))
        story.append(Paragraph(
            f"Kehadiran kelas terjadwal: {st['attended']} dari {st['total']} kelas, "
            f"{st['current']} kelas berturut-turut saat ini (terbaik {st['best']}).", small))

    now = datetime.utcnow() + WIB
    story += [Spacer(1, 14), Paragraph(
        f"Dibuat pada {now.day} {MONTHS_ID[now.month - 1]} {now.year}, {now.hour:02d}:{now.minute:02d} WIB.", small)]

    doc.build(story)
    return buf.getvalue()
