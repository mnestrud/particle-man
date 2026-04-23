# Weather

Particle Man creates a native Home Assistant weather entity using the [Google Weather API](https://developers.google.com/maps/documentation/weather/overview), along with several extra sensors for data that doesn't fit the standard weather card.

---

## The Weather Entity

The weather entity appears as **Particle Man Weather** in your weather cards and automations. It works with all native HA weather cards and supports the `weather.get_forecasts` action.

### Current Conditions

| Property | Source |
|---|---|
| Condition | Mapped from Google's weather condition type |
| Temperature | Current air temperature |
| Feels Like | Apparent temperature accounting for humidity and wind |
| Dew Point | Temperature at which air becomes saturated |
| Humidity | Relative humidity (%) |
| Wind Speed | Speed at standard anemometer height |
| Wind Direction | Bearing in degrees |
| Wind Gust | Maximum gust speed |
| Pressure | Mean sea level pressure (hPa) |
| Visibility | Horizontal visibility distance |
| UV Index | Current UV index |
| Cloud Cover | Percentage of sky covered by clouds |
| Precipitation | Liquid equivalent precipitation (1h) |

### Forecast Types

The entity exposes three forecast types accessible via `weather.get_forecasts`:

| Type | Coverage | Entries |
|---|---|---|
| `hourly` | Next 24 hours | 24 entries, one per hour |
| `daily` | Next 5 days | 5 entries, daytime conditions |
| `twice_daily` | Next 5 days | 10 entries (day + night per day) |

Each forecast entry includes: condition, temperature, precipitation probability, wind speed/bearing/gust, humidity, pressure, cloud coverage, and UV index. Daily entries also include a low temperature.

### Condition Mapping

Google's weather conditions are mapped to Home Assistant standard conditions. ([Google weather condition types](https://developers.google.com/maps/documentation/weather/weather-conditions))

| Google Condition | HA Condition |
|---|---|
| CLEAR (daytime) | sunny |
| CLEAR (nighttime) | clear-night |
| MOSTLY_CLEAR, PARTLY_CLOUDY | partlycloudy |
| MOSTLY_CLOUDY, CLOUDY, OVERCAST | cloudy |
| DRIZZLE, LIGHT_RAIN, RAIN, RAIN_SHOWERS | rainy |
| HEAVY_RAIN, HEAVY_RAIN_SHOWERS | pouring |
| THUNDERSTORM, THUNDERSTORM_WITH_RAIN, SCATTERED_THUNDERSTORMS | lightning-rainy |
| LIGHTNING | lightning |
| LIGHT_SNOW, SNOW, HEAVY_SNOW, SNOW_SHOWERS, BLIZZARD | snowy |
| SLEET, HAIL, FREEZING_RAIN, FREEZING_DRIZZLE, ICE_PELLETS, WINTRY_MIX | hail |
| FOG, HAZE, SMOKE | fog |
| WINDY, BREEZY | windy |
| DUST, SAND, TORNADO, HURRICANE, TROPICAL_STORM | exceptional |

---

## Extra Weather Sensors

These sensors expose weather data that doesn't fit into the standard `WeatherEntity` schema.

### Thunderstorm Probability (%)

The probability of a thunderstorm occurring in the current hour. Useful for automations that need to respond before a storm arrives rather than after conditions worsen.

### Heat Index (°)

The "feels like" temperature accounting for high humidity in warm conditions. Only meaningful when temperature and humidity are both elevated; Google returns `null` otherwise.

### Wind Chill (°)

The "feels like" temperature accounting for wind in cold conditions. Only meaningful in cold weather; Google returns `null` otherwise.

---

## Weather Alerts Sensor

When weather alerts are enabled (Configure → Weather Options), Particle Man creates a **Weather Alerts** sensor.

**State:** The count of currently active weather alerts (0 = no alerts).

**Attributes:**

| Attribute | Description |
|---|---|
| `alerts` | List of active alerts, each with title, severity, event type, area, start/expiration time, description, and instructions |
| `highest_severity` | Worst severity level among active alerts: `MINOR`, `MODERATE`, `SEVERE`, or `EXTREME` |
| `active_event_types` | Unique list of event types (e.g. `TORNADO_WARNING`, `FLOOD_WATCH`) |

A value of 0 with empty attributes means no alerts are currently active — the sensor is working normally.

!!! note
    Weather alerts are only available in regions covered by Google's public alerts service, primarily the US and some international regions. ([Weather API coverage](https://developers.google.com/maps/documentation/weather/coverage))

---

## Units

The weather entity and extra sensors use the units selected in **Configure → Weather Options**:

| Setting | Temperature | Wind | Precipitation | Visibility |
|---|---|---|---|---|
| **Metric** | °C | km/h | mm | km |
| **Imperial** | °F | mph | in | mi |

Home Assistant can convert between units for display purposes independently of the units stored in the sensor.

---

## API Calls

The weather data is fetched from three Google Weather API endpoints per poll cycle:

| Endpoint | Purpose |
|---|---|
| [`GET /currentConditions`](https://developers.google.com/maps/documentation/weather/reference/rest/v1/currentConditions/lookup) | Current state, extra sensors |
| [`GET /forecast/hours`](https://developers.google.com/maps/documentation/weather/reference/rest/v1/forecast.hours/lookup) | 24-hour hourly forecast |
| [`GET /forecast/days`](https://developers.google.com/maps/documentation/weather/reference/rest/v1/forecast.days/lookup) | 5-day daily + twice-daily forecast |
| [`GET /publicAlerts`](https://developers.google.com/maps/documentation/weather/reference/rest/v1/publicAlerts/lookup) | Active weather alerts (only if enabled) |

This totals **3 calls per poll** (4 with alerts enabled). At 60-minute polling: ~2,160 calls/month — well within Google's 10,000/month free tier. See [Reference — How data updates](reference.md#how-data-updates) for full quota math.
