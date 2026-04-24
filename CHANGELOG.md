# Changelog

## [Unreleased]

### Added

- **Diagnostics endpoint** (`diagnostics.py`) — exposes coordinator state, API failure counts, backoff timers, and monthly usage via the HA diagnostics download; API key is redacted. Satisfies Gold quality rule.
- **Icon translations** (`icons.json`) — entity icons now declared via HA's translation system rather than `_attr_icon`, satisfying the Gold icon-translations rule.
- **Strict typing markers** (`py.typed`, `mypy.ini`) — enables mypy strict mode and marks the package as typed, satisfying the Platinum strict-typing rule.
- **Full test suite** — expanded from 2 test files to 8 (`test_init`, `test_coordinator`, `test_config_flow`, `test_options_flow`, `test_sensor`, `test_switch`, `test_weather`, `test_diagnostics`); 231 tests at 99% overall coverage, 100% on `config_flow`.

### Fixed

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
