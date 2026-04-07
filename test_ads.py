"""Szybki test: pobiera kampanie z konta Google Ads po customer_id."""

from google.ads.googleads.client import GoogleAdsClient
from datetime import date
from dateutil.relativedelta import relativedelta

CUSTOMER_ID = "6411978603"  # DNNŻ_26 (bez myślników)

# Luty + marzec (do dziś)
today = date.today()
date_from = "2026-02-01"
date_to = str(today)

print(f"📅 Okres: {date_from} — {date_to}\n")

client = GoogleAdsClient.load_from_storage("google-ads.yaml")
service = client.get_service("GoogleAdsService")

query = f"""
    SELECT
        campaign.name,
        metrics.cost_micros,
        metrics.clicks,
        metrics.impressions,
        metrics.ctr,
        metrics.conversions,
        metrics.cost_per_conversion
    FROM campaign
    WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
      AND campaign.status = 'ENABLED'
    ORDER BY metrics.cost_micros DESC
"""

response = service.search(customer_id=CUSTOMER_ID, query=query)

print(f"{'Kampania':<40} {'Wydatki':>10} {'Kliknięcia':>11} {'CTR':>6} {'Konw.':>6}")
print("-" * 80)

total_cost = 0
total_clicks = 0
total_conv = 0.0

for row in response:
    cost = row.metrics.cost_micros / 1_000_000
    total_cost += cost
    total_clicks += row.metrics.clicks
    total_conv += row.metrics.conversions
    print(
        f"{row.campaign.name:<40} "
        f"{cost:>9.2f}zł "
        f"{row.metrics.clicks:>10} "
        f"{row.metrics.ctr*100:>5.2f}% "
        f"{row.metrics.conversions:>6.1f}"
    )

print("-" * 80)
print(f"{'RAZEM':<40} {total_cost:>9.2f}zł {total_clicks:>10}  {'':>6} {total_conv:>6.1f}")
