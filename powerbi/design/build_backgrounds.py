"""
Lloyds portfolio | Power BI page backgrounds (1920 x 1080 PNG) + layout spec
The geometry below is the single source of truth: backgrounds are drawn from it and
layout_spec.md lists the exact X / Y / Width / Height to type in Power BI (Format > General > Properties).
"""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent
W, H = 1920, 1080
C = dict(bg="#F3F6F4", panel="#FFFFFF", border="#DDE6E1", brand="#006A4D", brand_dark="#00402E",
         ink="#0E2A20", ink2="#51625A", muted="#8A9A92", accent="#0B8157")

HEADER_H, M = 88, 40
SLICER = (M, 104, W - 2 * M, 56)
KPI_Y, KPI_H, GAP = 176, 128, 16
ROW_A = (320, 356)
ROW_B = (692, 348)


def kpi_boxes():
    w = (W - 2 * M - 5 * GAP) / 6
    return [(round(M + i * (w + GAP)), KPI_Y, round(w), KPI_H) for i in range(6)]


def row(y, h, widths):
    boxes, x = [], M
    for w in widths:
        boxes.append((x, y, w, h)); x += w + GAP
    return boxes


PAGES = {
    "p1_profitability": {
        "title": "Profitability & Balance Sheet",
        "kpis": ["Net Interest Income", "Net Interest Margin", "Fee Income", "Cost:Income Ratio",
                 "Customer Deposits", "Net Loans"],
        "a": [("NII by month vs budget", 1112), ("NIM vs Bank Rate (%)", 712)],
        "b": [("NII bridge vs prior year", 600), ("Deposit mix", 600), ("Budget delivery by region", 608)]},
    "p2_credit_risk": {
        "title": "Lending & Credit Risk",
        "kpis": ["Gross New Lending", "Loan Book", "90+ Arrears Rate", "Stage 2 Share", "ECL Coverage",
                 "Cost of Risk"],
        "a": [("IFRS 9 stage mix", 912), ("Remortgage wall", 912)],
        "b": [("90+ arrears by product", 600), ("LTV x credit score heatmap", 600),
              ("Bounce Back Loans default curve", 608)]},
    "p3_customers": {
        "title": "Customers, Digital & Conduct",
        "kpis": ["Active Customers", "Digital Active Share", "App Monthly Users", "Open Branches",
                 "Complaints per 1,000", "APP Scam Reimbursement"],
        "a": [("Branches vs digital users (index)", 912), ("Transaction channel mix", 912)],
        "b": [("Complaints by category", 600), ("APP scam losses vs reimbursed", 600), ("Branch network", 608)]},
    "p4_platform": {
        "title": "Data Platform & Quality",
        "kpis": ["Rows in Warehouse", "Data As Of", "Pipeline Success Rate", "Last Load Duration",
                 "Data Quality Issues Fixed", "Tables Monitored"],
        "a": [("Architecture (image: docs/architecture.png)", 1112), ("Rows by layer and table", 712)],
        "b": [("Pipeline runs (rows written, duration, status)", 912), ("Data quality checks and actions", 912)]},
    "p5_region_drill": {
        "title": "Region Deep Dive",
        "kpis": ["Net Interest Income", "Net Interest Margin", "Customer Deposits", "Loan Book",
                 "90+ Arrears Rate", "Active Customers"],
        "a": [("NII vs budget | selected region", 912), ("Product scorecard (matrix)", 912)],
        "b": [("IFRS 9 stage mix", 600), ("Digital active share vs UK", 600), ("Branches in region (map)", 608)]},
}

CSS = f"""
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:{W}px;height:{H}px;background:{C['bg']};font-family:'Segoe UI',Helvetica,Arial,sans-serif;position:relative;overflow:hidden}}
.abs{{position:absolute}}
.panel{{position:absolute;background:{C['panel']};border:1px solid {C['border']};border-radius:12px;
        box-shadow:0 1px 2px rgba(14,42,32,.05),0 4px 14px rgba(14,42,32,.05)}}
.kpi{{border-top:4px solid {C['brand']}}}
.header{{position:absolute;left:0;top:0;width:{W}px;height:{HEADER_H}px;background:{C['panel']};border-bottom:1px solid {C['border']}}}
.bar{{position:absolute;left:0;top:0;width:8px;height:{HEADER_H}px;background:{C['brand']}}}
.t1{{position:absolute;left:{M}px;top:14px;font-size:30px;font-weight:600;color:{C['ink']};letter-spacing:-.2px}}
.t2{{position:absolute;left:{M}px;top:54px;font-size:14px;color:{C['ink2']}}}
.foot{{position:absolute;left:{M}px;top:1050px;font-size:12px;color:{C['muted']}}}
"""


def page_html(p):
    parts = [] if True else []
    parts += [f"<div class='header'><div class='bar'></div><div class='t1'>{p['title']}</div>"
             f"<div class='t2'>Lloyds Banking Group case study &nbsp;|&nbsp; UK Retail &amp; SME Banking &nbsp;|&nbsp; "
             f"hypothetical data</div></div>"]
    x, y, w, h = SLICER
    parts.append(f"<div class='panel' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px'></div>")
    for (x, y, w, h) in kpi_boxes():
        parts.append(f"<div class='panel kpi' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px'></div>")
    for (x, y, w, h) in row(*ROW_A, [b[1] for b in p["a"]]) + row(*ROW_B, [b[1] for b in p["b"]]):
        parts.append(f"<div class='panel' style='left:{x}px;top:{y}px;width:{w}px;height:{h}px'></div>")
    parts.append("<div class='foot'>Synthetic data generated for a portfolio project, not affiliated with Lloyds Banking Group "
                 "&nbsp;|&nbsp; Bank Rate: Bank of England (real series IUDBEDR)</div>")
    return f"<html><head><style>{CSS}</style></head><body>{''.join(parts)}</body></html>"


def cover_html():
    nav = [("01", "Profitability & Balance Sheet", "NII, NIM, deposits, budget delivery"),
           ("02", "Lending & Credit Risk", "Arrears, IFRS 9, remortgage wall, BBL vintages"),
           ("03", "Customers, Digital & Conduct", "Digital adoption, branches, complaints, fraud"),
           ("04", "Data Platform & Quality", "Pipeline runs, data freshness, automated quality checks")]
    left_w = 760
    parts = [f"""
<div class='abs' style='left:0;top:0;width:{left_w}px;height:{H}px;
     background:linear-gradient(160deg,{C['brand_dark']} 0%,{C['brand']} 100%)'></div>
<div class='abs' style='left:72px;top:120px;font-size:15px;letter-spacing:3px;color:#BFE3D2;font-weight:600'>EXECUTIVE DASHBOARD</div>
<div class='abs' style='left:72px;top:160px;width:620px;font-size:54px;line-height:62px;color:#FFFFFF;font-weight:700'>UK Retail &amp; SME Banking</div>
<div class='abs' style='left:72px;top:300px;width:600px;font-size:24px;line-height:34px;color:#E3F2EA'>Performance &amp; Risk | Jan 2020 to Aug 2026</div>
<div class='abs' style='left:72px;top:372px;width:120px;height:4px;background:#7FD1AE'></div>
<div class='abs' style='left:72px;top:408px;width:600px;font-size:17px;line-height:28px;color:#D4EBDF'>
Lloyds Banking Group case study<br>500k customers &nbsp;|&nbsp; 12 UK regions &nbsp;|&nbsp; 3 brands<br>
Azure Data Lake &nbsp;|&nbsp; Data Factory &nbsp;|&nbsp; Azure SQL &nbsp;|&nbsp; Power BI</div>
<div class='abs' style='left:72px;top:930px;width:600px;font-size:13px;line-height:20px;color:#A9D3BF'>
Hypothetical data generated for a portfolio project. Not affiliated with, endorsed by or based on
internal data of Lloyds Banking Group. Bank Rate series from the Bank of England.</div>
<div class='abs' style='left:{left_w + 80}px;top:120px;font-size:15px;letter-spacing:3px;color:{C['ink2']};font-weight:600'>HEADLINES | YEAR TO DATE</div>"""]
    kx, kw, kg = left_w + 80, 320, 20
    for i in range(3):
        parts.append(f"<div class='panel kpi' style='left:{kx + i * (kw + kg)}px;top:160px;width:{kw}px;height:170px'></div>")
    parts.append(f"<div class='abs' style='left:{left_w + 80}px;top:400px;font-size:15px;letter-spacing:3px;color:{C['ink2']};font-weight:600'>EXPLORE</div>")
    for i, (n, t, d) in enumerate(nav):
        y = 440 + i * 140
        parts.append(f"""<div class='panel' style='left:{left_w + 80}px;top:{y}px;width:1000px;height:124px'></div>
<div class='abs' style='left:{left_w + 112}px;top:{y + 24}px;font-size:40px;font-weight:700;color:{C['accent']}'>{n}</div>
<div class='abs' style='left:{left_w + 210}px;top:{y + 26}px;font-size:28px;font-weight:600;color:{C['ink']}'>{t}</div>
<div class='abs' style='left:{left_w + 210}px;top:{y + 70}px;font-size:17px;color:{C['ink2']}'>{d}</div>
<div class='abs' style='left:{left_w + 1010}px;top:{y + 36}px;font-size:40px;color:{C['accent']}'>&#8250;</div>""")
    return f"<html><head><style>{CSS}</style></head><body>{''.join(parts)}</body></html>"


def main():
    spec = ["# Lloyds dashboard | layout spec (canvas 1920 x 1080)", "",
            "Power BI: View > Page view > Actual size; Page format > Canvas settings > Custom 1920 x 1080;",
            "Canvas background > Image > Fit, transparency 0%. For each visual: Format > General > Properties.", ""]
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        pg = br.new_page(viewport={"width": W, "height": H})
        pg.set_content(cover_html()); pg.screenshot(path=str(OUT / "bg_p0_cover.png"))
        spec += ["## Cover", "", "| Visual | X | Y | W | H |", "|---|---|---|---|---|"]
        for i in range(3):
            spec.append(f"| Hero KPI {i + 1} (card) | {840 + i * 340} | 160 | 320 | 170 |")
        for i in range(4):
            spec.append(f"| Nav button {i + 1} (blank button, transparent) | 840 | {440 + i * 140} | 1000 | 124 |")
        spec.append("")
        for key, p in PAGES.items():
            pg.set_content(page_html(p)); pg.screenshot(path=str(OUT / f"bg_{key}.png"))
            spec += [f"## {p['title']}", "", "| Visual | X | Y | W | H |", "|---|---|---|---|---|",
                     f"| Slicer strip (4-5 slicers inside) | {SLICER[0]} | {SLICER[1]} | {SLICER[2]} | {SLICER[3]} |"]
            for name, b in zip(p["kpis"], kpi_boxes()):
                spec.append(f"| KPI {name} | {b[0]} | {b[1]} | {b[2]} | {b[3]} |")
            for (name, _), b in zip(p["a"], row(*ROW_A, [x[1] for x in p["a"]])):
                spec.append(f"| {name} | {b[0]} | {b[1]} | {b[2]} | {b[3]} |")
            for (name, _), b in zip(p["b"], row(*ROW_B, [x[1] for x in p["b"]])):
                spec.append(f"| {name} | {b[0]} | {b[1]} | {b[2]} | {b[3]} |")
            spec.append("")
        br.close()
    (OUT / "layout_spec.md").write_text("\n".join(spec))
    print("backgrounds + layout_spec.md written to", OUT)


if __name__ == "__main__":
    main()
