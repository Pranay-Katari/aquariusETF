"""Portable, disclosure-first PDF tear sheets for completed backtests."""

from io import BytesIO
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


def tear_sheet(name: str, artifact: dict) -> bytes:
    metrics = artifact["metrics"]
    config = artifact["metadata"]["config"]
    out = BytesIO(); pdf = canvas.Canvas(out, pagesize=letter); width, height = letter
    pdf.setFillColor(HexColor("#0A1424")); pdf.rect(0, 0, width, height, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#2DD4BF")); pdf.rect(44, height-56, 155, 3, fill=1, stroke=0)
    pdf.setFillColor(HexColor("#F0F6FF")); pdf.setFont("Helvetica-Bold", 24); pdf.drawString(44, height-100, name)
    pdf.setFillColor(HexColor("#9DB1CC")); pdf.setFont("Helvetica", 10); pdf.drawString(44, height-121, "Hypothetical backtest - not investment advice")
    labels = [("Ending value", f"${metrics['ending_value']:,.0f}"), ("CAGR", f"{metrics['cagr']*100:.2f}%"), ("Max drawdown", f"{metrics['max_drawdown']*100:.2f}%"), ("Benchmark", config["benchmark"])]
    for i, (label, value) in enumerate(labels):
        x = 44 + i * 130; pdf.setFillColor(HexColor("#132541")); pdf.roundRect(x, height-215, 116, 62, 10, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#9DB1CC")); pdf.setFont("Helvetica", 8); pdf.drawString(x+12, height-174, label)
        pdf.setFillColor(HexColor("#F0F6FF")); pdf.setFont("Helvetica-Bold", 15); pdf.drawString(x+12, height-198, value)
    pdf.setFillColor(HexColor("#F0F6FF")); pdf.setFont("Helvetica-Bold", 13); pdf.drawString(44, height-265, "Portfolio allocation")
    y = height-292
    for holding in artifact["metadata"]["holdings"]:
        pdf.setFillColor(HexColor("#DCE8FA")); pdf.setFont("Helvetica-Bold", 10); pdf.drawString(44, y, holding["ticker"])
        pdf.setFillColor(HexColor("#294869")); pdf.roundRect(104, y-4, 280, 8, 4, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#2DD4BF")); pdf.roundRect(104, y-4, 280*holding["target_weight"], 8, 4, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#DCE8FA")); pdf.setFont("Helvetica", 9); pdf.drawRightString(420, y, f"{holding['target_weight']*100:.1f}%"); y -= 24
        if y < 105: break
    disclaimer = "Hypothetical backtested results include assumed costs and do not predict future performance. This material is for information only and is not a recommendation to buy or sell any security."
    pdf.setFillColor(HexColor("#9DB1CC")); pdf.setFont("Helvetica", 8)
    words = disclaimer.split(); line = ""; y = 78
    for word in words:
        candidate = f"{line} {word}".strip()
        if stringWidth(candidate, "Helvetica", 8) > width-88:
            pdf.drawString(44, y, line); y -= 11; line = word
        else: line = candidate
    pdf.drawString(44, y, line); pdf.save(); return out.getvalue()
