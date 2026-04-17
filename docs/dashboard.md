# Dashboard Examples

Sample card configurations for common Particle Man use cases. These require the entity IDs from your installation — replace `YOUR_ENTRY_ID` with the actual prefix shown in your entities list.

!!! tip
    Find your entity IDs under **Settings → Devices & Services → Particle Man → entities**, or use the Developer Tools → States search.

---

## AQI Gauge

A simple gauge showing current Universal AQI with color zones.

```yaml
type: gauge
entity: sensor.universal_aqi
min: 0
max: 300
severity:
  green: 0
  yellow: 51
  red: 101
name: Air Quality
```

---

## 96-Hour AQI Forecast Chart

Requires the [mini-graph-card](https://github.com/kalkih/mini-graph-card) custom card (available in HACS).

```yaml
type: custom:mini-graph-card
entity: sensor.universal_aqi
attribute: hourly_forecast
attribute_path: $.*.aqi
name: AQI — Next 96 Hours
hours_to_show: 96
points_per_hour: 1
line_color: "#2196f3"
show:
  labels: true
  points: false
```

---

## 5-Day Daily AQI Forecast

Requires [ApexCharts Card](https://github.com/RomRider/apexcharts-card) (available in HACS).

```yaml
type: custom:apexcharts-card
header:
  title: AQI Forecast — 5 Days
  show: true
series:
  - entity: sensor.universal_aqi
    attribute: daily_forecast
    data_generator: |
      return entity.attributes.daily_forecast.map(d => [
        new Date(d.datetime).getTime(),
        d.aqi
      ]);
    name: Peak AQI
    type: bar
    color: "#2196f3"
```

---

## Pollen Summary Glance

```yaml
type: glance
title: Pollen Today
entities:
  - entity: sensor.grass_pollen
    name: Grass
  - entity: sensor.tree_pollen
    name: Tree
  - entity: sensor.weed_pollen
    name: Weed
```

---

## Pollutant Overview

```yaml
type: entities
title: Current Pollutants
entities:
  - entity: sensor.pm2_5
    name: PM2.5
  - entity: sensor.pm10
    name: PM10
  - entity: sensor.ozone_o3
    name: Ozone
  - entity: sensor.nitrogen_dioxide_no2
    name: NO2
  - entity: sensor.carbon_monoxide_co
    name: CO
  - entity: sensor.sulfur_dioxide_so2
    name: SO2
```

---

More examples coming. If you've built something useful, feel free to open a [GitHub issue](https://github.com/mnestrud/particle-man/issues) to share it.
