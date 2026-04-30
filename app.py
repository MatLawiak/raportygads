"""
Generator Raportów Marketingowych — interfejs Streamlit

Uruchomienie:
    streamlit run app.py
"""

import os
import json
import uuid
import sys
from pathlib import Path
from datetime import date, timedelta

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

import streamlit as st
import auth

# ─── Ścieżki ──────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent

# ─── Inicjalizacja plików z Secrets (Streamlit Cloud) ─────────────────────────

def init_from_secrets() -> None:
    """Tworzy pliki konfiguracyjne ze Streamlit Secrets jeśli działamy w chmurze."""
    try:
        # google-ads.yaml
        gads_yaml = st.secrets.get("GOOGLE_ADS_YAML", "")
        if gads_yaml and not (BASE_DIR / "google-ads.yaml").exists():
            (BASE_DIR / "google-ads.yaml").write_text(gads_yaml, encoding="utf-8")

        # GA4 credentials JSON
        ga4_json = st.secrets.get("GA4_CREDENTIALS_JSON", "")
        if ga4_json and not (BASE_DIR / "ga4_credentials.json").exists():
            (BASE_DIR / "ga4_credentials.json").write_text(ga4_json, encoding="utf-8")
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(BASE_DIR / "ga4_credentials.json")

        # Klucze API
        for key in ("OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "ENCRYPTION_KEY"):
            val = st.secrets.get(key, "")
            if val:
                os.environ[key] = val

    except Exception:
        pass  # lokalnie st.secrets nie istnieje — pomijamy


init_from_secrets()

REPORTS_DIR = BASE_DIR / "raporty"
REPORTS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(BASE_DIR))

# Per-user paths — ustawiane po uwierzytelnieniu
CONFIG_FILE: Path = BASE_DIR / "config.json"          # placeholder, nadpisywany po logowaniu
GA4_CREDS_PATH: Path = BASE_DIR / "ga4_credentials.json"
GADS_YAML_PATH: Path = BASE_DIR / "google-ads.yaml"

# ─── Helpers konfiguracji ─────────────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "clients": [],
        "email": {
            "recipients": [],
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "",
            "smtp_password": "",
        },
    }


def save_config(cfg: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    uid = st.session_state.get("user_id")
    if uid:
        auth.save_user_data(uid, {"config_json": json.dumps(cfg, ensure_ascii=False)})


# ─── Konfiguracja strony ──────────────────────────────────────────────────────

st.set_page_config(
    page_title="Generator Raportów Marketingowych",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .main-title { font-size: 1.7rem; font-weight: 700; margin-bottom: 0.2rem; }
    .page-subtitle { color: #888; font-size: 0.95rem; margin-bottom: 1.5rem; }
    div[data-testid="stDownloadButton"] button { width: 100%; }
</style>
""", unsafe_allow_html=True)

# ─── Stan sesji ───────────────────────────────────────────────────────────────

if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "report_text" not in st.session_state:
    st.session_state.report_text = None
if "report_filename" not in st.session_state:
    st.session_state.report_filename = None
if "report_client" not in st.session_state:
    st.session_state.report_client = None
if "show_faq" not in st.session_state:
    st.session_state.show_faq = False

# ─── Landing page / Auth ──────────────────────────────────────────────────────

ACCENT_L   = "#E8630A"
ACCENT2_L  = "#1A3A5C"


def show_landing() -> None:
    st.markdown("""
    <style>
        [data-testid="stSidebar"] { display: none !important; }
        .block-container { padding-top: 0 !important; max-width: 860px; }
    </style>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{ACCENT2_L} 0%,{ACCENT_L} 100%);
                padding:56px 40px 48px;border-radius:0 0 20px 20px;text-align:center;margin-bottom:32px">
        <p style="color:rgba(255,255,255,0.75);font-size:0.9rem;margin:0 0 10px;letter-spacing:.1em;text-transform:uppercase">
            Generator Raportów Marketingowych
        </p>
        <h1 style="color:white;margin:0;font-size:2.4rem;font-weight:800;line-height:1.2">
            Raporty Google Ads + GA4<br>gotowe w 30 sekund
        </h1>
        <p style="color:rgba(255,255,255,0.82);margin:18px 0 0;font-size:1.05rem;max-width:540px;margin-left:auto;margin-right:auto">
            Podłącz swoje konto reklamowe i stronę internetową — aplikacja automatycznie pobierze dane
            i wygeneruje profesjonalny raport miesięczny lub tygodniowy.
        </p>
    </div>""", unsafe_allow_html=True)

    # Features
    c1, c2, c3 = st.columns(3)
    for col, icon, title, desc in [
        (c1, "📈", "Google Ads", "Kampanie, kliknięcia, konwersje, CPC, CTR — wszystko w jednym miejscu."),
        (c2, "🔍", "Google Analytics 4", "Ruch na stronie, źródła, zaangażowanie i konwersje GA4."),
        (c3, "📧", "Wysyłka emailem", "Raport trafia automatycznie do skrzynki klienta po wygenerowaniu."),
    ]:
        col.markdown(f"""
        <div style="background:#F9F9F9;border-radius:12px;padding:24px 20px;text-align:center;height:160px">
            <div style="font-size:2rem">{icon}</div>
            <p style="font-weight:700;color:{ACCENT2_L};margin:8px 0 6px">{title}</p>
            <p style="color:#666;font-size:0.85rem;margin:0">{desc}</p>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Login / Register tabs
    tab_login, tab_reg = st.tabs(["Zaloguj się", "Zarejestruj się — bezpłatnie"])

    with tab_login:
        with st.form("login_form"):
            email_l = st.text_input("Adres email", placeholder="twoj@email.com")
            pass_l  = st.text_input("Hasło", type="password")
            if st.form_submit_button("Zaloguj się", type="primary", use_container_width=True):
                if not email_l or not pass_l:
                    st.error("Uzupełnij email i hasło.")
                else:
                    ok, result = auth.login(email_l, pass_l)
                    if ok:
                        st.session_state.user_id    = result
                        st.session_state.user_email = email_l.lower().strip()
                        st.rerun()
                    else:
                        st.error(result)

    with tab_reg:
        with st.form("register_form"):
            email_r  = st.text_input("Adres email", placeholder="twoj@email.com", key="reg_email")
            pass_r   = st.text_input("Hasło", type="password", key="reg_pass",
                                     help="Minimum 8 znaków.")
            pass_r2  = st.text_input("Powtórz hasło", type="password", key="reg_pass2")
            st.caption(
                "Rejestrując się akceptujesz przechowywanie Twojego emaila i "
                "zaszyfrowanych kluczy API w bazie danych (Supabase, region EU). "
                "Możesz trwale usunąć konto w Ustawieniach."
            )
            if st.form_submit_button("Zarejestruj się", type="primary", use_container_width=True):
                if not email_r or "@" not in email_r:
                    st.error("Podaj poprawny adres email.")
                elif len(pass_r) < 8:
                    st.error("Hasło musi mieć co najmniej 8 znaków.")
                elif pass_r != pass_r2:
                    st.error("Hasła nie są identyczne.")
                else:
                    ok, result = auth.register(email_r, pass_r)
                    if ok:
                        st.session_state.user_id    = result
                        st.session_state.user_email = email_r.lower().strip()
                        st.success("Konto utworzone. Witamy!")
                        st.rerun()
                    else:
                        st.error(result)

    st.stop()


if not st.session_state.user_id:
    show_landing()

# ─── Per-user paths (po uwierzytelnieniu) ────────────────────────────────────

_uid = st.session_state.user_id
CONFIG_FILE      = BASE_DIR / f"config_{_uid}.json"
GA4_CREDS_PATH   = BASE_DIR / f"ga4_{_uid}.json"
GADS_YAML_PATH   = BASE_DIR / f"gads_{_uid}.yaml"

# Odtwórz dane z Supabase przy starcie sesji (raz per login)
if st.session_state.get("config_user") != _uid:
    _ud = auth.load_user_data(_uid)

    if _ud.get("openai_key"):
        os.environ["OPENAI_API_KEY"] = _ud["openai_key"]

    if _ud.get("gads_yaml"):
        GADS_YAML_PATH.write_text(_ud["gads_yaml"], encoding="utf-8")
        os.environ["GOOGLE_ADS_CONFIGURATION_FILE_PATH"] = str(GADS_YAML_PATH)

    if _ud.get("ga4_json"):
        GA4_CREDS_PATH.write_text(_ud["ga4_json"], encoding="utf-8")
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GA4_CREDS_PATH)

    if _ud.get("config_json"):
        try:
            st.session_state.config = json.loads(_ud["config_json"])
        except Exception:
            pass

    if "config" not in st.session_state:
        st.session_state.config = load_config()

    st.session_state.config_user = _uid

elif GA4_CREDS_PATH.exists():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GA4_CREDS_PATH)

cfg: dict = st.session_state.config

# ─── Pasek boczny ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📊 Raporty Marketingowe")
    st.caption(st.session_state.user_email or "")
    st.markdown("---")
    page = st.radio(
        "Nawigacja",
        ["Generuj raport", "Klienci", "Ustawienia"],
        label_visibility="collapsed",
    )
    st.markdown("---")

    # Szybki status API
    openai_ok = bool(os.environ.get("OPENAI_API_KEY"))
    gads_ok   = GADS_YAML_PATH.exists()
    ga4_ok    = GA4_CREDS_PATH.exists()

    st.caption("Status API")
    st.write("🟢 OpenAI" if openai_ok else "🔴 OpenAI — brak klucza")
    st.write("🟢 Google Ads" if gads_ok else "🔴 Google Ads — brak pliku")
    st.write("🟢 GA4" if ga4_ok else "🟡 GA4 — brak credentials")

    st.markdown("<br>" * 6, unsafe_allow_html=True)
    st.markdown("---")
    if st.button("❓ Pomoc / FAQ", use_container_width=True):
        st.session_state.show_faq = True
        st.rerun()
    if st.button("Wyloguj", use_container_width=True):
        for key in ["user_id", "user_email", "config", "config_user",
                    "report_text", "report_filename", "report_client"]:
            st.session_state.pop(key, None)
        st.rerun()


# ─── Helpers generowania ──────────────────────────────────────────────────────

def get_last_full_week() -> tuple[str, str]:
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return str(last_monday), str(last_sunday)


def build_weekly_prompt(client_name: str, period_label: str, ads_data: dict, ga4_data: dict) -> str:
    from main import _format_campaigns_table, _format_sources_table

    ads_section = "Brak danych Google Ads za ten tydzień."
    if ads_data:
        t = ads_data["totals"]
        table = _format_campaigns_table(ads_data.get("campaigns", []))
        ads_section = (
            f"Wydatki: {t['cost_pln']} zł | Kliknięcia: {t['clicks']} | "
            f"Wyświetlenia: {t['impressions']}\n"
            f"CTR: {t['ctr_pct']}% | Konwersje: {t['conversions']} | "
            f"Koszt/konw.: {t['cost_per_conversion_pln']} zł\n\n{table}"
        )

    ga4_section = "Brak danych GA4 za ten tydzień."
    if ga4_data:
        g = ga4_data["general"]
        table = _format_sources_table(ga4_data.get("sources", []))
        ga4_section = f"Użytkownicy: {g['users']} | Sesje: {g['sessions']}\n{table}"

    return f"""Wygeneruj TYGODNIOWY raport marketingowy. To raport operacyjny — pisz zwięźle.

KLIENT: {client_name}
TYDZIEŃ: {period_label}

=== GOOGLE ADS ===
{ads_section}

=== GOOGLE ANALYTICS 4 ===
{ga4_section}

=== FORMAT (trzymaj się go ściśle) ===
## Wyniki tygodnia — Google Ads
(tabela z kluczowymi metrykami + 2 zdania komentarza)

## Ruch na stronie — GA4
(jeśli dane dostępne, inaczej napisz że brak danych)

## Co zwraca uwagę
(maks. 3 punkty — tylko to co istotne)

## Działania na przyszły tydzień
(maks. 3 punkty — konkretne, krótkie)

Pisz po polsku. Prosto, bez żargonu. Maksymalnie 350 słów łącznie."""


def generate_full_report(
    client: dict,
    report_type: str,
    date_from: str,
    date_to: str,
    period_label: str,
) -> tuple[str, str, dict, dict]:
    from main import (
        fetch_google_ads_data,
        fetch_ga4_data,
        build_report_prompt,
        generate_report,
    )

    ads_data: dict = {}
    ga4_data: dict = {}

    if client.get("ads_customer_id"):
        try:
            # Wskaż per-user plik konfiguracyjny Google Ads
            if GADS_YAML_PATH.exists():
                os.environ["GOOGLE_ADS_CONFIGURATION_FILE_PATH"] = str(GADS_YAML_PATH)
            ads_data = fetch_google_ads_data(client["ads_customer_id"], date_from, date_to)
        except Exception as e:
            st.warning(f"Google Ads: nie udało się pobrać danych — {e}")

    if client.get("ga4_property_id"):
        try:
            ga4_data = fetch_ga4_data(client["ga4_property_id"], date_from, date_to)
        except Exception as e:
            st.warning(f"GA4: nie udało się pobrać danych — {e}")

    if report_type == "Tygodniowy":
        prompt = build_weekly_prompt(client["name"], period_label, ads_data, ga4_data)
    else:
        prompt = build_report_prompt(client["name"], period_label, ads_data, ga4_data)

    report_text = generate_report(prompt)

    safe_name = client["name"].replace(" ", "_").lower()
    suffix = "_tyg" if report_type == "Tygodniowy" else ""
    filename = f"raport_{safe_name}_{date_from[:7]}{suffix}.md"
    path = REPORTS_DIR / filename
    path.write_text(report_text, encoding="utf-8")

    return report_text, filename, ads_data, ga4_data


# ─── Helpers wizualne ────────────────────────────────────────────────────────

ACCENT = "#E8630A"        # pomarańczowy jak w PDF Białej Damy
ACCENT2 = "#1A3A5C"       # granatowy
LIGHT_BG = "#FFF8F3"
GRAY = "#F5F5F5"


def _header_html(logo_b64: str, logo_mime: str, client_name: str, period: str, date_range: str = "") -> str:
    logo_html = ""
    if logo_b64:
        logo_html = f'<img src="data:{logo_mime};base64,{logo_b64}" style="max-height:70px;margin-bottom:8px">'
    return f"""
    <div style="background:linear-gradient(135deg,{ACCENT2} 0%,{ACCENT} 100%);
                padding:36px 32px;border-radius:12px;text-align:center;margin-bottom:24px">
        {logo_html}
        <h1 style="color:white;margin:0;font-size:2rem;font-weight:700">{client_name}</h1>
        <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:1.1rem">
            Raport miesięczny &nbsp;|&nbsp; {period}{(' &nbsp;|&nbsp; ' + date_range) if date_range else ''}
        </p>
    </div>"""


def _kpi_card(label: str, value: str, sub: str = "") -> str:
    return f"""
    <div style="background:{LIGHT_BG};border-left:4px solid {ACCENT};border-radius:8px;
                padding:16px 20px;text-align:center">
        <p style="margin:0;font-size:0.78rem;color:#888;text-transform:uppercase;letter-spacing:.05em">{label}</p>
        <p style="margin:4px 0;font-size:1.6rem;font-weight:700;color:{ACCENT2}">{value}</p>
        {"<p style='margin:0;font-size:0.75rem;color:#aaa'>" + sub + "</p>" if sub else ""}
    </div>"""


def _section_title(text: str) -> None:
    st.markdown(
        f"<h2 style='border-bottom:3px solid {ACCENT};padding-bottom:6px;"
        f"color:{ACCENT2};margin-top:8px'>{text}</h2>",
        unsafe_allow_html=True,
    )


def _plotly_table(header_vals: list, rows: list, height: int = None) -> None:
    import plotly.graph_objects as go
    if not rows:
        return
    cols = list(zip(*rows))
    row_colors = []
    for i in range(len(rows)):
        row_colors.append(GRAY if i % 2 == 0 else "white")
    fig = go.Figure(data=[go.Table(
        header=dict(
            values=[f"<b>{h}</b>" for h in header_vals],
            fill_color=ACCENT2,
            font=dict(color="white", size=12),
            align="left",
            height=32,
        ),
        cells=dict(
            values=list(cols),
            fill_color=[row_colors],
            align="left",
            font=dict(size=11, color="#333"),
            height=28,
        ),
    )])
    h = height or (80 + len(rows) * 30)
    fig.update_layout(margin=dict(t=4, b=4, l=0, r=0), height=h)
    st.plotly_chart(fig, use_container_width=True)


# ─── Wizualizacja raportu ─────────────────────────────────────────────────────

def render_visual_report(client_name: str, period_label: str, ads_data: dict, ga4_data: dict, report_text: str) -> None:
    import plotly.graph_objects as go
    import plotly.express as px

    logo_b64 = cfg.get("logo_b64", "")
    logo_mime = cfg.get("logo_mime", "image/png")

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Strona tytułowa", "Google Ads", "Google Analytics", "Podsumowanie", "Wnioski i rekomendacje"
    ])

    # ══════════════════════════════════════════════════════
    # TAB 1 — STRONA TYTUŁOWA
    # ══════════════════════════════════════════════════════
    with tab1:
        st.markdown(_header_html(logo_b64, logo_mime, client_name, period_label), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        if ads_data and ga4_data:
            t = ads_data["totals"]
            g = ga4_data["general"]
            dur = g["avg_session_duration_sec"]
            cols = st.columns(4)
            cols[0].markdown(_kpi_card("Wydatki Google Ads", f"{t['cost_pln']} zł"), unsafe_allow_html=True)
            cols[1].markdown(_kpi_card("Konwersje", f"{int(t['conversions'])}"), unsafe_allow_html=True)
            cols[2].markdown(_kpi_card("Użytkownicy strony", f"{g['users']:,}"), unsafe_allow_html=True)
            cols[3].markdown(_kpi_card("Śr. czas wizyty", f"{dur//60}m {dur%60}s"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(
            f"<p style='text-align:center;color:#aaa;font-size:0.85rem'>Raport przygotowany automatycznie "
            f"na podstawie danych z Google Ads i Google Analytics 4</p>",
            unsafe_allow_html=True,
        )

    # ══════════════════════════════════════════════════════
    # TAB 2 — GOOGLE ADS
    # ══════════════════════════════════════════════════════
    with tab2:
        st.markdown(_header_html(logo_b64, logo_mime, client_name, period_label), unsafe_allow_html=True)
        _section_title("Emisja i kliknięcia")

        if ads_data:
            t = ads_data["totals"]
            conv_rate = round(t["conversions"] / t["clicks"] * 100, 2) if t["clicks"] else 0
            cols = st.columns(4)
            cols[0].markdown(_kpi_card("Kliknięcia", f"{t['clicks']:,}"), unsafe_allow_html=True)
            cols[1].markdown(_kpi_card("Koszt konwersji", f"{t['cost_per_conversion_pln']} zł"), unsafe_allow_html=True)
            cols[2].markdown(_kpi_card("Współcz. konwersji", f"{conv_rate}%"), unsafe_allow_html=True)
            cols[3].markdown(_kpi_card("CTR", f"{t['ctr_pct']}%"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            col_l, col_r = st.columns([1, 1])

            # Konwersje per typ — wykres poziomy
            events = (ads_data.get("conversion_events") or [])
            if not events:
                # fallback jeśli brak per-event — pokaż sumę
                events = []

            # Wykres kampanii — koszt vs konwersje
            campaigns = ads_data.get("campaigns", [])
            with col_l:
                _section_title("Rodzaj konwersji")
                if events:
                    top_ev = events[:10]
                    ev_labels = [
                        e["event"]
                        .replace("restauracja_biala_dama_(web)_", "")
                        .replace("restauracja_biala_dama (web) ", "")
                        .replace("_", " ")
                        for e in top_ev
                    ]
                    fig = go.Figure(go.Bar(
                        x=[e["conversions"] for e in top_ev],
                        y=ev_labels,
                        orientation="h",
                        marker=dict(color=ACCENT, line=dict(width=0)),
                        text=[str(int(e["conversions"])) for e in top_ev],
                        textposition="outside",
                    ))
                    fig.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        margin=dict(t=10, b=10, l=10, r=40),
                        height=300,
                        xaxis=dict(showgrid=False, visible=False),
                        yaxis=dict(autorange="reversed"),
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    total_conv = sum(e["conversions"] for e in events)
                    st.markdown(f"**Suma całkowita: {int(total_conv)}**")
                else:
                    st.info("Brak danych konwersji per typ.")

            with col_r:
                _section_title("Efektywność kampanii")
                if campaigns:
                    names = [c["name"].replace("_", " ") for c in campaigns]
                    fig = go.Figure(data=[
                        go.Bar(
                            name="Koszt (zł)",
                            x=[c["cost_pln"] for c in campaigns],
                            y=names,
                            orientation="h",
                            marker_color=ACCENT2,
                            opacity=0.85,
                        ),
                        go.Bar(
                            name="Konwersje",
                            x=[c["conversions"] for c in campaigns],
                            y=names,
                            orientation="h",
                            marker_color=ACCENT,
                            opacity=0.85,
                        ),
                    ])
                    fig.update_layout(
                        barmode="group",
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        legend=dict(orientation="h", y=1.1),
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=300,
                        xaxis=dict(showgrid=True, gridcolor="#eee"),
                    )
                    st.plotly_chart(fig, use_container_width=True)

            # Tabela kampanii
            st.markdown("<br>", unsafe_allow_html=True)
            _section_title("Tabela kampanii")
            if campaigns:
                rows = [
                    [c["name"], f"{c['clicks']:,}", f"{c['impressions']:,}",
                     f"{c['avg_cpc_pln']} zł", round(c["conversions"], 1),
                     f"{c['cost_per_conversion_pln']} zł", f"{c['cost_pln']} zł"]
                    for c in campaigns
                ]
                rows.append([
                    "Suma całkowita",
                    f"{t['clicks']:,}", f"{t['impressions']:,}",
                    "—", round(t["conversions"], 1),
                    f"{t['cost_per_conversion_pln']} zł", f"{t['cost_pln']} zł",
                ])
                _plotly_table(
                    ["Kampania", "Kliknięcia", "Wyświetlenia", "Śr. CPC", "Konwersje", "Koszt konw.", "Koszt"],
                    rows,
                )
        else:
            st.info("Brak danych Google Ads za ten okres.")

    # ══════════════════════════════════════════════════════
    # TAB 3 — GOOGLE ANALYTICS
    # ══════════════════════════════════════════════════════
    with tab3:
        st.markdown(_header_html(logo_b64, logo_mime, client_name, period_label), unsafe_allow_html=True)
        _section_title("Źródła ruchu na stronie")

        if ga4_data:
            g = ga4_data["general"]
            dur = g["avg_session_duration_sec"]
            cols = st.columns(4)
            cols[0].markdown(_kpi_card("Użytkownicy", f"{g['users']:,}"), unsafe_allow_html=True)
            cols[1].markdown(_kpi_card("Sesje", f"{g['sessions']:,}"), unsafe_allow_html=True)
            cols[2].markdown(_kpi_card("Śr. czas wizyty", f"{dur//60}m {dur%60}s"), unsafe_allow_html=True)
            cols[3].markdown(_kpi_card("Wsp. zaangażowania", f"{100 - g['bounce_rate_pct']:.1f}%"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            sources = ga4_data.get("sources", [])
            col_l, col_r = st.columns([1, 1])

            with col_l:
                if sources:
                    fig = go.Figure(go.Pie(
                        labels=[s["channel"] for s in sources],
                        values=[s["sessions"] for s in sources],
                        hole=0.45,
                        textinfo="label+percent",
                        marker=dict(colors=[
                            ACCENT, ACCENT2, "#F0A868", "#2E6EA6", "#A8D8EA",
                            "#E8A0BF", "#B5EAD7", "#FFDAC1",
                        ]),
                        textfont=dict(size=11),
                    ))
                    fig.update_layout(
                        showlegend=False,
                        margin=dict(t=10, b=10, l=10, r=10),
                        height=320,
                        paper_bgcolor="rgba(0,0,0,0)",
                    )
                    st.plotly_chart(fig, use_container_width=True)

            with col_r:
                if sources:
                    top_src = sorted(sources, key=lambda x: x["sessions"], reverse=True)[:8]
                    fig = go.Figure(go.Bar(
                        x=[s["sessions"] for s in top_src],
                        y=[s["channel"] for s in top_src],
                        orientation="h",
                        marker_color=ACCENT2,
                        text=[str(s["sessions"]) for s in top_src],
                        textposition="outside",
                    ))
                    fig.update_layout(
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        margin=dict(t=10, b=10, l=10, r=40),
                        height=320,
                        xaxis=dict(showgrid=False, visible=False),
                        yaxis=dict(autorange="reversed"),
                    )
                    st.plotly_chart(fig, use_container_width=True)

            # Tabela źródeł
            if sources:
                _plotly_table(
                    ["Źródło / medium", "Sesje", "Użytkownicy"],
                    [[s["channel"], f"{s['sessions']:,}", f"{s['users']:,}"] for s in sources],
                )

            # Konwersje GA4
            events = ga4_data.get("conversion_events", [])
            if events:
                st.markdown("<br>", unsafe_allow_html=True)
                _section_title("Konwersje na stronie")
                top_ev = events[:10]
                ev_labels = [
                    e["event"]
                    .replace("restauracja_biala_dama_(web)_", "")
                    .replace("restauracja_biala_dama (web) ", "")
                    .replace("_", " ")
                    for e in top_ev
                ]
                fig = go.Figure(go.Bar(
                    x=ev_labels,
                    y=[e["conversions"] for e in top_ev],
                    marker=dict(
                        color=[e["conversions"] for e in top_ev],
                        colorscale=[[0, "#FFF8F3"], [1, ACCENT]],
                        showscale=False,
                        line=dict(width=0),
                    ),
                    text=[str(int(e["conversions"])) for e in top_ev],
                    textposition="outside",
                ))
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=10, b=60, l=10, r=10),
                    height=320,
                    xaxis=dict(tickangle=-25),
                    yaxis=dict(showgrid=False, visible=False),
                )
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Brak danych Google Analytics 4 za ten okres.")

    # ══════════════════════════════════════════════════════
    # TAB 4 — PODSUMOWANIE
    # ══════════════════════════════════════════════════════
    with tab4:
        st.markdown(_header_html(logo_b64, logo_mime, client_name, period_label), unsafe_allow_html=True)
        _section_title(f"Podsumowanie działań marketingowych – {period_label}")

        # Wyciągnij sekcje z wygenerowanego tekstu
        import re
        sections = re.split(r"#{1,3}\s+", report_text)
        # Pokaż cały tekst raportu z wyjątkiem sekcji "Plan na kolejny miesiąc"
        clean = re.sub(r"#{1,3}\s+4\. Plan na kolejny miesiąc.*", "", report_text, flags=re.DOTALL)
        st.markdown(clean)

        # Gauges podsumowujące
        if ads_data:
            t = ads_data["totals"]
            conv_rate = round(t["conversions"] / t["clicks"] * 100, 1) if t["clicks"] else 0
            st.markdown("<br>", unsafe_allow_html=True)
            _section_title("Kluczowe wskaźniki miesiąca")
            c1, c2, c3 = st.columns(3)
            for col, val, maxv, label in [
                (c1, t["cost_per_conversion_pln"], 20, "Koszt konwersji (zł)"),
                (c2, conv_rate, 50, "Wsp. konwersji (%)"),
                (c3, t["ctr_pct"], 20, "CTR (%)"),
            ]:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=val,
                    title={"text": label, "font": {"size": 13}},
                    gauge={
                        "axis": {"range": [0, maxv]},
                        "bar": {"color": ACCENT},
                        "bgcolor": GRAY,
                        "borderwidth": 0,
                        "steps": [{"range": [0, maxv * 0.5], "color": "#FFF8F3"}],
                    },
                    number={"font": {"color": ACCENT2}},
                ))
                fig.update_layout(height=200, margin=dict(t=30, b=10, l=20, r=20),
                                  paper_bgcolor="rgba(0,0,0,0)")
                col.plotly_chart(fig, use_container_width=True)

    # ══════════════════════════════════════════════════════
    # TAB 5 — WNIOSKI I REKOMENDACJE
    # ══════════════════════════════════════════════════════
    with tab5:
        st.markdown(_header_html(logo_b64, logo_mime, client_name, period_label), unsafe_allow_html=True)
        _section_title("Wnioski i rekomendacje")

        # Wyciągnij sekcję planu z raportu
        import re
        match = re.search(r"#{1,3}\s+4\. Plan na kolejny miesiąc(.*)", report_text, re.DOTALL)
        if match:
            st.markdown(match.group(1).strip())
        else:
            st.markdown(report_text)

        # Podsumowanie wydatków — sparkline
        if ads_data:
            campaigns = ads_data.get("campaigns", [])
            if campaigns:
                st.markdown("<br>", unsafe_allow_html=True)
                _section_title("Budżet per kampania")
                names = [c["name"].replace("_", " ") for c in campaigns]
                costs = [c["cost_pln"] for c in campaigns]
                colors = [ACCENT if i == 0 else ACCENT2 for i in range(len(campaigns))]
                fig = go.Figure(go.Bar(
                    x=names, y=costs,
                    marker_color=colors,
                    text=[f"{v} zł" for v in costs],
                    textposition="outside",
                ))
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=10, b=20, l=10, r=10),
                    height=300,
                    xaxis=dict(tickangle=-20),
                    yaxis=dict(showgrid=False, visible=False),
                )
                st.plotly_chart(fig, use_container_width=True)


# ─── HTML export ─────────────────────────────────────────────────────────────

def _report_to_html(client_name: str, period_label: str, report_text: str) -> str:
    try:
        import markdown as _md
        body_html = _md.markdown(report_text, extensions=["tables", "fenced_code"])
    except ImportError:
        import html
        body_html = "<pre>" + html.escape(report_text) + "</pre>"

    return f"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Raport — {client_name} — {period_label}</title>
<style>
  body {{
    font-family: Arial, Helvetica, sans-serif;
    max-width: 900px;
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
  @media print {{
    body {{ margin: 20px; }}
    .report-header {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  }}
</style>
</head>
<body>
<div class="report-header">
  <h1>{client_name}</h1>
  <p>Raport marketingowy &nbsp;|&nbsp; {period_label}</p>
</div>
{body_html}
</body>
</html>"""


# ─── Strona: Generuj raport ───────────────────────────────────────────────────

def page_generate():
    st.markdown('<p class="main-title">Generuj raport</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Wybierz klienta, typ raportu i kliknij Generuj.</p>', unsafe_allow_html=True)

    clients = cfg.get("clients", [])
    if not clients:
        st.warning("Brak klientów. Przejdź do sekcji **Klienci** i dodaj pierwsze konto.")
        return

    col1, col2 = st.columns([2, 1])
    with col1:
        selected_name = st.selectbox(
            "Klient",
            [c["name"] for c in clients],
        )
        selected_client = next(c for c in clients if c["name"] == selected_name)
    with col2:
        report_type = st.selectbox("Typ raportu", ["Miesięczny", "Tygodniowy"])

    if report_type == "Miesięczny":
        from main import get_last_full_month
        date_from, date_to = get_last_full_month()
        period_label = date.fromisoformat(date_from).strftime("%B %Y")
    else:
        date_from, date_to = get_last_full_week()
        period_label = f"{date_from} – {date_to}"

    st.caption(f"Okres: **{period_label}** ({date_from} — {date_to})")
    st.markdown("---")

    if st.button("▶ Generuj raport", type="primary", use_container_width=True):
        if not os.environ.get("OPENAI_API_KEY"):
            st.error("Brak klucza OpenAI. Przejdź do **Ustawienia** i dodaj swój klucz API OpenAI.")
        else:
            with st.spinner("Pobieranie danych z Google Ads i GA4..."):
                try:
                    report_text, filename, ads_data, ga4_data = generate_full_report(
                        selected_client, report_type, date_from, date_to, period_label
                    )
                    st.session_state.report_text = report_text
                    st.session_state.report_filename = filename
                    st.session_state.report_client = selected_name
                    st.session_state.report_ads_data = ads_data
                    st.session_state.report_ga4_data = ga4_data
                    st.session_state.report_period = period_label
                    st.success(f"Raport wygenerowany i zapisany jako `{filename}`")
                except Exception as e:
                    st.error(f"Błąd generowania raportu: {e}")

    # Wyświetl raport jeśli istnieje
    if st.session_state.report_text:
        st.markdown("---")

        dl_col, dl_html_col, email_col = st.columns([1, 1, 1])
        with dl_col:
            st.download_button(
                label="⬇ Pobierz (.md)",
                data=st.session_state.report_text.encode("utf-8"),
                file_name=st.session_state.report_filename,
                mime="text/markdown",
                use_container_width=True,
            )
        with dl_html_col:
            html_content = _report_to_html(
                st.session_state.report_client,
                st.session_state.report_period,
                st.session_state.report_text,
            )
            st.download_button(
                label="⬇ Pobierz (.html)",
                data=html_content.encode("utf-8"),
                file_name=st.session_state.report_filename.replace(".md", ".html"),
                mime="text/html",
                use_container_width=True,
            )
        with email_col:
            recipients = cfg["email"].get("recipients", [])
            smtp_configured = bool(cfg["email"].get("smtp_user") and cfg["email"].get("smtp_password"))
            if recipients and smtp_configured:
                if st.button("✉ Wyślij emailem", use_container_width=True):
                    with st.spinner(f"Wysyłanie do {len(recipients)} odbiorcy/ów..."):
                        try:
                            from email_sender import send_report_email
                            for r in recipients:
                                send_report_email(
                                    recipient=r,
                                    subject=f"Raport marketingowy — {st.session_state.report_client} — {st.session_state.report_period}",
                                    body=st.session_state.report_text,
                                    smtp_config=cfg["email"],
                                    filename=st.session_state.report_filename,
                                )
                            st.success(f"Wysłano na: {', '.join(recipients)}")
                        except Exception as e:
                            st.error(f"Błąd wysyłania: {e}")
            else:
                st.button("✉ Wyślij emailem", disabled=True, use_container_width=True,
                          help="Brak odbiorców lub brak konfiguracji SMTP — przejdź do Ustawień.")

        st.markdown("---")
        render_visual_report(
            st.session_state.report_client,
            st.session_state.report_period,
            st.session_state.get("report_ads_data", {}),
            st.session_state.get("report_ga4_data", {}),
            st.session_state.report_text,
        )


# ─── Strona: Klienci ──────────────────────────────────────────────────────────

def page_clients():
    st.markdown('<p class="main-title">Klienci</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Zarządzaj kontami klientów — Google Ads i Google Analytics 4.</p>', unsafe_allow_html=True)

    clients = cfg.get("clients", [])

    if "saved_client" not in st.session_state:
        st.session_state.saved_client = None

    if clients:
        st.subheader("Zapisane konta")
        for i, client in enumerate(clients):
            with st.expander(f"**{client['name']}**"):
                with st.form(key=f"edit_form_{i}"):
                    name_edit = st.text_input("Nazwa klienta", value=client.get("name", ""), key=f"name_e_{i}")
                    col1, col2 = st.columns(2)
                    with col1:
                        ads_edit = st.text_input(
                            "Google Ads Customer ID",
                            value=client.get("ads_customer_id", ""),
                            key=f"ads_e_{i}",
                            help="ID konta bez myślników.",
                        )
                    with col2:
                        ga4_edit = st.text_input(
                            "GA4 Property ID",
                            value=client.get("ga4_property_id", ""),
                            key=f"ga4_e_{i}",
                        )
                    save_col, del_col = st.columns([2, 1])
                    with save_col:
                        saved = st.form_submit_button("Zapisz zmiany", type="primary", use_container_width=True)
                    with del_col:
                        deleted = st.form_submit_button("Usuń klienta", use_container_width=True)

                if saved:
                    cfg["clients"][i].update({
                        "name": name_edit.strip(),
                        "ads_customer_id": ads_edit.strip(),
                        "ga4_property_id": ga4_edit.strip(),
                    })
                    save_config(cfg)
                    st.session_state.saved_client = name_edit.strip()
                    st.rerun()

                if deleted:
                    cfg["clients"].pop(i)
                    save_config(cfg)
                    st.rerun()

                if st.session_state.saved_client == client.get("name"):
                    st.success(f"Zmiany dla **{client['name']}** zostały zapisane.")
                    st.session_state.saved_client = None
    else:
        st.info("Brak klientów. Dodaj pierwsze konto poniżej.")

    st.markdown("---")
    st.subheader("Dodaj nowego klienta")

    with st.form("add_client_form", clear_on_submit=True):
        name = st.text_input(
            "Nazwa klienta *",
            placeholder="np. Firma XYZ",
        )
        col1, col2 = st.columns(2)
        with col1:
            ads_id = st.text_input(
                "Google Ads Customer ID",
                placeholder="np. 1234567890",
                help="ID konta bez myślników. Znajdziesz je w prawym górnym rogu panelu Google Ads.",
            )
        with col2:
            ga4_id = st.text_input(
                "GA4 Property ID",
                placeholder="np. 987654321",
                help="ID property w Google Analytics 4. Znajdziesz je w: Ustawienia → Informacje o usłudze.",
            )

        if st.form_submit_button("Dodaj klienta", type="primary"):
            if not name.strip():
                st.error("Nazwa klienta jest wymagana.")
            elif any(c["name"].lower() == name.strip().lower() for c in cfg["clients"]):
                st.error("Klient o tej nazwie już istnieje.")
            else:
                cfg["clients"].append({
                    "id": str(uuid.uuid4()),
                    "name": name.strip(),
                    "ads_customer_id": ads_id.strip(),
                    "ga4_property_id": ga4_id.strip(),
                })
                save_config(cfg)
                st.success(f"Dodano klienta: **{name.strip()}**")
                st.rerun()


# ─── Helper: aktualizacja .env ───────────────────────────────────────────────

def update_env_key(key: str, value: str) -> None:
    """Ustawia lub aktualizuje klucz w pliku .env."""
    env_path = BASE_DIR / ".env"
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    found = False
    new_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.environ[key] = value


# ─── Strona: Ustawienia ───────────────────────────────────────────────────────

def page_settings():
    st.markdown('<p class="main-title">Ustawienia</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Konfiguracja połączeń z API i wysyłki email.</p>', unsafe_allow_html=True)

    # ── OpenAI API Key ────────────────────────────────────────────────────────
    st.subheader("OpenAI — klucz API")
    st.caption(
        "Klucz API jest wymagany do generowania treści raportów. "
        "Pobierz go na platform.openai.com → API keys."
    )

    current_openai = os.environ.get("OPENAI_API_KEY", "")
    with st.form("openai_key_form"):
        openai_input = st.text_input(
            "Klucz API OpenAI",
            value=current_openai,
            type="password",
            placeholder="sk-proj-...",
        )
        if st.form_submit_button("Zapisz klucz OpenAI", type="primary"):
            val = openai_input.strip()
            if val.startswith("sk-"):
                update_env_key("OPENAI_API_KEY", val)
                auth.save_user_data(_uid, {"openai_key": val})
                st.success("Klucz OpenAI zapisany.")
                st.rerun()
            elif val == "":
                st.error("Wpisz klucz API.")
            else:
                st.error("Klucz powinien zaczynać się od 'sk-'.")

    # ── Google Ads ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Google Ads — konfiguracja")
    st.caption("Wgraj gotowy plik google-ads.yaml lub wypełnij dane ręcznie.")

    if GADS_YAML_PATH.exists():
        st.success("Plik google-ads.yaml jest wgrany.")
        if st.button("Usuń konfigurację Google Ads"):
            GADS_YAML_PATH.unlink()
            st.success("Plik usunięty.")
            st.rerun()
    else:
        st.info("Brak pliku google-ads.yaml.")

    uploaded_yaml = st.file_uploader(
        "Wgraj plik google-ads.yaml",
        type=["yaml", "yml"],
        help="Plik pobierasz z panelu Google Ads lub generujesz przez google-ads-python.",
    )
    if uploaded_yaml is not None:
        GADS_YAML_PATH.write_bytes(uploaded_yaml.read())
        st.success("Plik google-ads.yaml zapisany.")
        st.rerun()

    with st.expander("Lub wpisz dane konfiguracyjne ręcznie"):
        st.caption(
            "Developer token znajdziesz w Google Ads → Narzędzia → Centrum API. "
            "Client ID / Secret / Refresh token — z Google Cloud Console (OAuth 2.0). "
            "Login Customer ID — to Twój MCC (ID bez myślników)."
        )
        with st.form("gads_manual_form"):
            dev_token = st.text_input("Developer Token", placeholder="AbCdEfGhIjKlMnOpQrSt")
            c1, c2 = st.columns(2)
            with c1:
                client_id = st.text_input("Client ID", placeholder="123456789-abc...apps.googleusercontent.com")
                refresh_token = st.text_input("Refresh Token", type="password", placeholder="1//0g...")
            with c2:
                client_secret = st.text_input("Client Secret", type="password", placeholder="GOCSPX-...")
                login_cid = st.text_input("Login Customer ID (MCC)", placeholder="8612470472")

            if st.form_submit_button("Zapisz konfigurację Google Ads", type="primary"):
                if all([dev_token.strip(), client_id.strip(), client_secret.strip(),
                        refresh_token.strip(), login_cid.strip()]):
                    yaml_content = (
                        f"developer_token: {dev_token.strip()}\n"
                        f"use_proto_plus: True\n"
                        f"client_id: {client_id.strip()}\n"
                        f"client_secret: {client_secret.strip()}\n"
                        f"refresh_token: {refresh_token.strip()}\n"
                        f"login_customer_id: {login_cid.strip().replace('-', '')}\n"
                    )
                    GADS_YAML_PATH.write_text(yaml_content, encoding="utf-8")
                    auth.save_user_data(_uid, {"gads_yaml": yaml_content})
                    st.success("Konfiguracja Google Ads zapisana.")
                    st.rerun()
                else:
                    st.error("Wypełnij wszystkie pola.")

    st.markdown("---")
    # ── GA4 Service Account ───────────────────────────────────────────────────
    st.subheader("Google Analytics 4 — credentials")

    if GA4_CREDS_PATH.exists():
        st.success(f"Plik credentials wgrany.")
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("Usuń credentials GA4"):
                GA4_CREDS_PATH.unlink()
                os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
                st.success("Credentials usunięte.")
                st.rerun()
    else:
        st.info("Brak pliku credentials GA4. Wgraj plik JSON z Google Cloud Console.")

    uploaded = st.file_uploader(
        "Wgraj plik Service Account JSON (Google Analytics 4)",
        type="json",
        help=(
            "Jak uzyskać plik: Google Cloud Console → IAM → Konta usługi → "
            "utwórz klucz JSON. Następnie dodaj email konta usługi jako Czytelnik w GA4."
        ),
    )
    if uploaded is not None:
        content = uploaded.read()
        GA4_CREDS_PATH.write_bytes(content)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GA4_CREDS_PATH)
        auth.save_user_data(_uid, {"ga4_json": content.decode("utf-8")})
        st.success("Credentials GA4 zapisane. Status GA4 zmienił się na aktywny.")
        st.rerun()

    # ── Logo ──────────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Logo")
    st.caption("Logo będzie wyświetlane na górze każdego raportu.")

    import base64

    logo_b64 = cfg.get("logo_b64", "")
    logo_mime = cfg.get("logo_mime", "image/png")

    if logo_b64:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(
                f'<img src="data:{logo_mime};base64,{logo_b64}" style="max-width:160px">',
                unsafe_allow_html=True,
            )
        with col2:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            if st.button("Usuń logo"):
                cfg["logo_b64"] = ""
                cfg["logo_mime"] = ""
                save_config(cfg)
                st.rerun()
    else:
        st.info("Brak logo. Wgraj plik PNG lub JPG.")

    uploaded_logo = st.file_uploader("Wgraj logo (PNG lub JPG)", type=["png", "jpg", "jpeg"])
    if uploaded_logo:
        mime = "image/png" if uploaded_logo.name.endswith(".png") else "image/jpeg"
        b64 = base64.b64encode(uploaded_logo.read()).decode("utf-8")
        cfg["logo_b64"] = b64
        cfg["logo_mime"] = mime
        save_config(cfg)
        st.success("Logo zapisane.")
        st.rerun()

    # ── Odbiorcy emaili ───────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Odbiorcy raportów")
    st.caption("Raporty będą wysyłane na wszystkie poniższe adresy.")

    recipients = cfg["email"].get("recipients", [])

    if recipients:
        for i, r in enumerate(recipients):
            col1, col2 = st.columns([5, 1])
            with col1:
                st.text_input("Email", value=r, key=f"rec_{i}", disabled=True, label_visibility="collapsed")
            with col2:
                if st.button("Usuń", key=f"del_rec_{i}"):
                    cfg["email"]["recipients"].pop(i)
                    save_config(cfg)
                    st.rerun()
    else:
        st.info("Brak skonfigurowanych odbiorców.")

    with st.form("add_recipient_form", clear_on_submit=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            new_email = st.text_input("Dodaj adres email", placeholder="klient@example.com", label_visibility="collapsed")
        with col2:
            if st.form_submit_button("Dodaj"):
                if "@" in new_email and "." in new_email:
                    if new_email.strip() not in cfg["email"]["recipients"]:
                        cfg["email"]["recipients"].append(new_email.strip())
                        save_config(cfg)
                        st.success(f"Dodano: {new_email.strip()}")
                        st.rerun()
                    else:
                        st.warning("Ten adres już jest na liście.")
                else:
                    st.error("Podaj poprawny adres email.")

    # ── Konfiguracja SMTP ─────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Konfiguracja wysyłki email (SMTP)")
    st.caption(
        "Dla kont Gmail: wejdź w Ustawienia konta Google → Bezpieczeństwo → "
        "Hasła do aplikacji i wygeneruj hasło specjalnie dla tej aplikacji."
    )

    with st.form("smtp_form"):
        col1, col2 = st.columns([3, 1])
        with col1:
            smtp_host = st.text_input("Serwer SMTP", value=cfg["email"].get("smtp_host", "smtp.gmail.com"))
        with col2:
            smtp_port = st.number_input("Port", value=int(cfg["email"].get("smtp_port", 587)), step=1, min_value=1, max_value=65535)
        smtp_user = st.text_input(
            "Email nadawcy",
            value=cfg["email"].get("smtp_user", ""),
            placeholder="twoj@gmail.com",
        )
        smtp_pass = st.text_input(
            "Hasło aplikacji",
            value=cfg["email"].get("smtp_password", ""),
            type="password",
            placeholder="xxxx xxxx xxxx xxxx",
        )
        if st.form_submit_button("Zapisz ustawienia SMTP", type="primary"):
            cfg["email"].update({
                "smtp_host": smtp_host.strip(),
                "smtp_port": int(smtp_port),
                "smtp_user": smtp_user.strip(),
                "smtp_password": smtp_pass,
            })
            save_config(cfg)
            st.success("Ustawienia SMTP zapisane.")

    # Test połączenia
    if cfg["email"].get("smtp_user") and cfg["email"].get("smtp_password"):
        if st.button("Testuj połączenie SMTP"):
            with st.spinner("Testowanie..."):
                try:
                    import smtplib
                    with smtplib.SMTP(cfg["email"]["smtp_host"], cfg["email"]["smtp_port"], timeout=10) as s:
                        s.ehlo()
                        s.starttls()
                        s.login(cfg["email"]["smtp_user"], cfg["email"]["smtp_password"])
                    st.success("Połączenie SMTP działa poprawnie.")
                except Exception as e:
                    st.error(f"Błąd połączenia: {e}")

    # ── Status API ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Status konfiguracji API")

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    gads_yaml  = GADS_YAML_PATH.exists()
    ga4_creds  = str(GA4_CREDS_PATH) if GA4_CREDS_PATH.exists() else ""

    col1, col2, col3 = st.columns(3)
    with col1:
        if openai_key:
            st.success("OpenAI API Key")
            st.caption("Klucz ustawiony — generowanie raportów działa.")
        else:
            st.error("OpenAI API Key — brak")
            st.caption("Uzupełnij klucz w sekcji OpenAI powyżej.")
    with col2:
        if gads_yaml:
            st.success("google-ads.yaml")
            st.caption("Plik konfiguracyjny Google Ads znaleziony.")
        else:
            st.error("google-ads.yaml — brak")
            st.caption("Wgraj plik lub wypełnij formularz w sekcji Google Ads powyżej.")
    with col3:
        if ga4_creds:
            st.success("GA4 Service Account")
            st.caption(f"Credentials: `{Path(ga4_creds).name}`")
        else:
            st.warning("GA4 Service Account — brak")
            st.caption("Wgraj plik JSON w sekcji Google Analytics 4 powyżej.")

    # ── Usuń konto (RODO) ─────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Dane osobowe i usunięcie konta")
    st.caption(
        "Zgodnie z RODO (art. 17) masz prawo do trwałego usunięcia swojego konta "
        "i wszystkich powiązanych danych. Operacja jest nieodwracalna."
    )
    st.markdown("""
**Jakie dane przechowujemy na Twoim koncie:**
- Adres email (do logowania)
- Klucz API OpenAI *(szyfrowany)*
- Konfiguracja Google Ads *(szyfrowana)*
- Credentials Google Analytics 4 *(szyfrowane)*
- Lista klientów, ustawienia email i logo *(szyfrowane)*

Dane przechowywane są w bazie Supabase (region EU) i szyfrowane algorytmem AES-128-CBC.
    """)
    with st.expander("Usuń konto trwale"):
        st.warning("Ta operacja jest nieodwracalna. Wszystkie dane zostaną usunięte.")
        with st.form("delete_account_form"):
            confirm_email = st.text_input(
                "Potwierdź swój adres email aby usunąć konto",
                placeholder=st.session_state.get("user_email", ""),
            )
            if st.form_submit_button("Usuń konto i wszystkie dane", type="primary"):
                if confirm_email.strip().lower() == (st.session_state.get("user_email") or "").lower():
                    ok, msg = auth.delete_account(_uid)
                    if ok:
                        for key in list(st.session_state.keys()):
                            del st.session_state[key]
                        st.success("Konto zostało usunięte.")
                        st.rerun()
                    else:
                        st.error(f"Błąd: {msg}")
                else:
                    st.error("Adres email nie zgadza się.")


# ─── Strona: Pomoc / FAQ ──────────────────────────────────────────────────────

def page_faq():
    st.markdown('<p class="main-title">Pomoc / FAQ</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="page-subtitle">Instrukcje krok po kroku — jak znaleźć każdy klucz i skonfigurować aplikację.</p>',
        unsafe_allow_html=True,
    )

    # ── OpenAI API Key ────────────────────────────────────────────────────────
    with st.expander("Klucz API OpenAI — jak go zdobyć?", expanded=False):
        st.markdown("""
**Do czego służy:** OpenAI generuje treść raportu (analizę, wnioski, rekomendacje).

**Krok po kroku:**

1. Wejdź na stronę **platform.openai.com** i zaloguj się (lub załóż konto).
2. W lewym menu kliknij **API keys**.
3. Kliknij przycisk **Create new secret key** — nadaj mu dowolną nazwę np. *Raporty Marketingowe*.
4. Skopiuj wygenerowany klucz — zaczyna się od `sk-proj-...`
   > Uwaga: klucz jest widoczny tylko raz. Jeśli go zamkniesz bez skopiowania, musisz wygenerować nowy.
5. Wklej klucz w **Ustawienia → OpenAI API Key** i kliknij *Zapisz*.

**Koszt:** Generowanie jednego raportu miesięcznego to ok. 0,01–0,05 USD (model gpt-4o-mini jest bardzo tani).
        """)

    # ── Google Ads ────────────────────────────────────────────────────────────
    with st.expander("Google Ads — credentials (Developer Token, Client ID, Refresh Token...)", expanded=False):
        st.markdown("""
**Do czego służy:** Aplikacja łączy się z Twoim kontem Google Ads, żeby pobrać dane o kampaniach.

Potrzebujesz 5 wartości. Poniżej wyjaśnienie gdzie każdą znaleźć.

---

**1. Login Customer ID (MCC)**

To numer Twojego konta menedżerskiego (MCC) w Google Ads.

- Zaloguj się na **ads.google.com**
- W prawym górnym rogu zobaczysz numer w formacie `XXX-XXX-XXXX`
- Przepisz go bez myślników, np. `8612470472`

---

**2. Developer Token**

- W panelu Google Ads kliknij ikonę klucza (Narzędzia i ustawienia) → **Centrum API**
- Skopiuj wartość pola *Developer token*
- Jeśli jeszcze nie masz tokenu — złóż wniosek (standardowy token wystarczy do pobierania danych)

---

**3. Client ID i Client Secret**

To dane aplikacji OAuth w Google Cloud Console.

1. Wejdź na **console.cloud.google.com**
2. Wybierz projekt (lub utwórz nowy)
3. Menu boczne → **APIs & Services → Credentials**
4. Kliknij **Create Credentials → OAuth 2.0 Client IDs**
5. Typ aplikacji: *Desktop app* — nadaj nazwę i zapisz
6. Skopiuj **Client ID** (kończy się na `.apps.googleusercontent.com`) i **Client Secret**

> Upewnij się, że w projekcie włączyłeś Google Ads API: APIs & Services → Library → wyszukaj *Google Ads API* → Enable.

---

**4. Refresh Token**

Refresh token uzyskujesz przez jednorazową autoryzację OAuth.

W folderze projektu znajduje się skrypt `get_token.py`:
```
python get_token.py
```
Skrypt otworzy przeglądarkę, poprosisz o zgodę na dostęp do konta Google Ads, a następnie wypisze `refresh_token` w terminalu.

> Potrzebujesz do tego uzupełnionych pól Client ID i Client Secret powyżej.

---

Po zebraniu wszystkich 5 wartości wklej je w **Ustawienia → Google Ads → formularz ręczny**.
        """)

    # ── GA4 Service Account ───────────────────────────────────────────────────
    with st.expander("Google Analytics 4 — credentials (plik JSON)", expanded=False):
        st.markdown("""
**Do czego służy:** Aplikacja pobiera dane o ruchu na stronie (użytkownicy, sesje, źródła, konwersje).

Wymaga pliku JSON z kluczem konta usługi (Service Account) w Google Cloud Console.

---

**Krok 1 — Utwórz konto usługi (Service Account)**

1. Wejdź na **console.cloud.google.com**
2. Menu boczne → **IAM i administracja → Konta usługi**
3. Kliknij **Utwórz konto usługi**
4. Nadaj nazwę np. *raporty-ga4* i kliknij *Utwórz i kontynuuj*
5. Rolę możesz pominąć — kliknij *Gotowe*

---

**Krok 2 — Pobierz klucz JSON**

1. Kliknij na utworzone konto usługi
2. Zakładka **Klucze → Dodaj klucz → Utwórz nowy klucz**
3. Wybierz format **JSON** → kliknij *Utwórz*
4. Plik JSON zostanie pobrany na Twój komputer

---

**Krok 3 — Dodaj konto usługi do GA4**

To ważny krok — bez niego aplikacja nie będzie mieć dostępu do danych.

1. Wejdź do **Google Analytics (analytics.google.com)**
2. Kliknij **Ustawienia (ikona koła zębatego)** → sekcja *Usługa* → **Zarządzanie dostępem do usługi**
3. Kliknij **+** (Dodaj użytkownika)
4. Wklej adres email konta usługi — wygląda tak: `nazwa@nazwa-projektu.iam.gserviceaccount.com`
   *(znajdziesz go w pliku JSON pod kluczem `client_email`)*
5. Rola: **Czytelnik** — kliknij *Dodaj*

---

**Krok 4 — Wgraj plik do aplikacji**

Przejdź do **Ustawienia → Google Analytics 4** i wgraj pobrany plik JSON.

---

**Gdzie znaleźć GA4 Property ID?**

- W Google Analytics: **Ustawienia → Informacje o usłudze → Identyfikator usługi**
- To liczba, np. `123456789`
- Wpisz ją w zakładce **Klienci** przy danym kliencie
        """)

    # ── SMTP Email ───────────────────────────────────────────────────────────
    with st.expander("Wysyłka email (SMTP) — konfiguracja dla Gmail", expanded=False):
        st.markdown("""
**Do czego służy:** Po wygenerowaniu raportu możesz wysłać go emailem do klienta.

Najłatwiej skonfigurować przez konto Gmail z *hasłem do aplikacji*.

---

**Krok 1 — Włącz weryfikację dwuetapową**

Hasła do aplikacji działają tylko gdy masz aktywną weryfikację dwuetapową.

1. Wejdź na **myaccount.google.com → Bezpieczeństwo**
2. Znajdź sekcję *Jak logujesz się w Google*
3. Kliknij **Weryfikacja dwuetapowa** i włącz ją (jeśli jeszcze nie jest)

---

**Krok 2 — Wygeneruj hasło do aplikacji**

1. Na tej samej stronie Bezpieczeństwo wpisz w wyszukiwarce **"hasła do aplikacji"** lub przejdź do:
   `myaccount.google.com/apppasswords`
2. Kliknij **Wybierz aplikację → Inna (niestandardowa nazwa)**
3. Wpisz np. *Raporty Marketingowe* → kliknij *Generuj*
4. Zobaczysz hasło w formacie: `xxxx xxxx xxxx xxxx` (16 znaków)
5. Skopiuj je — jest widoczne tylko raz

---

**Krok 3 — Wpisz dane w Ustawieniach**

Przejdź do **Ustawienia → Konfiguracja wysyłki email (SMTP)** i uzupełnij:

| Pole | Wartość |
|---|---|
| Serwer SMTP | `smtp.gmail.com` |
| Port | `587` |
| Email nadawcy | Twój adres Gmail, np. `twoj@gmail.com` |
| Hasło aplikacji | Wklej skopiowane hasło (16 znaków) |

Kliknij **Zapisz**, a następnie **Testuj połączenie SMTP** aby sprawdzić czy działa.

---

**Krok 4 — Dodaj odbiorców**

W sekcji **Odbiorcy raportów** wpisz adresy email, na które mają trafiać raporty.
Możesz dodać kilka adresów — raport zostanie wysłany do każdego z nich.
        """)

    # ── Najczęstsze problemy ──────────────────────────────────────────────────
    with st.expander("Najczęstsze problemy i rozwiązania", expanded=False):
        st.markdown("""
| Problem | Przyczyna | Rozwiązanie |
|---|---|---|
| *Brak klucza OpenAI* | Klucz nie jest wpisany | Ustawienia → OpenAI API Key |
| *Google Ads: brak danych* | Podałeś ID konta klienta zamiast MCC | Upewnij się, że Login Customer ID to numer MCC (konto menedżerskie) |
| *GA4: błąd 403 (brak dostępu)* | Service account nie ma uprawnień do GA4 | Dodaj email konta usługi jako Czytelnik w GA4 (krok 3 instrukcji powyżej) |
| *GA4: brak danych* | Zły Property ID | Sprawdź ID w GA4: Ustawienia → Informacje o usłudze |
| *Email: błąd logowania* | Zwykłe hasło Gmail zamiast hasła do aplikacji | Wygeneruj *hasło do aplikacji* (16 znaków) — patrz instrukcja SMTP |
| *Raport się nie generuje* | Brak klucza OpenAI lub brak połączenia | Sprawdź Status API w Ustawieniach |
| *"Your app is in the oven"* | Streamlit Cloud przebudowuje aplikację | Odczekaj 1–2 minuty i odśwież stronę |
        """)


# ─── Router ───────────────────────────────────────────────────────────────────

if st.session_state.show_faq:
    # powrót do głównej nawigacji po kliknięciu w radio
    if "last_page" not in st.session_state or st.session_state.last_page != page:
        st.session_state.show_faq = False
        st.session_state.last_page = page
    else:
        page_faq()
        st.stop()

st.session_state.last_page = page

if page == "Generuj raport":
    page_generate()
elif page == "Klienci":
    page_clients()
elif page == "Ustawienia":
    page_settings()
