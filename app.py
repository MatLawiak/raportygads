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

# ─── Logowanie ────────────────────────────────────────────────────────────────

def check_password() -> bool:
    """Zwraca True jeśli użytkownik podał prawidłowe hasło."""
    password = os.environ.get("APP_PASSWORD", "")
    if not password:
        return True  # brak hasła w .env = tryb lokalny bez ochrony

    if st.session_state.get("authenticated"):
        return True

    st.markdown("## Raporty Marketingowe")
    st.markdown("Podaj hasło dostępu aby kontynuować.")
    entered = st.text_input("Hasło", type="password", key="password_input")
    if st.button("Zaloguj", type="primary"):
        if entered == password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Nieprawidłowe hasło.")
    st.stop()


check_password()

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
        for key in ("OPENAI_API_KEY", "APP_PASSWORD"):
            val = st.secrets.get(key, "")
            if val:
                os.environ[key] = val

    except Exception:
        pass  # lokalnie st.secrets nie istnieje — pomijamy


init_from_secrets()

CONFIG_FILE = BASE_DIR / "config.json"
REPORTS_DIR = BASE_DIR / "raporty"
REPORTS_DIR.mkdir(exist_ok=True)
sys.path.insert(0, str(BASE_DIR))

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

if "config" not in st.session_state:
    st.session_state.config = load_config()
if "report_text" not in st.session_state:
    st.session_state.report_text = None
if "report_filename" not in st.session_state:
    st.session_state.report_filename = None
if "report_client" not in st.session_state:
    st.session_state.report_client = None

cfg: dict = st.session_state.config

# ─── Pasek boczny ─────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📊 Raporty Marketingowe")
    st.markdown("---")
    page = st.radio(
        "Nawigacja",
        ["Generuj raport", "Klienci", "Ustawienia"],
        label_visibility="collapsed",
    )
    st.markdown("---")

    # Szybki status API
    openai_ok = bool(os.environ.get("OPENAI_API_KEY"))
    gads_ok = (BASE_DIR / "google-ads.yaml").exists()
    ga4_ok = bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")) or (BASE_DIR / "ga4_credentials.json").exists()

    st.caption("Status API")
    st.write("🟢 OpenAI" if openai_ok else "🔴 OpenAI — brak klucza")
    st.write("🟢 Google Ads" if gads_ok else "🔴 Google Ads — brak pliku")
    st.write("🟢 GA4" if ga4_ok else "🟡 GA4 — brak credentials")


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


# ─── Wizualizacja raportu ─────────────────────────────────────────────────────

def render_visual_report(client_name: str, period_label: str, ads_data: dict, ga4_data: dict, report_text: str) -> None:
    import plotly.graph_objects as go
    import base64

    # Logo
    logo_b64 = cfg.get("logo_b64", "")
    logo_mime = cfg.get("logo_mime", "image/png")
    if logo_b64:
        col_l, col_m, col_r = st.columns([1, 2, 1])
        with col_m:
            st.markdown(
                f'<img src="data:{logo_mime};base64,{logo_b64}" style="max-width:180px;display:block;margin:auto">',
                unsafe_allow_html=True,
            )

    st.markdown(f"<h1 style='text-align:center'>Raport miesięczny — {client_name}</h1>", unsafe_allow_html=True)
    st.markdown(f"<p style='text-align:center;color:#888'>Okres: {period_label}</p>", unsafe_allow_html=True)
    st.markdown("---")

    # ── Google Ads ────────────────────────────────────────────────────────────
    st.markdown("## 1. Wyniki Google Ads")
    if ads_data:
        t = ads_data["totals"]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Wydatki", f"{t['cost_pln']} zł")
        c2.metric("Kliknięcia", f"{t['clicks']:,}")
        c3.metric("Wyświetlenia", f"{t['impressions']:,}")
        c4.metric("Konwersje", f"{int(t['conversions'])}")
        c5.metric("Koszt/konw.", f"{t['cost_per_conversion_pln']} zł")

        campaigns = ads_data.get("campaigns", [])
        if campaigns:
            st.markdown("**Wyniki kampanii:**")
            names = [c["name"].replace("_", " ") for c in campaigns]
            fig = go.Figure(data=[
                go.Bar(name="Wydatki (zł)", x=names, y=[c["cost_pln"] for c in campaigns],
                       marker_color="#4C78A8"),
                go.Bar(name="Konwersje", x=names, y=[c["conversions"] for c in campaigns],
                       marker_color="#F58518"),
            ])
            fig.update_layout(
                barmode="group",
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02),
                margin=dict(t=40, b=20),
                height=320,
            )
            st.plotly_chart(fig, use_container_width=True)

            # Tabela kampanii
            header = ["Kampania", "Wydatki (zł)", "Kliknięcia", "CTR", "Konwersje", "Koszt/konw."]
            rows = [[c["name"], f"{c['cost_pln']} zł", c["clicks"],
                     f"{c['ctr_pct']}%", c["conversions"], f"{c['cost_per_conversion_pln']} zł"]
                    for c in campaigns]
            fig_t = go.Figure(data=[go.Table(
                header=dict(values=header, fill_color="#4C78A8", font=dict(color="white", size=12), align="left"),
                cells=dict(values=list(zip(*rows)) if rows else [[] for _ in header],
                           fill_color=[["#f9f9f9", "white"] * len(rows)],
                           align="left", font=dict(size=11)),
            )])
            fig_t.update_layout(margin=dict(t=10, b=10), height=120 + len(campaigns) * 30)
            st.plotly_chart(fig_t, use_container_width=True)
    else:
        st.info("Brak danych Google Ads za ten okres.")

    st.markdown("---")

    # ── GA4 ───────────────────────────────────────────────────────────────────
    st.markdown("## 2. Ruch na stronie — Google Analytics")
    if ga4_data:
        g = ga4_data["general"]
        dur = g["avg_session_duration_sec"]
        dur_str = f"{dur // 60}m {dur % 60}s"
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Użytkownicy", f"{g['users']:,}")
        c2.metric("Sesje", f"{g['sessions']:,}")
        c3.metric("Śr. czas wizyty", dur_str)
        c4.metric("Wsp. zaangażowania", f"{100 - g['bounce_rate_pct']:.1f}%")

        col_pie, col_conv = st.columns(2)

        # Źródła ruchu — wykres kołowy
        sources = ga4_data.get("sources", [])
        if sources:
            with col_pie:
                st.markdown("**Źródła ruchu:**")
                fig = go.Figure(data=[go.Pie(
                    labels=[s["channel"] for s in sources],
                    values=[s["sessions"] for s in sources],
                    hole=0.4,
                    textinfo="label+percent",
                )])
                fig.update_layout(
                    showlegend=False,
                    margin=dict(t=20, b=20, l=20, r=20),
                    height=280,
                    paper_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)

        # Konwersje — wykres poziomy
        events = ga4_data.get("conversion_events", [])
        if events:
            with col_conv:
                st.markdown("**Konwersje na stronie:**")
                top = events[:8]
                labels = [e["event"].replace("_", " ").replace("restauracja biala dama (web) ", "") for e in top]
                fig = go.Figure(data=[go.Bar(
                    x=[e["conversions"] for e in top],
                    y=labels,
                    orientation="h",
                    marker_color="#F58518",
                )])
                fig.update_layout(
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    margin=dict(t=10, b=10, l=10, r=10),
                    height=280,
                    xaxis=dict(title="Liczba"),
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Brak danych GA4 za ten okres.")

    st.markdown("---")

    # ── Analiza tekstowa ──────────────────────────────────────────────────────
    st.markdown("## 3. Analiza i rekomendacje")
    st.markdown(report_text)


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
            st.error("Brak klucza OPENAI_API_KEY. Ustaw zmienną środowiskową i uruchom aplikację ponownie.")
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

        dl_col, email_col, _ = st.columns([1, 1, 2])
        with dl_col:
            st.download_button(
                label="⬇ Pobierz (.md)",
                data=st.session_state.report_text.encode("utf-8"),
                file_name=st.session_state.report_filename,
                mime="text/markdown",
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
            placeholder="np. Restauracja Biała Dama",
        )
        col1, col2 = st.columns(2)
        with col1:
            ads_id = st.text_input(
                "Google Ads Customer ID",
                placeholder="np. 8612470472",
                help="ID konta bez myślników. Znajdziesz je w prawym górnym rogu panelu Google Ads.",
            )
        with col2:
            ga4_id = st.text_input(
                "GA4 Property ID",
                placeholder="np. 123456789",
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

    # ── GA4 Service Account ───────────────────────────────────────────────────
    st.subheader("Google Analytics 4 — credentials")

    ga4_creds_path = BASE_DIR / "ga4_credentials.json"
    ga4_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")

    if ga4_creds_path.exists():
        st.success(f"Plik credentials wgrany: `ga4_credentials.json`")
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("Usuń credentials GA4"):
                ga4_creds_path.unlink()
                update_env_key("GOOGLE_APPLICATION_CREDENTIALS", "")
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
        ga4_creds_path.write_bytes(uploaded.read())
        update_env_key("GOOGLE_APPLICATION_CREDENTIALS", str(ga4_creds_path))
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
    gads_yaml = (BASE_DIR / "google-ads.yaml").exists()
    ga4_creds = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "") or str(BASE_DIR / "ga4_credentials.json") if (BASE_DIR / "ga4_credentials.json").exists() else ""

    col1, col2, col3 = st.columns(3)
    with col1:
        if openai_key:
            st.success("OpenAI API Key")
            st.caption("Klucz ustawiony — generowanie raportów działa.")
        else:
            st.error("OpenAI API Key — brak")
            st.caption("Ustaw zmienną środowiskową `OPENAI_API_KEY` przed uruchomieniem aplikacji.")
    with col2:
        if gads_yaml:
            st.success("google-ads.yaml")
            st.caption("Plik konfiguracyjny Google Ads znaleziony.")
        else:
            st.error("google-ads.yaml — brak")
            st.caption("Utwórz plik `google-ads.yaml` w folderze projektu.")
    with col3:
        if ga4_creds:
            st.success("GA4 Service Account")
            st.caption(f"Credentials: `{Path(ga4_creds).name}`")
        else:
            st.warning("GA4 Service Account — brak")
            st.caption("Ustaw `GOOGLE_APPLICATION_CREDENTIALS` aby pobierać dane z GA4.")


# ─── Router ───────────────────────────────────────────────────────────────────

if page == "Generuj raport":
    page_generate()
elif page == "Klienci":
    page_clients()
elif page == "Ustawienia":
    page_settings()
