# Changelog

## [1.7.2] — 2026-08-13

### Changed

- **Pollen action level raised to UPI 3 (Moderate)** — None, Very Low and Low are now quiet (was: only None/Very Low). Applies to `below_action_level` on the pollen sensors and their forecast entries.

---

## [1.7.1] — 2026-08-13

### Fixed

- **Universal AQI colors now come from the documented band palette instead of the API's `color` gradient.** Google's default gradient returns green hues for UAQI below 50 — the red/green channels appear transposed upstream (uaqi 38 comes back `#01ba00` where the gradient math implies `#ba0100`) — contradicting the official band table where those bands are orange/red. Severity-indexed mapping, so localized category strings can't break it. Local AQIs keep their API-provided palettes.
- Daily UAQI forecast entries now carry `dominant_pollutant` (from the day's worst hour); previously only hourly entries had it.

### Added

- Forecast array entries (UAQI hourly/daily, pollutants, pollen) now carry `below_action_level`, matching the current-state sensors, so dashboards can apply the same quiet-row treatment to forecast data.

---

## [1.7.0] — 2026-08-13

### Added

- **Harmonized severity attributes** on every categorized sensor: `severity` (the reading's rank within its own canonical scale, 0 = least severe), `severity_max`, and `below_action_level`, so dashboards can draw uniform severity graphics without hardcoding any thresholds or vocabulary. The canonical categories, colors, states, and scales are unchanged and remain authoritative; severity asserts no cross-domain equivalence. Action boundaries are documented in the reference (AQ quiet only in the Good/Excellent UAQI bands; pollutants quiet only at EPA Good; pollen quiet below UPI 2; alerts never quiet).
- **Index colors captured from the API.** Google returns a `color` on every air-quality index; it is now exposed as `color_hex` on the Universal AQI, Local AQI, and advisory sensors (with the official UAQI category palette as fallback), and the numeric pollutant sensors now carry the EPA category color. Previously only the `*_level` sensors had colors, so dashboard swatches for the AQI and pollutants rendered grey.
- Forecast array entries (`daily_forecast` / `hourly_forecast` on AQ, pollutant, and pollen sensors) now carry `color_hex` and `severity` per entry; weather alert entries carry `severity_rank`; minutecast segments and the Precipitation Intensity sensor carry `severity`.

### Fixed

- **UAQI daily forecast summarized each day with its *cleanest* hour.** UAQI is inverted (higher = better) and the aggregation took `max(aqi)`; it now reports the worst hour. Local AQI daily forecasts (higher = worse) are unchanged.
- Documentation: the reference claimed Google's Universal AQI uses the six EPA category names — it uses its own five-band ladder (Excellent → Poor air quality) on an inverted 0–100 scale. Corrected, with both scales now documented separately.

---

## [1.6.0] — 2026-08-12

### Added

- **Longer hourly forecasts** — the hourly forecast now reaches up to 240 hours, configurable in Configure → Weather Options (24 / 48 / 72 / 120 / 240, default **120**). Google returns at most 24 hours per API call, so each choice states its per-refresh cost.
- **Minute-by-minute precipitation nowcast** (opt-in, experimental) — a six-hour precipitation forecast refreshed every 15 minutes, adding **Minutes Until Precipitation**, **Precipitation Ends In**, **Precipitation Intensity** and **Precipitation Type** sensors. These update every minute independently of the API refresh, so countdowns stay accurate between fetches.
- **`particle_man.get_minute_forecast` action** — returns the next hour of nowcast data in the same shape as Home Assistant's OpenWeatherMap integration, so nowcast-capable dashboard cards work against it.
- **Hourly Forecast and Daily Forecast sensors** (disabled by default) — expose the full forecast list as an attribute, so templates can reach forecast data without building a trigger-based template sensor. Matches how the air quality and pollen sensors already work.
- Weather diagnostics now report the resolved plan: per-endpoint cadences, page counts, projected monthly calls, scale factor, and which endpoints (if any) were disabled to fit the budget.

### Changed

- **Weather endpoints now refresh on independent cadences** instead of all firing on every poll. Current conditions every 15 min, hourly forecast every 60, daily every 180, alerts every 30. At one location this projects **6,324 calls/month against the 10,000 free tier, down from 8,928** — while extending the hourly forecast from 24 to 120 hours.
- **Quota exhaustion now degrades instead of stopping dead.** Past 95% of the monthly weather limit only alerts and current conditions keep running; below that, endpoints drop in reverse priority order until the refresh fits the remaining quota.
- **Billable calls are now counted on any HTTP response**, including errors. A failed request still consumes quota, so reported usage may be slightly higher than before — it is more accurate, not higher in reality.
- **`calls_per_poll` on the weather diagnostic sensor is now an average** (a float) rather than a fixed integer, because endpoints refresh at different rates. The relationship it always satisfied still holds: `calls_per_poll × (effective_minutes ÷ fetch_interval_minutes) ≈ projected_monthly_calls`.
- **The options flow no longer skips the API and detail steps in Automagic mode.** Weather units, alerts, forecast length, air-quality and language options were previously unreachable at default settings.
- Air quality and pollen forecast arrays are no longer written to the recorder database. Nothing is lost — the frontend and templates still see them.

### Fixed

- **Quiet hours used the host's timezone rather than the one Home Assistant is configured for.** On any install where those differ, quiet hours started and ended at the wrong time — and since quiet hours feed the polling budget, so did the usage projection.
- A malformed response from one weather endpoint no longer aborts the whole update; the other endpoints, and air quality and pollen, keep their data.
- Weather endpoints no longer share a single error/backoff bucket, so a failure on one cannot suppress the others.
- CI: the Ruff job installed an unpinned version and had been failing since an upstream release changed its default rules. Pinned, with the findings fixed.
- Tests: the mock for the public alerts endpoint never matched its URL, so every test using it silently exercised the failure path.

---

## [1.5.3] — 2026-05-05

### Added

- **Pollen plant level sensors** — each plant species sensor (Oak, Maple, Ragweed, etc.) now has a corresponding `*_level` entity whose state is the category text (Very Low / Low / Moderate / High / Very High), consistent with pollutant and pollen type level sensors.

### Changed

- Pollutant level sensors, pollen type level sensors, and pollen plant level sensors are now **enabled by default** — no manual entity-registry toggle needed.

---

## [1.5.2] — 2026-05-04

### Changed

- Plant species sensors are now always created and enabled by default; the "Individual plant species sensors" Configure option has been removed.
- Air Quality Advisory sensor state is now the direct 6-level category string from Google (Good / Moderate / Unhealthy for Sensitive Groups / Unhealthy / Very Unhealthy / Hazardous), replacing the simplified 4-level mapping.

### Removed

- Precipitation Now binary sensor.

---

## [1.5.1] — 2026-05-04

### Added

- **Precipitation Now binary sensor** — `True` when it is currently raining or snowing; derived from the existing weather condition field, no additional API calls. Created automatically when the Weather API is enabled.
- **Weather alert sensors expanded to three** — replaces the single Weather Alerts sensor with three focused sensors, all created when weather alerts are enabled:
  - *Alert Count* — integer count of active warnings; full alert list, `highest_severity`, and `active_event_types` retained as attributes for backward-compatible automations.
  - *Alert Highest Severity* — text state: `MINOR` / `MODERATE` / `SEVERE` / `EXTREME`; `None` when no alerts are active.
  - *Alert Event Types* — comma-separated sorted list of active alert codes (e.g. `FLOOD_WATCH, TORNADO_WARNING`); `None` when no alerts are active.
- **`ozone` on weather entity** — current ozone concentration (ppb) sourced from the Air Quality API's existing `o3` pollutant data; no additional API calls. Returns `None` gracefully when the Air Quality API is disabled.
- **`native_apparent_temperature` in daily and twice-daily forecasts** — sourced from `feelsLikeMaxTemperature` (daytime) and `feelsLikeMinTemperature` (nighttime) from Google's daily forecast response.
- **Diagnostics endpoint** (`diagnostics.py`) — exposes coordinator state, API failure counts, backoff timers, and monthly usage via the HA diagnostics download; API key is redacted. Satisfies Gold quality rule.
- **Icon translations** (`icons.json`) — entity icons now declared via HA's translation system rather than `_attr_icon`, satisfying the Gold icon-translations rule.
- **Strict typing markers** (`py.typed`, `mypy.ini`) — enables mypy strict mode and marks the package as typed, satisfying the Platinum strict-typing rule.
- **Full test suite** — 280 tests at 99% overall coverage across 9 test files (`test_init`, `test_coordinator`, `test_config_flow`, `test_options_flow`, `test_sensor`, `test_binary_sensor`, `test_switch`, `test_weather`, `test_diagnostics`).

### Fixed

- **Automagic calculation uses actual billing month days** — interval was computed using a fixed 30-day month; it now uses `calendar.monthrange` on the current Pacific Time billing month (28–31 days), matching Google's quota reset cycle.
- **AQ and pollen fetch intervals scale with location count** — at 7+ locations both were previously hardcoded to 60 min regardless of monthly limits. Both now use the same `safe_interval_minutes()` formula as weather, floored at 60 min (Google's data refresh rate). Coordinator stores these as instance attributes so they can be overridden independently.
- **Quiet hours credited in automagic interval calculation** — the formula previously assumed 24/7 polling, so enabling quiet hours had no effect on the computed interval. Effective polling minutes per month are now reduced by the quiet hours window before computing the safe interval, giving fresher daytime data while still fitting within the limit.
- **5% safety buffer applied consistently** — a single `_AUTOMAGIC_BUFFER = 1.05` constant is applied inside `safe_interval_minutes()`. Previously, fudge factors were scattered across callers.
- **Projection sensors expose all interval assumptions as attributes** — the Monthly AQ Calls, Monthly Pollen Calls, and Monthly Weather Calls diagnostic sensors now include: `automagic_mode`, `num_locations`, `calls_per_poll`, `fetch_interval_minutes`, `quiet_hours_enabled`, `quiet_hours_window`, `active_hours_per_day`, `billing_month_days`, `effective_minutes_per_month`, `safety_buffer_pct`, `days_remaining`, and `calls_per_day`.
- **Config flow usage projections now use actual active polling time** — projected monthly call counts in the options form previously used a 30-day constant. They now use the actual billing month days and, when quiet hours are enabled, the reduced active polling window.
- **Weather alerts API call included in automagic calculation** — enabling weather alerts adds a 4th call per poll (`/publicAlerts`); this was not factored into the automagic interval or usage preview. The interval now uses 3 or 4 calls per poll depending on whether alerts are enabled.
- **Hourly forecast staleness during quiet hours** — hourly forecast entries are now filtered at read time to start from the current hour; previously, data fetched before quiet hours began would include past hours for the rest of the overnight window.
- **Daily forecast precipitation was daytime-only** — `native_precipitation` in daily forecast entries now sums daytime and nighttime QPF for a true 24-hour total; overnight rain and snow were previously dropped.
- **Removed invalid `native_precipitation` entity property** — `WeatherEntity` has no entity-level `native_precipitation` attribute (only the `Forecast` TypedDict does); the property was dead code that HA never surfaced.
- `resp.ok` usage replaced with `resp.status < 400` throughout `config_flow.py` and `coordinator.py` — `AiohttpClientMockResponse` has no `.ok` attribute, causing silent test failures with PHCC.
- Weather unit handling updated for HA 2026.x — `UnitSystem.is_metric` / `UnitSystem.name` removed in 2026.x; code now uses the configured `DEFAULT_WEATHER_UNITS` option directly.
- Quiet hours logic in automagic mode was silently dropped during a Samba deploy; restored the branch that gates polling when quiet hours are active regardless of mode.
- `_automagic()` in `OptionsFlow` crashed with `ValueError` on direct instantiation because `_get()` was evaluated eagerly before `self._options` was populated; deferred to lazy access.

### HA ADR Compliance

- **Fixed config flow translation bug** — `strings.json` and `en.json` had a duplicate `"step"` key under `"config"`; JSON parsers silently drop the first occurrence, so the initial setup screen displayed raw key names (`api_key`, `name`, `latitude`, `longitude`) instead of human-readable labels. All three config steps (`user`, `reauth_confirm`, `reconfigure`) are now correctly merged under a single key.
- **Added `integration_type: service` to manifest** — declares the integration as a cloud service, required for correct HACS and hassfest classification.
- **Added `quality_scale: platinum` to manifest** — documents the achieved quality tier.
- **Coordinator `_async_setup()` pattern** — renamed `async_load_tracking` to the standard `_async_setup()` hook introduced in HA 2024.8; the framework now calls it automatically before the first data fetch, and failures surface as `ConfigEntryNotReady` (with automatic retry) instead of a raw exception.
- **`always_update=False` on coordinator** — entity listeners no longer fire during quiet hours or API backoff when cached data is returned unchanged, preventing unnecessary state writes.
- **Fixed `EntityCategory` import paths** — both `sensor.py` and `switch.py` were importing from the deprecated `homeassistant.helpers.entity` path with a `# type: ignore` suppressor; updated to `homeassistant.const`.
- **`hass.data[DOMAIN]` cleanup on unload** — shared coordinator locks are now removed from `hass.data` when the last config entry for the domain is unloaded.
- **Parallel multi-location startup** — coordinator first-refresh calls are now run concurrently with `asyncio.gather()`; startup time for N locations is now ~1 API round-trip instead of N.

---

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
