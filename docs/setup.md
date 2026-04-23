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
    2. Go to **Integrations → three-dot menu → Custom repositories**
    3. Add `https://github.com/mnestrud/particle-man` as an **Integration**
    4. Find **Particle Man** and click **Download**
    5. Restart Home Assistant

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

### Polling & limits

| Option | Default | Description |
|---|---|---|
| Stay within Google's free tier | On | Pauses each API automatically when its monthly free quota is reached. Turn off to set custom limits |
| Check every (minutes) | 60 | How often to fetch new data (15–1440 min) |

The options form shows **projected monthly usage** and a **suggested minimum interval** based on your enabled APIs and number of locations.

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
| Add regional AQI sensor | Off | Show a country-specific AQI alongside Universal AQI — see [About the two AQI types](sensors.md#about-the-two-aqi-types) |
| Regional AQI standard | us_aqi | Which regional standard to use |
| Include health guidance | Off | Adds per-population activity recommendations as sensor attributes |

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

### Pollen options

| Option | Default | Description |
|---|---|---|
| Individual plant species sensors | On | Creates a sensor for each plant species in your area (Oak, Ragweed, etc.) |
| Plant details | On | Adds family, genus, typical season, and cross-reactions as sensor attributes |

### Weather options

| Option | Default | Description |
|---|---|---|
| Units | Metric | Temperature, wind, and precipitation units. HA can convert for display independently |
| Weather alerts sensor | Off | Creates a sensor showing active weather warnings; shows 0 when none are active |

### Custom limits & quiet hours

*Only shown when "Stay within Google's free tier" is off.*

| Option | Default | Description |
|---|---|---|
| Air Quality limit | 5,000 | Monthly AQ call ceiling |
| Pollen limit | 5,000 | Monthly Pollen call ceiling |
| Weather limit | 10,000 | Monthly Weather call ceiling |
| Pause overnight | Off | Skip all API fetches during a configured window |
| Pause from | 22:00 | Start of overnight pause |
| Resume at | 06:00 | End of overnight pause |

### Locations

Multiple locations can be monitored using the same API key. Each location gets its own Pollution, Pollen, and Weather devices but shares the Diagnostics device and monthly quota.

Add, edit, or remove locations via **Configure → Locations**.

!!! warning
    Multiple locations multiply API call counts proportionally. The options form shows the combined projected usage. Consider increasing the polling interval when adding locations.

---

## Removing the integration

1. Go to **Settings → Devices & Services → Particle Man**
2. Click the three-dot menu → **Delete**
3. Restart Home Assistant
4. (Optional) Uninstall via HACS or delete `custom_components/particle_man/` from your config directory
