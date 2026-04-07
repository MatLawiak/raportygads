"""Szybki test: pobiera dane ruchu z GA4 po property_id."""

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, DateRange, Dimension, Metric, OrderBy
)
from datetime import date
from dateutil.relativedelta import relativedelta

PROPERTY_ID = "522059373"  # DNNŻ_26

# Luty + marzec (do dziś)
today = date.today()
date_from = "2026-02-01"
date_to = str(today)

print(f"📅 Okres: {date_from} — {date_to}\n")

client = BetaAnalyticsDataClient()

# Metryki ogólne
overview = client.run_report(RunReportRequest(
    property=f"properties/{PROPERTY_ID}",
    date_ranges=[DateRange(start_date=date_from, end_date=date_to)],
    metrics=[
        Metric(name="totalUsers"),
        Metric(name="sessions"),
        Metric(name="bounceRate"),
        Metric(name="averageSessionDuration"),
        Metric(name="conversions"),
    ],
))

row = overview.rows[0].metric_values
print("📊 OGÓLNE STATYSTYKI")
print(f"  Użytkownicy:          {int(row[0].value)}")
print(f"  Sesje:                {int(row[1].value)}")
print(f"  Współczynnik odrzuceń: {round(float(row[2].value)*100, 1)}%")
print(f"  Śr. czas wizyty:      {round(float(row[3].value))} sek")
print(f"  Konwersje:            {int(row[4].value)}")

# Źródła ruchu
traffic = client.run_report(RunReportRequest(
    property=f"properties/{PROPERTY_ID}",
    date_ranges=[DateRange(start_date=date_from, end_date=date_to)],
    dimensions=[Dimension(name="sessionDefaultChannelGroup")],
    metrics=[Metric(name="sessions"), Metric(name="totalUsers")],
    order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="sessions"), desc=True)],
))

print("\n🔀 ŹRÓDŁA RUCHU")
print(f"  {'Kanał':<30} {'Sesje':>6} {'Użytkownicy':>12}")
print("  " + "-" * 52)
for r in traffic.rows:
    print(f"  {r.dimension_values[0].value:<30} {int(r.metric_values[0].value):>6} {int(r.metric_values[1].value):>12}")
