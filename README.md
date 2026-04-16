# Particle Man

A Home Assistant custom integration that pulls air quality and pollen data from the [Google Air Quality API](https://developers.google.com/maps/documentation/air-quality) and [Google Pollen API](https://developers.google.com/maps/documentation/pollen).

## Features

- Universal AQI with health category and dominant pollutant
- Per-pollutant sensors (PM2.5, PM10, O3, NO2, CO, SO2) with EPA health categories
- Hourly and daily AQI forecasts
- Pollen sensors by type (Grass, Tree, Weed) with trend and peak forecasts
- Optional per-plant-species pollen sensors (Oak, Ragweed, etc.) with family/genus/cross-reaction attributes
- EPA AQI calculation using 2024 NAAQS revised PM2.5 breakpoints
- API call tracking with free-tier usage projections
- Optional regional AQI indices and health recommendations

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
| Local AQI index | disabled | Show a regional AQI index (e.g., US AQI) in addition to universal AQI |
| Health recommendations | disabled | Include health recommendation text in sensor attributes |
| Plant sensors | disabled | Create individual sensors for each pollen plant species |
| Plant descriptions | disabled | Include plant family, genus, and cross-reaction info in plant sensor attributes |

## License

MIT
