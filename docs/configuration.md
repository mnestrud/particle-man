# Configuration Reference

---

## Initial Setup

Prompted when you first add the integration.

| Field | Description |
|---|---|
| API Key | Your Google Cloud API key with Air Quality and Pollen APIs enabled |
| Latitude | Location latitude (defaults to your HA home location) |
| Longitude | Location longitude (defaults to your HA home location) |
| Update interval | How often to poll the API in minutes (default: 60) |

---

## Options (Configure)

Accessed via the **Configure** button on the integration card after setup. Settings are organized into sections.

### Location & Polling

| Option | Default | Description |
|---|---|---|
| Latitude | (from setup) | Location latitude |
| Longitude | (from setup) | Location longitude |
| Update interval | 60 min | How often to poll both APIs (15–1440 minutes) |

### Forecast

| Option | Default | Description |
|---|---|---|
| Forecast days | 5 | Days of daily forecast data (1–5) |
| Language | en | BCP-47 language code for health recommendations and display names |

### Air Quality

| Option | Default | Description |
|---|---|---|
| Local AQI index | disabled | Show a regional AQI index in addition to Universal AQI |
| Local AQI index code | us_aqi | Which regional index to use when Local AQI is enabled |
| Health recommendations | disabled | Include per-population health recommendation text in sensor attributes |

### Pollen

| Option | Default | Description |
|---|---|---|
| Plant sensors | enabled | Create individual sensors for each pollen plant species |
| Plant descriptions | enabled | Include plant family, genus, and cross-reaction info in plant sensor attributes |

### API Limits

| Option | Default | Description |
|---|---|---|
| AQ API monthly limit | 10,000 | Monthly call limit for usage tracking and warnings |
| Pollen API monthly limit | 5,000 | Monthly call limit for usage tracking and warnings |
| Billing period reset day | 1 | Day of the month tracking resets (1–28) |
| Enforce limits | disabled | When enabled, polling stops when a limit is reached |

---

## Local AQI Index Codes

| Code | Index |
|---|---|
| `us_aqi` | United States (EPA AQI) |
| `can_ec` | Canada (Environment Canada) |
| `gbr_defra` | United Kingdom (DEFRA) |
| `deu_uba` | Germany (UBA) |
| `fra_atmo` | France (ATMO) |
| `chn_mep` | China (MEP) |
| `ind_cpcb` | India (CPCB) |
| `jpn_caqi` | Japan (CAQI) |
| `mex_sedema` | Mexico (SEDEMA) |
| `nld_lki` | Netherlands (LKI) |
| `sgp_nea` | Singapore (NEA) |
| `kor_keco` | South Korea (KECO) |
| `esp_calidad` | Spain (Calidad) |

---

## Sensor Attributes

### AQI and Pollutant sensors

| Attribute | Description |
|---|---|
| `daily_forecast` | List of daily peak values up to 5 days. Each entry: `datetime`, `aqi` or `max`, `category`, `epa_category` |
| `hourly_forecast` | List of hourly values up to 96 hours. Each entry: `datetime`, `aqi` or `value`, `category`, `epa_category` |
| `trend` | Direction based on hourly slope: `rising`, `falling`, or `stable` |

### Pollen sensors

| Attribute | Description |
|---|---|
| `daily_forecast` | List of daily forecast entries. Each entry: `datetime`, `index`, `category`, `color_hex` |
| `trend` | Direction based on today vs tomorrow: `up`, `down`, or `flat` |
| `expected_peak` | Forecast entry with the highest index value |
