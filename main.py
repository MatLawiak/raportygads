"""
Generator miesięcznych raportów marketingowych.
Pobiera dane z Google Ads i Google Analytics 4, następnie generuje
raport w języku polskim przy użyciu Claude API.

Użycie:
    python main.py "Nazwa Klienta"
    python main.py  # pyta o nazwę interaktywnie
"""

import sys
import json
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

from dateutil.relativedelta import relativedelta


# ---------------------------------------------------------------------------
# Krok 2 — Zakres dat
# ---------------------------------------------------------------------------

def get_last_full_month() -> tuple[str, str]:
    """Zwraca (date_from, date_to) jako stringi 'YYYY-MM-DD'."""
    today = date.today()
    first_day_this_month = today.replace(day=1)
    last_month_end = first_day_this_month - relativedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    return str(last_month_start), str(last_month_end)


def get_last_full_week() -> tuple[str, str]:
    """Zwraca (date_from, date_to) dla poprzedniego pełnego tygodnia (pon–niedz)."""
    from datetime import timedelta
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return str(last_monday), str(last_sunday)


# ---------------------------------------------------------------------------
# Krok 1 — Weryfikacja kont
# ---------------------------------------------------------------------------

def verify_google_ads_account(client_name: str) -> dict | None:
    """
    Wyszukuje konto Google Ads po nazwie klienta.
    Zwraca słownik z customer_id i nazwą lub None jeśli nie znaleziono.
    """
    try:
        from google.ads.googleads.client import GoogleAdsClient
        from google.ads.googleads.errors import GoogleAdsException
    except ImportError:
        print("⚠️  Biblioteka google-ads nie jest zainstalowana. Pomiń Google Ads.")
        return None

    try:
        client = GoogleAdsClient.load_from_storage("google-ads.yaml")
    except Exception as e:
        print(f"⚠️  Nie można załadować google-ads.yaml: {e}")
        return None

    customer_service = client.get_service("CustomerService")
    googleads_service = client.get_service("GoogleAdsService")

    try:
        accessible_customers = customer_service.list_accessible_customers()
    except Exception as e:
        print(f"⚠️  Błąd pobierania kont Google Ads: {e}")
        return None

    for resource_name in accessible_customers.resource_names:
        customer_id = resource_name.split("/")[-1]
        query = f"""
            SELECT customer.descriptive_name, customer.id
            FROM customer
            WHERE customer.descriptive_name LIKE '%{client_name}%'
        """
        try:
            response = googleads_service.search(customer_id=customer_id, query=query)
            for row in response:
                return {
                    "customer_id": str(row.customer.id),
                    "name": row.customer.descriptive_name
                }
        except GoogleAdsException:
            continue

    return None


def verify_ga4_account(client_name: str) -> dict | None:
    """
    Wyszukuje property GA4 po nazwie klienta.
    Zwraca słownik z property_id i nazwą lub None jeśli nie znaleziono.
    """
    try:
        from google.analytics.admin import AnalyticsAdminServiceClient
    except ImportError:
        print("⚠️  Biblioteka google-analytics-admin nie jest zainstalowana. Pomiń GA4.")
        return None

    try:
        admin_client = AnalyticsAdminServiceClient()
    except Exception as e:
        print(f"⚠️  Błąd inicjalizacji GA4 Admin Client: {e}")
        return None

    try:
        for account in admin_client.list_accounts():
            account_id = account.name.split("/")[-1]
            for prop in admin_client.list_properties(
                filter=f"parent:accounts/{account_id}"
            ):
                if client_name.lower() in prop.display_name.lower():
                    return {
                        "property_id": prop.name.split("/")[-1],
                        "name": prop.display_name
                    }
    except Exception as e:
        print(f"⚠️  Błąd pobierania kont GA4: {e}")

    return None


# ---------------------------------------------------------------------------
# Krok 3 — Pobieranie danych z Google Ads
# ---------------------------------------------------------------------------

def fetch_google_ads_data(customer_id: str, date_from: str, date_to: str) -> dict:
    """
    Pobiera kluczowe metryki kampanii z Google Ads za podany okres.
    Zwraca zagregowane dane oraz breakdown per kampania.
    """
    from google.ads.googleads.client import GoogleAdsClient

    client = GoogleAdsClient.load_from_storage("google-ads.yaml")
    googleads_service = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
            campaign.name,
            campaign.status,
            metrics.cost_micros,
            metrics.clicks,
            metrics.impressions,
            metrics.ctr,
            metrics.conversions,
            metrics.cost_per_conversion,
            metrics.average_cpc
        FROM campaign
        WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
          AND metrics.impressions > 0
        ORDER BY metrics.cost_micros DESC
    """

    response = googleads_service.search(customer_id=customer_id, query=query)

    campaigns = []
    totals = {
        "cost_pln": 0.0,
        "clicks": 0,
        "impressions": 0,
        "conversions": 0.0,
    }

    for row in response:
        cost_pln = row.metrics.cost_micros / 1_000_000
        campaigns.append({
            "name": row.campaign.name,
            "cost_pln": round(cost_pln, 2),
            "clicks": row.metrics.clicks,
            "impressions": row.metrics.impressions,
            "ctr_pct": round(row.metrics.ctr * 100, 2),
            "conversions": round(row.metrics.conversions, 1),
            "cost_per_conversion_pln": round(row.metrics.cost_per_conversion / 1_000_000, 2),
            "avg_cpc_pln": round(row.metrics.average_cpc / 1_000_000, 2),
        })
        totals["cost_pln"] += cost_pln
        totals["clicks"] += row.metrics.clicks
        totals["impressions"] += row.metrics.impressions
        totals["conversions"] += row.metrics.conversions

    totals["cost_pln"] = round(totals["cost_pln"], 2)
    totals["ctr_pct"] = (
        round(totals["clicks"] / totals["impressions"] * 100, 2)
        if totals["impressions"] else 0
    )
    totals["cost_per_conversion_pln"] = (
        round(totals["cost_pln"] / totals["conversions"], 2)
        if totals["conversions"] else 0
    )

    return {"totals": totals, "campaigns": campaigns}


# ---------------------------------------------------------------------------
# Krok 4 — Pobieranie danych z Google Analytics 4
# ---------------------------------------------------------------------------

def fetch_ga4_data(property_id: str, date_from: str, date_to: str) -> dict:
    """
    Pobiera dane o ruchu na stronie z GA4.
    Zwraca metryki ogólne oraz breakdown po źródle ruchu.
    """
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        RunReportRequest, DateRange, Dimension, Metric, OrderBy
    )

    client = BetaAnalyticsDataClient()
    property_path = f"properties/{property_id}"

    # --- Metryki ogólne ---
    overview_request = RunReportRequest(
        property=property_path,
        date_ranges=[DateRange(start_date=date_from, end_date=date_to)],
        metrics=[
            Metric(name="totalUsers"),
            Metric(name="sessions"),
            Metric(name="bounceRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="conversions"),
        ],
    )
    overview = client.run_report(overview_request)
    row = overview.rows[0].metric_values

    general = {
        "users": int(row[0].value),
        "sessions": int(row[1].value),
        "bounce_rate_pct": round(float(row[2].value) * 100, 1),
        "avg_session_duration_sec": round(float(row[3].value)),
        "conversions": int(row[4].value),
    }

    # --- Źródła ruchu ---
    traffic_request = RunReportRequest(
        property=property_path,
        date_ranges=[DateRange(start_date=date_from, end_date=date_to)],
        dimensions=[Dimension(name="sessionDefaultChannelGroup")],
        metrics=[Metric(name="sessions"), Metric(name="totalUsers")],
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="sessions"),
                desc=True
            )
        ],
    )
    traffic = client.run_report(traffic_request)

    sources = []
    for r in traffic.rows:
        sources.append({
            "channel": r.dimension_values[0].value,
            "sessions": int(r.metric_values[0].value),
            "users": int(r.metric_values[1].value),
        })

    # --- Konwersje per zdarzenie ---
    conversions_request = RunReportRequest(
        property=property_path,
        date_ranges=[DateRange(start_date=date_from, end_date=date_to)],
        dimensions=[Dimension(name="eventName")],
        metrics=[Metric(name="eventCount"), Metric(name="conversions")],
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="conversions"),
                desc=True
            )
        ],
    )
    conv_response = client.run_report(conversions_request)

    conversion_events = []
    for r in conv_response.rows:
        conv_count = float(r.metric_values[1].value)
        if conv_count > 0:
            conversion_events.append({
                "event": r.dimension_values[0].value,
                "count": int(float(r.metric_values[0].value)),
                "conversions": round(conv_count, 1),
            })

    return {"general": general, "sources": sources, "conversion_events": conversion_events}


# ---------------------------------------------------------------------------
# Krok 5 — Budowanie promptu i generowanie raportu
# ---------------------------------------------------------------------------

def _format_campaigns_table(campaigns: list[dict]) -> str:
    if not campaigns:
        return "Brak aktywnych kampanii w tym okresie."
    lines = ["| Kampania | Wydatki (zł) | Kliknięcia | CTR% | Konwersje | Koszt/konw. |",
             "|----------|-------------|------------|------|-----------|-------------|"]
    for c in campaigns:
        lines.append(
            f"| {c['name']} | {c['cost_pln']} | {c['clicks']} "
            f"| {c['ctr_pct']} | {c['conversions']} | {c['cost_per_conversion_pln']} |"
        )
    return "\n".join(lines)


def _format_sources_table(sources: list[dict]) -> str:
    if not sources:
        return "Brak danych o źródłach ruchu."
    lines = ["| Kanał | Sesje | Użytkownicy |",
             "|-------|-------|-------------|"]
    for s in sources:
        lines.append(f"| {s['channel']} | {s['sessions']} | {s['users']} |")
    return "\n".join(lines)


def build_report_prompt(
    client_name: str,
    month_label: str,
    ads_data: dict,
    ga4_data: dict,
) -> str:
    """Buduje prompt użytkownika do generowania raportu."""

    ads_section = "Brak danych Google Ads (konto nie zostało znalezione)."
    if ads_data:
        t = ads_data["totals"]
        campaigns_table = _format_campaigns_table(ads_data.get("campaigns", []))
        ads_section = f"""Łączne wydatki: {t['cost_pln']} zł
Kliknięcia: {t['clicks']}
Wyświetlenia: {t['impressions']}
CTR: {t['ctr_pct']}%
Konwersje: {t['conversions']}
Koszt za konwersję: {t['cost_per_conversion_pln']} zł

Wyniki per kampania:
{campaigns_table}"""

    ga4_section = "Brak danych Google Analytics 4 (konto nie zostało znalezione)."
    if ga4_data:
        g = ga4_data["general"]
        sources_table = _format_sources_table(ga4_data.get("sources", []))
        conv_events = ga4_data.get("conversion_events", [])
        conv_lines = "\n".join(
            f"  - {e['event']}: {e['conversions']} konwersji ({e['count']} zdarzeń)"
            for e in conv_events
        ) if conv_events else "  Brak zarejestrowanych konwersji."
        ga4_section = f"""Użytkownicy: {g['users']}
Sesje: {g['sessions']}
Współczynnik odrzuceń: {g['bounce_rate_pct']}%
Średni czas wizyty: {g['avg_session_duration_sec']} sekund

Źródła ruchu:
{sources_table}

Konwersje per zdarzenie (KLUCZOWE — uwzględnij w raporcie):
{conv_lines}"""

    return f"""Wygeneruj profesjonalny raport miesięczny na podstawie poniższych danych.

KLIENT: {client_name}
OKRES: {month_label}

=== GOOGLE ADS ===
{ads_section}

=== GOOGLE ANALYTICS 4 ===
{ga4_section}

=== ZASADY PISANIA ===
- Pisz po polsku, prostym językiem — odbiorca to właścicielka biznesu, nie marketer
- Używaj **pogrubień** dla ważnych liczb i wniosków
- Interpretuj dane — wyjaśniaj co oznaczają dla biznesu, nie tylko przepisuj liczby
- Konwersje (wysłane formularze, kliknięcia telefonu) to najważniejszy wskaźnik — zawsze je wyróżniaj
- Jeśli coś spada — wyjaśnij możliwą przyczynę
- Jeśli coś rośnie — podkreśl co na to wpłynęło
- Nie używaj emoji
- Krótkie akapity, konkretne zdania
- Kampanie wstrzymane (status PAUSED/wstrzymana) opisuj tylko jeśli miały wyniki — NIE sugeruj ich włączenia ani zmian w nich

=== FORMAT RAPORTU (trzymaj się go ściśle) ===

# Raport miesięczny — {client_name}
**Okres: {month_label}**

---

## 1. Wyniki Google Ads

[Tabela: Wskaźnik | Wartość — Wydatki, Kliknięcia, Wyświetlenia, CTR, Średni koszt kliknięcia, Konwersje łącznie, Koszt jednej konwersji]

[2-3 zdania komentarza — co te liczby oznaczają dla restauracji]

**Wyniki kampanii:**

[Tabela: Kampania | Wydatki (zł) | Kliknięcia | CTR | Konwersje | Koszt/konw.]

[Krótki komentarz do każdej kampanii]

---

## 2. Ruch na stronie — Google Analytics

[Tabela: Wskaźnik | Wartość — Użytkownicy, Sesje, Śr. czas wizyty, Współczynnik odrzuceń]

**Skąd przychodzili odwiedzający:**

[Tabela źródeł ruchu: Źródło | Sesje | Użytkownicy]

**Konwersje na stronie:**

[Tabela: Typ konwersji | Liczba — wyjaśnij każde zdarzenie prostym językiem, np. "Wysłanie formularza", "Kliknięcie telefonu". Posortuj od największej liczby.]

---

## 3. Podsumowanie i wnioski

**Co zadziałało najlepiej:**
[3 punkty z konkretnymi liczbami]

**Co wymaga uwagi:**
[2-3 punkty z wyjaśnieniem]

**Ogólna ocena:** [2-3 zdania podsumowania całego miesiąca. Wspomnij łączną liczbę konwersji z Google Ads i GA4 jako kluczowy wynik miesiąca.]

---

## 4. Plan na kolejny miesiąc

[5 punktów w formacie: **Działanie** — opis + krótkie uzasadnienie dlaczego]

---
*Raport wygenerowany automatycznie na podstawie danych z Google Ads i Google Analytics 4*
"""


def generate_report(prompt: str) -> str:
    """
    Generuje raport przy użyciu OpenAI API (gpt-4o-mini).
    """
    from openai import OpenAI

    client = OpenAI()  # używa zmiennej OPENAI_API_KEY

    system_prompt = (
        "Jesteś ekspertem marketingowym piszącym miesięczny raport dla właścicielki restauracji. "
        "Piszesz w języku polskim. Używasz prostego, ludzkiego języka — bez żargonu marketingowego. "
        "Formatujesz raport w Markdown: nagłówki ##, tabele, **pogrubienia** dla kluczowych liczb. "
        "Zawsze interpretujesz dane biznesowo — co dana liczba oznacza dla restauracji. "
        "Konwersje (formularze, telefony) traktujesz jako najważniejszy wskaźnik sukcesu. "
        "Nie używasz emoji. Piszesz konkretnie i zwięźle."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        max_tokens=4096,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    )

    return response.choices[0].message.content


# ---------------------------------------------------------------------------
# Krok 6 — Zapis raportu
# ---------------------------------------------------------------------------

def save_report(client_name: str, report_text: str) -> Path:
    """Zapisuje raport jako plik .md z datą w nazwie."""
    safe_name = client_name.replace(" ", "_").lower()
    month_str = date.today().strftime("%Y-%m")
    filename = f"raport_{safe_name}_{month_str}.md"
    path = Path("raporty") / filename
    path.parent.mkdir(exist_ok=True)
    path.write_text(report_text, encoding="utf-8")
    print(f"✅ Raport zapisany: {path}")
    return path


# ---------------------------------------------------------------------------
# Główna funkcja
# ---------------------------------------------------------------------------

def run(client_name: str) -> None:
    print(f"\n🔍 Weryfikacja konta: {client_name}")

    # 1. Weryfikacja
    ads_account = verify_google_ads_account(client_name)
    ga4_account = verify_ga4_account(client_name)

    if not ads_account and not ga4_account:
        print(f'\n❌ Nie znaleziono konta "{client_name}" w systemie.')
        print(
            "Sprawdź poprawność nazwy lub połączenie z API.\n"
            "Upewnij się, że:\n"
            "  - plik google-ads.yaml jest poprawnie skonfigurowany\n"
            "  - zmienna GOOGLE_APPLICATION_CREDENTIALS wskazuje na plik service account\n"
            "  - zmienna ANTHROPIC_API_KEY jest ustawiona"
        )
        sys.exit(1)

    print(f"✅ Google Ads: {ads_account['name'] if ads_account else 'nie znaleziono'}")
    print(f"✅ GA4:        {ga4_account['name'] if ga4_account else 'nie znaleziono'}")

    # 2. Zakres dat
    date_from, date_to = get_last_full_month()
    month_label = date.fromisoformat(date_from).strftime("%B %Y")
    print(f"📅 Okres: {month_label} ({date_from} — {date_to})")

    # 3. Pobieranie danych
    ads_data: dict = {}
    ga4_data: dict = {}

    if ads_account:
        print("📡 Pobieranie danych Google Ads...")
        try:
            ads_data = fetch_google_ads_data(
                ads_account["customer_id"], date_from, date_to
            )
            print(
                f"   Wydatki: {ads_data['totals']['cost_pln']} zł  |  "
                f"Kliknięcia: {ads_data['totals']['clicks']}  |  "
                f"Konwersje: {ads_data['totals']['conversions']}"
            )
        except Exception as e:
            print(f"⚠️  Błąd pobierania danych Google Ads: {e}")

    if ga4_account:
        print("📡 Pobieranie danych GA4...")
        try:
            ga4_data = fetch_ga4_data(
                ga4_account["property_id"], date_from, date_to
            )
            print(
                f"   Użytkownicy: {ga4_data['general']['users']}  |  "
                f"Sesje: {ga4_data['general']['sessions']}"
            )
        except Exception as e:
            print(f"⚠️  Błąd pobierania danych GA4: {e}")

    # 4. Budowanie promptu
    prompt = build_report_prompt(client_name, month_label, ads_data, ga4_data)

    # 5. Generowanie raportu
    print("🧠 Generowanie raportu przez Claude...")
    try:
        report_text = generate_report(prompt)
    except Exception as e:
        print(f"❌ Błąd generowania raportu: {e}")
        sys.exit(1)

    # 6. Zapis
    path = save_report(client_name, report_text)
    print(f"\n📄 Gotowe! Raport: {path}")
    print("\n" + "=" * 70)
    print(report_text)


if __name__ == "__main__":
    client = sys.argv[1] if len(sys.argv) > 1 else input("Podaj nazwę klienta: ").strip()
    if not client:
        print("❌ Nazwa klienta nie może być pusta.")
        sys.exit(1)
    run(client)
