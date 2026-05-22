"""
Pobieranie danych kampanii z Meta Marketing API.

Logika rozróżniania kampanii:
- objective == LEAD_GENERATION  →  formularz błyskawiczny: zwraca leads + CPL + spend
- pozostałe cele               →  standardowe: spend, impressions, clicks, CTR
"""

import time
import requests


def list_meta_ad_accounts(access_token: str) -> list[dict]:
    """
    Zwraca listę dostępnych kont reklamowych dla danego tokenu.
    Każdy element: {"id" (act_XXX), "account_id" (XXX), "name", "account_status"}
    account_status: 1=ACTIVE, 2=DISABLED, 3=UNSETTLED, 7=PENDING_RISK_REVIEW, 9=IN_GRACE_PERIOD
    """
    url = "https://graph.facebook.com/v22.0/me/adaccounts"
    params = {
        "access_token": access_token,
        "fields": "id,account_id,name,account_status",
        "limit": 100,
    }
    return _fetch_all_pages(url, params)


def list_meta_campaigns(ad_account_id: str, access_token: str) -> list[dict]:
    """
    Zwraca listę wszystkich kampanii na koncie reklamowym.
    Każdy element: {"id", "name", "status", "objective"}
    """
    url = f"https://graph.facebook.com/v22.0/{ad_account_id}/campaigns"
    params = {
        "access_token": access_token,
        "fields": "id,name,status,objective",
        "limit": 100,
    }
    return _fetch_all_pages(url, params)


def fetch_meta_campaign_data(
    ad_account_id: str,
    date_from: str,
    date_to: str,
    access_token: str,
    campaign_ids: list[str] | None = None,
) -> dict:
    """
    Pobiera dane per kampania z Insights API.

    Zwraca:
    {
        "lead_campaigns":  [{"name", "leads", "spend", "cpl"}, ...],
        "other_campaigns": [{"name", "spend", "impressions", "clicks", "ctr_pct"}, ...],
        "lead_totals":     {"leads", "spend", "cpl"},
        "other_totals":    {"spend", "impressions", "clicks"},
    }
    """
    url = f"https://graph.facebook.com/v22.0/{ad_account_id}/insights"
    params = {
        "access_token": access_token,
        "level": "campaign",
        "fields": (
            "campaign_id,campaign_name,objective,spend,"
            "impressions,clicks,ctr,"
            "actions,cost_per_action_type"
        ),
        "time_range": f'{{"since":"{date_from}","until":"{date_to}"}}',
        "limit": 100,
    }

    campaigns_raw = _fetch_all_pages(url, params)

    if campaign_ids:
        campaigns_raw = [c for c in campaigns_raw if c.get("campaign_id") in campaign_ids]

    lead_campaigns = []
    other_campaigns = []

    for c in campaigns_raw:
        spend = float(c.get("spend", 0))
        name = c.get("campaign_name", "")

        if c.get("objective") == "LEAD_GENERATION":
            leads = _extract_action_value(c.get("actions", []), "lead")
            cpl = _extract_action_value(c.get("cost_per_action_type", []), "lead", as_float=True)
            if not cpl and leads:
                cpl = round(spend / leads, 2)
            lead_campaigns.append({
                "name": name,
                "leads": leads,
                "spend": round(spend, 2),
                "cpl": round(cpl, 2),
            })
        else:
            other_campaigns.append({
                "name": name,
                "spend": round(spend, 2),
                "impressions": int(c.get("impressions", 0)),
                "clicks": int(c.get("clicks", 0)),
                "ctr_pct": round(float(c.get("ctr", 0)) * 100, 2),
            })

    lead_totals = {
        "leads": sum(c["leads"] for c in lead_campaigns),
        "spend": round(sum(c["spend"] for c in lead_campaigns), 2),
    }
    lead_totals["cpl"] = (
        round(lead_totals["spend"] / lead_totals["leads"], 2)
        if lead_totals["leads"] else 0.0
    )

    other_totals = {
        "spend": round(sum(c["spend"] for c in other_campaigns), 2),
        "impressions": sum(c["impressions"] for c in other_campaigns),
        "clicks": sum(c["clicks"] for c in other_campaigns),
    }

    return {
        "lead_campaigns": lead_campaigns,
        "other_campaigns": other_campaigns,
        "lead_totals": lead_totals,
        "other_totals": other_totals,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_all_pages(url: str, params: dict) -> list:
    results = []
    next_url: str | None = url
    next_params: dict = params

    while next_url:
        resp = _get_with_retry(next_url, next_params)
        body = resp.json()
        results.extend(body.get("data", []))
        next_url = body.get("paging", {}).get("next")
        next_params = {}

    return results


def _get_with_retry(url: str, params: dict, max_attempts: int = 3) -> requests.Response:
    for attempt in range(max_attempts):
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            wait = int(resp.headers.get("Retry-After", 60))
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp  # unreachable, satisfies type checker


def _extract_action_value(actions: list, action_type: str, as_float: bool = False):
    for a in actions:
        if a.get("action_type") == action_type:
            return float(a["value"]) if as_float else int(a["value"])
    return 0.0 if as_float else 0
