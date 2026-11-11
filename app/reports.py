"""Downloadable, paginated PDF report generated from the selected real records."""
from io import BytesIO
from html import escape


def pdf_report(records, title="Prediction report"):
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    stream = BytesIO()
    doc = SimpleDocTemplate(stream, pagesize=landscape(A4), rightMargin=34, leftMargin=34, topMargin=34, bottomMargin=34)
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Detail", fontSize=9, leading=14, textColor=colors.HexColor("#536276")))
    content = [Paragraph(escape(title), styles["Title"]), Paragraph("Prediction Model | Equipment failure intelligence", styles["Detail"]), Spacer(1,14)]
    if records:
        content += [Paragraph(f"{len(records)} snapshot(s) | Source: {escape(', '.join(sorted(set(r['source'] for r in records))))} | Model artifact: {escape(records[0]['version'])}", styles["Detail"]), Spacer(1,10)]
    rows = [["Run ID", "Time (IST)", "Type", "Risk", "Failure", "Threshold", "Batch ms"]]
    from services import IST
    from datetime import datetime
    for r in records:
        rows.append([r["id"], datetime.fromisoformat(r["timestamp"]).astimezone(IST).strftime("%d %b %H:%M"), r["inputs"]["Type"], r["risk"], f"{r['probability']:.1%}", f"{r['threshold']:.0%}", f"{r['latency_ms']:.2f}"])
    t = Table(rows, repeatRows=1, colWidths=[132,130,55,65,80,80,90])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#12151C")),("TEXTCOLOR",(0,0),(-1,0),colors.white),
                          ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),9),
                          ("TOPPADDING",(0,0),(-1,-1),8),("BOTTOMPADDING",(0,0),(-1,-1),8),
                          ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#F1F5F9"),colors.white]),("LINEBELOW",(0,0),(-1,0),1,colors.HexColor("#08758B"))]))
    content += [t, Spacer(1,16)]
    if len(records) == 1:
        r=records[0]
        content += [Paragraph("Operating snapshot", styles["Heading2"])]
        for k,v in r["inputs"].items():
            content.append(Paragraph(f"{escape(k)}: {escape(f'{v:.3f}' if isinstance(v,float) else str(v))}",styles["Detail"]))
    content.append(Spacer(1,12))
    content.append(Paragraph("Medium risk is a dashboard watch band at half the saved decision threshold. Failure probability is a model estimate, not a calibrated confidence score. Batch ms is the duration of the whole inference call. Demo timestamps are illustrative.", styles["Detail"]))
    def footer(canvas, doc):
        canvas.setFont("Helvetica",8)
        canvas.setFillColor(colors.HexColor("#536276"))
        canvas.drawString(34,20,"Prediction Model / Local workspace")
        canvas.drawRightString(807,20,f"Page {doc.page}")
    doc.build(content,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()
