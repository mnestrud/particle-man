<div align="center">
  <img src="images/PARTICLE_MAN_LARGE.png" alt="Particle Man" width="400"/>

  # PARTICLE MAN HELPS YOU FIGHT BAD AIR QUALITY

  A Home Assistant custom integration that pulls air quality and pollen data from the [Google Air Quality API](https://developers.google.com/maps/documentation/air-quality) and [Google Pollen API](https://developers.google.com/maps/documentation/pollen).
</div>

---

## Why Air Quality Matters

I live in Chicago. Between wildfire smoke drifting in from out west, traffic, an active industrial base, and just the general reality of dense city living, air quality has a real impact on day to day life here. It's not abstract.

The integrations that already existed weren't cutting it for me. Some had current conditions but no forecasts. Some covered a few pollutants but not all the ones I cared about. None of them surfaced the plain-language risk levels behind the numbers — the part that actually tells you what to do with the information. I wanted one integration that did all of it, in a consistent format, so I could see what's happening right now and what's coming, without bouncing between apps or stitching together multiple data sources.

That's what this is.

---

## Features

### Current Conditions

- **Universal AQI (UAQI)** with health category and dominant pollutant
- **Pollutant sensors** — each sensor includes concentration, unit, EPA health category (where applicable), dominant pollutant flag, and sources and effects. Pollutants are split by whether US EPA (Environmental Protection Agency) breakpoints exist:
  - *With EPA health category:* PM2.5, PM10, Ozone (O3), Nitrogen Dioxide (NO2), Carbon Monoxide (CO), Sulfur Dioxide (SO2)
  - *Concentration only:* Any additional pollutants returned by the API for your location (varies by region)
- **Pollen sensors** by type (Grass, Tree, Weed) with index and color
- **API call tracker** with free-tier usage projections

### Forecast

- **Hourly and daily AQI forecast** up to 5 days
- **Daily pollutant forecast** for all tracked pollutants
- **Pollen trend and peak forecast** per type (Grass, Tree, Weed)

### Optional

- **Regional AQI index** — US AQI and 12 other country-specific indices (see [supported indices](#local-aqi-index))
- **Health recommendations** — text guidance included as sensor attributes
- **Per-plant pollen sensors** — individual species (Oak, Ragweed, etc.) with index, trend, and peak
- **Plant descriptions** — family, genus, and cross-reaction info added to plant sensor attributes

## About the AQI

The primary AQI sensor uses the [**Universal AQI (UAQI)**](https://developers.google.com/maps/documentation/air-quality/laqis) — a global index developed by Google that provides consistent, [hyper-local air quality readings](https://developers.google.com/maps/documentation/air-quality/overview) at 500m resolution across 100+ countries. It accounts for six core pollutants and is designed to work the same way everywhere in the world.

If you want a country-specific index like the US AQI, enable the **Local AQI index** option after setup. Both can be tracked simultaneously.

## Prerequisites

You need a Google Cloud API key with both the **Air Quality API** and **Pollen API** enabled.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use an existing one)
3. Enable the **Air Quality API** and **Pollen API**
4. Create an API key under **Credentials**

Google offers a free tier — the integration includes an API call counter so you can monitor usage.

## Installation

### Manual

1. Copy the `custom_components/particle_man/` directory into your Home Assistant `config/custom_components/` folder
2. Restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration** and search for **Particle Man**

### HACS (coming soon)

HACS support is planned.

## Configuration

During initial setup you will be prompted for:

| Field | Description |
|---|---|
| API Key | Your Google Cloud API key |
| Latitude | Location latitude (defaults to your HA home location) |
| Longitude | Location longitude (defaults to your HA home location) |
| Update interval | How often to poll the API (minutes, default: 60) |

## Options

After setup, additional options are available via **Configure**:

| Option | Default | Description |
|---|---|---|
| Forecast days | 5 | Number of days of forecast data (1–5) |
| Language | en | Language for health recommendations and pollutant descriptions |
| Local AQI index | disabled | Show a regional AQI index in addition to Universal AQI |
| Health recommendations | disabled | Include health recommendation text in sensor attributes |
| Plant sensors | disabled | Create individual sensors for each pollen plant species |
| Plant descriptions | disabled | Include plant family, genus, and cross-reaction info in plant sensor attributes |

### Local AQI Index

Supported regional indices: US AQI, Canada (EC), UK (DEFRA), Germany (UBA), France (ATMO), China (MEP), India (CPCB), Japan (CAQI), Mexico (SEDEMA), Netherlands (LKI), Singapore (NEA), South Korea (KECO), Spain (Calidad).

## License

MIT
