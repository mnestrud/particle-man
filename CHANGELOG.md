# Changelog

## [1.5.0] — 2026-04-23

### Added

- **Google Weather API** — full HA weather entity with hourly, daily, and twice-daily forecasts; current conditions include temperature, humidity, wind, pressure, UV index, visibility, and precipitation
- **Extra weather sensors** — Thunderstorm Probability, Heat Index, Wind Chill
- **Weather Alerts sensor** (optional) — count of active warnings with severity, event type, and full alert details as attributes
- **Air Quality Advisory sensor** — simplified 4-level (None / Caution / Warning / Alert) mapped from Universal AQI; intended for automations that don't need numeric thresholds
- **Pollen Advisory sensor** — worst pollen level across all in-season types in a single sensor
- **Multi-location support** — monitor multiple locations per API key; add, edit, and remove locations via Configure without re-adding the integration
- **Per-API toggles** — Air Quality, Pollen, and Weather can be independently enabled or disabled
- **Automagic mode** — calculates a safe polling interval automatically based on enabled APIs, monthly limits, and number of locations; eliminates manual interval tuning to stay within free tier
- **Quota enforcement** — each API pauses independently when its monthly free-tier limit is reached and resumes automatically at the start of the next billing period
- **Quiet hours** — configurable overnight polling pause (default 23:00–05:00)
- **Projected usage preview** — options form shows estimated monthly API calls before saving, with a suggested minimum interval based on enabled APIs and number of locations
- **3 automation blueprints** — AQI Alert, Morning Pollen Brief, Outdoor Activity Check

### Changed

- Options flow restructured into multi-step pages: Polling & Limits, APIs, Air Quality, Pollen, Weather, Custom Limits
- Billing period reset: configurable reset day replaced with fixed 1st of month at midnight Pacific Time, matching Google's actual billing cycle
- Quota tracking is now shared across multiple config entries using the same API key
- Documentation site refactored from 8 pages to 6 with a quick-start-first structure
- Self-assessed compliance with all HA Integration Quality Scale criteria through Platinum tier (Bronze 16/16, Silver 9/9, Gold 18/18, Platinum 3/3 — note: the official Platinum designation is awarded by Nabu Casa to core HA integrations only)

### Removed

- Configurable billing reset day (replaced by fixed Pacific Time billing cycle)

---

## [1.1.0] — prior release

Initial public release with Air Quality API and Pollen API support.
