# What's Included

Particle Man creates four devices, each grouping related sensors.

---

## Particle Man Pollution

### Universal AQI

The main air quality number. This is Google's **Universal AQI (UAQI)** — a single 0–500 scale that works the same way in every country. Higher is worse.

| Range | Category | What it means |
|---|---|---|
| 0–50 | Good | Air quality is satisfactory |
| 51–100 | Moderate | Acceptable; some pollutants may be a concern for sensitive people |
| 101–150 | Unhealthy for Sensitive Groups | Children, elderly, and people with lung or heart conditions should limit outdoor exertion |
| 151–200 | Unhealthy | Everyone may begin to experience health effects |
| 201–300 | Very Unhealthy | Health alert — everyone may experience serious effects |
| 301–500 | Hazardous | Emergency conditions |

The sensor also includes a **trend** (`rising`, `falling`, `stable`) calculated from the hourly forecast, and a `daily_forecast` and `hourly_forecast` attribute for charts.

### Universal AQI Level

The same data as Universal AQI but expressed as the category text (`Good`, `Moderate`, etc.) rather than a number. Useful for display cards and condition-based automations.

### Air Quality Advisory

A simplified advisory level for easy automation. Maps the Universal AQI category to four levels:

| Advisory | AQI Categories |
|---|---|
| None | Good, Moderate |
| Caution | Unhealthy for Sensitive Groups |
| Warning | Unhealthy |
| Alert | Very Unhealthy, Hazardous |

**Attributes:** AQI value, full category, dominant pollutant, elevated pollutants (list of pollutants above Good threshold), trend, and health recommendations (if enabled).

### Local AQI *(optional)*

A country-specific index in addition to the Universal AQI — for example, the US AQI, UK DEFRA index, or German UBA index. Enable this in **Configure → Air Quality Options**. Supports 13 regional indices.

### Pollutant Sensors

A sensor for each pollutant detected at your location. Common pollutants include:

| Pollutant | What it is |
|---|---|
| PM2.5 | Fine particles from smoke, traffic, industry |
| PM10 | Coarser particles — dust, pollen, mold spores |
| O3 (Ozone) | Ground-level ozone from sunlight + traffic exhaust |
| NO2 (Nitrogen Dioxide) | Mainly from vehicles and power plants |
| CO (Carbon Monoxide) | From combustion — vehicles, fires |
| SO2 (Sulfur Dioxide) | From burning fossil fuels, industrial activity |

Each pollutant sensor shows the current concentration and includes an **EPA health category** (for the six pollutants above), a trend, and hourly and daily forecasts.

A matching **Level sensor** (e.g. "PM2.5 Level") shows the plain-language EPA category for easier use in dashboards and automations.

---

## Particle Man Pollen

### Pollen Advisory

A simplified pollen level for easy automation — shows the **worst level across all in-season pollen types**. Levels: `None`, `Very Low`, `Low`, `Moderate`, `High`, `Very High`.

**Attributes:** dominant type (whichever type is worst), dominant index value, in-season types list, all levels by type, and health recommendations (if enabled).

### Pollen Type Sensors

Three sensors covering the main pollen categories: **Grass**, **Tree**, and **Weed**. Each shows a 0–5 index value and a category (`None` through `Very High`), plus a trend and a 5-day daily forecast.

### Pollen Plant Sensors *(optional)*

Individual sensors for specific plant species — Oak, Ragweed, Birch, and others depending on your region. Each includes the same index/category/trend data, plus family, genus, and cross-reaction information if plant descriptions are enabled.

!!! note
    Pollen data is only available in regions covered by Google's Pollen API, which includes most of North America and Europe. If your location isn't covered, pollen sensors will remain unavailable.

---

## Particle Man Weather

The weather device includes the native Home Assistant weather entity plus several extra sensors. See [Weather](weather.md) for full details.

### Weather Entity

Shows current conditions and provides hourly (24h), daily (5-day), and twice-daily (5-day day+night) forecasts. Works with all native HA weather cards and the `weather.get_forecasts` action.

### Extra Sensors

| Sensor | What it shows |
|---|---|
| Thunderstorm Probability | Probability (%) of a thunderstorm this hour |
| Heat Index | "Feels like" temperature in hot and humid conditions |
| Wind Chill | "Feels like" temperature in cold and windy conditions |

### Weather Alerts *(optional)*

When enabled, shows the count of currently active weather warnings (0 = no alerts). Attributes include the full alert list with severity, event type, area, and instructions. Enable in **Configure → Weather Options**.

---

## Particle Man Diagnostics

### Last API Update

A timestamp showing when Google last refreshed the data for your location.

### AQ API Calls (Monthly)

Tracks how many Air Quality API calls have been made in the current billing period. Includes projected usage through end of period and a status (`ok` / `warning` / `critical`) based on your configured limit.

**Attributes:** `monthly_limit`, `projected_monthly`, `pct_of_limit`, `pct_projected`, `status`, `billing_period`, `shared_total_calls`, `locations_sharing_key`

### Pollen API Calls (Monthly)

Same as above, but for Pollen API calls.

### Weather API Calls (Monthly)

Same as above, but for Weather API calls.

See [API Usage & Free Tier](api-usage.md) for details on staying within Google's free limits.
