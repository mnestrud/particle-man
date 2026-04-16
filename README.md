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

That's what this is.

---

## Features

### Current Conditions

- **Universal AQI (UAQI)** with health category, dominant pollutant, and trend
- **Pollutant sensors** — each sensor includes concentration, unit, EPA health category (where applicable), dominant pollutant flag, sources and effects, and trend. Pollutants are split by whether US EPA (Environmental Protection Agency) breakpoints exist:
  - *With EPA health category:* PM2.5, PM10, Ozone (O3), Nitrogen Dioxide (NO2), Carbon Monoxide (CO), Sulfur Dioxide (SO2)
  - *Concentration only:* Any additional pollutants returned by the API for your location (varies by region)
- **Pollen sensors** by type (Grass, Tree, Weed) with index, color, and trend
- **API usage tracking** — monthly call counts with projected usage and free-tier warnings (see [API Usage Tracking](#api-usage-tracking))

### Forecast

- **Hourly AQI forecast** up to 96 hours — available as a sensor attribute for use in dashboard charts
- **Daily AQI forecast** up to 5 days — peak AQI per day
- **Hourly pollutant forecast** up to 96 hours per pollutant — available as a sensor attribute
- **Daily pollutant forecast** up to 5 days — peak concentration per day
- **Daily pollen forecast** up to 5 days with trend and expected peak (pollen data is daily only — no hourly pollen data is available from Google)

### Optional

- **Regional AQI index** — US AQI and 12 other country-specific indices (see [supported indices](#local-aqi-index))
- **Health recommendations** — text guidance included as sensor attributes
- **Per-plant pollen sensors** — individual species (Oak, Ragweed, etc.) with index, trend, and peak
- **Plant descriptions** — family, genus, and cross-reaction info added to plant sensor attributes

---

## About the AQI

The primary AQI sensor uses the [**Universal AQI (UAQI)**](https://developers.google.com/maps/documentation/air-quality/laqis) — a global index developed by Google that provides consistent, [hyper-local air quality readings](https://developers.google.com/maps/documentation/air-quality/overview) at 500m resolution across 100+ countries. It accounts for six core pollutants and is designed to work the same way everywhere in the world.

If you want a country-specific index like the US AQI, enable the **Local AQI index** option after setup. Both can be tracked simultaneously.

---

## API Usage Tracking

Particle Man includes two diagnostic sensors that track how many API calls have been made this calendar month and project your usage through the end of the month:

- **AQ API Calls (Monthly)** — tracks Air Quality API calls (current conditions + forecast = 2 calls per poll)
- **Pollen API Calls (Monthly)** — tracks Pollen API calls (1 call per poll)

Each sensor includes attributes for `monthly_limit`, `projected_monthly`, `pct_of_limit`, `pct_projected`, and `status` (`ok` / `warning` at 80% projected / `critical` at 95% projected).

**Important notes:**
- Tracking resets on the **1st of each calendar month**, not your Google billing cycle — these may not align exactly
- Usage is **estimated, not pulled from Google** — Google does not expose actual quota usage through the API key. This is a projection based on calls made since the tracking reset
- Counts survive HA restarts via persistent storage
- Default limits match the Google free tier: **10,000 AQ calls/month** and **5,000 Pollen calls/month**. You can adjust these in the integration's Configure options if you have a paid plan

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

After setup, additional options are available via **Configure**:

| Option | Default | Description |
|---|---|---|
| Forecast days | 5 | Number of days of daily forecast data (1–5) |
| Language | en | Language for health recommendations and pollutant descriptions |
| Local AQI index | disabled | Show a regional AQI index in addition to Universal AQI |
| Local AQI index code | us_aqi | Which regional index to use when local AQI is enabled |
| Health recommendations | disabled | Include health recommendation text in sensor attributes |
| Plant sensors | enabled | Create individual sensors for each pollen plant species |
| Plant descriptions | enabled | Include plant family, genus, and cross-reaction info in plant sensor attributes |
| AQ API monthly limit | 10,000 | Monthly call limit for usage tracking and warnings |
| Pollen API monthly limit | 5,000 | Monthly call limit for usage tracking and warnings |

### Local AQI Index

Supported regional indices: US AQI, Canada (EC), UK (DEFRA), Germany (UBA), France (ATMO), China (MEP), India (CPCB), Japan (CAQI), Mexico (SEDEMA), Netherlands (LKI), Singapore (NEA), South Korea (KECO), Spain (Calidad).

---

## License

MIT
