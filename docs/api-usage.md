# API Usage & Free Tier

Particle Man is designed to stay within Google's free API tier by default. This page explains how usage is tracked and what to do if you approach your limits.

---

## Google's free tier limits

| API | Free calls per month |
|---|---|
| Air Quality API | 10,000 |
| Pollen API | 5,000 |

At the default 60-minute update interval, Particle Man makes:

- **2 AQ calls per poll** (current conditions + forecast) × 24 polls/day × 30 days = **1,440 AQ calls/month**
- **1 Pollen call per poll** × 24 polls/day × 30 days = **720 Pollen calls/month**

This is well within both limits, even at 15-minute intervals.

!!! tip
    If you have a paid Google Cloud plan with higher quotas, update the limits in **Configure → API Limits** so the warning thresholds match your actual plan.

---

## How usage tracking works

Particle Man tracks API calls locally using Home Assistant's persistent storage. It does **not** pull usage data from Google — Google doesn't expose actual quota consumption through the API key. The counts are a projection based on calls made since the last reset.

Two diagnostic sensors show this data:

- **AQ API Calls (Monthly)** — current count and projected end-of-period total
- **Pollen API Calls (Monthly)** — same for pollen

Each sensor's attributes include:

| Attribute | Description |
|---|---|
| `monthly_limit` | Your configured limit for this API |
| `projected_monthly` | Estimated calls by end of billing period at current rate |
| `pct_of_limit` | Percentage of limit used so far |
| `pct_projected` | Percentage of limit the projection will reach |
| `status` | `ok` / `warning` (≥80% projected) / `critical` (≥95% projected) |
| `tracking_period_start` | When the current tracking period started |

---

## Billing period reset

Usage resets on the **configured reset day** each month (default: the 1st). Change this in **Configure → API Limits → Billing period reset day** to match your actual Google billing cycle.

---

## Enforcing limits

By default, Particle Man keeps polling even if you approach your limit — it just shows a warning. If you enable **Enforce limits** in Configure, polling will automatically suspend when a limit is reached. Sensors will show unavailable until the next billing period or until you disable enforcement.

---

## Resetting counts manually

If your counts get out of sync (e.g. after migrating to a new HA instance), the simplest fix is to disable and re-enable the integration, which resets the persistent storage. Note this also resets `tracking_period_start` to today.
