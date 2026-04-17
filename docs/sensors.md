# What's Included

Particle Man creates three devices, each grouping related sensors.

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

### Local AQI *(optional)*

A country-specific index in addition to the Universal AQI — for example, the US AQI, UK DEFRA index, or German UBA index. Enable this in **Configure** after setup. Supports 13 regional indices.

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

### Pollen Type Sensors

Three sensors covering the main pollen categories: **Grass**, **Tree**, and **Weed**. Each shows a 0–5 index value and a category (`None` through `Very High`), plus a trend and a 5-day daily forecast.

### Pollen Plant Sensors *(optional)*

Individual sensors for specific plant species — Oak, Ragweed, Birch, and others depending on your region. Each includes the same index/category/trend data, plus family, genus, and cross-reaction information if plant descriptions are enabled.

!!! note
    Pollen data is only available in regions covered by Google's Pollen API, which includes most of North America and Europe. If your location isn't covered, pollen sensors will remain unavailable.

---

## Particle Man Diagnostics

### Last API Update

A timestamp showing when Google last refreshed the data for your location. Useful for confirming the integration is working.

### AQ API Calls (Monthly)

Tracks how many Air Quality API calls have been made in the current billing period. Includes projected usage through end of period and a status (`ok` / `warning` / `critical`) based on your configured limit.

### Pollen API Calls (Monthly)

Same as above, but for Pollen API calls.

See [API Usage & Free Tier](api-usage.md) for details on staying within Google's free limits.
