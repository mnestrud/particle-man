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
| Ozone | Ozone concentration in ppb (from Air Quality API; `None` when Air Quality is disabled) |

### Forecast Types

The entity exposes three forecast types accessible via `weather.get_forecasts`:

| Type | Coverage | Entries |
|---|---|---|
| `hourly` | Configurable — 24, 48, 72, 120 (default) or 240 hours | One entry per hour |
| `daily` | Next 5 days | 5 entries, daytime conditions |
| `twice_daily` | Next 5 days | 10 entries (day + night per day) |

Hourly forecast length is set in **Configure → Weather Options**. Google returns
at most 24 hours per API call, so each additional 24 hours costs one more call
per refresh — the option lists the cost of each choice. Longer forecasts are
automatically refreshed less often to stay inside your monthly limit.

Each forecast entry includes: condition, temperature, apparent temperature, precipitation probability, precipitation amount, wind speed/bearing/gust, humidity, pressure, cloud coverage, and UV index. Daily and twice-daily entries also include a low temperature. Daily precipitation is the 24-hour total (daytime + overnight). Hourly entries additionally include dew point. Hourly entries are always filtered to start at the current hour — past hours are automatically excluded, so the list stays current even if data was fetched before quiet hours started.

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

### UV Index Category

The current UV index expressed as a plain-language WHO category: **Low**, **Moderate**, **High**, **Very High**, or **Extreme**. The raw UV index value is available as the `uv_index` attribute. The numeric UV index is also available directly on the weather entity.

---

## Weather Alert Sensors

When weather alerts are enabled (**Configure → Weather Options**), Particle Man creates three sensors:

### Alert Count

**State:** The integer count of currently active warnings (0 = no alerts).

**Attributes:**

| Attribute | Description |
|---|---|
| `alerts` | Full list of active alerts — each entry includes title, severity, event type, area, start/expiration time, description, and instructions |
| `highest_severity` | Worst severity among active alerts: `MINOR`, `MODERATE`, `SEVERE`, or `EXTREME` |
| `active_event_types` | Sorted unique list of active event type codes (e.g. `FLOOD_WATCH`, `TORNADO_WARNING`) |

### Alert Highest Severity

**State:** The worst severity level across all active alerts: `MINOR`, `MODERATE`, `SEVERE`, or `EXTREME`. `None` when no alerts are active.

Use directly in automations to trigger on severity level without reading attributes.

### Alert Event Types

**State:** Comma-separated sorted list of active alert type codes, e.g. `FLOOD_WATCH, TORNADO_WARNING`. `None` when no alerts are active.

!!! note
    Weather alerts are only available in regions covered by Google's public alerts service, primarily the US and some international regions. ([Weather API coverage](https://developers.google.com/maps/documentation/weather/coverage))

A count of 0 with `None` severity and event types means no alerts are currently active — the sensors are working normally.

---

## Units

The weather entity and extra sensors use the units selected in **Configure → Weather Options**:

| Setting | Temperature | Wind | Precipitation | Visibility |
|---|---|---|---|---|
| **Metric** | °C | km/h | mm | km |
| **Imperial** | °F | mph | in | mi |

Home Assistant can convert between units for display purposes independently of the units stored in the sensor.

---

## Minute Forecast (Nowcast)

!!! warning "Experimental"
    Google classifies the minute forecast as **Experimental (pre-GA)** — its
    lowest stability tier. It is absent from the REST reference, the coverage
    table and the pricing list, so its availability and billing are both
    undocumented. Particle Man therefore treats it as billed and leaves it
    **off by default**. Field names may change without notice.

Enable it in **Configure → Weather Options**. It adds a six-hour precipitation
nowcast refreshed every 15 minutes, at a cost of roughly 2,200 calls per month
per location — about a quarter of the free tier.

Coverage appears limited to the US and Europe. Where Google has no nowcast for
your location the API returns an error; Particle Man disables the feature for
that location and raises a repair notice rather than retrying. It re-arms on the
next reload, so a later Google rollout is picked up automatically. No other
weather data is affected.

### Nowcast sensors

| Sensor | State |
|---|---|
| **Minutes Until Precipitation** | Minutes until precipitation begins; `0` while it is falling; unknown if none is expected in the window |
| **Precipitation Ends In** | Minutes until the current precipitation stops; unknown when nothing is falling |
| **Precipitation Intensity** | `NO_INTENSITY`, `LIGHT`, `MODERATE` or `HEAVY` right now |
| **Precipitation Type** | `RAIN`, `SNOW`, `HAIL` or `NONE` right now — the only place hail surfaces distinctly |

These update every minute, independently of the API refresh, so the countdown is
always current rather than jumping once per refresh cycle.

**Minutes Until Precipitation** attributes:

| Attribute | Description |
|---|---|
| `is_precipitating` | Whether precipitation is falling now |
| `starts_at` / `ends_at` | Bounds of the relevant precipitation run |
| `type` / `types` | Type of the run; `types` lists every type if it changes mid-run (e.g. rain turning to snow) |
| `max_intensity` / `max_probability` | Worst intensity and highest probability across the run |
| `runs` | Every distinct precipitation block in the window — usually 0–3 |
| `segments` | The full normalized segment list |
| `horizon_start` / `horizon_end` | Bounds of the forecast window |
| `stale` | True once the window has elapsed |

A segment counts as precipitation only when its type is not `NONE`, its
intensity is not `NO_INTENSITY`, and its probability is at least 50% — without
that threshold the sensor would read "raining" almost permanently in a drizzly
climate.

### `get_minute_forecast` action

The weather entity exposes `particle_man.get_minute_forecast`, returning the
next hour in the same shape as Home Assistant's OpenWeatherMap integration, so
nowcast-capable dashboard cards work against it:

```yaml
action: particle_man.get_minute_forecast
target:
  entity_id: weather.home_weather
```

```json
{
  "weather.home_weather": {
    "forecast": [
      {
        "datetime": "2026-08-12T14:22:00+00:00",
        "precipitation": 6.0,
        "type": "RAIN",
        "probability": 82,
        "intensity": "LIGHT",
        "end": "2026-08-12T14:24:00+00:00"
      }
    ]
  }
}
```

`precipitation` is a rate in mm/h. Dry stretches report `0` rather than being
omitted, so consumers draw a dry spell instead of a gap.

---

## Forecast Sensors

Home Assistant removed the `forecast` attribute from weather entities in 2024.4,
so templates can no longer read forecasts directly from `weather.*`. Particle
Man provides **Hourly Forecast** and **Daily Forecast** sensors whose `forecast`
attribute holds the full list, matching how the air quality and pollen sensors
already work.

Both are **disabled by default** — enable them in the entity settings if you
template against forecast data. The arrays are excluded from the recorder, so
they cost nothing to store no matter how long your history retention is.

---

## API Calls

Weather data comes from up to five Google Weather API endpoints, each refreshing
on its own cadence rather than all together:

| Endpoint | Purpose | Default cadence |
|---|---|---|
| [`GET /currentConditions`](https://developers.google.com/maps/documentation/weather/reference/rest/v1/currentConditions/lookup) | Current state, extra sensors | 15 min |
| [`GET /forecast/hours`](https://developers.google.com/maps/documentation/weather/reference/rest/v1/forecast.hours/lookup) | Hourly forecast | 60 min |
| [`GET /forecast/days`](https://developers.google.com/maps/documentation/weather/reference/rest/v1/forecast.days/lookup) | Daily + twice-daily forecast | 180 min |
| [`GET /publicAlerts`](https://developers.google.com/maps/documentation/weather/reference/rest/v1/publicAlerts/lookup) | Active weather alerts (if enabled) | 30 min |
| `GET /forecast/minutes` | Precipitation nowcast (if enabled) | 15 min |

At one location with default settings that projects to about **6,324 calls per
month** against Google's 10,000 free tier — or 8,556 with minutecast enabled.
See [Reference — How data updates](reference.md#automagic-the-weather-budget)
for the full budget model.
