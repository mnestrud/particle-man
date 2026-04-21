# Automations & Blueprints

Common automation patterns using Particle Man sensors. These can be added directly in the Home Assistant automation editor.

!!! note
    Blueprint imports and a dedicated blueprint library are planned. For now, use the YAML examples below as a starting point.

---

## Advisory Sensors — the easy way to automate

For most automations, the advisory sensors are simpler to use than the raw numeric values:

- **Air Quality Advisory** — `None` / `Caution` / `Warning` / `Alert`
- **Pollen Advisory** — `None` / `Very Low` / `Low` / `Moderate` / `High` / `Very High`
- **Weather Alerts** — integer count of active alerts

These update whenever the underlying data changes, so you don't need to set numeric thresholds.

---

## Alert when air quality gets bad

```yaml
alias: Alert — Air Quality Advisory
trigger:
  - platform: state
    entity_id: sensor.air_quality_advisory
    to:
      - Caution
      - Warning
      - Alert
  - platform: state
    entity_id: sensor.air_quality_advisory
    to: None
    id: cleared
action:
  - choose:
      - conditions:
          - condition: trigger
            id: cleared
        sequence:
          - service: notify.mobile_app_your_phone
            data:
              title: "✅ Air Quality Clear"
              message: "AQI is back to {{ state_attr('sensor.air_quality_advisory', 'aqi') }}."
      - conditions: []
        sequence:
          - service: notify.mobile_app_your_phone
            data:
              title: "⚠️ Air Quality {{ states('sensor.air_quality_advisory') }}"
              message: >
                AQI {{ state_attr('sensor.air_quality_advisory', 'aqi') }} —
                {{ state_attr('sensor.air_quality_advisory', 'category') }}.
                Dominant pollutant: {{ state_attr('sensor.air_quality_advisory', 'dominant_pollutant') }}.
```

---

## Alert when pollen is high

```yaml
alias: Alert — High Pollen Morning
trigger:
  - platform: time
    at: "07:00:00"
condition:
  - condition: state
    entity_id: sensor.pollen_advisory
    state:
      - High
      - Very High
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "🌿 {{ states('sensor.pollen_advisory') }} Pollen Today"
      message: >
        Dominant type: {{ state_attr('sensor.pollen_advisory', 'dominant_type') }}
        (index: {{ state_attr('sensor.pollen_advisory', 'dominant_index') }}).
        In season: {{ state_attr('sensor.pollen_advisory', 'in_season_types') | join(', ') }}.
```

---

## Alert on active weather warnings

```yaml
alias: Alert — Weather Warning
trigger:
  - platform: numeric_state
    entity_id: sensor.weather_alerts
    above: 0
  - platform: numeric_state
    entity_id: sensor.weather_alerts
    below: 1
    id: cleared
action:
  - choose:
      - conditions:
          - condition: trigger
            id: cleared
        sequence:
          - service: notify.mobile_app_your_phone
            data:
              title: "✅ Weather Alert Expired"
              message: "No active weather warnings."
      - conditions: []
        sequence:
          - service: notify.mobile_app_your_phone
            data:
              title: >
                ⛈️ {{ states('sensor.weather_alerts') }} Active Weather Warning(s)
              message: >
                Highest severity: {{ state_attr('sensor.weather_alerts', 'highest_severity') }}.
                Types: {{ state_attr('sensor.weather_alerts', 'active_event_types') | join(', ') }}.
```

---

## Close HVAC fresh-air intake on poor air quality

```yaml
alias: HVAC — Suspend fresh-air intake on bad AQI
trigger:
  - platform: state
    entity_id: sensor.air_quality_advisory
    to:
      - Warning
      - Alert
  - platform: state
    entity_id: sensor.air_quality_advisory
    to:
      - None
      - Caution
    id: ok
action:
  - service: >
      {{ 'input_boolean.turn_on' if trigger.id != 'ok' else 'input_boolean.turn_off' }}
    target:
      entity_id: input_boolean.hvac_fresh_air_suspended
```

---

## Alert when AQI crosses a numeric threshold

Use the numeric sensor when you need a specific threshold not covered by the advisory levels.

```yaml
alias: Alert — AQI Threshold
trigger:
  - platform: numeric_state
    entity_id: sensor.universal_aqi
    above: 150
    id: unhealthy
  - platform: numeric_state
    entity_id: sensor.universal_aqi
    below: 100
    id: recovered
action:
  - choose:
      - conditions:
          - condition: trigger
            id: unhealthy
        sequence:
          - service: notify.mobile_app_your_phone
            data:
              title: "⚠️ Air Quality Unhealthy"
              message: >
                AQI is {{ states('sensor.universal_aqi') }} —
                {{ state_attr('sensor.universal_aqi', 'category') }}.
      - conditions:
          - condition: trigger
            id: recovered
        sequence:
          - service: notify.mobile_app_your_phone
            data:
              title: "✅ Air Quality Improved"
              message: "AQI is back to {{ states('sensor.universal_aqi') }}."
```

---

## API usage warning

```yaml
alias: Alert — Particle Man API Usage Warning
trigger:
  - platform: template
    value_template: >
      {{ state_attr('sensor.aq_api_calls_monthly', 'status') in ['warning', 'critical']
         or state_attr('sensor.weather_api_calls_monthly', 'status') in ['warning', 'critical'] }}
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "📊 Particle Man API Usage"
      message: >
        AQ: {{ state_attr('sensor.aq_api_calls_monthly', 'pct_projected') }}% of limit.
        Weather: {{ state_attr('sensor.weather_api_calls_monthly', 'pct_projected') }}% of limit.
        Consider increasing your update interval.
```
