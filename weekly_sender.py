"""
Standalone weekly report sender — uruchamiany przez GitHub Actions cron
co poniedziałek rano.

Iteruje po wszystkich użytkownikach z Supabase. Dla każdego, kto włączył
flagę `auto_send_weekly` w konfiguracji, generuje raport tygodniowy
dla każdego klienta i wysyła emailem na adresy z `recipients`.

Wymaga env vars (te same co Streamlit Cloud):
- SUPABASE_URL
- SUPABASE_SERVICE_KEY
- ENCRYPTION_KEY
"""
import os
import sys
import json
import smtplib
import tempfile
import traceback
from datetime import date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from pathlib import Path

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import auth
from main import (
    fetch_google_ads_data,
    fetch_ga4_data,
    build_weekly_prompt,
    generate_report,
)
from report_html import report_to_html


def get_last_full_week() -> tuple[str, str]:
    """Poprzedni pełny tydzień pon–niedz."""
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    last_sunday = last_monday + timedelta(days=6)
    return str(last_monday), str(last_sunday)


def send_email(
    smtp_cfg: dict,
    to_email: str,
    subject: str,
    html_body: str,
    attachments: list[tuple[str, bytes, str]] = None,
) -> None:
    """attachments: lista (filename, content_bytes, mime_subtype)"""
    msg = MIMEMultipart("mixed")
    msg["From"] = smtp_cfg["smtp_user"]
    msg["To"] = to_email
    msg["Subject"] = subject

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(alt)

    for fname, content, subtype in attachments or []:
        att = MIMEApplication(content, _subtype=subtype)
        att.add_header("Content-Disposition", "attachment", filename=fname)
        msg.attach(att)

    with smtplib.SMTP(smtp_cfg["smtp_host"], int(smtp_cfg["smtp_port"]), timeout=30) as s:
        s.ehlo()
        s.starttls()
        s.login(smtp_cfg["smtp_user"], smtp_cfg["smtp_password"])
        s.send_message(msg)


def process_client(client: dict, recipients: list[str], smtp_cfg: dict,
                   logo_b64: str, logo_mime: str,
                   date_from: str, date_to: str, period_label: str) -> None:
    name = client.get("name", "?")
    print(f"  [{name}] generowanie raportu...")

    ads_data = {}
    ga4_data = {}

    if client.get("ads_customer_id"):
        try:
            ads_data = fetch_google_ads_data(client["ads_customer_id"], date_from, date_to)
        except Exception as exc:
            print(f"    Google Ads: błąd — {exc}")

    if client.get("ga4_property_id"):
        try:
            ga4_data = fetch_ga4_data(client["ga4_property_id"], date_from, date_to)
        except Exception as exc:
            print(f"    GA4: błąd — {exc}")

    if not ads_data and not ga4_data:
        print(f"    Brak danych — pomijam.")
        return

    prompt = build_weekly_prompt(
        name, period_label, ads_data, ga4_data,
        client.get("business_profile", ""),
    )
    report_text = generate_report(prompt)

    # Logo per-klient z fallbackiem na globalne
    client_logo_b64 = client.get("logo_b64") or logo_b64
    client_logo_mime = client.get("logo_mime") or logo_mime

    html_full = report_to_html(
        name, period_label, report_text, ads_data, ga4_data,
        client_logo_b64, client_logo_mime,
    )

    # Email body — uproszczona wersja HTML bez Plotly (gmail i tak blokuje JS)
    try:
        import markdown as _md
        body_simple = _md.markdown(report_text, extensions=["tables", "fenced_code"])
    except ImportError:
        import html as _html
        body_simple = "<pre>" + _html.escape(report_text) + "</pre>"

    email_html = f"""<html><body style="font-family:Arial;max-width:760px;margin:24px auto;color:#333">
<div style="background:linear-gradient(135deg,#1A3A5C,#E8630A);color:#fff;padding:24px;border-radius:10px;text-align:center">
<h1 style="margin:0">{name}</h1>
<p style="margin:6px 0 0;opacity:0.9">Raport tygodniowy &nbsp;|&nbsp; {period_label}</p>
</div>
{body_simple}
<hr style="margin-top:32px;border:none;border-top:1px solid #ddd">
<p style="font-size:0.85rem;color:#888">Pełna wersja z wykresami: zobacz załącznik <em>raport.html</em>.</p>
</body></html>"""

    safe_name = name.replace(" ", "_").lower()
    fname_html = f"raport_{safe_name}_{date_from}_html.html"
    fname_md = f"raport_{safe_name}_{date_from}.md"

    attachments = [
        (fname_html, html_full.encode("utf-8"), "html"),
        (fname_md, report_text.encode("utf-8"), "markdown"),
    ]

    sent = []
    for r in recipients:
        try:
            send_email(
                smtp_cfg, r,
                f"Raport tygodniowy — {name} — {period_label}",
                email_html, attachments,
            )
            sent.append(r)
        except Exception as exc:
            print(f"    Email do {r}: błąd — {exc}")
    if sent:
        print(f"    Wysłano do: {', '.join(sent)}")


def process_user(user_id: str, user_email: str) -> None:
    print(f"\n=== User {user_email} ({user_id}) ===")
    ud = auth.load_user_data(user_id)
    try:
        config = json.loads(ud.get("config_json") or "{}")
    except Exception as exc:
        print(f"  Niepoprawny config_json: {exc}")
        return

    if not config.get("auto_send_weekly"):
        print(f"  auto_send_weekly = False — pomijam.")
        return

    email_cfg = config.get("email", {})
    recipients = email_cfg.get("recipients", [])
    if not recipients:
        print(f"  Brak odbiorców — pomijam.")
        return
    if not (email_cfg.get("smtp_user") and email_cfg.get("smtp_password")):
        print(f"  Brak konfiguracji SMTP — pomijam.")
        return

    openai_key = ud.get("openai_key", "")
    if not openai_key:
        print(f"  Brak klucza OpenAI — pomijam.")
        return

    # Per-process env vars (skrypt jednostkowy, więc nadpisujemy)
    os.environ["OPENAI_API_KEY"] = openai_key

    gads_yaml = ud.get("gads_yaml", "")
    ga4_json = ud.get("ga4_json", "")

    gads_path = None
    ga4_path = None
    try:
        if gads_yaml:
            f = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8")
            f.write(gads_yaml)
            f.close()
            gads_path = f.name
            os.environ["GOOGLE_ADS_CONFIGURATION_FILE_PATH"] = gads_path
        if ga4_json:
            f = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
            f.write(ga4_json)
            f.close()
            ga4_path = f.name
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = ga4_path

        clients = config.get("clients", [])
        if not clients:
            print(f"  Brak klientów — pomijam.")
            return

        date_from, date_to = get_last_full_week()
        period_label = f"{date_from} – {date_to}"
        logo_b64 = config.get("logo_b64", "")
        logo_mime = config.get("logo_mime", "image/png")

        print(f"  Okres: {period_label}, klientów: {len(clients)}")

        for client in clients:
            try:
                process_client(client, recipients, email_cfg, logo_b64, logo_mime,
                               date_from, date_to, period_label)
            except Exception:
                print(f"  Błąd dla klienta {client.get('name','?')}:")
                traceback.print_exc()
    finally:
        for p in (gads_path, ga4_path):
            if p and os.path.exists(p):
                try:
                    os.unlink(p)
                except Exception:
                    pass


def main() -> None:
    print("Weekly report sender — start")

    for key in ("SUPABASE_URL", "SUPABASE_SERVICE_KEY", "ENCRYPTION_KEY"):
        if not os.environ.get(key):
            print(f"BŁĄD: brak env var {key}")
            sys.exit(1)

    sb = auth._sb()
    res = sb.table("users").select("id,email").execute()
    users = res.data or []
    print(f"Znaleziono {len(users)} użytkowników w bazie.")

    for u in users:
        try:
            process_user(u["id"], u["email"])
        except Exception:
            print(f"Błąd dla użytkownika {u.get('email','?')}:")
            traceback.print_exc()

    print("\nWeekly report sender — koniec.")


if __name__ == "__main__":
    main()
