# Configuration Reference

---

## Initial Setup

Shown when you first add the integration. These fields become the integration's identity and don't change unless you remove and re-add.

| Field | Description |
|---|---|
| API Key | Your Google Cloud API key with Air Quality, Pollen, and Weather APIs enabled |
| Latitude | Location latitude (pre-filled from your HA home address) |
| Longitude | Location longitude (pre-filled from your HA home address) |

---

## Options (Configure)

Accessed via the **Configure** button on the integration card after setup. Settings span up to six pages depending on which APIs you have enabled and whether enforce mode is on.

Saving options automatically reloads the integration with the new settings. API call counters are not reset on reload.

---

### Page 1 — Location & Limits

Set the location to monitor and whether to stay within Google's free tier.

| Option | Default | Description |
|---|---|---|
| Latitude | (from setup) | Location to monitor — can be changed here to move the integration without re-adding it |
| Longitude | (from setup) | Same as above |
| Stay within Google's free tier | On | When on, each API pauses automatically when its free monthly quota is reached. Turn off if you're on a paid plan or want to set your own limits on the last page |

---

### Page 2 — Data Sources

Choose which data to collect and how often to check for it.

| Option | Default | Description |
|---|---|---|
| Air Quality | On | AQI, pollutant levels, and forecasts |
| Pollen | On | Pollen index by type with forecasts and optional per-species detail |
| Weather | On | Current conditions, hourly and daily forecasts |
| Check every (minutes) | 60 | How often to fetch new data. 60 min works well for all three APIs within the free tier |

The page shows a projected monthly usage summary based on your current settings, so you can see the impact of your chosen interval alongside which APIs are enabled. A suggested minimum interval is calculated to keep all enabled APIs within their free quotas.

Disabling an API removes its sensors from HA on the next reload and stops counting calls for that service.

---

### Page 3 — Air Quality Options

*(Only shown if Air Quality is enabled)*

| Option | Default | Description |
|---|---|---|
| Forecast days | 5 | Days of forecast data (1 = today only, 5 = maximum) |
| Language | en | Language for pollutant names and health guidance (two-letter code: en, es, fr, etc.) |
| Add regional AQI sensor | Off | Show a country-specific AQI (e.g. US AQI) alongside the Universal AQI |
| Regional AQI standard | us_aqi | Which country's standard to use when the regional sensor is enabled |
| Include health guidance | Off | Adds per-population-group activity recommendations as attributes on AQI and pollen sensors |

**Supported regional AQI standards:**

| Code | Index |
|---|---|
| `us_aqi` | United States (EPA AQI) |
| `can_ec` | Canada (Environment Canada) |
| `gbr_defra` | United Kingdom (DEFRA) |
| `deu_uba` | Germany (UBA) |
| `fra_atmo` | France (ATMO) |
| `chn_mep` | China (MEP) |
| `ind_cpcb` | India (CPCB) |
| `jpn_caqi` | Japan (CAQI) |
| `mex_sedema` | Mexico (SEDEMA) |
| `nld_lki` | Netherlands (LKI) |
| `sgp_nea` | Singapore (NEA) |
| `kor_keco` | South Korea (KECO) |
| `esp_calidad` | Spain (Calidad) |

---

### Page 4 — Pollen Options

*(Only shown if Pollen is enabled)*

| Option | Default | Description |
|---|---|---|
| Individual plant species sensors | On | Creates a separate sensor for each plant in your area (Oak, Ragweed, etc.) — adds ~10–15 entities |
| Plant details | On | Adds family, genus, typical season, and cross-reactions as attributes on plant sensors |

---

### Page 5 — Weather Options

*(Only shown if Weather is enabled)*

| Option | Default | Description |
|---|---|---|
| Units | Metric | Units for temperature and wind in raw sensor values (Metric or Imperial). HA can convert for display independently |
| Weather alerts sensor | Off | Creates a sensor showing active weather warnings for your area. Shows 0 when no alerts are active |

---

### Page 6 — Custom Limits & Quiet Hours

*(Only shown when "Stay within Google's free tier" is turned OFF on Page 1)*

When enforce mode is off, you can set your own monthly limits and configure quiet hours. The page shows projected usage at your chosen interval to help you set sensible limits.

| Option | Default | Description |
|---|---|---|
| Air Quality limit | 5,000 | Maximum AQ checks per month before the API pauses |
| Pollen limit | 5,000 | Maximum Pollen checks per month |
| Weather limit | 10,000 | Maximum Weather checks per month |
| Pause overnight | Off | Skip all API fetches during a configured window |
| Pause from | 22:00 | Time to stop fetching data each day |
| Resume at | 06:00 | Time to resume. If earlier than "Pause from", the window spans midnight |

!!! tip
    Quiet hours work even in standard enforce mode — you can enable them under Custom Limits mode and then turn enforce back on. The quiet hours setting is preserved.

---

## Sensor Attributes

### AQI and Pollutant sensors

| Attribute | Description |
|---|---|
| `daily_forecast` | List of daily peak values up to configured forecast days. Each entry: `datetime`, `aqi` or `max`, `category` |
| `hourly_forecast` | List of hourly values up to 96 hours. Each entry: `datetime`, `aqi` or `value`, `category`, `epa_category` |
| `trend` | Direction based on hourly slope: `rising`, `falling`, or `stable` |

### Pollen sensors

| Attribute | Description |
|---|---|
| `daily_forecast` | List of daily forecast entries. Each entry: `datetime`, `index`, `category`, `color_hex` |
| `trend` | Direction based on today vs tomorrow: `up`, `down`, or `flat` |
| `expected_peak` | Forecast entry with the highest index value |

### Diagnostic sensors

| Attribute | Description |
|---|---|
| `monthly_limit` | Your configured limit for this API |
| `projected_monthly` | Estimated calls by end of billing period at current rate |
| `pct_of_limit` | Percentage of limit used so far |
| `pct_projected` | Percentage of limit the projection will reach |
| `status` | `ok` / `warning` (≥80% projected) / `critical` (≥95% projected) |
| `billing_period` | Current period in YYYY-MM format (Pacific Time) |
| `shared_total_calls` | Total across all entries using this API key this month |
| `locations_sharing_key` | Count of config entries using this API key |
