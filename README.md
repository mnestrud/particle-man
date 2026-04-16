<div align="center">
  <img src="images/PARTICLE_MAN_LARGE.png" alt="Particle Man" width="400"/>

  # PARTICLE MAN HELPS YOU FIGHT BAD AIR QUALITY

  A Home Assistant custom integration that pulls air quality and pollen data from the [Google Air Quality API](https://developers.google.com/maps/documentation/air-quality) and [Google Pollen API](https://developers.google.com/maps/documentation/pollen).
</div>

---

## Why Air Quality Matters

I live in Chicago, where wildfires, traffic, industrial activity, and city living cause moment by moment changes to air quality.  I also have allergies, and until the wildfires a couple years ago didn't realize how sensitive I was to particulates.  That's when I started looking for air quality sources for home assistant.  

The integrations that already existed weren't cutting it for me. Some had current conditions but no forecasts. Some covered a few pollutants but not all the ones I cared about.  Few surfaced the plain-language risk levels behind the numbers — the part that actually tells you what to do with the information. Hourly data was sparse.  I wanted one integration that did all of it, in a consistent format, so I could see what's happening right now and what's coming, without bouncing between apps or stitching together multiple data sources.  

I also became impressed by Google's ML models, which include a lot of predictive inputs unavailable even by robust city air monitoring programs - traffic, historical monitoring, effects of weather, etc. both on current conditions but especially on forecasts.  Originally I thought this would be a paid-API only integration, but I happily discovered that all of this fits neatly within Google's free API limits for both the Pollen and Pollution features.  I also surface the API usage information for transparency and confidence that this is indeed free, as long as you set reasonable limits.

Just Breathe.

---

## Features

### Current Conditions

- **Universal AQI (UAQI)** with health category, dominant pollutant, and trend
- **Pollutant sensors** — each sensor includes concentration, unit, EPA health category (where applicable), dominant pollutant flag, sources and effects, and trend. Pollutants are split by whether US EPA (Environmental Protection Agency) breakpoints exist:
  - *With EPA health category:* PM2.5, PM10, Ozone (O3), Nitrogen Dioxide (NO2), Carbon Monoxide (CO), Sulfur Dioxide (SO2)
  - *Concentration only:* Any additional pollutants returned by the API for your location (varies by region)
- **Pollen sensors** by type (Grass, Tree, Weed) with index, color, and trend
- **API usage tracking** — billing-period call counts with projected usage and free-tier warnings (see [API Usage Tracking](#api-usage-tracking))

### Forecast

- **Hourly AQI forecast** up to 96 hours — stored as `hourly_forecast` attribute for dashboard charts
- **Daily AQI forecast** up to 5 days — peak AQI per day, stored as `daily_forecast` attribute
- **Hourly pollutant forecast** up to 96 hours per pollutant — stored as `hourly_forecast` attribute
- **Daily pollutant forecast** up to 5 days — peak concentration per day, stored as `daily_forecast` attribute
- **Daily pollen forecast** up to 5 days with trend and expected peak — stored as `daily_forecast` attribute (pollen data is daily only — no hourly pollen data is available from Google)

### Optional

- **Regional AQI index** — US AQI and 12 other country-specific indices (see [supported indices](#local-aqi-index))
- **Health recommendations** — text guidance included as sensor attributes
- **Per-plant pollen sensors** — individual species (Oak, Ragweed, etc.) with index, trend, and peak
- **Plant descriptions** — family, genus, and cross-reaction info added to plant sensor attributes
- **Enforce API limits** — suspend polling when a monthly call limit is reached, keeping usage within the free tier

---

## About the AQI

The primary AQI sensor uses the [**Universal AQI (UAQI)**](https://developers.google.com/maps/documentation/air-quality/laqis) — a global index developed by Google that provides consistent, [hyper-local air quality readings](https://developers.google.com/maps/documentation/air-quality/overview) at 500m resolution across 100+ countries. It accounts for six core pollutants and is designed to work the same way everywhere in the world.

If you want a country-specific index like the US AQI, enable the **Local AQI index** option after setup. Both can be tracked simultaneously.

---

## Hyper-Local Data

Most air quality sources give you a reading for your city or your zip code. [Google's Air Quality API](https://mapsplatform.google.com/maps-products/air-quality/) goes further:

- **500-meter resolution** — data is localized to your specific block, not your neighborhood
- **50+ million updates daily** — powered by Google Maps data, continuously refreshed
- **100+ countries covered** — consistent global data with 70+ local and regional AQI indices
- **96-hour hourly forecast** — plan around air quality the way you plan around weather, with per-pollutant hourly projections
- **Multi-source modeling** — Google's ML models factor in traffic, weather, industrial activity, historical monitoring, and more — inputs that even robust city monitoring networks don't combine into a single number
- **Health guidance** — WHO-aligned recommendations for general and sensitive population groups, not just a raw number

This is the same data infrastructure that powers health apps, HVAC automation, and route optimization for developers worldwide. Particle Man surfaces it in Home Assistant.

---

## Devices

Particle Man creates three devices in Home Assistant:

| Device | Contains |
|---|---|
| **Particle Man Pollution** | Universal AQI, pollutant sensors, Local AQI (if enabled) |
| **Particle Man Pollen** | Pollen type sensors (Grass, Tree, Weed) and per-plant sensors (if enabled) |
| **Particle Man Diagnostics** | Last API Update timestamp, AQ API Calls (Monthly), Pollen API Calls (Monthly) |

---

## API Usage Tracking

Particle Man includes two diagnostic sensors that track how many API calls have been made in the current billing period and project usage through the end of the period:

- **AQ API Calls (Monthly)** — tracks Air Quality API calls (current conditions + forecast = 2 calls per poll)
- **Pollen API Calls (Monthly)** — tracks Pollen API calls (1 call per poll)

Each sensor includes attributes for `monthly_limit`, `projected_monthly`, `pct_of_limit`, `pct_projected`, `status` (`ok` / `warning` at 80% projected / `critical` at 95% projected), and `tracking_period_start`.

**Important notes:**
- Tracking resets on the **configured reset day** (default: 1st of each month). You can change this to match your Google billing cycle in the **API Limits** section of Configure
- Usage is **estimated, not pulled from Google** — Google does not expose actual quota usage through the API key. This is a projection based on calls made since the last reset
- Counts survive HA restarts via persistent storage
- Default limits match the Google free tier: **10,000 AQ calls/month** and **5,000 Pollen calls/month**. Adjust in Configure if you have a paid plan
- By default, limits are **not enforced** — the integration keeps polling regardless of usage. Enable **Enforce limits** to suspend polling when a limit is reached; sensors will show unavailable until the next billing period or until you disable enforcement

---

## Prerequisites

You need a Google Cloud API key with both the **Air Quality API** and **Pollen API** enabled.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Air Quality API** and **Pollen API**
4. Create an API key under **Credentials**

---

## Installation

### HACS (recommended)

1. In HACS, go to **Integrations → three-dot menu → Custom repositories**
2. Add `https://github.com/mnestrud/particle-man` as an **Integration**
3. Install **Particle Man** from HACS
4. Restart Home Assistant

### Manual

1. Copy the `custom_components/particle_man/` directory into your Home Assistant `config/custom_components/` folder
2. Restart Home Assistant

### Setup

Go to **Settings → Devices & Services → Add Integration** and search for **Particle Man**.

---

## Configuration

During initial setup you will be prompted for:

| Field | Description |
|---|---|
| API Key | Your Google Cloud API key |
| Latitude | Location latitude (defaults to your HA home location) |
| Longitude | Location longitude (defaults to your HA home location) |
| Update interval | How often to poll the API (minutes, default: 60) |

---

## Options

After setup, click **Configure** to access additional options. Settings are organized into collapsible sections.

### Location & Polling

| Option | Default | Description |
|---|---|---|
| Latitude | (from setup) | Location latitude |
| Longitude | (from setup) | Location longitude |
| Update interval | 60 min | How often to poll both APIs (15–1440 minutes) |

### Forecast

| Option | Default | Description |
|---|---|---|
| Forecast days | 5 | Number of days of daily forecast data (1–5) |
| Language | en | BCP-47 language code for health recommendations and display names |

### Air Quality

| Option | Default | Description |
|---|---|---|
| Local AQI index | disabled | Show a regional AQI index in addition to Universal AQI |
| Local AQI index code | us_aqi | Which regional index to use when local AQI is enabled |
| Health recommendations | disabled | Include per-population health recommendation text in sensor attributes |

### Pollen

| Option | Default | Description |
|---|---|---|
| Plant sensors | enabled | Create individual sensors for each pollen plant species |
| Plant descriptions | enabled | Include plant family, genus, and cross-reaction info in plant sensor attributes |

### API Limits

| Option | Default | Description |
|---|---|---|
| AQ API monthly limit | 10,000 | Monthly call limit for usage tracking and warnings |
| Pollen API monthly limit | 5,000 | Monthly call limit for usage tracking and warnings |
| Billing period reset day | 1 | Day of the month tracking resets (1–28). Set to match your Google billing cycle |
| Enforce limits | disabled | When enabled, polling stops when a limit is reached instead of just warning |

### Local AQI Index

Supported regional indices: US AQI, Canada (EC), UK (DEFRA), Germany (UBA), France (ATMO), China (MEP), India (CPCB), Japan (CAQI), Mexico (SEDEMA), Netherlands (LKI), Singapore (NEA), South Korea (KECO), Spain (Calidad).

---

## Sensor Attributes

Forecast data is stored as sensor attributes for use in dashboard cards and templates.

### AQI and Pollutant sensors

| Attribute | Description |
|---|---|
| `daily_forecast` | List of daily peak values, up to 5 days. Each entry: `datetime`, `aqi` or `max`, `category`, `epa_category` |
| `hourly_forecast` | List of hourly values, up to 96 hours. Each entry: `datetime`, `aqi` or `value`, `category`, `epa_category` |
| `trend` | Direction based on hourly slope: `rising`, `falling`, or `stable` |

### Pollen sensors

| Attribute | Description |
|---|---|
| `daily_forecast` | List of daily forecast entries. Each entry: `datetime`, `index`, `category`, `color_hex` |
| `trend` | Direction based on today vs tomorrow: `up`, `down`, or `flat` |
| `expected_peak` | Forecast entry with the highest index value |

---

## License

MIT
