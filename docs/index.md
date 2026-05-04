# Particle Man

Real-time air quality, pollen, and weather for Home Assistant — powered by Google's environmental APIs.

---

## What you can do with it

- **React to air quality events** — automatically close HVAC fresh-air intakes, send alerts, or pause outdoor routines when AQI rises from wildfire smoke or traffic
- **Stay ahead of pollen season** — trigger morning pollen briefs or allergy reminders on high-pollen days
- **Weather-aware automations** — combine AQI advisory, pollen level, and weather conditions to decide when outdoor activities are safe
- **Stay within Google's free tier** — automatic quota enforcement keeps all three APIs within their monthly limits by default
- **Automagic mode** — automatically calculates the optimal polling interval based on your enabled APIs, location count, and quiet hours window, so you get maximum data freshness while staying within Google's monthly limits

---

## Quick start

**1. Enable the Google APIs**

In the [Google Cloud Console](https://console.cloud.google.com/apis/credentials), enable:

- [Air Quality API](https://developers.google.com/maps/documentation/air-quality/overview)
- [Pollen API](https://developers.google.com/maps/documentation/pollen/overview)
- [Weather API](https://developers.google.com/maps/documentation/weather/overview)

Then create an API key under **APIs & Services → Credentials → Create Credentials → API key**.

**2. Install via HACS**

In HACS: **Integrations → Explore & Download Repositories** → search for **Particle Man** → Download → restart Home Assistant.

**3. Add the integration**

**Settings → Devices & Services → Add Integration → Particle Man** — enter your API key and confirm your location.

→ [Full setup guide: manual install, all configuration options, and removal instructions](setup.md)

---

## What you get

For each monitored location:

| Device | Contents |
|---|---|
| **Particle Man Pollution** | Universal AQI, Air Quality Advisory, pollutant sensors (PM2.5, PM10, O3, NO2, CO, SO2), optional regional AQI |
| **Particle Man Pollen** | Pollen Advisory, grass/tree/weed sensors, optional plant-species sensors |
| **Particle Man Weather** | HA weather entity with hourly/daily/twice-daily forecasts, thunderstorm probability, heat index, wind chill, optional weather alerts |
| **Particle Man Diagnostics** | Monthly API call tracking for all three services |

→ [Sensors & Entities](sensors.md) · [Weather entity](weather.md)

---

??? success "HACS compatible"

    Particle Man meets all HACS custom integration requirements:

    - Valid `manifest.json` with `domain`, `version`, `codeowners`, and `issue_tracker`
    - UI-based setup via `config_flow` — no YAML required
    - No external Python package dependencies (`requirements: []`)
    - Actively maintained with a public [issue tracker](https://github.com/mnestrud/particle-man/issues)

    **To install:** In HACS, go to **Integrations → Explore & Download Repositories**, search for **Particle Man**, and download it.

??? success "Meets HA Integration Quality Scale criteria through Platinum tier"

    The [HA Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/) defines 56 rules across Bronze, Silver, Gold, and Platinum tiers. Particle Man satisfies all applicable rules at every tier.

    !!! note
        The official Platinum designation is awarded by Nabu Casa exclusively to integrations in the core HA repository. Particle Man is a custom integration — this documents compliance with the same criteria, not possession of the official award.

    **🥉 Bronze — 16/16 applicable**

    | Rule | |
    |---|---|
    | appropriate-polling | ✅ Configurable interval, 15-min floor, quota-aware enforcement |
    | brands | ✅ icon.png + icon@2x.png |
    | common-modules | ✅ coordinator.py + const.py |
    | config-flow | ✅ Full UI setup, no YAML |
    | config-flow-test-coverage | ✅ 100% |
    | dependency-transparency | ✅ No external requirements |
    | docs-high-level-description | ✅ This page |
    | docs-installation-instructions | ✅ [Setup](setup.md) |
    | docs-removal-instructions | ✅ [Setup — Removing](setup.md#removing-the-integration) |
    | entity-event-setup | ✅ Coordinator-based updates |
    | entity-unique-id | ✅ All entities |
    | has-entity-name | ✅ `_attr_has_entity_name = True` |
    | runtime-data | ✅ `entry.runtime_data` |
    | test-before-configure | ✅ API key validated before entry created |
    | test-before-setup | ✅ Raises `ConfigEntryAuthFailed` / `ConfigEntryNotReady` |
    | unique-config-entry | ✅ MD5(api_key) as unique_id |

    **🥈 Silver — 9/9 applicable**

    | Rule | |
    |---|---|
    | config-entry-unloading | ✅ `async_unload_entry` implemented |
    | docs-configuration-parameters | ✅ [Setup — Options](setup.md#options) |
    | docs-installation-parameters | ✅ [Setup — Initial configuration](setup.md#initial-configuration) |
    | entity-unavailable | ✅ Marks unavailable on API failure |
    | integration-owner | ✅ codeowners: @mnestrud |
    | log-when-unavailable | ✅ Logs once on failure, once on recovery |
    | parallel-updates | ✅ `PARALLEL_UPDATES = 1` in all platforms |
    | reauthentication-flow | ✅ `async_step_reauth` + `async_step_reauth_confirm` |
    | test-coverage | ✅ 99% overall (231 tests) |

    **🥇 Gold — 18/18 applicable**

    | Rule | |
    |---|---|
    | devices | ✅ Pollution, Pollen, Weather, Diagnostics devices |
    | diagnostics | ✅ `diagnostics.py` with API key redaction |
    | docs-data-update | ✅ [Reference — How data updates](reference.md#how-data-updates) |
    | docs-examples | ✅ [Examples](examples.md) with published blueprints |
    | docs-known-limitations | ✅ [Reference — Known limitations](reference.md#known-limitations) |
    | docs-supported-functions | ✅ [Sensors](sensors.md) + [Weather](weather.md) |
    | docs-troubleshooting | ✅ [Reference — Troubleshooting](reference.md#troubleshooting) |
    | docs-use-cases | ✅ This page |
    | dynamic-devices | ✅ New pollen plant sensors added per poll |
    | entity-category | ✅ `DIAGNOSTIC` on diagnostic entities |
    | entity-device-class | ✅ `SensorDeviceClass.AQI`, `TEMPERATURE`, `HUMIDITY`, etc. |
    | entity-disabled-by-default | ✅ Pollutant sensors disabled by default |
    | entity-translations | ✅ `_attr_translation_key` on all entities |
    | exception-translations | ✅ `UpdateFailed` + `ConfigEntryAuthFailed` use translation keys |
    | icon-translations | ✅ `icons.json` |
    | reconfiguration-flow | ✅ `async_step_reconfigure` |
    | repair-issues | ✅ `async_create_issue` for quota exhaustion |
    | stale-devices | ✅ `_remove_stale_devices` in `__init__.py` |

    **🏆 Platinum — 3/3**

    | Rule | |
    |---|---|
    | async-dependency | ✅ No blocking I/O; aiohttp throughout |
    | inject-websession | ✅ `hass.helpers.aiohttp_client` |
    | strict-typing | ✅ `py.typed`, mypy strict mode, 0 errors |
