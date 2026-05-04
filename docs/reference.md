# Reference

---

## How data updates

Particle Man polls Google's APIs on a schedule and enforces monthly quotas to keep usage within Google's free tier.

### API calls per poll

| API | Calls per poll | Endpoints hit |
|---|---|---|
| Air Quality | 2 | current conditions + forecast |
| Pollen | 1 | daily forecast lookup |
| Weather | 3 | current conditions + hourly + daily forecast |
| Weather alerts (optional) | +1 | public alerts lookup |

### Polling cadence

**Air Quality and Pollen** are fetched at most once per hour, matching Google's own data refresh rate. Polling faster would return the same data. At 7+ locations they scale automatically — see [Automagic interval calculation](#automagic-interval-calculation) below.

**Weather** uses either the Automagic-calculated interval or a manually configured one.

### Automagic interval calculation

Automagic mode computes the minimum safe polling interval — the shortest interval that keeps total calls within the monthly limit over the billing period.

**Inputs:**

| Input | Source | Example |
|---|---|---|
| `calls_per_poll` | Fixed per API (weather = 3 or 4) | 4 (alerts on) |
| `num_locations` | Number of configured locations | 2 |
| `monthly_limit` | Google free tier or custom | 10,000 |
| `billing_month_days` | Actual days in current month (Pacific Time) | 31 |
| `active_minutes_per_month` | `billing_month_days × 24 × 60` minus quiet hours | 33,480 |
| `safety_buffer` | Fixed 5% | 1.05 |

**Formula:**

```
safe_interval_minutes = ⌈ active_minutes × calls_per_poll × num_locations × 1.05 / monthly_limit ⌉
```

Floored at 15 minutes. If the result would be less than 15, 15 is used.

**Example** — 2 locations, alerts on (4 calls/poll), 10,000 weather limit, May (31 days), quiet hours 23:00–05:00 (18 active hours/day):

```
active_minutes = 31 × 18 × 60 = 33,480
safe_interval  = ⌈ 33,480 × 4 × 2 × 1.05 / 10,000 ⌉ = ⌈ 28.1 ⌉ = 29 min
```

**Where to see the live assumptions:**

Open any of the three monthly usage diagnostic sensors (**Monthly AQ Calls**, **Monthly Pollen Calls**, **Monthly Weather Calls**) in **Developer Tools → States**. The attributes include every input used in the current calculation:

```
automagic_mode: true
num_locations: 2
calls_per_poll: 4
fetch_interval_minutes: 29
quiet_hours_enabled: true
quiet_hours_window: 23:00–05:00
active_hours_per_day: 18.0
billing_month_days: 31
effective_minutes_per_month: 33480
safety_buffer_pct: 5
days_remaining: 14
calls_per_day: 58.3
```

### Monthly usage at common intervals (1 location, all APIs, 31-day month, no quiet hours)

| Interval | AQ calls | Pollen calls | Weather calls | Status |
|---|---|---|---|---|
| 60 min | 1,488 | 744 | 2,232 | ✅ All within free tier |
| 30 min | 2,976 | 1,488 | 4,464 | ✅ All within free tier |
| 15 min | 5,952 | 2,976 | 8,928 | ❌ AQ exceeds 10k limit |

Free tier limits: [Air Quality](https://developers.google.com/maps/documentation/air-quality/usage-and-billing) (10,000/mo), [Pollen](https://developers.google.com/maps/documentation/pollen/usage-and-billing) (5,000/mo), [Weather](https://developers.google.com/maps/documentation/weather/usage-and-billing) (10,000/mo).

### Quota behavior

When an API reaches its monthly limit, Particle Man pauses **only that API**. Other APIs continue normally. Tracking resets automatically on the 1st of the month (midnight Pacific Time).

### Quota tracking

Particle Man tracks API calls locally using HA's persistent storage — it does not pull usage data from Google. Counts survive restarts and option changes.

If counts get out of sync (e.g. after migrating to a new HA instance), remove and re-add the integration to reset tracking.

---

## Level scales and sources

The four advisory/severity scales used by Particle Man sensors — air quality categories, pollen levels, UV index, and weather alert severity — come from different sources. Details below.

### Air Quality category scale

**Sensor:** Air Quality Advisory — state is the raw category text returned by Google.

**Source:** Google uses the same six category names as the [US EPA AQI](https://www.airnow.gov/aqi/aqi-basics/). The categories are also consistent with the WHO UAQI framework.

| Category | AQI range | PM2.5 (μg/m³, 24-h avg)* |
|---|---|---|
| Good | 0–50 | 0.0–9.0 |
| Moderate | 51–100 | 9.1–35.4 |
| Unhealthy for Sensitive Groups | 101–150 | 35.5–55.4 |
| Unhealthy | 151–200 | 55.5–125.4 |
| Very Unhealthy | 201–300 | 125.5–225.4 |
| Hazardous | 301–500 | ≥ 225.5 |

*PM2.5 breakpoints use the [2024 EPA NAAQS revision](https://www.epa.gov/criteria-air-pollutants/naaqs-table). Other pollutants (PM10, O3, NO2, CO, SO2) follow current EPA NAAQS breakpoints. Google derives its Universal AQI category from the dominant pollutant's concentration.

**Alignment note:** Google's category boundary *names* match EPA AQI exactly. The underlying index score uses Google's proprietary UAQI formula, which may assign different numeric values than raw EPA AQI — but the category text returned by the API (and exposed as the sensor state) is identical to EPA terminology.

The per-pollutant sensors (PM2.5, PM10, O3, etc.) under the Air Quality section also expose an `epa_category` attribute, calculated locally from the EPA breakpoints above.

---

### Pollen level scale

**Sensors:** Pollen Advisory, individual plant species sensors — state is one of six levels.

**Source:** [Google Universal Pollen Index (UPI)](https://developers.google.com/maps/documentation/pollen/pollen-index). Google returns an integer index (0–5) per plant type; the integration maps it to the label below.

| Index | Level |
|---|---|
| 0 | None |
| 1 | Very Low |
| 2 | Low |
| 3 | Moderate |
| 4 | High |
| 5 | Very High |

Google does not publish fixed concentration thresholds for the UPI levels — the index is calculated from a proprietary model combining pollen concentration models, historical data, and regional plant phenology.

---

### UV Index category scale

**Sensor:** UV Index Category — state is calculated locally from the raw UV index value returned by the Weather API.

**Source:** [WHO Global Solar UV Index](https://www.who.int/news-room/questions-and-answers/item/radiation-the-ultraviolet-(uv)-index), adopted by WMO, UNEP, and national health agencies worldwide.

| Category | UV Index |
|---|---|
| Low | 0–2 |
| Moderate | 3–5 |
| High | 6–7 |
| Very High | 8–10 |
| Extreme | 11+ |

The raw UV index value is available as the `uv_index` attribute on the UV Index Category sensor, and also directly on the weather entity.

---

### Weather alert severity scale

**Sensor:** Alert Highest Severity — state is one of four levels.

**Source:** [Google Public Alerts](https://developers.google.com/maps/documentation/weather/get-public-alerts), which aggregates alerts from government meteorological agencies (e.g., NWS in the US). Severity is returned directly by the API.

| Severity | Meaning |
|---|---|
| MINOR | Minimal or no known threat |
| MODERATE | Possible threat to life or property |
| SEVERE | Significant threat to life or property |
| EXTREME | Extraordinary threat to life or property |

`None` is the state when no active alerts are present.

---

## Known limitations

- **Pollen API coverage:** primarily North America and Europe. Outside covered regions, pollen sensors remain unavailable. ([Coverage map](https://developers.google.com/maps/documentation/pollen/coverage))
- **Weather API coverage:** varies by region. ([Coverage](https://developers.google.com/maps/documentation/weather/coverage))
- **Weather alerts:** only available in regions covered by Google's public alerts service, primarily the US.
- **Local AQI indices are region-specific:** US EPA AQI values are only valid for US coordinates; other regional standards apply only in their respective countries.
- **API call counts are estimated locally:** counts are based on calls made by this integration and may diverge from Google's actual billing counter after migration, reinstall, or key sharing across multiple HA instances.
- **Multiple locations share the monthly quota:** all locations using the same API key count against the same free tier limit. Automagic mode factors this in when suggesting the minimum interval.
- **Minimum polling interval:** 15 minutes, enforced by the integration.
- **AQ data refreshes hourly:** polling faster than 60 minutes fetches the same data with no improvement in freshness.
- **Plant species availability depends on location:** not all covered regions have species-level pollen data.

---

## Troubleshooting

### Pollen sensors are unavailable or missing

**Cause:** Google's Pollen API doesn't cover all countries.

1. Check HA logs (**Settings → System → Logs**) for a line containing `Pollen API fetch failed`
2. If the error indicates a coverage issue, pollen sensors won't be available at your location — this is a limitation of the upstream API
3. If the error indicates an authentication problem, verify your API key has the Pollen API enabled ([Google Cloud Console](https://console.cloud.google.com/apis/credentials))
4. If pollen should be available in your region but sensors are missing, try removing and re-adding the integration

([Pollen API coverage](https://developers.google.com/maps/documentation/pollen/coverage))

---

### All sensors show unavailable (400 or 403 errors)

**Cause:** API key issue or API not enabled.

1. Open the [Google Cloud Console](https://console.cloud.google.com/apis/credentials) and confirm **Air Quality API**, **Pollen API**, and **Weather API** are all enabled
2. Confirm the API key is associated with the correct project
3. Check that the key has no restrictions blocking your HA server's IP or referrer
4. If the key was just created, wait a few minutes — Google can take time to propagate new keys

---

### Weather entity or sensors are missing

**Cause:** Weather API not enabled on the API key, or the Weather option was disabled in Configure.

1. Verify the **Weather API** is enabled in the [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. In HA, go to **Settings → Devices & Services → Particle Man → Configure** and confirm **Weather** is toggled on
3. Check HA logs for `Weather API fetch failed`

---

### Sensors show stale data

**Cause:** API errors or long polling interval.

1. Check the **Last API Update** diagnostic sensor — if it hasn't updated recently, check logs for API errors
2. Check **Configure → Polling & Limits** to confirm the polling interval is what you expect
3. If enforce mode paused an API, the diagnostic sensors will show `critical` status and the HA log will note the pause

---

### API usage counts seem wrong

**Cause:** Counts are estimated locally, not from Google's billing.

Counts diverge when:
- The integration was removed and re-added mid-period
- HA was migrated to a new instance
- The same API key is used in multiple HA instances

To reset: remove and re-add the integration. This clears persistent storage and restarts tracking from today.

---

### Integration doesn't appear after installation

**Cause:** Custom integrations require a restart to load.

Restart Home Assistant after installing via HACS or copying files manually.

---

### Configure changes don't take effect

**Cause:** Integration didn't reload after saving.

After saving options, the integration card should briefly show "reloading." If it doesn't, manually reload via the three-dot menu on the integration card.

---

### Something else

Open an issue on [GitHub](https://github.com/mnestrud/particle-man/issues) with your HA version, integration version, and the relevant section from **Settings → System → Logs**.
