# Automations & Blueprints

Common automation patterns using Particle Man sensors. These can be added directly in the Home Assistant automation editor.

!!! note
    Blueprint imports and a dedicated blueprint library are planned. For now, use the YAML examples below as a starting point.

---

## Alert when AQI crosses a threshold

Sends a notification when air quality becomes Unhealthy (AQI > 150) and again when it recovers.

```yaml
alias: Alert — Air Quality Unhealthy
description: Notify when AQI rises above 150 or recovers below 100
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
              title: "⚠️ Air Quality Alert"
              message: >
                AQI is {{ states('sensor.universal_aqi') }} —
                {{ state_attr('sensor.universal_aqi', 'category') }}.
                Limit outdoor activity.
      - conditions:
          - condition: trigger
            id: recovered
        sequence:
          - service: notify.mobile_app_your_phone
            data:
              title: "✅ Air Quality Improved"
              message: >
                AQI is back to {{ states('sensor.universal_aqi') }} —
                {{ state_attr('sensor.universal_aqi', 'category') }}.
```

---

## Close HVAC fresh-air intake on poor air quality

Triggers an input boolean (or switch) that your HVAC automation can act on.

```yaml
alias: HVAC — Close fresh-air intake on bad AQI
trigger:
  - platform: numeric_state
    entity_id: sensor.universal_aqi
    above: 100
    for:
      minutes: 15
  - platform: numeric_state
    entity_id: sensor.universal_aqi
    below: 75
    for:
      minutes: 15
action:
  - service: >
      {% if trigger.to_state.state | int > 100 %}
        input_boolean.turn_on
      {% else %}
        input_boolean.turn_off
      {% endif %}
    target:
      entity_id: input_boolean.hvac_fresh_air_suspended
```

---

## Morning pollen warning

Sends a notification each morning when pollen is forecast to be High or above.

```yaml
alias: Alert — High pollen morning warning
trigger:
  - platform: time
    at: "07:00:00"
condition:
  - condition: or
    conditions:
      - condition: state
        entity_id: sensor.grass_pollen_level
        state: High
      - condition: state
        entity_id: sensor.tree_pollen_level
        state: High
      - condition: state
        entity_id: sensor.weed_pollen_level
        state: High
      - condition: state
        entity_id: sensor.grass_pollen_level
        state: Very High
      - condition: state
        entity_id: sensor.tree_pollen_level
        state: Very High
      - condition: state
        entity_id: sensor.weed_pollen_level
        state: Very High
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "🌿 High Pollen Today"
      message: >
        Grass: {{ states('sensor.grass_pollen_level') }},
        Tree: {{ states('sensor.tree_pollen_level') }},
        Weed: {{ states('sensor.weed_pollen_level') }}.
        Consider taking allergy medication before going out.
```

---

## API usage warning

Notifies you if projected monthly API usage exceeds 80% of your configured limit.

```yaml
alias: Alert — Particle Man API usage warning
trigger:
  - platform: template
    value_template: >
      {{ state_attr('sensor.aq_api_calls_monthly', 'status') in ['warning', 'critical'] }}
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "📊 Particle Man API Usage"
      message: >
        AQ API projected usage:
        {{ state_attr('sensor.aq_api_calls_monthly', 'pct_projected') }}% of monthly limit.
        Consider increasing your update interval.
```
