# Getting Started

Particle Man brings hyper-local air quality, pollen, and weather data into Home Assistant using Google's APIs — the same data behind health apps and smart HVAC automation worldwide.

Once set up, you'll have sensors for current AQI, individual pollutants, pollen levels by type and plant species, full weather conditions with hourly and daily forecasts, and API usage tracking so you can stay within Google's free tier.

---

## What you need

- A [Google Cloud account](https://console.cloud.google.com/) (free)
- A Google Cloud API key with three APIs enabled:
    - **Air Quality API**
    - **Pollen API**
    - **Weather API**
- Home Assistant 2025.1.0 or later

---

## Step 1 — Get a Google API key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. In the left menu, go to **APIs & Services → Library**
4. Search for and enable each of: **Air Quality API**, **Pollen API**, **Weather API**
5. Go to **APIs & Services → Credentials**
6. Click **Create Credentials → API key**
7. Copy the key — you'll need it in the next step

!!! tip
    You don't need to restrict the key for home use. An unrestricted key is fine.

---

## Step 2 — Install Particle Man

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations → three-dot menu → Custom repositories**
3. Add `https://github.com/mnestrud/particle-man` as an **Integration**
4. Find **Particle Man** in the list and click **Download**
5. Restart Home Assistant

### Manually

1. Download the latest release from [GitHub](https://github.com/mnestrud/particle-man/releases)
2. Copy the `custom_components/particle_man/` folder into your `config/custom_components/` directory
3. Restart Home Assistant

---

## Step 3 — Add the integration

1. Go to **Settings → Devices & Services**
2. Click **Add Integration**
3. Search for **Particle Man**
4. Enter your Google API key, confirm your location, and click **Submit**

That's it. All other settings (which data to collect, polling interval, API limits) are available any time via the **Configure** button and can be adjusted without re-adding the integration.

---

## What happens next

After setup you'll find four new devices under **Settings → Devices & Services → Particle Man**:

- **Particle Man Pollution** — AQI, pollutant sensors, and air quality advisory
- **Particle Man Pollen** — pollen type, plant species, and pollen advisory
- **Particle Man Weather** — weather entity, extra weather sensors, and alerts
- **Particle Man Diagnostics** — API call tracking for all three services

Head to [What's Included](sensors.md) for a full guide to every sensor, or [Weather](weather.md) for the weather entity and forecasts.

---

## Removing the integration

1. Go to **Settings → Devices & Services → Particle Man**
2. Click the three-dot menu → **Delete**
3. Restart Home Assistant
4. (Optional) Remove the component files via HACS or manually delete `custom_components/particle_man/` from your config directory
