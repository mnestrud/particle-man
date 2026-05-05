# Sensors & Entities

Particle Man creates four devices per monitored location, each grouping related sensors.

---

## Particle Man Pollution

!!! info "About the two AQI types"

    **Universal AQI (UAQI)** is Google's own air quality index — a single 0–500 scale that means the same thing everywhere. It is always available and is the primary AQI sensor. ([Google UAQI reference](https://developers.google.com/maps/documentation/air-quality/air-quality-indexes))

    **Regional/Local AQI** is the official index published by your country's regulatory authority — for example, the US EPA AQI, UK DEFRA index, or Germany's UBA index. It measures the same air quality but applies the thresholds and categories defined by that authority. This is optional and disabled by default; enable it in Configure if you want your country's standard alongside the universal one. 13 regional standards are supported — see [Setup](setup.md#air-quality-options).

### Universal AQI

The main air quality number. Google's **Universal AQI (UAQI)** — a single 0–500 scale that works the same way in every country. Higher is worse.

| Range | Category | What it means |
|---|---|---|
| 0–50 | Good | Air quality is satisfactory |
| 51–100 | Moderate | Acceptable; some pollutants may be a concern for sensitive people |
| 101–150 | Unhealthy for Sensitive Groups | Children, elderly, and people with lung or heart conditions should limit outdoor exertion |
| 151–200 | Unhealthy | Everyone may begin to experience health effects |
| 201–300 | Very Unhealthy | Health alert — everyone may experience serious effects |
| 301–500 | Hazardous | Emergency conditions |

Includes a **trend** (`rising`, `falling`, `stable`) calculated from the hourly forecast, plus `daily_forecast` and `hourly_forecast` attributes for charts.

### Universal AQI Level

The same data as Universal AQI expressed as a category text (`Good`, `Moderate`, etc.). Useful for display cards and condition-based automations.

### Air Quality Advisory

A simplified advisory level for automations — maps the UAQI category to four levels:

| Advisory | AQI Categories |
|---|---|
| None | Good, Moderate |
| Caution | Unhealthy for Sensitive Groups |
| Warning | Unhealthy |
| Alert | Very Unhealthy, Hazardous |

**Attributes:** AQI value, full category, dominant pollutant, elevated pollutants list, trend, and health recommendations (if enabled).

Use this sensor in automations when you want simple state-based triggers without numeric thresholds.

### Local AQI *(optional)*

A country-specific index alongside the Universal AQI. Enable in **Configure → Air Quality Options**. Supports 13 regional standards. ([AQI indexes reference](https://developers.google.com/maps/documentation/air-quality/air-quality-indexes))

### Pollutant Sensors

A sensor for each pollutant detected at your location:

| Pollutant | What it is |
|---|---|
| PM2.5 | Fine particles from smoke, traffic, industry |
| PM10 | Coarser particles — dust, pollen, mold spores |
| O3 (Ozone) | Ground-level ozone from sunlight + traffic exhaust |
| NO2 (Nitrogen Dioxide) | Mainly from vehicles and power plants |
| CO (Carbon Monoxide) | From combustion — vehicles, fires |
| SO2 (Sulfur Dioxide) | From burning fossil fuels, industrial activity |

Each shows current concentration with an **EPA health category**, trend, and hourly/daily forecasts. A matching **Level sensor** (e.g. "PM2.5 Level") shows the plain-language EPA category.

Pollutant sensors are **disabled by default** — enable individually as needed.

([Pollutants reference](https://developers.google.com/maps/documentation/air-quality/pollutants))

??? "Sensor attributes"

    **AQI and Pollutant sensors**

    | Attribute | Description |
    |---|---|
    | `daily_forecast` | Daily peak values up to configured forecast days. Each entry: `datetime`, `aqi` or `max`, `category` |
    | `hourly_forecast` | Hourly values up to 96 hours. Each entry: `datetime`, `aqi` or `value`, `category`, `epa_category` |
    | `trend` | Direction based on hourly slope: `rising`, `falling`, or `stable` |

---

## Particle Man Pollen

### Pollen Advisory

The worst pollen level across all in-season pollen types. Levels: `None`, `Very Low`, `Low`, `Moderate`, `High`, `Very High`.

**Attributes:** dominant type, dominant index value, in-season types list, all levels by type, health recommendations (if enabled).

Use this for simple automations — trigger on `High` or `Very High` without checking each type individually.

### Pollen Type Sensors

Three sensors covering the main pollen categories: **Grass**, **Tree**, and **Weed**. Each shows a 0–5 index value and category, plus a trend and 5-day daily forecast.

### Pollen Plant Sensors

Individual sensors for specific plant species — Oak, Ragweed, Birch, and others depending on your region. Each includes the same index/category/trend data, plus family, genus, and cross-reaction information. Each species also has a corresponding **Level sensor** (e.g. "Oak Pollen Level") whose state is the category text, consistent with pollutant and pollen type sensors.

!!! note
    Pollen data is only available in regions covered by Google's Pollen API. [Coverage map](https://developers.google.com/maps/documentation/pollen/coverage) — primarily North America and Europe. If your location isn't covered, pollen sensors will remain unavailable.

??? "Sensor attributes"

    | Attribute | Description |
    |---|---|
    | `daily_forecast` | Daily forecast entries: `datetime`, `index`, `category`, `color_hex` |
    | `trend` | `up`, `down`, or `flat` based on today vs tomorrow |
    | `expected_peak` | Forecast entry with the highest index value |

([Pollen types reference](https://developers.google.com/maps/documentation/pollen/pollen-types))

---

## Particle Man Weather

The weather device includes a native HA weather entity and several extra sensors. See [Weather](weather.md) for full details.

### Weather Entity

Current conditions and three forecast types (hourly 24h, daily 5-day, twice-daily 5-day). Works with all native HA weather cards and the `weather.get_forecasts` action.

### Extra Sensors

| Sensor | Description |
|---|---|
| Thunderstorm Probability | Probability (%) of a thunderstorm this hour |
| Heat Index | Feels-like temperature in hot and humid conditions |
| Wind Chill | Feels-like temperature in cold and windy conditions |
| UV Index Category | WHO UV scale text: Low / Moderate / High / Very High / Extreme |

### Weather Alert Sensors *(optional)*

Three sensors created together when **Enable weather alerts** is on in **Configure → Weather Options**:

| Sensor | State | Notes |
|---|---|---|
| Alert Count | Integer | Number of active warnings. Attributes: full alert list, `highest_severity`, `active_event_types`. |
| Alert Highest Severity | Text | `MINOR`, `MODERATE`, `SEVERE`, or `EXTREME`; `None` when no alerts. |
| Alert Event Types | Text | Comma-separated sorted list of active alert codes, e.g. `FLOOD_WATCH, TORNADO_WARNING`; `None` when no alerts. |

The Alert Count sensor retains the `highest_severity` and `active_event_types` attributes for automations already using them. The two new sensors expose those same values as first-class entity states.

---

## Particle Man Diagnostics

### Fetch Timestamp Sensors

Three sensors — one per API — showing when Particle Man last successfully called each Google API. Only created when the corresponding API is enabled.

| Sensor | State | `data_timestamp` attribute |
|---|---|---|
| **AQ Last Fetched** | When the integration last called the Air Quality API | When Google generated that AQ observation |
| **Pollen Last Fetched** | When the integration last called the Pollen API | — (not available from Pollen API) |
| **Weather Last Fetched** | When the integration last called the Weather API | When Google generated that weather observation |

The state and `data_timestamp` are typically different: the state is the actual poll time, while `data_timestamp` reflects when Google published the underlying data (usually rounded to the hour). Before the first poll after a restart, all three sensors are `unavailable`.

### API Call Sensors (Monthly)

One sensor each for AQ, Pollen, and Weather API calls.

| Attribute | Description |
|---|---|
| `monthly_limit` | Your configured limit for this API |
| `projected_monthly` | Estimated calls by end of billing period at current rate |
| `pct_of_limit` | Percentage of limit used so far |
| `pct_projected` | Percentage of limit the projection will reach |
| `status` | `ok` / `warning` (projected ≥95% of limit) / `critical` (projected ≥100% of limit) |
| `billing_period` | Current period in YYYY-MM format (Pacific Time) |
| `shared_total_calls` | Total across all entries sharing this API key |
| `locations_sharing_key` | Number of locations sharing this key |

### HA Diagnostics download

The full diagnostics payload (available via **Settings → Devices & Services → Particle Man → Download Diagnostics**) includes a `quiet_hours_active_now` field per location, indicating whether polling is currently paused due to quiet hours — distinct from `quiet_hours_enabled`, which only reflects whether the feature is turned on.
