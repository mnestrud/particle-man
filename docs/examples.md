# Examples

---

## Blueprints

Ready-to-import automations. Each blueprint uses entity selectors so it works with any Particle Man location.

### AQI Alert

Notify when the Air Quality Advisory reaches a configured level; send a recovery notification when it clears.

[Import Blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fmnestrud%2Fparticle-man%2Fmain%2Fblueprints%2Faqi_alert.yaml){ .md-button .md-button--primary }

??? "View blueprint YAML"

    ```yaml
    blueprint:
      name: "Particle Man: AQI Alert"
      description: >-
        Sends a notification when the Air Quality Advisory reaches a configured level,
        and a recovery notification when it clears.
      domain: automation
      source_url: https://github.com/mnestrud/particle-man/blob/main/blueprints/aqi_alert.yaml
      input:
        aqi_advisory:
          name: Air Quality Advisory sensor
          description: >-
            Select your Particle Man Air Quality Advisory sensor
            (Pollution device → Air Quality Advisory).
          selector:
            entity:
              domain: sensor
        alert_level:
          name: Alert when advisory reaches
          default: Unhealthy for Sensitive Groups
          selector:
            select:
              options:
                - label: "Moderate"
                  value: Moderate
                - label: "Unhealthy for Sensitive Groups"
                  value: Unhealthy for Sensitive Groups
                - label: "Unhealthy"
                  value: Unhealthy
                - label: "Very Unhealthy"
                  value: Very Unhealthy
                - label: "Hazardous"
                  value: Hazardous
        alert_actions:
          name: Actions on alert
          description: What to do when air quality reaches the alert level.
          selector:
            action: {}
        clear_actions:
          name: Actions on clear
          description: What to do when air quality returns below the alert level. Leave empty to skip.
          default: []
          selector:
            action: {}

    variables:
      level: !input alert_level
      all_levels:
        - Good
        - Moderate
        - Unhealthy for Sensitive Groups
        - Unhealthy
        - Very Unhealthy
        - Hazardous
      threshold_idx: "{{ all_levels.index(level) }}"

    triggers:
      - trigger: state
        entity_id: !input aqi_advisory
        id: changed

    conditions:
      - condition: or
        conditions:
          - condition: and
            conditions:
              - condition: trigger
                id: changed
              - condition: template
                value_template: >-
                  {{ trigger.to_state.state in all_levels
                     and all_levels.index(trigger.to_state.state) >= threshold_idx | int }}
          - condition: and
            conditions:
              - condition: trigger
                id: changed
              - condition: template
                value_template: >-
                  {{ trigger.from_state is not none
                     and trigger.from_state.state in all_levels
                     and all_levels.index(trigger.from_state.state) >= threshold_idx | int
                     and (trigger.to_state.state not in all_levels
                          or all_levels.index(trigger.to_state.state) < threshold_idx | int) }}

    actions:
      - if:
          - condition: template
            value_template: >-
              {{ trigger.to_state.state in all_levels
                 and all_levels.index(trigger.to_state.state) >= threshold_idx | int }}
        then: !input alert_actions
        else: !input clear_actions
    ```

---

### Morning Pollen Brief

Daily notification when the Pollen Advisory reaches a configured level.

[Import Blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fmnestrud%2Fparticle-man%2Fmain%2Fblueprints%2Fpollen_morning_brief.yaml){ .md-button .md-button--primary }

??? "View blueprint YAML"

    ```yaml
    blueprint:
      name: "Particle Man: Morning Pollen Brief"
      description: >-
        Sends a daily notification at a configured time when the Pollen Advisory
        is at or above a configured level.
      domain: automation
      source_url: https://github.com/mnestrud/particle-man/blob/main/blueprints/pollen_morning_brief.yaml
      input:
        pollen_advisory:
          name: Pollen Advisory sensor
          description: >-
            Select your Particle Man Pollen Advisory sensor
            (Pollen device → Pollen Advisory).
          selector:
            entity:
              domain: sensor
        grass_sensor:
          name: Grass Pollen sensor
          selector:
            entity:
              domain: sensor
        tree_sensor:
          name: Tree Pollen sensor
          selector:
            entity:
              domain: sensor
        weed_sensor:
          name: Weed Pollen sensor
          selector:
            entity:
              domain: sensor
        alert_level:
          name: Notify when pollen reaches
          default: High
          selector:
            select:
              options:
                - Very Low
                - Low
                - Moderate
                - High
                - Very High
        brief_time:
          name: Notification time
          default: "07:00:00"
          selector:
            time: {}
        notify_actions:
          name: Notification actions
          selector:
            action: {}

    variables:
      level: !input alert_level
      all_levels: ["Very Low", "Low", "Moderate", "High", "Very High"]

    triggers:
      - trigger: time
        at: !input brief_time

    conditions:
      - condition: template
        value_template: >-
          {% set idx = all_levels.index(level) %}
          {{ all_levels.index(states(pollen_advisory)) >= idx }}

    actions: !input notify_actions
    ```

---

### Outdoor Activity Check

Morning summary combining current AQI advisory and weather conditions.

[Import Blueprint](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fmnestrud%2Fparticle-man%2Fmain%2Fblueprints%2Foutdoor_activity_check.yaml){ .md-button .md-button--primary }

??? "View blueprint YAML"

    ```yaml
    blueprint:
      name: "Particle Man: Outdoor Activity Check"
      description: >-
        Morning summary combining AQI advisory and weather conditions
        to help plan outdoor activities.
      domain: automation
      source_url: https://github.com/mnestrud/particle-man/blob/main/blueprints/outdoor_activity_check.yaml
      input:
        aqi_advisory:
          name: Air Quality Advisory sensor
          selector:
            entity:
              domain: sensor
        weather_entity:
          name: Weather entity
          description: Select your Particle Man Weather entity.
          selector:
            entity:
              domain: weather
        check_time:
          name: Check time
          default: "07:30:00"
          selector:
            time: {}
        notify_actions:
          name: Notification actions
          selector:
            action: {}

    triggers:
      - trigger: time
        at: !input check_time

    actions: !input notify_actions
    ```

    !!! tip
        In your notification action, use template variables to build the message:
        ```
        AQI: {{ states(aqi_advisory) }} ({{ state_attr(aqi_advisory, 'aqi') }}).
        Weather: {{ states(weather_entity) }}, {{ state_attr(weather_entity, 'temperature') }}°.
        ```

---

## Automation YAML

Raw YAML for direct use in the Home Assistant automation editor. Replace entity IDs with your own — find them under **Settings → Devices & Services → Particle Man → entities**.

### Alert when air quality gets bad

Uses the Air Quality Advisory sensor for simple state-based triggers.

```yaml
alias: Alert — Air Quality Advisory
trigger:
  - trigger: state
    entity_id: sensor.air_quality_advisory
    to:
      - Unhealthy for Sensitive Groups
      - Unhealthy
      - Very Unhealthy
      - Hazardous
  - trigger: state
    entity_id: sensor.air_quality_advisory
    to:
      - Good
      - Moderate
    id: cleared
action:
  - choose:
      - conditions:
          - condition: trigger
            id: cleared
        sequence:
          - action: notify.mobile_app_your_phone
            data:
              title: "✅ Air Quality Clear"
              message: "Advisory is back to {{ states('sensor.air_quality_advisory') }} (AQI {{ state_attr('sensor.air_quality_advisory', 'aqi') }})."
      - conditions: []
        sequence:
          - action: notify.mobile_app_your_phone
            data:
              title: "⚠️ Air Quality {{ states('sensor.air_quality_advisory') }}"
              message: >
                AQI {{ state_attr('sensor.air_quality_advisory', 'aqi') }}.
                Dominant pollutant: {{ state_attr('sensor.air_quality_advisory', 'dominant_pollutant') }}.
```

### Alert when pollen is high

```yaml
alias: Alert — High Pollen Morning
trigger:
  - trigger: time
    at: "07:00:00"
condition:
  - condition: state
    entity_id: sensor.pollen_advisory
    state:
      - High
      - Very High
action:
  - action: notify.mobile_app_your_phone
    data:
      title: "🌿 {{ states('sensor.pollen_advisory') }} Pollen Today"
      message: >
        Dominant type: {{ state_attr('sensor.pollen_advisory', 'dominant_type') }}
        (index: {{ state_attr('sensor.pollen_advisory', 'dominant_index') }}).
        In season: {{ state_attr('sensor.pollen_advisory', 'in_season_types') | join(', ') }}.
```

### Alert on active weather warnings

```yaml
alias: Alert — Weather Warning
trigger:
  - trigger: numeric_state
    entity_id: sensor.weather_alerts
    above: 0
  - trigger: numeric_state
    entity_id: sensor.weather_alerts
    below: 1
    id: cleared
action:
  - choose:
      - conditions:
          - condition: trigger
            id: cleared
        sequence:
          - action: notify.mobile_app_your_phone
            data:
              title: "✅ Weather Alert Expired"
              message: "No active weather warnings."
      - conditions: []
        sequence:
          - action: notify.mobile_app_your_phone
            data:
              title: >
                ⛈️ {{ states('sensor.weather_alerts') }} Active Weather Warning(s)
              message: >
                Highest severity: {{ state_attr('sensor.weather_alerts', 'highest_severity') }}.
                Types: {{ state_attr('sensor.weather_alerts', 'active_event_types') | join(', ') }}.
```

### Close HVAC fresh-air intake on poor air quality

```yaml
alias: HVAC — Suspend fresh-air intake on bad AQI
trigger:
  - trigger: state
    entity_id: sensor.air_quality_advisory
    to:
      - Unhealthy
      - Very Unhealthy
      - Hazardous
  - trigger: state
    entity_id: sensor.air_quality_advisory
    to:
      - Good
      - Moderate
      - Unhealthy for Sensitive Groups
    id: ok
action:
  - action: >
      {{ 'input_boolean.turn_on' if trigger.id != 'ok' else 'input_boolean.turn_off' }}
    target:
      entity_id: input_boolean.hvac_fresh_air_suspended
```

### Alert when AQI crosses a numeric threshold

Use the numeric Universal AQI sensor when you need a specific threshold not covered by advisory levels.

```yaml
alias: Alert — AQI Threshold
trigger:
  - trigger: numeric_state
    entity_id: sensor.universal_aqi
    above: 150
    id: unhealthy
  - trigger: numeric_state
    entity_id: sensor.universal_aqi
    below: 100
    id: recovered
action:
  - choose:
      - conditions:
          - condition: trigger
            id: unhealthy
        sequence:
          - action: notify.mobile_app_your_phone
            data:
              title: "⚠️ Air Quality Unhealthy"
              message: >
                AQI is {{ states('sensor.universal_aqi') }} —
                {{ state_attr('sensor.universal_aqi', 'category') }}.
      - conditions:
          - condition: trigger
            id: recovered
        sequence:
          - action: notify.mobile_app_your_phone
            data:
              title: "✅ Air Quality Improved"
              message: "AQI is back to {{ states('sensor.universal_aqi') }}."
```

### API usage warning

```yaml
alias: Alert — Particle Man API Usage Warning
trigger:
  - trigger: template
    value_template: >
      {{ state_attr('sensor.aq_api_calls_monthly', 'status') in ['warning', 'critical']
         or state_attr('sensor.weather_api_calls_monthly', 'status') in ['warning', 'critical'] }}
action:
  - action: notify.mobile_app_your_phone
    data:
      title: "📊 Particle Man API Usage"
      message: >
        AQ: {{ state_attr('sensor.aq_api_calls_monthly', 'pct_projected') }}% of limit.
        Weather: {{ state_attr('sensor.weather_api_calls_monthly', 'pct_projected') }}% of limit.
        Consider increasing your update interval.
```

---

## Dashboard examples

??? "AQI Gauge"

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

??? "96-Hour AQI Forecast Chart"

    Requires [mini-graph-card](https://github.com/kalkih/mini-graph-card) (available in HACS).

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

??? "5-Day Daily AQI Forecast"

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

??? "Pollen Summary Glance"

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

??? "Pollutant Overview"

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
