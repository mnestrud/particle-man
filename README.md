<div align="center">
  <img src="images/PARTICLE_MAN_LARGE.png" alt="Particle Man" width="400"/>

  # PARTICLE MAN HELPS YOU FIGHT BAD AIR QUALITY

  A Home Assistant custom integration that pulls air quality and pollen data from the [Google Air Quality API](https://developers.google.com/maps/documentation/air-quality) and [Google Pollen API](https://developers.google.com/maps/documentation/pollen).

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

### Current Conditions

- **Universal AQI (UAQI)** with health category, dominant pollutant, and trend
- **Pollutant sensors** — PM2.5, PM10, O3, NO2, CO, SO2 with concentration, EPA health category, and trend; additional pollutants vary by region
- **Pollen sensors** by type (Grass, Tree, Weed) with index, color, and trend
- **API usage tracking** — billing-period call counts with projected usage and free-tier warnings

### Forecast

- **Hourly AQI forecast** up to 96 hours
- **Daily AQI forecast** up to 5 days — peak AQI per day
- **Hourly and daily pollutant forecasts** — per-pollutant projections
- **Daily pollen forecast** up to 5 days with trend and expected peak

### Optional

- **Regional AQI index** — US AQI and 12 other country-specific indices
- **Health recommendations** — text guidance included as sensor attributes
- **Per-plant pollen sensors** — individual species (Oak, Ragweed, etc.) with index, trend, and peak
- **Plant descriptions** — family, genus, and cross-reaction info added to plant sensor attributes
- **Enforce API limits** — suspend polling when a monthly call limit is reached

→ [Full sensor details](https://mnestrud.github.io/particle-man/sensors/)

---

## Quick Start

1. Get a free Google Cloud API key with the **Air Quality API** and **Pollen API** enabled
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
| [Dashboard Examples](https://mnestrud.github.io/particle-man/dashboard/) | Copy-paste card YAML for charts and gauges |
| [Automations & Blueprints](https://mnestrud.github.io/particle-man/automations/) | AQI alerts, HVAC control, pollen notifications |
| [API Usage & Free Tier](https://mnestrud.github.io/particle-man/api-usage/) | How to stay within Google's free limits |
| [Troubleshooting](https://mnestrud.github.io/particle-man/troubleshooting/) | Common issues and fixes |
| [Configuration Reference](https://mnestrud.github.io/particle-man/configuration/) | Full options reference |

---

## TODO

### Features

- **Multiple locations** — each config entry covers one lat/lon; support for multiple addresses (home, work, cabin) is a natural extension but requires per-entry coordinator isolation and careful entity naming.
- **Google Solar API integration** — surface solar irradiance and sunlight data alongside air quality, enabling automations that combine UV index, cloud cover, and solar energy potential with pollution and pollen conditions.
- **Alert binary sensors** — simple on/off threshold sensors (e.g. "AQI is Unhealthy", "Tree pollen is High") that work cleanly in automations and notifications without requiring the user to write templates.
- **Automation / notification blueprints** — starter blueprints for common use cases: alert when AQI crosses a threshold, close HVAC fresh-air intake when air quality drops, notify on high pollen days before going outside.
- **Dashboard card examples** — sample YAML for common cards: mini-graph card showing the 96-hour hourly AQI forecast, ApexCharts daily forecast bar chart, glance card with EPA color coding. The data is already in attributes; this just makes it usable out of the box.
- **Weather entity parity** — expose AQI and pollen forecasts as proper HA `weather`-style forecast events so native forecast cards can render them without custom YAML.
- **HACS default catalog** — submit to the HACS default repository list for easier discoverability (requires passing `hassfest` validation and HACS validation checks).

### Code Quality & Linting

- **Add CI pipeline** — add a GitHub Actions workflow running `ruff` (linting + formatting), `mypy` (type checking), and [`hassfest`](https://developers.home-assistant.io/docs/development_testing) (HA integration validator). No CI currently means issues accumulate silently.
- **Fix `device_info` return type** — all three base sensor classes (`_BaseGaqSensor`, `_BasePollenSensor`, `_BaseDiagnosticSensor` in `sensor.py`) annotate `device_info` as `-> dict` instead of `-> DeviceInfo`. Swap in `homeassistant.helpers.entity.DeviceInfo` for correct typing.
- **Fix `SensorStateClass.TOTAL` + `last_reset`** — `MonthlyAqUsageSensor` and `MonthlyPollenUsageSensor` use `SensorStateClass.TOTAL` but never set `last_reset` when the billing period rolls over. HA's long-term statistics engine will misinterpret the monthly reset as a data gap. Either set `last_reset` to the period start datetime or switch to `SensorStateClass.MEASUREMENT`.
- **Deduplicate billing projection logic** — the ~35-line projection calculation in `extra_state_attributes` is copy-pasted between `MonthlyAqUsageSensor` and `MonthlyPollenUsageSensor`. Extract to a shared helper method on the coordinator or a base diagnostic sensor class.
- **Remove dead session-level counters** — `_session_start`, `_aq_current_calls`, and `_aq_forecast_calls` are set in `coordinator.py` `__init__` but never read anywhere. Remove or expose them.

### HA Integration Quality Scale

Particle Man targets [Silver tier](https://www.home-assistant.io/docs/quality_scale/). Current status:

**Bronze**
- [x] UI setup via config flow
- [x] Code adheres to basic HA standards
- [x] Basic end-user documentation
- [ ] Automated tests (`pytest-homeassistant-custom-component` — cover coordinator init, mocked poll cycle, config flow, options flow)

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
