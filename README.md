<div align="center">
  <img src="images/PARTICLE_MAN_LARGE.png" alt="Particle Man" width="400"/>

  # PARTICLE MAN HELPS YOU FIGHT BAD AIR QUALITY

  A Home Assistant custom integration that brings hyper-local air quality, pollen, and weather data into Home Assistant using Google's APIs — the same data behind health apps and smart HVAC automation worldwide.

  [📖 Documentation](https://mnestrud.github.io/particle-man/)
</div>

---

## Why Air Quality Matters

I live in Chicago, where wildfires, traffic, industrial activity, and city living cause moment by moment changes to air quality.  I also have allergies, and until the wildfires a couple years ago didn't realize how sensitive I was to particulates.  That's when I started looking for air quality sources for home assistant.  

The integrations that already existed weren't cutting it for me. Some had current conditions but no forecasts. Some covered a few pollutants but not all the ones I cared about.  Few surfaced the plain-language risk levels behind the numbers — the part that actually tells you what to do with the information. Hourly data was sparse.  I wanted one integration that did all of it, in a consistent format, so I could see what's happening right now and what's coming, without bouncing between apps or stitching together multiple data sources.  

I also became impressed by Google's ML models, which include a lot of predictive inputs unavailable even by robust city air monitoring programs - traffic, historical monitoring, effects of weather, etc. both on current conditions but especially on forecasts.  Originally I thought this would be a paid-API only integration, but I happily discovered that all of this fits neatly within Google's free API limits for both the Pollen and Pollution features.  I also surface the API usage information for transparency and confidence that this is indeed free, as long as you set reasonable limits.

Just Breathe.

---

## Features

### Air Quality

- **Universal AQI (UAQI)** with health category, dominant pollutant, and trend
- **Air Quality Advisory** — simplified `None` / `Caution` / `Warning` / `Alert` for easy automations
- **Pollutant sensors** — PM2.5, PM10, O3, NO2, CO, SO2 with concentration, EPA health category, and trend; additional pollutants vary by region
- **Hourly AQI forecast** up to 96 hours; **daily AQI forecast** up to 5 days

### Pollen

- **Pollen Advisory** — worst in-season level across all pollen types for easy automations
- **Pollen sensors** by type (Grass, Tree, Weed) with index, color, and trend
- **Daily pollen forecast** up to 5 days with trend and expected peak
- **Per-plant pollen sensors** — individual species (Oak, Ragweed, etc.) with index, trend, and peak

### Weather

- **Native weather entity** — current conditions with hourly (24h), daily (5-day), and twice-daily forecasts; works with all HA weather cards
- **Weather Alerts sensor** — count of active weather warnings with severity, event types, and full alert details (optional)
- **Extra sensors** — Thunderstorm Probability, Heat Index, Wind Chill, UV Index Category

### API Management

- **Automagic mode** — automatically calculates the optimal polling interval based on your enabled APIs, number of locations, and quiet hours; no manual interval tuning needed to stay within the free tier
- **Free-tier enforce mode** — each API pauses automatically when its monthly quota is reached
- **Multi-location support** — shared quota tracking across all locations using the same API key
- **Quiet hours** — skip fetches during a configured overnight window to stretch your monthly budget
- **API usage sensors** — billing-period call counts with projected usage and status (`ok` / `warning` / `critical`)

→ [Full sensor details](https://mnestrud.github.io/particle-man/sensors/)

---

## Quick Start

1. Get a free Google Cloud API key with the **Air Quality API**, **Pollen API**, and **Weather API** enabled
2. Install via HACS — search for **Particle Man** and restart Home Assistant
3. Go to **Settings → Devices & Services → Add Integration** and search for **Particle Man**
4. Enter your API key — location defaults to your HA home address

→ [Full setup guide](https://mnestrud.github.io/particle-man/)

---

## Documentation

| | |
|---|---|
| [Getting Started](https://mnestrud.github.io/particle-man/) | Step-by-step setup for new users |
| [What's Included](https://mnestrud.github.io/particle-man/sensors/) | Every sensor explained in plain language |
| [Weather](https://mnestrud.github.io/particle-man/weather/) | Weather entity, extra sensors, and alerts |
| [Dashboard Examples](https://mnestrud.github.io/particle-man/dashboard/) | Copy-paste card YAML for charts and gauges |
| [Automations & Blueprints](https://mnestrud.github.io/particle-man/automations/) | AQI alerts, HVAC control, pollen and weather notifications |
| [API Usage & Free Tier](https://mnestrud.github.io/particle-man/api-usage/) | How to stay within Google's free limits |
| [Troubleshooting](https://mnestrud.github.io/particle-man/troubleshooting/) | Common issues and fixes |
| [Configuration Reference](https://mnestrud.github.io/particle-man/configuration/) | Full options reference |

---

## License

MIT
