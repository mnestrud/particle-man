<div align="center">
  <img src="images/PARTICLE_MAN_LARGE.png" alt="Particle Man" width="400"/>

  # PARTICLE MAN FIGHTS BAD AIR QUALITY
</div>

---

## Why Air Quality Matters

Most people don't think about the air they breathe until it's a problem — and by then, the damage is already being done. Air quality affects everyone, but especially kids, the elderly, and anyone with asthma or other respiratory conditions. Bad air days aren't just uncomfortable, they're a genuine health risk. Wildfire smoke, ground-level ozone, particulate pollution from traffic and industry — these things are measurable, they're trackable, and knowing about them lets you make smarter decisions about when to go outside, when to open your windows, and when to keep your family inside.

I built this integration because I wanted that data in my smart home — not buried in an app, but right alongside everything else I monitor. If you've got Home Assistant running, you might as well know what you're breathing.

---

A Home Assistant custom integration that pulls air quality and pollen data from the [Google Air Quality API](https://developers.google.com/maps/documentation/air-quality) and [Google Pollen API](https://developers.google.com/maps/documentation/pollen).

## Features

- **Universal AQI** (UAQI) with health category and dominant pollutant — this is Google's Universal Air Quality Index, a global standard, not the US EPA AQI
- Optional **US AQI** and other regional indices (see [Local AQI index](#options) option)
- Per-pollutant sensors (PM2.5, PM10, O3, NO2, CO, SO2) with health categories calculated using US EPA (Environmental Protection Agency) breakpoints
- Hourly and daily AQI forecasts
- Pollen sensors by type (Grass, Tree, Weed) with trend and peak forecasts
- Optional per-plant-species pollen sensors (Oak, Ragweed, etc.) with family/genus/cross-reaction attributes
- EPA AQI calculation using 2024 NAAQS revised PM2.5 breakpoints
- API call tracking with free-tier usage projections
- Optional health recommendations

## About the AQI

The primary AQI sensor uses the **Universal AQI (UAQI)** — a global index developed by Google that works consistently across all countries. It is **not** the same as the US EPA AQI (US Environmental Protection Agency Air Quality Index).

If you want the US EPA AQI specifically, enable the **Local AQI index** option after setup and select **US AQI**. Both can be tracked simultaneously.

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
| Local AQI index | disabled | Show a regional AQI index (e.g., US AQI) in addition to Universal AQI |
| Health recommendations | disabled | Include health recommendation text in sensor attributes |
| Plant sensors | disabled | Create individual sensors for each pollen plant species |
| Plant descriptions | disabled | Include plant family, genus, and cross-reaction info in plant sensor attributes |

## License

MIT
