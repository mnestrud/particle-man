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
- **Per-plant pollen sensors** — individual species (Oak, Ragweed, etc.) with index, trend, and peak (optional)

### Weather

- **Native weather entity** — current conditions with hourly (24h), daily (5-day), and twice-daily forecasts; works with all HA weather cards
- **Weather Alerts sensor** — count of active weather warnings with severity, event types, and full alert details (optional)
- **Extra sensors** — Thunderstorm Probability, Heat Index, Wind Chill

### API Management

- **Free-tier enforce mode** — each API pauses automatically when its monthly quota is reached
- **Multi-location support** — shared quota tracking across all locations using the same API key
- **Quiet hours** — skip fetches during a configured overnight window to stretch your monthly budget
- **API usage sensors** — billing-period call counts with projected usage and status (`ok` / `warning` / `critical`)

→ [Full sensor details](https://mnestrud.github.io/particle-man/sensors/)

---

## Quick Start

1. Get a free Google Cloud API key with the **Air Quality API**, **Pollen API**, and **Weather API** enabled
2. Install via HACS (custom repository: `https://github.com/mnestrud/particle-man`) and restart Home Assistant
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

## TODO

### Features

- Google Solar API integration
- HACS default catalog

### HACS Default Catalog Submission

Requirements per [HACS publishing docs](https://www.hacs.xyz/docs/publish/include/).

- [x] Public GitHub repository
- [x] Repository description set
- [x] Issues enabled
- [x] README with documentation
- [x] `hacs.json` with `name` field
- [x] GitHub release published (v1.0.3)
- [x] `manifest.json` with all required fields (`domain`, `name`, `version`, `documentation`, `issue_tracker`, `codeowners`)
- [x] Brand directory with `icon.png`
- [x] GitHub Topics added (`home-assistant`, `hacs`, `air-quality`, `pollen`, `home-assistant-integration`, `google-api`)
- [x] HACS validation GitHub Action added and passing (required before PR submission)
- [x] Hassfest GitHub Action added and passing (required for integrations)
- [ ] Submit PR to [hacs/default](https://github.com/hacs/default) adding entry alphabetically to `integration` file

### HA Integration Quality Scale

Particle Man targets [Gold tier](https://www.home-assistant.io/docs/quality_scale/). Current status:

**Bronze** — ALL REQUIREMENTS MET
- [x] UI setup via config flow
- [x] Basic end-user documentation
- [x] Code adheres to basic HA standards — CI (`ruff`, `mypy`, `hassfest`, `hacs`) via `.github/workflows/validate.yml` — all passing
- [x] Automated tests (`pytest-homeassistant-custom-component`) — coordinator, config flow, options flow, EPA category — all passing via CI

**Silver** (requires Bronze)
- [x] Stable experience — pollen API failures are caught and logged without crashing the integration
- [x] Active maintenance — `@mnestrud` listed as codeowner in `manifest.json`
- [x] Error recovery — AQ API errors raise `UpdateFailed`; pollen errors fall back to last known data
- [ ] Re-authentication flow — if the API key is revoked, the integration retries indefinitely; needs `async_start_reauth` to surface a reauthentication prompt in the HA UI
- [ ] Detailed documentation — covered by the [docs site](https://mnestrud.github.io/particle-man/); troubleshooting page in progress

**Gold** (requires Silver)
- [x] Reconfigurability — options flow (`Configure` button) supports all settings after initial setup
- [x] Translation support — `strings.json` and `translations/en.json` present
- [ ] Auto-discovery — N/A for cloud API integrations (no local device to discover)
- [ ] Firmware updates — N/A for cloud API integrations
- [ ] Comprehensive documentation for non-technical users — [docs site](https://mnestrud.github.io/particle-man/) scaffolded; content in progress
- [ ] Full test coverage — same gap as Bronze; blocks all tiers above it

---

## License

MIT
