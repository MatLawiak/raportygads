"""
Pobieranie danych kampanii z Meta Marketing API.

Logika rozróżniania kampanii:
- cele lead-genowe (LEAD_GENERATION / OUTCOME_LEADS)
  lub kampanie z faktycznymi leadami → formularz błyskawiczny: leads + CPL + spend
- pozostałe cele → standardowe: spend, impressions, clicks, CTR
"""

import time
import requests

# Cele kampanii klasyfikowane jako lead-generation
LEAD_OBJECTIVES = {"LEAD_GENERATION", "OUTCOME_LEADS"}

# Action types, które liczymy jako pozyskany lead (formularz błyskawiczny)
LEAD_ACTION_TYPES = {"lead", "onsite_conversion.lead_grouped"}


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
        objective = c.get("objective", "")
        actions = c.get("actions", [])
        leads = _sum_action_values(actions, LEAD_ACTION_TYPES)

        # Kampania jest klasyfikowana jako lead-generation jeśli:
        # - ma cel lead-genowy (LEAD_GENERATION / OUTCOME_LEADS)
        # - lub faktycznie pozyskała leady (action_type: lead)
        is_lead_campaign = objective in LEAD_OBJECTIVES or leads > 0

        if is_lead_campaign:
            cpl = _sum_action_values(
                c.get("cost_per_action_type", []), LEAD_ACTION_TYPES, as_float=True
            )
            if not cpl and leads:
                cpl = spend / leads
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
                # Meta API zwraca CTR już w procentach — NIE mnożymy przez 100
                "ctr_pct": round(float(c.get("ctr", 0)), 2),
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


def _sum_action_values(actions: list, action_types: set, as_float: bool = False):
    """Sumuje wartości dla wszystkich pasujących action_type (np. lead + onsite_conversion.lead_grouped)."""
    total = 0.0
    for a in actions:
        if a.get("action_type") in action_types:
            try:
                total += float(a.get("value", 0))
            except (TypeError, ValueError):
                continue
    return total if as_float else int(total)
