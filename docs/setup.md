# Setup

---

## Prerequisites

- [Google Cloud account](https://console.cloud.google.com/) (free tier is sufficient)
- Google Cloud API key with the following APIs enabled:
    - [Air Quality API](https://developers.google.com/maps/documentation/air-quality/overview)
    - [Pollen API](https://developers.google.com/maps/documentation/pollen/overview)
    - [Weather API](https://developers.google.com/maps/documentation/weather/overview)
- Home Assistant 2025.1.0 or later

See [Google Maps Platform pricing](https://developers.google.com/maps/billing-and-pricing/pricing#environment-pricing) for free tier limits.

---

## Get an API key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Go to **APIs & Services → Library**
4. Search for and enable each of: **Air Quality API**, **Pollen API**, **Weather API**
5. Go to **APIs & Services → [Credentials](https://console.cloud.google.com/apis/credentials) → Create Credentials → API key**
6. Copy the key

!!! tip
    For home use, an unrestricted key is fine. To restrict it, allow HTTP referrers or the IP address of your HA server.

---

## Install

=== "HACS (recommended)"

    1. Open HACS in Home Assistant
    2. Go to **Integrations → Explore & Download Repositories**
    3. Search for **Particle Man** and click **Download**
    4. Restart Home Assistant

=== "Manual"

    1. Download the latest release from [GitHub Releases](https://github.com/mnestrud/particle-man/releases)
    2. Copy the `custom_components/particle_man/` folder into your `config/custom_components/` directory
    3. Restart Home Assistant

---

## Initial configuration

Shown when you add the integration via **Settings → Devices & Services → Add Integration → Particle Man**.

| Field | Description |
|---|---|
| **API Key** | Your Google Cloud API key with Air Quality, Pollen, and Weather APIs enabled |
| **Location name** | Label for this location (default: Home) |
| **Latitude** | Pre-filled from your HA home address |
| **Longitude** | Pre-filled from your HA home address |

After setup, all other settings are available at any time via the **Configure** button — no need to remove and re-add the integration.

---

## Options

Accessed via **Configure** on the integration card. Settings span multiple pages depending on which APIs are enabled.

Saving options automatically reloads the integration. API call counters are not reset on reload.

### Automagic mode (default)

With **Automagic** on, Particle Man automatically calculates the safest polling interval for your setup. You don't set an interval manually — it's derived from:

| Factor | What it does |
|---|---|
| **APIs enabled** | Determines how many calls are made per poll |
| **Number of locations** | Multiplies calls (each location is polled separately) |
| **Monthly API limits** | Sets the ceiling the interval must stay under |
| **Quiet hours window** | Reduces effective polling time, so active polls are closer together |
| **5% safety buffer** | Adds headroom so the projection doesn't land exactly at the limit |

**Specific formula (weather interval):**

```
safe_interval = ⌈ active_minutes_per_month × calls_per_poll × num_locations × 1.05 / monthly_limit ⌉
```

The result is floored at 15 minutes. `active_minutes_per_month` uses the actual day count of the current billing month (not a fixed 30-day assumption), minus any quiet hours.

**Air Quality and Pollen** are always fetched on a separate 60-minute cadence (matching Google's data refresh rate). At 7+ locations they scale above 60 minutes automatically.

All of these assumptions are surfaced as attributes on the **Monthly AQ Calls**, **Monthly Pollen Calls**, and **Monthly Weather Calls** diagnostic sensors. Open any of these in Developer Tools → States to see exactly what interval and assumptions are in effect.

**With Automagic on, the quiet hours and location settings from Configure are the only inputs you need.** The interval calculation is invisible unless you inspect the diagnostic sensors.

### Manual mode

Switch **Automagic** off to control the interval and limits yourself.

| Option | Default | Description |
|---|---|---|
| Check every (minutes) | 20 | How often to fetch new data (15–1440 min) |
| Air Quality limit | 10,000 | Monthly AQ call ceiling before pausing |
| Pollen limit | 5,000 | Monthly Pollen call ceiling before pausing |
| Weather limit | 10,000 | Monthly Weather call ceiling before pausing |

The options form shows **projected monthly usage** and a **suggested minimum interval** for the current month, quiet hours, and location count.

### Quiet hours

Quiet hours pause all API fetches during a nightly window. They reduce API consumption and, in Automagic mode, allow a shorter daytime polling interval while still fitting within the monthly limit.

| Option | Default | Description |
|---|---|---|
| Enable quiet hours | On | Pause polling overnight |
| Pause from | 23:00 | Start of the quiet window |
| Resume at | 05:00 | End of the quiet window |

Quiet hours apply globally — all locations pause and resume together.

### APIs to enable

| Option | Default |
|---|---|
| Air Quality | On |
| Pollen | On |
| Weather | On |

Disabling an API removes its sensors and stops counting calls for that service.

### Air Quality options

| Option | Default | Description |
|---|---|---|
| Forecast days | 5 | Days of forecast data (1–5) |
| Language | en | Language for display names and health guidance ([BCP-47](https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry)) |
| Add regional AQI sensor | Off | Show a country-specific AQI alongside Universal AQI — see [About the two AQI types](sensors.md#particle-man-pollution) |
| Regional AQI standard | us_aqi | Which regional standard to use |

??? "Supported regional AQI standards"

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

### Weather options

| Option | Default | Description |
|---|---|---|
| Units | Metric | Temperature, wind, and precipitation units. HA can convert for display independently |
| Weather alerts sensors | Off | Creates three sensors: **Alert Count** (integer), **Alert Highest Severity** (MINOR/MODERATE/SEVERE/EXTREME), and **Alert Event Types** (comma-separated codes). All show empty/0 when no alerts are active |

### Locations

Multiple locations can be monitored using the same API key. Each location gets its own Pollution, Pollen, and Weather devices but shares the Diagnostics device and monthly quota.

Add, edit, or remove locations via **Configure → Locations**.

!!! warning
    Multiple locations multiply API call counts proportionally. Automagic mode accounts for this automatically. In manual mode, the options form shows combined projected usage — increase the interval if you add locations.

---

## Removing the integration

1. Go to **Settings → Devices & Services → Particle Man**
2. Click the three-dot menu → **Delete**
3. Restart Home Assistant
4. (Optional) Uninstall via HACS or delete `custom_components/particle_man/` from your config directory
