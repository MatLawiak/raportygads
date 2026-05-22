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
from report_html import report_to_html as _report_to_html

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

        # Klucze infrastruktury (NIE openai_key — każdy user dodaje własny)
        for key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "ENCRYPTION_KEY"):
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
        .block-container { padding-top: 0 !important; max-width: 980px; }
        .feature-card {
            background:#fff;
            border-radius:14px;
            padding:24px 22px;
            height:200px;
            box-shadow:0 2px 12px rgba(0,0,0,0.06);
            border-top:3px solid var(--card-accent, #E8630A);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        .feature-card:hover {
            transform: translateY(-3px);
            box-shadow:0 8px 20px rgba(0,0,0,0.10);
        }
        .feature-icon {
            font-size:1.8rem;
            line-height:1;
            margin-bottom:10px;
        }
        .source-badge {
            display:inline-block;
            background:rgba(255,255,255,0.18);
            color:white;
            padding:5px 12px;
            border-radius:20px;
            font-size:0.8rem;
            margin:0 4px;
            font-weight:600;
        }
        .step-row {
            display:flex;
            align-items:center;
            gap:14px;
            margin:14px 0;
        }
        .step-num {
            min-width:34px;
            height:34px;
            border-radius:50%;
            background:#1A3A5C;
            color:white;
            display:flex;
            align-items:center;
            justify-content:center;
            font-weight:700;
            font-size:0.95rem;
        }
    </style>""", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{ACCENT2_L} 0%,{ACCENT_L} 100%);
                padding:60px 40px 52px;border-radius:0 0 24px 24px;text-align:center;margin-bottom:36px">
        <p style="color:rgba(255,255,255,0.8);font-size:0.85rem;margin:0 0 14px;letter-spacing:.15em;text-transform:uppercase;font-weight:600">
            Generator Raportów Marketingowych
        </p>
        <h1 style="color:white;margin:0;font-size:2.6rem;font-weight:800;line-height:1.15">
            Raporty z 3 platform<br>gotowe w 30 sekund
        </h1>
        <div style="margin:22px 0 14px">
            <span class="source-badge">Google Ads</span>
            <span class="source-badge">Meta Ads</span>
            <span class="source-badge">Google Analytics 4</span>
        </div>
        <p style="color:rgba(255,255,255,0.85);margin:18px auto 0;font-size:1.05rem;max-width:580px;line-height:1.5">
            Podłącz konta reklamowe i analitykę — aplikacja pobierze dane, porówna kanały
            i wygeneruje profesjonalny raport z analizą wykonaną przez AI.
        </p>
    </div>""", unsafe_allow_html=True)

    # Features — 3 źródła danych
    c1, c2, c3 = st.columns(3)
    for col, icon, title, desc, accent in [
        (c1, "📈", "Google Ads",
         "Kampanie, kliknięcia, CTR, średni CPC, wydatki — pełne dane z Search, Performance Max i Display.",
         "#4285F4"),
        (c2, "📱", "Meta Ads",
         "Wyniki kampanii Facebook i Instagram. Liczba leadów z formularzy błyskawicznych i koszt pozyskania (CPL).",
         "#0866FF"),
        (c3, "🔍", "Google Analytics 4",
         "Ruch na stronie, źródła wizyt, czas wizyty, zaangażowanie i konwersje GA4.",
         "#F9AB00"),
    ]:
        col.markdown(f"""
        <div class="feature-card" style="--card-accent:{accent}">
            <div class="feature-icon">{icon}</div>
            <p style="font-weight:700;color:{ACCENT2_L};margin:6px 0 8px;font-size:1.1rem">{title}</p>
            <p style="color:#555;font-size:0.88rem;margin:0;line-height:1.5">{desc}</p>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # AI + sposób działania
    cc1, cc2 = st.columns([1, 1])
    with cc1:
        st.markdown(f"""
        <div style="background:linear-gradient(135deg,#FFF8F3 0%,#FFE8D6 100%);
                    border-radius:14px;padding:28px 24px;height:240px;
                    border-left:4px solid {ACCENT_L}">
            <div style="font-size:1.6rem;margin-bottom:6px">🤖</div>
            <p style="font-weight:700;color:{ACCENT2_L};font-size:1.15rem;margin:8px 0 10px">
                Analiza wykonana przez AI
            </p>
            <p style="color:#444;font-size:0.92rem;margin:0;line-height:1.55">
                AI porównuje skuteczność Google Ads i Meta Ads, łączy je z danymi GA4,
                wyciąga wnioski i rekomenduje działania — w języku zrozumiałym dla właściciela firmy.
            </p>
        </div>""", unsafe_allow_html=True)

    with cc2:
        st.markdown(f"""
        <div style="background:#fff;border-radius:14px;padding:24px 24px;height:240px;
                    box-shadow:0 2px 12px rgba(0,0,0,0.06)">
            <p style="font-weight:700;color:{ACCENT2_L};font-size:1.05rem;margin:0 0 10px">
                Jak to działa
            </p>
            <div class="step-row">
                <div class="step-num">1</div>
                <div style="color:#444;font-size:0.9rem">Podłącz konta API (Google Ads, Meta, GA4)</div>
            </div>
            <div class="step-row">
                <div class="step-num">2</div>
                <div style="color:#444;font-size:0.9rem">Wybierz klienta i okres raportu</div>
            </div>
            <div class="step-row">
                <div class="step-num">3</div>
                <div style="color:#444;font-size:0.9rem">Pobierz raport (.md/.html) lub wyślij emailem</div>
            </div>
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

    if _ud.get("meta_token"):
        os.environ["META_ACCESS_TOKEN"] = _ud["meta_token"]

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

    meta_ok = bool(os.environ.get("META_ACCESS_TOKEN"))

    st.caption("Status API")
    st.write("🟢 OpenAI" if openai_ok else "🔴 OpenAI — brak klucza")
    st.write("🟢 Google Ads" if gads_ok else "🔴 Google Ads — brak pliku")
    st.write("🟢 GA4" if ga4_ok else "🟡 GA4 — brak credentials")
    st.write("🟢 Meta Ads" if meta_ok else "🟡 Meta Ads — brak tokenu")

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


# build_weekly_prompt przeniesiono do main.py (współdzielone z weekly_sender.py)


def _ensure_gads_yaml() -> bool:
    """
    Gwarantuje, że per-user plik google-ads.yaml istnieje na dysku
    i że env var wskazuje na niego. Jeśli plik nie istnieje, odzyskuje
    go z Supabase. Zwraca True jeśli gotowy do użycia.
    """
    if GADS_YAML_PATH.exists():
        os.environ["GOOGLE_ADS_CONFIGURATION_FILE_PATH"] = str(GADS_YAML_PATH)
        return True
    uid = st.session_state.get("user_id")
    if not uid:
        return False
    try:
        ud = auth.load_user_data(uid)
        if ud.get("gads_yaml"):
            GADS_YAML_PATH.write_text(ud["gads_yaml"], encoding="utf-8")
            os.environ["GOOGLE_ADS_CONFIGURATION_FILE_PATH"] = str(GADS_YAML_PATH)
            return True
    except Exception:
        pass
    return False


def _ensure_ga4_creds() -> bool:
    """To samo dla pliku Service Account GA4."""
    if GA4_CREDS_PATH.exists():
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GA4_CREDS_PATH)
        return True
    uid = st.session_state.get("user_id")
    if not uid:
        return False
    try:
        ud = auth.load_user_data(uid)
        if ud.get("ga4_json"):
            GA4_CREDS_PATH.write_text(ud["ga4_json"], encoding="utf-8")
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(GA4_CREDS_PATH)
            return True
    except Exception:
        pass
    return False


def generate_full_report(
    client: dict,
    report_type: str,
    date_from: str,
    date_to: str,
    period_label: str,
) -> tuple[str, str, dict, dict, dict | None]:
    from main import (
        fetch_google_ads_data,
        fetch_ga4_data,
        build_report_prompt,
        build_weekly_prompt,
        generate_report,
    )

    ads_data: dict = {}
    ga4_data: dict = {}

    if client.get("ads_customer_id"):
        if not _ensure_gads_yaml():
            st.warning(
                "Google Ads: brak pliku google-ads.yaml. "
                "Wgraj go w **Ustawienia → Google Ads**."
            )
        else:
            try:
                ads_data = fetch_google_ads_data(client["ads_customer_id"], date_from, date_to)
            except Exception as e:
                st.warning(f"Google Ads: nie udało się pobrać danych — {e}")

    if client.get("ga4_property_id"):
        if not _ensure_ga4_creds():
            st.warning(
                "GA4: brak pliku credentials. "
                "Wgraj go w **Ustawienia → Google Analytics 4**."
            )
        else:
            try:
                ga4_data = fetch_ga4_data(client["ga4_property_id"], date_from, date_to)
            except Exception as e:
                st.warning(f"GA4: nie udało się pobrać danych — {e}")

    business_profile = client.get("business_profile", "")

    meta_data: dict | None = None
    meta_token = os.environ.get("META_ACCESS_TOKEN")
    meta_account_id = client.get("meta_ad_account_id", "").strip()
    if meta_token and meta_account_id:
        try:
            from meta_ads import fetch_meta_campaign_data
            meta_campaign_ids = client.get("meta_campaign_ids") or None
            meta_data = fetch_meta_campaign_data(
                meta_account_id, date_from, date_to, meta_token,
                campaign_ids=meta_campaign_ids,
            )
        except Exception as e:
            st.warning(f"Meta Ads: nie udało się pobrać danych — {e}")

    if report_type == "Tygodniowy":
        prompt = build_weekly_prompt(client["name"], period_label, ads_data, ga4_data, business_profile)
    else:
        prompt = build_report_prompt(client["name"], period_label, ads_data, ga4_data, business_profile, meta_data=meta_data)

    report_text = generate_report(prompt)

    safe_name = client["name"].replace(" ", "_").lower()
    suffix = "_tyg" if report_type == "Tygodniowy" else ""
    filename = f"raport_{safe_name}_{date_from[:7]}{suffix}.md"
    path = REPORTS_DIR / filename
    path.write_text(report_text, encoding="utf-8")

    return report_text, filename, ads_data, ga4_data, meta_data


# ─── Helpers wizualne ────────────────────────────────────────────────────────

ACCENT = "#E8630A"        # pomarańczowy jak w PDF Białej Damy
ACCENT2 = "#1A3A5C"       # granatowy
LIGHT_BG = "#FFF8F3"
GRAY = "#F5F5F5"


def _header_html(logo_b64: str, logo_mime: str, client_name: str, period: str, date_range: str = "") -> str:
    logo_html = ""
    if logo_b64:
        logo_html = f'<img src="data:{logo_mime};base64,{logo_b64}" style="max-height:70px;margin-bottom:8px">'
    dr = f" &nbsp;|&nbsp; {date_range}" if date_range else ""
    return (
        f'<div style="background:linear-gradient(135deg,{ACCENT2} 0%,{ACCENT} 100%);'
        f'padding:36px 32px;border-radius:12px;text-align:center;margin-bottom:24px">'
        f'{logo_html}'
        f'<h1 style="color:white;margin:0;font-size:2rem;font-weight:700">{client_name}</h1>'
        f'<p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:1.1rem">'
        f'Raport miesięczny &nbsp;|&nbsp; {period}{dr}'
        f'</p></div>'
    )


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

def render_visual_report(
    client_name: str,
    period_label: str,
    ads_data: dict,
    ga4_data: dict,
    report_text: str,
    logo_b64: str = "",
    logo_mime: str = "image/png",
    meta_data: dict | None = None,
) -> None:
    import plotly.graph_objects as go
    import plotly.express as px

    if not logo_b64:
        logo_b64 = cfg.get("logo_b64", "")
        logo_mime = cfg.get("logo_mime", "image/png")

    tab_labels = ["Strona tytułowa", "Google Ads", "Google Analytics"]
    if meta_data:
        tab_labels.append("Meta Ads")
    tab_labels += ["Podsumowanie", "Wnioski i rekomendacje"]

    tabs = st.tabs(tab_labels)
    tab1 = tabs[0]
    tab2 = tabs[1]
    tab3 = tabs[2]
    tab_meta = tabs[3] if meta_data else None
    tab4 = tabs[4] if meta_data else tabs[3]
    tab5 = tabs[5] if meta_data else tabs[4]

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
            ga4_conv = sum(int(e.get("conversions", 0)) for e in ga4_data.get("conversion_events", []))
            cols = st.columns(4)
            cols[0].markdown(_kpi_card("Wydatki Google Ads", f"{t['cost_pln']} zł"), unsafe_allow_html=True)
            cols[1].markdown(_kpi_card("Konwersje GA4", f"{ga4_conv}"), unsafe_allow_html=True)
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
            avg_cpc = round(t["cost_pln"] / t["clicks"], 2) if t["clicks"] else 0
            cols = st.columns(4)
            cols[0].markdown(_kpi_card("Wyświetlenia", f"{t['impressions']:,}"), unsafe_allow_html=True)
            cols[1].markdown(_kpi_card("Kliknięcia", f"{t['clicks']:,}"), unsafe_allow_html=True)
            cols[2].markdown(_kpi_card("CTR", f"{t['ctr_pct']}%"), unsafe_allow_html=True)
            cols[3].markdown(_kpi_card("Średni CPC", f"{avg_cpc} zł"), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            campaigns = ads_data.get("campaigns", [])

            # Wykres: koszt vs kliknięcia per kampania
            _section_title("Efektywność kampanii — koszt vs kliknięcia")
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
                        name="Kliknięcia",
                        x=[c["clicks"] for c in campaigns],
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
                    legend=dict(orientation="h", y=1.15),
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=320,
                    xaxis=dict(showgrid=True, gridcolor="#eee"),
                )
                st.plotly_chart(fig, use_container_width=True)

            # Tabela kampanii
            st.markdown("<br>", unsafe_allow_html=True)
            _section_title("Tabela kampanii")
            if campaigns:
                rows = [
                    [c["name"], f"{c['impressions']:,}", f"{c['clicks']:,}",
                     f"{c['ctr_pct']}%", f"{c['avg_cpc_pln']} zł", f"{c['cost_pln']} zł"]
                    for c in campaigns
                ]
                rows.append([
                    "Suma całkowita",
                    f"{t['impressions']:,}", f"{t['clicks']:,}",
                    f"{t['ctr_pct']}%", f"{avg_cpc} zł", f"{t['cost_pln']} zł",
                ])
                _plotly_table(
                    ["Kampania", "Wyświetlenia", "Kliknięcia", "CTR", "Śr. CPC", "Koszt"],
                    rows,
                )
            st.caption("Konwersje są analizowane wyłącznie w GA4 — patrz zakładka Google Analytics.")
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
    # TAB META ADS (opcjonalny)
    # ══════════════════════════════════════════════════════
    if tab_meta is not None and meta_data:
        with tab_meta:
            st.markdown(_header_html(logo_b64, logo_mime, client_name, period_label), unsafe_allow_html=True)

            lt = meta_data.get("lead_totals", {})
            ot = meta_data.get("other_totals", {})
            lead_camps = meta_data.get("lead_campaigns", [])
            other_camps = meta_data.get("other_campaigns", [])

            if lt.get("leads") or lt.get("spend"):
                _section_title("Kampanie Lead Ads — formularze błyskawiczne")
                c1, c2, c3 = st.columns(3)
                c1.markdown(_kpi_card("Leady łącznie", str(lt.get("leads", 0))), unsafe_allow_html=True)
                c2.markdown(_kpi_card("Koszt pozyskania leadu", f"{lt.get('cpl', 0)} zł"), unsafe_allow_html=True)
                c3.markdown(_kpi_card("Wydatki Lead Ads", f"{lt.get('spend', 0)} zł"), unsafe_allow_html=True)

                if lead_camps:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if len(lead_camps) > 1:
                        fig = go.Figure(go.Bar(
                            x=[c["name"] for c in lead_camps],
                            y=[c["leads"] for c in lead_camps],
                            marker_color=ACCENT,
                            text=[f"{c['leads']} leadów<br>CPL: {c['cpl']} zł" for c in lead_camps],
                            textposition="outside",
                        ))
                        fig.update_layout(
                            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                            margin=dict(t=10, b=20, l=10, r=10), height=300,
                            xaxis=dict(tickangle=-20), yaxis=dict(showgrid=False, visible=False),
                        )
                        st.plotly_chart(fig, use_container_width=True)

                    _plotly_table(
                        ["Kampania", "Leady", "Wydatki (zł)", "CPL (zł)"],
                        [[c["name"], c["leads"], c["spend"], c["cpl"]] for c in lead_camps],
                    )

            if other_camps:
                st.markdown("<br>", unsafe_allow_html=True)
                _section_title("Pozostałe kampanie Meta")
                cols = st.columns(3)
                cols[0].markdown(_kpi_card("Wydatki", f"{ot.get('spend', 0)} zł"), unsafe_allow_html=True)
                cols[1].markdown(_kpi_card("Wyświetlenia", f"{ot.get('impressions', 0):,}"), unsafe_allow_html=True)
                cols[2].markdown(_kpi_card("Kliknięcia", f"{ot.get('clicks', 0):,}"), unsafe_allow_html=True)
                st.markdown("<br>", unsafe_allow_html=True)
                _plotly_table(
                    ["Kampania", "Wydatki (zł)", "Wyświetlenia", "Kliknięcia", "CTR%"],
                    [[c["name"], c["spend"], f"{c['impressions']:,}", f"{c['clicks']:,}", c["ctr_pct"]]
                     for c in other_camps],
                )

            if not lead_camps and not other_camps:
                st.info("Brak danych Meta Ads za ten okres.")

    # ══════════════════════════════════════════════════════
    # TAB 4 — PODSUMOWANIE
    # ══════════════════════════════════════════════════════
    with tab4:
        st.markdown(_header_html(logo_b64, logo_mime, client_name, period_label), unsafe_allow_html=True)
        _section_title(f"Podsumowanie działań marketingowych – {period_label}")

        # Wyciągnij sekcje z wygenerowanego tekstu
        import re
        sections = re.split(r"#{1,3}\s+", report_text)
        # Pokaż cały tekst raportu z wyjątkiem sekcji "Wnioski i rekomendacje" / "Plan na kolejny miesiąc"
        clean = re.sub(
            r"#{1,3}\s+\d+\.\s+(Wnioski i rekomendacje|Plan na kolejny miesiąc).*",
            "", report_text, flags=re.DOTALL,
        )
        st.markdown(clean)

        # Gauges podsumowujące
        if ads_data or ga4_data:
            st.markdown("<br>", unsafe_allow_html=True)
            _section_title("Kluczowe wskaźniki miesiąca")
            c1, c2, c3 = st.columns(3)

            ctr_val = ads_data["totals"]["ctr_pct"] if ads_data else 0
            cpc_val = (
                round(ads_data["totals"]["cost_pln"] / ads_data["totals"]["clicks"], 2)
                if ads_data and ads_data["totals"].get("clicks") else 0
            )
            engagement_val = (
                round(100 - ga4_data["general"]["bounce_rate_pct"], 1) if ga4_data else 0
            )
            for col, val, maxv, label in [
                (c1, ctr_val, 20, "CTR (%)"),
                (c2, cpc_val, max(cpc_val * 1.5, 5), "Średni CPC (zł)"),
                (c3, engagement_val, 100, "Zaangażowanie GA4 (%)"),
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
        match = re.search(
            r"#{1,3}\s+\d+\.\s+(?:Wnioski i rekomendacje|Plan na kolejny miesiąc)(.*)",
            report_text, re.DOTALL,
        )
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


# ─── HTML export — przeniesione do report_html.py ────────────────────────────

# Wszystkie funkcje HTML zostały przeniesione do report_html.py — importowane na górze pliku.


# ─── Edytor wniosków i rekomendacji ──────────────────────────────────────────

EDITABLE_SECTIONS = [
    ("Wnioski i rekomendacje", "wnioski"),
    ("Plan na kolejny miesiąc", "plan"),
]


def _parse_section_points(report_text: str, section_title: str) -> list[str]:
    """Wyciąga punkty listy (numerowanej lub bullet) z konkretnej sekcji raportu."""
    import re
    pattern = rf"##\s+\d+\.\s+{re.escape(section_title)}\s*\n(.*?)(?=\n##\s+\d+\.|\n---|\Z)"
    match = re.search(pattern, report_text, re.DOTALL)
    if not match:
        return []

    body = match.group(1).strip()
    points: list[str] = []
    current: list[str] = []
    list_marker = re.compile(r"^\s*(?:\d+\.|\-|\*)\s+")

    for line in body.split("\n"):
        if list_marker.match(line):
            if current:
                points.append("\n".join(current).strip())
            current = [list_marker.sub("", line, count=1)]
        elif current:
            current.append(line.strip())
    if current:
        points.append("\n".join(current).strip())

    return [p for p in points if p.strip()]


def _replace_section_points(report_text: str, section_title: str, points: list[str]) -> str:
    """Wstawia nowe punkty (numerowane) w miejsce starej zawartości sekcji."""
    import re
    if not points:
        new_body = "_Brak wpisów._"
    else:
        new_body = "\n\n".join(f"{i+1}. {p.strip()}" for i, p in enumerate(points))

    pattern = rf"(##\s+\d+\.\s+{re.escape(section_title)}\s*\n)(.*?)(?=\n##\s+\d+\.|\n---|\Z)"
    replacement = lambda m: m.group(1) + "\n" + new_body + "\n"
    return re.sub(pattern, replacement, report_text, flags=re.DOTALL)


def _init_editor_state(report_text: str) -> None:
    """Inicjalizuje listę punktów per sekcja, jeśli jeszcze nie jest w session_state."""
    for title, slug in EDITABLE_SECTIONS:
        state_key = f"edit_points_{slug}"
        if state_key not in st.session_state:
            parsed = _parse_section_points(report_text, title)
            st.session_state[state_key] = [
                {"id": str(uuid.uuid4()), "text": p} for p in parsed
            ]


def _reset_editor_state() -> None:
    for _, slug in EDITABLE_SECTIONS:
        st.session_state.pop(f"edit_points_{slug}", None)


def render_recommendations_editor(report_text: str) -> None:
    st.markdown("---")
    with st.expander("Edytuj wnioski i plan na kolejny miesiąc", expanded=False):
        st.caption(
            "Możesz poprawiać treść każdego punktu, usuwać niepotrzebne lub dodać nowe. "
            "Po kliknięciu **Zastosuj zmiany** raporty (.md, .html) i wizualizacja zostaną zaktualizowane."
        )

        _init_editor_state(report_text)

        for title, slug in EDITABLE_SECTIONS:
            state_key = f"edit_points_{slug}"
            points = st.session_state[state_key]

            st.markdown(f"#### {title}")

            if not points:
                st.info("Brak punktów. Możesz dodać nowy poniżej.")

            for idx, point in enumerate(points):
                cols = st.columns([18, 1])
                with cols[0]:
                    new_value = st.text_area(
                        f"Punkt {idx + 1}",
                        value=point["text"],
                        key=f"{slug}_text_{point['id']}",
                        label_visibility="collapsed",
                        height=80,
                    )
                    point["text"] = new_value
                with cols[1]:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("✕", key=f"{slug}_del_{point['id']}", help="Usuń punkt"):
                        st.session_state[state_key] = [
                            p for p in points if p["id"] != point["id"]
                        ]
                        st.rerun()

            with st.form(f"add_{slug}_form", clear_on_submit=True):
                new_text = st.text_area(
                    "Dodaj nowy punkt",
                    key=f"{slug}_new_text",
                    placeholder="Wpisz treść nowego punktu...",
                    height=80,
                )
                if st.form_submit_button(f"+ Dodaj do '{title}'"):
                    if new_text.strip():
                        st.session_state[state_key].append(
                            {"id": str(uuid.uuid4()), "text": new_text.strip()}
                        )
                        st.rerun()

            st.markdown("---")

        col_apply, col_reset = st.columns([2, 1])
        with col_apply:
            if st.button("Zastosuj zmiany do raportu", type="primary", use_container_width=True):
                new_report = report_text
                for title, slug in EDITABLE_SECTIONS:
                    points = [
                        p["text"].strip()
                        for p in st.session_state[f"edit_points_{slug}"]
                        if p["text"].strip()
                    ]
                    new_report = _replace_section_points(new_report, title, points)
                st.session_state.report_text = new_report
                _reset_editor_state()
                st.success("Zmiany zostały zastosowane. Przewiń wyżej aby pobrać zaktualizowany raport.")
                st.rerun()
        with col_reset:
            if st.button("Przywróć z raportu", use_container_width=True,
                         help="Anuluje niezatwierdzone zmiany i wczyta punkty z aktualnego raportu."):
                _reset_editor_state()
                st.rerun()


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
        import calendar
        today = date.today()
        # Domyślnie poprzedni miesiąc
        default_month = today.month - 1 if today.month > 1 else 12
        default_year  = today.year if today.month > 1 else today.year - 1

        mc1, mc2 = st.columns(2)
        with mc1:
            months_pl = ["Styczeń","Luty","Marzec","Kwiecień","Maj","Czerwiec",
                         "Lipiec","Sierpień","Wrzesień","Październik","Listopad","Grudzień"]
            selected_month = st.selectbox(
                "Miesiąc",
                options=list(range(1, 13)),
                format_func=lambda m: months_pl[m - 1],
                index=default_month - 1,
            )
        with mc2:
            selected_year = st.selectbox(
                "Rok",
                options=list(range(today.year - 3, today.year + 1)),
                index=today.year - (today.year - 3) - (0 if today.month > 1 else 1),
            )

        last_day = calendar.monthrange(selected_year, selected_month)[1]
        date_from   = f"{selected_year}-{selected_month:02d}-01"
        date_to     = f"{selected_year}-{selected_month:02d}-{last_day:02d}"
        period_label = f"{months_pl[selected_month - 1]} {selected_year}"
    else:
        date_from, date_to = get_last_full_week()
        period_label = f"{date_from} – {date_to}"

    st.caption(f"Okres: **{period_label}** ({date_from} — {date_to})")
    st.markdown("---")

    if st.button("▶ Generuj raport", type="primary", use_container_width=True):
        if not os.environ.get("OPENAI_API_KEY"):
            st.error("Brak klucza OpenAI. Przejdź do **Ustawienia** i dodaj swój klucz API OpenAI.")
        else:
            with st.spinner("Pobieranie danych z Google Ads, GA4 i Meta Ads..."):
                try:
                    report_text, filename, ads_data, ga4_data, meta_data = generate_full_report(
                        selected_client, report_type, date_from, date_to, period_label
                    )
                    st.session_state.report_text = report_text
                    st.session_state.report_filename = filename
                    st.session_state.report_client = selected_name
                    st.session_state.report_ads_data = ads_data
                    st.session_state.report_ga4_data = ga4_data
                    st.session_state.report_meta_data = meta_data
                    st.session_state.report_period = period_label
                    st.session_state.report_logo_b64 = (
                        selected_client.get("logo_b64") or cfg.get("logo_b64", "")
                    )
                    st.session_state.report_logo_mime = (
                        selected_client.get("logo_mime") or cfg.get("logo_mime", "image/png")
                    )
                    _reset_editor_state()
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
                st.session_state.get("report_ads_data", {}),
                st.session_state.get("report_ga4_data", {}),
                st.session_state.get("report_logo_b64", ""),
                st.session_state.get("report_logo_mime", "image/png"),
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
            st.session_state.get("report_logo_b64", ""),
            st.session_state.get("report_logo_mime", "image/png"),
            st.session_state.get("report_meta_data"),
        )

        render_recommendations_editor(st.session_state.report_text)


# ─── Strona: Klienci ──────────────────────────────────────────────────────────

@st.cache_data(ttl=300, show_spinner=False)
def _fetch_meta_accounts_cached(token: str) -> list:
    """Cache na 5 min — nie odpytujemy API przy każdym renderze."""
    from meta_ads import list_meta_ad_accounts
    return list_meta_ad_accounts(token)


def _render_client_meta_section(i: int, client: dict) -> None:
    """Sekcja Meta dla pojedynczego klienta — wybór konta + kampanii."""
    st.markdown("**Meta Ads**")

    meta_token = os.environ.get("META_ACCESS_TOKEN")
    if not meta_token:
        st.info(
            "Aby skonfigurować Meta Ads dla tego klienta — wklej **System User Token** "
            "w **Ustawienia → Meta Ads**."
        )
        return

    # 1. Wybór konta reklamowego z listy
    try:
        accounts = _fetch_meta_accounts_cached(meta_token)
    except Exception as e:
        st.warning(f"Nie udało się pobrać listy kont reklamowych Meta: {e}")
        # Awaryjnie — pole tekstowe
        manual = st.text_input(
            "Wpisz ID konta reklamowego ręcznie (act_XXXXXXXXX)",
            value=client.get("meta_ad_account_id", ""),
            key=f"meta_manual_{i}",
        )
        if st.button("Zapisz ID konta", key=f"meta_manual_save_{i}"):
            cfg["clients"][i]["meta_ad_account_id"] = manual.strip()
            save_config(cfg)
            st.rerun()
        return

    if not accounts:
        st.warning(
            "System User nie ma przypisanych kont reklamowych. "
            "Wejdź w Business Manager → Użytkownicy systemowi → wybierz usera → Przypisz zasoby → Konta reklamowe."
        )
        return

    options = {"— nie powiązuj —": ""}
    for acc in accounts:
        status_label = {1: "🟢", 2: "🔴", 3: "🟡", 7: "🟠", 9: "🟡"}.get(
            acc.get("account_status", 0), "⚪"
        )
        label = f"{status_label} {acc.get('name', '?')}  ({acc.get('id', '')})"
        options[label] = acc.get("id", "")

    current_id = client.get("meta_ad_account_id", "").strip()
    current_label = next((lbl for lbl, val in options.items() if val == current_id), "— nie powiązuj —")

    selected_label = st.selectbox(
        "Konto reklamowe Meta",
        list(options.keys()),
        index=list(options.keys()).index(current_label),
        key=f"meta_acc_sel_{i}",
        help="Lista kont reklamowych przypisanych do System Usera w Business Manager.",
    )
    selected_id = options[selected_label]

    if selected_id != current_id:
        if st.button("Zapisz konto reklamowe", key=f"meta_acc_save_{i}", type="primary"):
            cfg["clients"][i]["meta_ad_account_id"] = selected_id
            # Wyczyść stare kampanie — należą do innego konta
            cfg["clients"][i]["meta_campaign_ids"] = []
            save_config(cfg)
            st.session_state.pop(f"meta_campaigns_for_{i}", None)
            st.rerun()
        return

    if not selected_id:
        return  # nie ma co wybierać kampanii dopóki konto nie jest zapisane

    # 2. Wybór kampanii
    st.markdown("&nbsp;", unsafe_allow_html=True)
    saved_ids: list = client.get("meta_campaign_ids") or []
    st.caption(f"Aktualnie wybrane: **{len(saved_ids)}** kampanii do raportu.")

    fetch_key = f"meta_campaigns_for_{i}"
    if st.button("Pobierz kampanie z tego konta", key=f"fetch_meta_camps_{i}"):
        try:
            from meta_ads import list_meta_campaigns
            with st.spinner("Pobieranie kampanii..."):
                st.session_state[fetch_key] = list_meta_campaigns(selected_id, meta_token)
        except Exception as e:
            st.error(f"Błąd: {e}")

    camps = st.session_state.get(fetch_key, [])
    if camps:
        camp_options = {}
        for c in camps:
            status_icon = "🟢" if c.get("status") == "ACTIVE" else "⚪"
            label = f"{status_icon} {c.get('name', '?')}"
            camp_options[label] = c["id"]

        default_labels = [lbl for lbl, cid in camp_options.items() if cid in saved_ids]

        selected_labels = st.multiselect(
            "Kampanie uwzględnione w raporcie",
            options=list(camp_options.keys()),
            default=default_labels,
            key=f"meta_camp_sel_{i}",
            help="Tylko zaznaczone kampanie trafią do raportu tego klienta.",
        )

        if st.button("Zapisz wybór kampanii", key=f"save_meta_camps_{i}", type="primary"):
            cfg["clients"][i]["meta_campaign_ids"] = [
                camp_options[lbl] for lbl in selected_labels
            ]
            save_config(cfg)
            st.success(f"Zapisano {len(selected_labels)} kampanii.")
            st.rerun()


def _render_meta_campaign_assignment(clients: list) -> None:
    """Dedykowana sekcja do przypisywania kampanii Meta do klientów."""
    meta_token = os.environ.get("META_ACCESS_TOKEN")
    if not meta_token:
        return
    if not clients:
        return

    # Zbierz unikalne konta reklamowe ze wszystkich klientów
    accounts = {}
    for c in clients:
        aid = c.get("meta_ad_account_id", "").strip()
        if aid:
            accounts[aid] = accounts.get(aid, []) + [c["name"]]

    if not accounts:
        st.markdown("---")
        st.subheader("Kampanie Meta Ads — przypisanie do klientów")
        st.info(
            "Aby zarządzać kampaniami Meta — najpierw wybierz konto reklamowe dla "
            "przynajmniej jednego klienta (sekcja **Meta Ads** w karcie klienta poniżej)."
        )
        return

    st.markdown("---")
    st.subheader("Kampanie Meta Ads — przypisanie do klientów")
    st.caption(
        "Pobierz kampanie z konta reklamowego i przypisz każdą do właściwego klienta. "
        "Tylko przypisane kampanie trafiają do raportu."
    )

    # Wybór konta jeśli jest kilka
    all_accounts = list(accounts.keys())
    if len(all_accounts) > 1:
        selected_account = st.selectbox(
            "Konto reklamowe Meta",
            all_accounts,
            format_func=lambda a: f"{a}  (klienci: {', '.join(accounts[a])})",
            key="meta_assign_account",
        )
    else:
        selected_account = all_accounts[0]
        st.caption(f"Konto: **{selected_account}**")

    col_fetch, col_clear = st.columns([2, 1])
    with col_fetch:
        if st.button("Pobierz kampanie z Meta", key="meta_fetch_assign", type="primary", use_container_width=True):
            with st.spinner("Pobieranie kampanii..."):
                try:
                    from meta_ads import list_meta_campaigns
                    camps = list_meta_campaigns(selected_account, meta_token)
                    st.session_state["meta_assign_campaigns"] = camps
                    st.session_state["meta_assign_account_id"] = selected_account
                    st.success(f"Pobrano {len(camps)} kampanii.")
                except Exception as e:
                    st.error(f"Błąd: {e}")

    with col_clear:
        if st.button("Wyczyść", key="meta_clear_assign", use_container_width=True):
            st.session_state.pop("meta_assign_campaigns", None)
            st.rerun()

    camps: list = st.session_state.get("meta_assign_campaigns", [])
    if not camps:
        return

    # Buduj mapę: campaign_id → które klienty go mają w meta_campaign_ids
    client_names = ["— nie przypisuj —"] + [c["name"] for c in clients]

    def _current_client_for(campaign_id: str) -> str:
        for c in clients:
            if campaign_id in (c.get("meta_campaign_ids") or []):
                return c["name"]
        return "— nie przypisuj —"

    st.markdown("<br>", unsafe_allow_html=True)

    # Nagłówek tabeli
    h1, h2, h3, h4 = st.columns([3, 2, 2, 2])
    h1.markdown("**Kampania**")
    h2.markdown("**Cel kampanii**")
    h3.markdown("**Status**")
    h4.markdown("**Przypisz do klienta**")
    st.markdown("<hr style='margin:4px 0 8px'>", unsafe_allow_html=True)

    selections: dict[str, str] = {}  # campaign_id → client_name
    for camp in camps:
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        c1.write(camp.get("name", ""))
        obj = camp.get("objective", "").replace("_", " ").title()
        c2.caption(obj)
        status = camp.get("status", "")
        status_color = "🟢" if status == "ACTIVE" else "⚪"
        c3.caption(f"{status_color} {status}")
        current = _current_client_for(camp["id"])
        selected = c4.selectbox(
            "",
            client_names,
            index=client_names.index(current) if current in client_names else 0,
            key=f"meta_assign_{camp['id']}",
            label_visibility="collapsed",
        )
        selections[camp["id"]] = selected

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Zapisz przypisania", key="meta_save_assign", type="primary", use_container_width=True):
        # Wyczyść stare przypisania z tego konta dla wszystkich klientów
        fetched_ids = {c["id"] for c in camps}
        for ci, client in enumerate(cfg["clients"]):
            old_ids = client.get("meta_campaign_ids") or []
            cfg["clients"][ci]["meta_campaign_ids"] = [
                cid for cid in old_ids if cid not in fetched_ids
            ]

        # Dodaj nowe przypisania
        for camp_id, client_name in selections.items():
            if client_name == "— nie przypisuj —":
                continue
            for ci, client in enumerate(cfg["clients"]):
                if client["name"] == client_name:
                    ids = cfg["clients"][ci].get("meta_campaign_ids") or []
                    if camp_id not in ids:
                        ids.append(camp_id)
                    cfg["clients"][ci]["meta_campaign_ids"] = ids

        save_config(cfg)
        # Podsumowanie
        assigned = sum(1 for v in selections.values() if v != "— nie przypisuj —")
        st.success(f"Zapisano. Przypisano {assigned} kampanii do klientów.")
        st.rerun()


def page_clients():
    st.markdown('<p class="main-title">Klienci</p>', unsafe_allow_html=True)
    st.markdown('<p class="page-subtitle">Zarządzaj kontami klientów — Google Ads i Google Analytics 4.</p>', unsafe_allow_html=True)

    clients = cfg.get("clients", [])

    _render_meta_campaign_assignment(clients)

    if "saved_client" not in st.session_state:
        st.session_state.saved_client = None

    if clients:
        import base64
        st.subheader("Konta klientów")
        for i, client in enumerate(clients):
            with st.expander(f"**{client['name']}**"):
                # ── Logo klienta (poza formularzem — auto-zapis) ──────────
                cur_logo  = client.get("logo_b64", "")
                cur_mime  = client.get("logo_mime", "image/png")

                logo_col1, logo_col2 = st.columns([3, 1])
                with logo_col1:
                    if cur_logo:
                        st.markdown(
                            f'<img src="data:{cur_mime};base64,{cur_logo}" '
                            f'style="max-width:160px;background:#fff;padding:6px;border-radius:6px">',
                            unsafe_allow_html=True,
                        )
                    else:
                        st.caption(
                            "Brak loga klienta. Jeśli ustawione jest logo globalne (Ustawienia), "
                            "zostanie użyte zamiast niego."
                        )
                with logo_col2:
                    if cur_logo and st.button("Usuń logo", key=f"del_logo_{i}"):
                        cfg["clients"][i]["logo_b64"]  = ""
                        cfg["clients"][i]["logo_mime"] = ""
                        save_config(cfg)
                        st.rerun()

                upl_logo = st.file_uploader(
                    "Wgraj logo klienta (PNG / JPG)",
                    type=["png", "jpg", "jpeg"],
                    key=f"logo_upl_{i}",
                )
                if upl_logo is not None:
                    mime = "image/png" if upl_logo.name.lower().endswith(".png") else "image/jpeg"
                    b64 = base64.b64encode(upl_logo.read()).decode("utf-8")
                    cfg["clients"][i]["logo_b64"]  = b64
                    cfg["clients"][i]["logo_mime"] = mime
                    save_config(cfg)
                    st.success("Logo klienta zapisane.")
                    st.rerun()

                st.markdown("---")

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
                    profile_edit = st.text_area(
                        "Profil działalności",
                        value=client.get("business_profile", ""),
                        key=f"profile_e_{i}",
                        height=120,
                        help=(
                            "Krótki opis branży, oferty i celów konwersji. "
                            "AI użyje tego jako kontekstu — bez tego raport może błędnie zakładać branżę."
                        ),
                        placeholder=(
                            "np. Sklep internetowy z odżywkami i suplementami diety dla sportowców. "
                            "Główne kanały sprzedaży: sklep własny i Allegro. "
                            "Kluczowa konwersja: zakończenie transakcji w sklepie."
                        ),
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
                        "business_profile": profile_edit.strip(),
                    })
                    save_config(cfg)
                    st.session_state.saved_client = name_edit.strip()
                    st.rerun()

                # ── Meta Ads — konto + kampanie (poza formą, interaktywne) ────
                st.markdown("---")
                _render_client_meta_section(i, client)

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
        # Meta Ads — selectbox z listy kont jeśli token jest, inaczej text input
        meta_token_new = os.environ.get("META_ACCESS_TOKEN")
        meta_id = ""
        if meta_token_new:
            try:
                meta_accs = _fetch_meta_accounts_cached(meta_token_new)
            except Exception:
                meta_accs = []
            if meta_accs:
                meta_opts = {"— pomiń (skonfigurujesz później) —": ""}
                for acc in meta_accs:
                    status_label = {1: "🟢", 2: "🔴", 3: "🟡"}.get(
                        acc.get("account_status", 0), "⚪"
                    )
                    label = f"{status_label} {acc.get('name', '?')}  ({acc.get('id', '')})"
                    meta_opts[label] = acc.get("id", "")
                meta_choice = st.selectbox(
                    "Meta Ads — konto reklamowe (opcjonalnie)",
                    list(meta_opts.keys()),
                    help="Po dodaniu klienta będziesz mógł wybrać kampanie do raportu.",
                )
                meta_id = meta_opts[meta_choice]
            else:
                meta_id = st.text_input(
                    "Meta Ads — ID konta reklamowego (opcjonalnie)",
                    placeholder="act_123456789",
                    help="Brak dostępnych kont — wpisz ID ręcznie lub przypisz konto do System Usera.",
                )
        else:
            st.caption("Aby skonfigurować Meta Ads dla nowego klienta — najpierw dodaj token w Ustawieniach.")

        profile = st.text_area(
            "Profil działalności",
            height=120,
            help=(
                "Krótki opis branży, oferty i celów konwersji. "
                "AI użyje tego jako kontekstu — bez tego raport może błędnie zakładać branżę."
            ),
            placeholder=(
                "np. Sklep internetowy z odżywkami i suplementami diety dla sportowców. "
                "Główne kanały sprzedaży: sklep własny i Allegro. "
                "Kluczowa konwersja: zakończenie transakcji w sklepie."
            ),
        )
        new_logo = st.file_uploader(
            "Logo klienta (opcjonalnie — PNG / JPG)",
            type=["png", "jpg", "jpeg"],
            help="Pojawi się w nagłówku raportu HTML i wizualizacji.",
        )

        if st.form_submit_button("Dodaj klienta", type="primary"):
            if not name.strip():
                st.error("Nazwa klienta jest wymagana.")
            elif any(c["name"].lower() == name.strip().lower() for c in cfg["clients"]):
                st.error("Klient o tej nazwie już istnieje.")
            else:
                import base64
                new_client = {
                    "id": str(uuid.uuid4()),
                    "name": name.strip(),
                    "ads_customer_id": ads_id.strip(),
                    "ga4_property_id": ga4_id.strip(),
                    "meta_ad_account_id": meta_id.strip(),
                    "business_profile": profile.strip(),
                }
                if new_logo is not None:
                    mime = "image/png" if new_logo.name.lower().endswith(".png") else "image/jpeg"
                    new_client["logo_b64"]  = base64.b64encode(new_logo.read()).decode("utf-8")
                    new_client["logo_mime"] = mime
                cfg["clients"].append(new_client)
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

    # ── Meta Ads ──────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Meta Ads — token dostępu")
    st.caption(
        "System User Token z Meta Business Manager. "
        "Wymagane uprawnienie: `ads_read`. "
        "Wygeneruj go w: Business Settings → System Users → Generuj token."
    )

    current_meta_token = os.environ.get("META_ACCESS_TOKEN", "")
    with st.form("meta_token_form"):
        meta_token_input = st.text_input(
            "Token dostępu Meta",
            value=current_meta_token,
            type="password",
            placeholder="EAABwzLixnjY...",
        )
        if st.form_submit_button("Zapisz token Meta", type="primary"):
            val = meta_token_input.strip()
            if val:
                update_env_key("META_ACCESS_TOKEN", val)
                auth.save_user_data(_uid, {"meta_token": val})
                os.environ["META_ACCESS_TOKEN"] = val
                st.success("Token Meta zapisany.")
                st.rerun()
            else:
                st.error("Wpisz token.")

    if current_meta_token:
        st.success("Token Meta ustawiony.")

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
        content = uploaded_yaml.read()
        GADS_YAML_PATH.write_bytes(content)
        os.environ["GOOGLE_ADS_CONFIGURATION_FILE_PATH"] = str(GADS_YAML_PATH)
        try:
            auth.save_user_data(_uid, {"gads_yaml": content.decode("utf-8")})
        except Exception as exc:
            st.warning(f"Plik zapisany lokalnie, ale błąd zapisu do Supabase: {exc}")
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

    # ── Automatyczna wysyłka tygodniowa ───────────────────────────────────────
    st.markdown("---")
    st.subheader("Automatyczna wysyłka tygodniowa")
    st.caption(
        "Po włączeniu — w każdy poniedziałek rano serwer automatycznie wygeneruje "
        "raport tygodniowy (dane z poprzedniego pełnego tygodnia, pon–niedz) "
        "dla każdego Twojego klienta i wyśle go emailem na adresy z listy odbiorców powyżej."
    )

    smtp_ready = bool(cfg["email"].get("smtp_user") and cfg["email"].get("smtp_password"))
    recipients_ready = bool(cfg["email"].get("recipients"))
    clients_ready = bool(cfg.get("clients"))

    if not (smtp_ready and recipients_ready and clients_ready):
        missing = []
        if not smtp_ready:      missing.append("konfiguracja SMTP")
        if not recipients_ready: missing.append("odbiorcy")
        if not clients_ready:    missing.append("klienci")
        st.warning(
            f"Aby włączyć automatyczną wysyłkę, najpierw uzupełnij: **{', '.join(missing)}**."
        )

    current_auto = cfg.get("auto_send_weekly", False)
    new_auto = st.toggle(
        "Wysyłaj raporty tygodniowe automatycznie (poniedziałki rano)",
        value=current_auto,
        disabled=not (smtp_ready and recipients_ready and clients_ready),
        help=(
            "Skrypt cron sprawdza tę flagę co poniedziałek. "
            "Jeśli włączona — generuje raporty dla wszystkich Twoich klientów "
            "i wysyła na każdy adres z listy odbiorców."
        ),
    )
    if new_auto != current_auto:
        cfg["auto_send_weekly"] = new_auto
        save_config(cfg)
        if new_auto:
            st.success("Automatyczna wysyłka tygodniowa włączona.")
        else:
            st.info("Automatyczna wysyłka tygodniowa wyłączona.")

    if cfg.get("auto_send_weekly"):
        st.info(
            f"✅ Aktywne — w każdy poniedziałek raporty trafią na: "
            f"**{', '.join(cfg['email'].get('recipients', []))}**"
        )

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

---

**Czy jeden plik JSON wystarczy dla wielu klientów?**

Tak — jeden plik Service Account działa dla wszystkich klientów.
Wystarczy, że dla każdego nowego klienta dodasz email konta usługi jako Czytelnika w jego GA4:

1. Wejdź do GA4 klienta → **Ustawienia → Zarządzanie dostępem do usługi**
2. Kliknij **+** → wpisz email konta usługi (np. `raporty@raporty-489018.iam.gserviceaccount.com`)
3. Rola: **Czytelnik** → zapisz

Email konta usługi znajdziesz w pobranym pliku JSON pod kluczem `client_email`.
        """)

    # ── Meta Ads ──────────────────────────────────────────────────────────────
    with st.expander("Meta Ads — token dostępu (jak go wygenerować?)", expanded=False):
        st.markdown("""
**Do czego służy:** Aplikacja pobiera dane z kampanii Meta Ads Manager — wyniki kampanii,
liczbę leadów z formularzy błyskawicznych i koszt pozyskania leadu (CPL).

---

**Krok 1 — Utwórz aplikację Meta**

1. Wejdź na **developers.facebook.com** → **My Apps → Create App**
2. Podaj nazwę aplikacji, np. *Raporty*
3. W kroku **Use cases** wybierz wyłącznie: **Measure ad performance data with Marketing API**
4. Przypisz swój Business Manager i kliknij **Create app**

---

**Krok 2 — Utwórz System Usera**

1. Wejdź do **business.facebook.com → Ustawienia → Użytkownicy → Użytkownicy systemowi**
2. Kliknij **+ Dodaj** → nadaj nazwę (np. *Raporty API*) → rola: **Employee** → zapisz

---

**Krok 3 — Przypisz konto reklamowe**

1. Kliknij utworzonego System Usera
2. Kliknij **Przypisz zasoby** → wybierz typ **Konta reklamowe**
3. Zaznacz konta reklamowe klientów których chcesz raportować
4. Uprawnienie: **Wyświetl wyniki** (tylko odczyt) → **Przypisz zasoby**

---

**Krok 4 — Wygeneruj token**

1. Kliknij **Wygeneruj token** (przycisk przy System Userze)
2. Wybierz aplikację *Raporty* z listy
3. Zaznacz uprawnienie **ads_read**
4. Kliknij **Generuj token** → skopiuj

> Token ważny jest 60 dni. Wygeneruj nowy przed upłynięciem terminu.

---

**Krok 5 — Wklej token w aplikacji**

Przejdź do **Ustawienia → Meta Ads → Token dostępu Meta** i wklej skopiowany token.

---

**Krok 6 — Dodaj ID konta reklamowego dla klienta**

W sekcji **Klienci** przy danym kliencie:
- Wpisz **ID konta reklamowego** w formacie `act_123456789`
- ID znajdziesz w Ads Manager — górny pasek lub URL strony (liczba po `act_`)
- Kliknij **Pobierz listę kampanii** i zaznacz kampanie do raportu
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
