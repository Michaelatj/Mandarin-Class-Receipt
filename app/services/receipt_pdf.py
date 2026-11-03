"""
services/receipt_pdf.py - a printable PDF for any receipt (billing or prepaid).
Open it to print, or share the file. Dates are shown in WIB.
"""
import io
from datetime import datetime, timedelta
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .prepaid import prepaid_usage

WIB = timedelta(hours=7)
MONTHS_ID = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli",
             "Agustus", "September", "Oktober", "November", "Desember"]
DAYS_ID = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu"]

RED = colors.HexColor("#c8161d")
GREEN = colors.HexColor("#1a7a4a")
INK = colors.HexColor("#1a1816")
MUTED = colors.HexColor("#6b655e")
LINE = colors.HexColor("#ddd6c8")
SOFT = colors.HexColor("#faf6ec")


def idr(n):
    return "Rp " + f"{int(n or 0):,}".replace(",", ".")


def _date(dt):
    w = dt + WIB
    return f"{w.day} {MONTHS_ID[w.month - 1]} {w.year}"


def receipt_number(r):
    return r.receipt_no if r.receipt_no else r.id


def pdf_filename(r):
    import re
    who = re.sub(r"[^A-Za-z0-9]+", "_", r.student_name or "student").strip("_") or "student"
    return f"Kwitansi_{receipt_number(r)}_{who}.pdf"


def render_receipt_pdf(r):
    base = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=base["BodyText"], fontName="Helvetica", fontSize=10, leading=14, textColor=INK)
    small = ParagraphStyle("s", parent=body, fontSize=8.5, leading=11, textColor=MUTED)
    cell = ParagraphStyle("c", parent=body, fontSize=9.5, leading=12.5)
    right = ParagraphStyle("r", parent=cell, alignment=2)
    h2 = ParagraphStyle("h2", parent=body, fontName="Helvetica-Bold", fontSize=11, spaceBefore=12, spaceAfter=5, textColor=RED)

    prepaid = (r.kind or "billing") == "prepaid"
    dates = []
    for raw in (r.raw_dates or "").split("|"):
        raw = raw.strip()
        if raw:
            try:
                dates.append(datetime.fromisoformat(raw))
            except ValueError:
                pass

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm,
                            bottomMargin=16 * mm, title=f"Kwitansi #{receipt_number(r)}", author=r.teacher_name)
    width = A4[0] - 36 * mm
    story = []

    title = "Kwitansi Pembayaran di Muka" if prepaid else "Kwitansi Pembayaran"
    head = Table([[
        Paragraph(f'<font color="white" size="17"><b>{title}</b></font><br/>'
                  '<font color="#ffe1dc" size="9.5">Payment receipt · Mandarin class</font>', body),
        Paragraph(f'<font color="white" size="11"><b>No. #{receipt_number(r)}</b></font><br/>'
                  f'<font color="#ffe1dc" size="9.5">{_date(r.issue_date or datetime.utcnow())}</font>',
                  ParagraphStyle("hr", parent=body, alignment=2)),
    ]], colWidths=[width * 0.68, width * 0.32])
    head.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), RED), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story += [head, Spacer(1, 10)]

    rows = [
        [Paragraph("<b>Diterima dari</b>", cell), Paragraph(escape(r.student_name or "-"), cell),
         Paragraph("<b>Guru</b>", cell), Paragraph(escape(r.teacher_name or "-"), cell)],
        [Paragraph("<b>Tanggal</b>", cell), Paragraph(_date(r.paid_at or r.issue_date or datetime.utcnow()) if r.paid else _date(r.issue_date or datetime.utcnow()), cell),
         Paragraph("<b>Metode</b>", cell), Paragraph(escape(r.method or "-"), cell)],
    ]
    info = Table(rows, colWidths=[width * 0.16, width * 0.34, width * 0.12, width * 0.38])
    info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), SOFT), ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(info)

    story.append(Paragraph("Rincian", h2))
    if prepaid:
        used, total = prepaid_usage(r)
        desc = "Biaya kursus Mandarin (dibayar di muka)<br/><font size='8.5' color='#6b655e'>" + escape(r.covers or "") + "</font>"
        qty = "-" if r.packet_type == "monthly" else str(total or 0)
        item_rows = [["Keterangan", "Jumlah", "Total"],
                     [Paragraph(desc, cell), Paragraph(qty, right), Paragraph(idr(r.total_fee), right)]]
    elif r.packet_type == "monthly":
        item_rows = [["Keterangan", "Jumlah", "Total"],
                     [Paragraph("Biaya kursus Mandarin (paket bulanan)", cell),
                      Paragraph(f"{r.custom_qty or len(dates) or 1} pertemuan", right), Paragraph(idr(r.total_fee), right)]]
    else:
        qty = r.custom_qty if r.custom_qty is not None else len(dates)
        item_rows = [["Keterangan", "Jumlah", "Total"],
                     [Paragraph("Biaya kursus Mandarin (per pertemuan)", cell),
                      Paragraph(f"{qty} x {idr(round(r.total_fee / qty)) if qty else '-'}", right), Paragraph(idr(r.total_fee), right)]]
    tbl = Table(item_rows, colWidths=[width * 0.6, width * 0.2, width * 0.2])
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#5a3128")),
        ("ALIGN", (1, 0), (-1, 0), "RIGHT"), ("LINEBELOW", (0, 1), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(tbl)

    # total and status
    status = "LUNAS" if r.paid else "BELUM DIBAYAR"
    tot = Table([[Paragraph(f'<font color="{"#1a7a4a" if r.paid else "#c8161d"}"><b>{status}</b></font>', cell),
                  Paragraph("<b>Total</b>", right), Paragraph(f"<b>{idr(r.total_fee)}</b>", ParagraphStyle("t", parent=right, fontSize=13))]],
                colWidths=[width * 0.4, width * 0.2, width * 0.4])
    tot.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.9, GREEN if r.paid else RED),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eef8f1") if r.paid else colors.HexColor("#fdf1f0")),
        ("TOPPADDING", (0, 0), (-1, -1), 9), ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story += [Spacer(1, 10), tot]

    if not r.paid and r.bank_account and r.bank_account != "N/A":
        story += [Spacer(1, 8), Paragraph(f"Transfer ke {escape(r.bank_name or 'rekening')}: <b>{escape(r.bank_account)}</b>", body)]

    # classes listed on the receipt
    if dates:
        story.append(Paragraph("Pertemuan yang tercatat" if not prepaid else "Pertemuan yang sudah memakai pembayaran ini", h2))
        data = [["No", "Tanggal", "Jam (WIB)"]]
        for i, d in enumerate(sorted(dates), 1):
            w = d + WIB
            data.append([str(i), f"{DAYS_ID[w.weekday()]}, {w.day} {MONTHS_ID[w.month - 1]} {w.year}", f"{w.hour:02d}:{w.minute:02d}"])
        g = Table(data, colWidths=[width * 0.1, width * 0.6, width * 0.3], repeatRows=1)
        g.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), INK), ("BACKGROUND", (0, 0), (-1, 0), SOFT),
            ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE), ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(g)
    if prepaid:
        used, total = prepaid_usage(r)
        if total:
            left = max(total - used, 0)
            note = f"Sesi terpakai: {used} dari {total}. Sisa: {left} sesi."
        else:
            note = f"Pertemuan dalam periode ini sejauh ini: {used}."
        story += [Spacer(1, 8), Paragraph(note, small)]

    now = datetime.utcnow() + WIB
    story += [Spacer(1, 16), Paragraph(f"Dokumen ini dibuat otomatis pada {now.day} {MONTHS_ID[now.month - 1]} {now.year}, "
                                       f"{now.hour:02d}:{now.minute:02d} WIB.", small)]
    doc.build(story)
    return buf.getvalue()
