"""
Generowanie raportu HTML z osadzonymi wykresami Plotly.
Współdzielone między app.py (download) a weekly_sender.py (email attachment).
Brak zależności od Streamlit.
"""


def _kpi_card_html(label: str, value: str) -> str:
    return (
        f'<div class="kpi-card">'
        f'<div class="kpi-label">{label}</div>'
        f'<div class="kpi-value">{value}</div>'
        f'</div>'
    )


def build_charts_html(ads_data: dict, ga4_data: dict) -> str:
    """Generuje sekcję z KPI + interaktywnymi wykresami Plotly do osadzenia w HTML."""
    import plotly.graph_objects as go
    import plotly.io as pio

    PLOT_CONFIG = {"displayModeBar": False, "responsive": True}
    PLOT_LAYOUT = dict(
        paper_bgcolor="white",
        plot_bgcolor="white",
        font=dict(family="Arial, Helvetica, sans-serif", color="#333"),
    )

    sections = []

    # ── KPI summary ─────────────────────────────────────────────────────────
    kpis = []
    if ads_data:
        t = ads_data["totals"]
        avg_cpc = round(t["cost_pln"] / t["clicks"], 2) if t["clicks"] else 0
        kpis += [
            ("Wydatki Google Ads", f"{t['cost_pln']} zł"),
            ("Wyświetlenia", f"{t['impressions']:,}"),
            ("Kliknięcia", f"{t['clicks']:,}"),
            ("CTR", f"{t['ctr_pct']}%"),
            ("Średni CPC", f"{avg_cpc} zł"),
        ]
    if ga4_data:
        g = ga4_data["general"]
        dur = g["avg_session_duration_sec"]
        ga4_conv = sum(int(e.get("conversions", 0)) for e in ga4_data.get("conversion_events", []))
        kpis += [
            ("Użytkownicy strony", f"{g['users']:,}"),
            ("Sesje", f"{g['sessions']:,}"),
            ("Śr. czas wizyty", f"{dur//60}m {dur%60}s"),
            ("Wsp. zaangażowania", f"{round(100 - g['bounce_rate_pct'], 1)}%"),
            ("Konwersje GA4", f"{ga4_conv}"),
        ]
    if kpis:
        cards = "".join(_kpi_card_html(l, v) for l, v in kpis)
        sections.append(f'<div class="kpi-grid">{cards}</div>')

    # ── Wykres: Koszt vs kliknięcia per kampania ───────────────────────────
    if ads_data:
        campaigns = ads_data.get("campaigns", [])
        if campaigns:
            names = [c["name"] for c in campaigns]
            fig = go.Figure(data=[
                go.Bar(name="Koszt (zł)", x=names, y=[c["cost_pln"] for c in campaigns],
                       marker_color="#1A3A5C"),
                go.Bar(name="Kliknięcia", x=names, y=[c["clicks"] for c in campaigns],
                       marker_color="#E8630A", yaxis="y2"),
            ])
            fig.update_layout(
                title="Efektywność kampanii: koszt vs kliknięcia",
                barmode="group",
                xaxis=dict(tickangle=-20),
                yaxis=dict(title="Koszt (zł)"),
                yaxis2=dict(title="Kliknięcia", overlaying="y", side="right"),
                height=400, margin=dict(t=50, b=80, l=60, r=60),
                **PLOT_LAYOUT,
            )
            sections.append('<h2>Wyniki kampanii Google Ads</h2>')
            sections.append(pio.to_html(fig, include_plotlyjs="cdn", full_html=False, config=PLOT_CONFIG))

    # ── Wykres: Źródła ruchu (donut) ───────────────────────────────────────
    if ga4_data:
        sources = ga4_data.get("sources", [])
        if sources:
            fig = go.Figure(go.Pie(
                labels=[s["channel"] for s in sources],
                values=[s["sessions"] for s in sources],
                hole=0.45,
                textinfo="label+percent",
                marker=dict(colors=["#E8630A", "#1A3A5C", "#F0A868", "#2E6EA6",
                                    "#A8D8EA", "#E8A0BF", "#B5EAD7", "#FFDAC1"]),
            ))
            fig.update_layout(
                title="Źródła ruchu na stronie (sesje)",
                height=420, margin=dict(t=50, b=20, l=20, r=20),
                **PLOT_LAYOUT,
            )
            sections.append('<h2>Źródła ruchu</h2>')
            sections.append(pio.to_html(fig, include_plotlyjs=False, full_html=False, config=PLOT_CONFIG))

    # ── Wykres: Konwersje GA4 per zdarzenie ────────────────────────────────
    if ga4_data:
        events = [e for e in ga4_data.get("conversion_events", []) if e.get("conversions", 0) > 0]
        if events:
            top_ev = events[:12]
            fig = go.Figure(go.Bar(
                x=[e["conversions"] for e in top_ev],
                y=[e["event"] for e in top_ev],
                orientation="h",
                marker_color="#E8630A",
                text=[str(int(e["conversions"])) for e in top_ev],
                textposition="outside",
            ))
            fig.update_layout(
                title="Konwersje na stronie (GA4) — wg zdarzenia",
                height=max(280, 35 * len(top_ev) + 80),
                margin=dict(t=50, b=20, l=200, r=60),
                xaxis=dict(showgrid=False),
                yaxis=dict(autorange="reversed"),
                **PLOT_LAYOUT,
            )
            sections.append('<h2>Konwersje na stronie</h2>')
            sections.append(pio.to_html(fig, include_plotlyjs=False, full_html=False, config=PLOT_CONFIG))

    return "\n".join(sections)


def report_to_html(
    client_name: str,
    period_label: str,
    report_text: str,
    ads_data: dict = None,
    ga4_data: dict = None,
    logo_b64: str = "",
    logo_mime: str = "image/png",
) -> str:
    """Generuje pełny dokument HTML z nagłówkiem, wykresami i treścią raportu."""
    try:
        import markdown as _md
        body_html = _md.markdown(report_text, extensions=["tables", "fenced_code"])
    except ImportError:
        import html
        body_html = "<pre>" + html.escape(report_text) + "</pre>"

    charts_html = build_charts_html(ads_data or {}, ga4_data or {})
    logo_html = ""
    if logo_b64:
        logo_html = (
            f'<img src="data:{logo_mime};base64,{logo_b64}" '
            f'style="max-height:80px;margin-bottom:14px;background:white;'
            f'padding:6px 10px;border-radius:6px">'
        )

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Raport — {client_name} — {period_label}</title>
<style>
  body {{
    font-family: Arial, Helvetica, sans-serif;
    max-width: 980px;
    margin: 40px auto;
    padding: 0 20px;
    color: #333;
    line-height: 1.65;
  }}
  h1, h2, h3 {{ color: #1A3A5C; }}
  h2 {{
    border-bottom: 3px solid #E8630A;
    padding-bottom: 6px;
    margin-top: 36px;
  }}
  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 16px 0;
    font-size: 0.9rem;
  }}
  th {{
    background: #1A3A5C;
    color: white;
    padding: 10px 14px;
    text-align: left;
  }}
  td {{ padding: 8px 14px; border-bottom: 1px solid #eee; }}
  tr:nth-child(even) td {{ background: #F5F5F5; }}
  .report-header {{
    background: linear-gradient(135deg, #1A3A5C 0%, #E8630A 100%);
    color: white;
    padding: 36px 32px;
    border-radius: 12px;
    text-align: center;
    margin-bottom: 32px;
  }}
  .report-header h1 {{ color: white; margin: 0; font-size: 2rem; }}
  .report-header p {{ color: rgba(255,255,255,0.85); margin: 8px 0 0; font-size: 1.1rem; }}
  .kpi-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
    margin: 24px 0 8px;
  }}
  .kpi-card {{
    background: #FFF8F3;
    border-left: 4px solid #E8630A;
    border-radius: 8px;
    padding: 14px 18px;
    text-align: center;
  }}
  .kpi-label {{
    font-size: 0.75rem;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 4px;
  }}
  .kpi-value {{
    font-size: 1.5rem;
    font-weight: 700;
    color: #1A3A5C;
  }}
  @media print {{
    body {{ margin: 20px; max-width: none; }}
    .report-header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .kpi-card {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>
<div class="report-header">
  {logo_html}
  <h1>{client_name}</h1>
  <p>Raport marketingowy &nbsp;|&nbsp; {period_label}</p>
</div>
{charts_html}
{body_html}
</body>
</html>"""
