"""
Generator miesięcznych raportów marketingowych.
Pobiera dane z Google Ads i Google Analytics 4, następnie generuje
raport w języku polskim przy użyciu Claude API.

Użycie:
    python main.py "Nazwa Klienta"
    python main.py  # pyta o nazwę interaktywnie
"""

import os
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

    yaml_path = os.environ.get("GOOGLE_ADS_CONFIGURATION_FILE_PATH", "google-ads.yaml")
    client = GoogleAdsClient.load_from_storage(yaml_path)
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
    lines = [
        "| Kampania | Wyświetlenia | Kliknięcia | CTR% | Śr. CPC (zł) | Konwersje | Koszt/konw. (zł) | Wydatki (zł) |",
        "|----------|-------------|------------|------|--------------|-----------|------------------|--------------|",
    ]
    for c in campaigns:
        lines.append(
            f"| {c['name']} | {c['impressions']:,} | {c['clicks']:,} | "
            f"{c['ctr_pct']} | {c['avg_cpc_pln']} | {c['conversions']} | "
            f"{c['cost_per_conversion_pln']} | {c['cost_pln']} |"
        )
    return "\n".join(lines)


def _format_sources_table(sources: list[dict]) -> str:
    if not sources:
        return "Brak danych o źródłach ruchu."
    total_sessions = sum(s["sessions"] for s in sources) or 1
    lines = [
        "| Kanał | Sesje | Udział % | Użytkownicy |",
        "|-------|-------|----------|-------------|",
    ]
    for s in sources:
        share = round(s["sessions"] / total_sessions * 100, 1)
        lines.append(f"| {s['channel']} | {s['sessions']:,} | {share}% | {s['users']:,} |")
    return "\n".join(lines)


def build_report_prompt(
    client_name: str,
    month_label: str,
    ads_data: dict,
    ga4_data: dict,
    business_profile: str = "",
) -> str:
    """Buduje prompt użytkownika do generowania raportu."""

    profile_section = ""
    if business_profile.strip():
        profile_section = (
            "\n=== PROFIL DZIAŁALNOŚCI KLIENTA (kluczowe — używaj jako kontekst) ===\n"
            f"{business_profile.strip()}\n"
        )

    ads_section = "Brak danych Google Ads (konto nie zostało znalezione)."
    kpi_ads_rows = ""
    campaigns_table_md = ""
    if ads_data:
        t = ads_data["totals"]
        avg_cpc = round(t["cost_pln"] / t["clicks"], 2) if t["clicks"] else 0
        conv_rate = round(t["conversions"] / t["clicks"] * 100, 2) if t["clicks"] else 0
        campaigns_table_md = _format_campaigns_table(ads_data.get("campaigns", []))
        ads_section = f"""Wyświetlenia: {t['impressions']:,}
Kliknięcia: {t['clicks']:,}
CTR: {t['ctr_pct']}%
Średni CPC: {avg_cpc} zł
Łączne wydatki: {t['cost_pln']} zł
Konwersje: {t['conversions']}
Koszt za konwersję: {t['cost_per_conversion_pln']} zł
Współczynnik konwersji: {conv_rate}%

Wyniki per kampania:
{campaigns_table_md}"""
        kpi_ads_rows = (
            f"| Wyświetlenia (Google Ads) | {t['impressions']:,} |\n"
            f"| Kliknięcia | {t['clicks']:,} |\n"
            f"| CTR | {t['ctr_pct']}% |\n"
            f"| Średni CPC | {avg_cpc} zł |\n"
            f"| Wydatki łącznie | {t['cost_pln']} zł |\n"
            f"| Konwersje (Google Ads) | {t['conversions']} |\n"
            f"| Koszt konwersji | {t['cost_per_conversion_pln']} zł |\n"
            f"| Współczynnik konwersji | {conv_rate}% |\n"
        )

    ga4_section = "Brak danych Google Analytics 4 (konto nie zostało znalezione)."
    sources_table_md = ""
    kpi_ga4_rows = ""
    if ga4_data:
        g = ga4_data["general"]
        sources_table_md = _format_sources_table(ga4_data.get("sources", []))
        conv_events = ga4_data.get("conversion_events", [])
        conv_lines = "\n".join(
            f"  - {e['event']}: {e['conversions']} konwersji ({e['count']} zdarzeń)"
            for e in conv_events
        ) if conv_events else "  Brak zarejestrowanych konwersji."
        engagement = round(100 - g["bounce_rate_pct"], 1)
        dur = g["avg_session_duration_sec"]
        dur_label = f"{dur//60}m {dur%60}s"
        ga4_section = f"""Użytkownicy: {g['users']:,}
Sesje: {g['sessions']:,}
Współczynnik odrzuceń: {g['bounce_rate_pct']}%
Współczynnik zaangażowania: {engagement}%
Średni czas wizyty: {dur} sekund ({dur_label})
Konwersje GA4: {g.get('conversions', 0)}

Źródła ruchu:
{sources_table_md}

Konwersje per zdarzenie (KLUCZOWE — uwzględnij w raporcie):
{conv_lines}"""
        kpi_ga4_rows = (
            f"| Użytkownicy strony | {g['users']:,} |\n"
            f"| Sesje | {g['sessions']:,} |\n"
            f"| Średni czas wizyty | {dur_label} |\n"
            f"| Współczynnik zaangażowania | {engagement}% |\n"
            f"| Współczynnik odrzuceń | {g['bounce_rate_pct']}% |\n"
            f"| Konwersje GA4 | {g.get('conversions', 0)} |\n"
        )

    kpi_table_md = (
        "| Wskaźnik | Wartość |\n"
        "|----------|---------|\n"
        f"{kpi_ads_rows}{kpi_ga4_rows}"
    ) if (kpi_ads_rows or kpi_ga4_rows) else "_Brak danych do wygenerowania tabeli wskaźników._"

    return f"""Wygeneruj profesjonalny raport miesięczny na podstawie poniższych danych.

KLIENT: {client_name}
OKRES: {month_label}
{profile_section}
=== GOOGLE ADS ===
{ads_section}

=== GOOGLE ANALYTICS 4 ===
{ga4_section}

=== ZASADY PISANIA ===
- Pisz po polsku, językiem profesjonalnym ale zrozumiałym — odbiorca to właściciel firmy bez wiedzy technicznej
- DOSTOSUJ ton, terminologię, przykłady i interpretacje do branży klienta opisanej w PROFILU DZIAŁALNOŚCI powyżej. Nigdy nie zakładaj branży na podstawie nazw kampanii — bazuj wyłącznie na profilu
- Styl analityczny: opisuj działania, interpretuj wyniki, wyciągaj wnioski biznesowe odpowiednie dla branży klienta
- Używaj **pogrubień** dla kluczowych liczb i wniosków
- Konwersje (formularze, kliknięcia w telefon, transakcje, zapisy — w zależności od branży klienta) to najważniejszy wskaźnik — zawsze je wyróżniaj z konkretnymi liczbami
- Jeśli kampania była uruchomiona w trakcie miesiąca — zaznacz to (np. "kampania uruchomiona 13 marca")
- Kampanie, które miały aktywność ale są wstrzymane — opisuj ich wyniki, NIE sugeruj zmian w nich
- Jeśli coś spada — wyjaśnij możliwą przyczynę i co zostało zrobione w odpowiedzi
- Jeśli coś rośnie — podkreśl co na to wpłynęło
- Nie używaj emoji

=== FORMAT RAPORTU (trzymaj się go ściśle, NIE pomijaj żadnej sekcji ani tabeli) ===

## 1. Kluczowe wskaźniki — {month_label}

[Wstaw DOKŁADNIE poniższą tabelę bez zmian — to jest źródło prawdy dla całego raportu:]

{kpi_table_md}

[Pod tabelą dopisz krótki, 2–3 zdaniowy komentarz interpretujący wskaźniki w kontekście branży klienta.]

## 2. Realizacja strategii i wyniki kampanii

[Akapit 1 — ogólne podsumowanie miesiąca: jakie działania prowadzono, jak wskaźniki przekładają się na cele biznesowe firmy klienta. Uwzględnij specyfikę branży z PROFILU DZIAŁALNOŚCI. Nie powtarzaj liczb z tabeli wskaźników — interpretuj je.]

[Akapit 2 — wskaż kluczowe typy konwersji z liczbami, dopasowane do branży klienta (np. dla e-commerce: transakcje; dla usług lokalnych: formularze i telefony; dla SaaS: rejestracje; dla deweloperów: zapytania o ofertę i umówione spotkania).]

## 3. Porównanie efektywności kampanii

[Wstaw DOKŁADNIE poniższą tabelę bez zmian:]

{campaigns_table_md}

[Pod tabelą — dla każdej kampanii 2–3 zdania komentarza: ocena skuteczności, co wpłynęło na wyniki, czy działa zgodnie z planem. Opisuj tylko kampanie które miały aktywność.]

## 4. Analiza źródeł ruchu na stronie

[Wstaw DOKŁADNIE poniższą tabelę bez zmian:]

{sources_table_md}

[Pod tabelą — akapit o głównych źródłach ruchu: które kanały dominują, jaka jest jakość ruchu (czas na stronie, zaangażowanie). Odnieś ruch do kampanii. Jeśli są dane o konwersjach per zdarzenie GA4 — wymień je z liczbami.]

## 5. Wnioski i rekomendacje

[3–4 punkty wniosków — co działa, co wymaga poprawy, jakie są ryzyka.]

## 6. Plan na kolejny miesiąc

[5 konkretnych punktów — każdy: **Działanie:** opis → uzasadnienie w jednym zdaniu. Działania mają być adekwatne do branży klienta.]

---
*Raport przygotowany na podstawie danych z Google Ads i Google Analytics 4 za {month_label}*
"""


def generate_report(prompt: str) -> str:
    """
    Generuje raport przy użyciu OpenAI API (gpt-4o-mini).
    """
    from openai import OpenAI

    client = OpenAI()  # używa zmiennej OPENAI_API_KEY

    system_prompt = (
        "Jesteś doświadczonym specjalistą Google Ads i Analytics piszącym raport marketingowy. "
        "Raporty piszesz po polsku, językiem analitycznym i profesjonalnym, zrozumiałym dla właściciela firmy bez wiedzy technicznej. "
        "DOSTOSOWUJESZ ton, terminologię, przykłady i interpretacje do branży klienta — zawsze opieraj się na sekcji PROFIL DZIAŁALNOŚCI w prompcie użytkownika. "
        "Nie używaj nazw branż ani przykładów spoza tego profilu (np. nie pisz o restauracji, jeśli klient jest e-commerce). "
        "Styl wzorcowy: 'W marcu działania reklamowe zostały rozszerzone o nową kampanię. "
        "Kampanie wygenerowały X kliknięć oraz Y konwersji przy współczynniku konwersji Z%.'. "
        "Zawsze podajesz konkretne liczby. Interpretujesz dane biznesowo w kontekście branży klienta. "
        "Konwersje (formularze, kliknięcia w telefon, transakcje, zapisy — zależnie od branży) to kluczowe wskaźniki — zawsze je wyróżniasz. "
        "Formatujesz w Markdown z nagłówkami ## i **pogrubieniami**. Nie używasz emoji."
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
