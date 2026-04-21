# API Usage & Free Tier

Particle Man is designed to stay within Google's free API tier by default. This page explains how usage is tracked, what happens when you approach your limits, and how to check your current usage.

---

## Google's free tier limits

| API | Free calls per month |
|---|---|
| Air Quality API | 5,000 |
| Pollen API | 5,000 |
| Weather API | 10,000 |

Quotas reset at **midnight Pacific Time on the 1st of each month** — this is hardcoded to match Google's actual billing cycle.

---

## Calls per poll cycle

At each poll, Particle Man makes:

| API | Calls | Endpoints |
|---|---|---|
| Air Quality | 2 | current conditions + forecast |
| Pollen | 1 | daily forecast lookup |
| Weather | 3 | current conditions + hourly forecast + daily forecast |
| Weather (with alerts) | +1 | public alerts lookup |

### Monthly projections at common intervals

| Interval | AQ calls | Pollen calls | Weather calls | Free tier status |
|---|---|---|---|---|
| 60 min | 1,440 | 720 | 2,160 | ✓ All well within limits |
| 30 min | 2,880 | 1,440 | 4,320 | ✓ All within limits |
| 15 min | 5,760 | 2,880 | 8,640 | ✗ AQ exceeds limit; Weather near limit |

At 15-minute polling with all APIs enabled, the Air Quality API will exceed its 5,000/month free tier. Particle Man's enforce mode will pause the AQ API automatically, or you can increase the interval.

---

## Multiple locations

If you add more than one location, all entries using the same API key share the same monthly quota — Google bills per API key, not per location.

**Example:** Two locations at 60 min = 2 × 1,440 = 2,880 AQ calls/month — still within 5,000. But two locations at 30 min = 5,760 — over the AQ limit.

Particle Man tracks usage across all locations sharing an API key using a shared store. The diagnostic sensors show:

- **`shared_total_calls`** — combined calls across all entries using this API key this month
- **`locations_sharing_key`** — how many locations share this API key

When enforce mode is on, enforcement is based on the shared total. When the combined calls reach the limit, all entries using that API key pause that API for the remainder of the month.

The options flow shows projected monthly usage before you save, factoring in your number of locations.

---

## Viewing your current usage

1. Go to **Developer Tools → States** and search for `monthly`
2. Or navigate to the **Particle Man Diagnostics** device under **Settings → Devices & Services**

The three diagnostic sensors (`AQ API Calls (Monthly)`, `Pollen API Calls (Monthly)`, `Weather API Calls (Monthly)`) show:

| Attribute | What it means |
|---|---|
| **State** | Calls made so far this month |
| `projected_monthly` | Extrapolated to end of month at current rate |
| `pct_of_limit` | Percentage of your limit used so far |
| `pct_projected` | Percentage of your limit the projection will reach |
| `status` | `ok` (under 80%), `warning` (80–95%), `critical` (95%+) |
| `billing_period` | Current period in YYYY-MM format |
| `shared_total_calls` | Total across all entries sharing this API key |
| `locations_sharing_key` | Number of locations sharing this key |

---

## Enforce mode (default: on)

By default, Particle Man pauses each API when its monthly limit is reached. The other APIs continue normally — for example, if AQ hits its limit, weather and pollen keep updating.

When enforcement pauses an API, its sensors hold their last known value and a warning is written to the HA log. Enforcement resumes automatically at the start of the next billing period.

To turn off enforcement: **Configure → Polling & Limits → Stay within Google's free tier → off**. This switches to [custom limits mode](#custom-limits-mode).

---

## Custom limits mode

With enforce mode off, you can set your own monthly limits and quiet hours for each API.

**When to use this:**
- You're on a paid Google Cloud plan with higher quotas
- You want to split budget differently across multiple locations
- You want overnight quiet hours to stretch your monthly budget

### Quiet hours

Quiet hours pause all API fetches during a configured window — for example, 22:00–06:00. No data is fetched during this time; sensors hold their last known values.

Quiet hours work even in enforce mode — they're a separate mechanism for time-based pausing.

At 60-min polling with 8 hours of quiet time per day: you save ~16 polls/day × 2 AQ calls = 32 calls/day, or ~960 AQ calls/month.

---

## How the tracking works

Particle Man tracks API calls locally using Home Assistant's persistent storage. Counts survive restarts and options changes. The tracking period is keyed to the Pacific Time billing month — counts reset automatically when the month rolls over.

Particle Man does **not** pull usage data from Google — Google doesn't expose actual quota consumption through the API key. The counts are based on calls made by this integration.

If counts get out of sync (e.g. after migrating to a new HA instance), remove and re-add the integration to reset tracking.
