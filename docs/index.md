# Getting Started

Particle Man brings hyper-local air quality and pollen data into Home Assistant using Google's APIs — the same data behind health apps and HVAC automation worldwide.

Once set up, you'll have sensors for current AQI, individual pollutants, pollen levels by type and plant species, up to 96 hours of hourly forecasts, and API usage tracking so you can stay within Google's free tier.

---

## What you need

- A [Google Cloud account](https://console.cloud.google.com/) (free)
- A Google Cloud API key with two APIs enabled:
    - **Air Quality API**
    - **Pollen API**
- Home Assistant 2025.1.0 or later

---

## Step 1 — Get a Google API key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. In the left menu, go to **APIs & Services → Library**
4. Search for **Air Quality API** and click **Enable**
5. Search for **Pollen API** and click **Enable**
6. Go to **APIs & Services → Credentials**
7. Click **Create Credentials → API key**
8. Copy the key — you'll need it in the next step

!!! tip
    You don't need to restrict the key unless you want to. For home use, an unrestricted key is fine.

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
4. Enter your Google API key
5. Confirm your location (latitude and longitude default to your Home Assistant home address)
6. Set an update interval (default is 60 minutes, which works well within Google's free tier)
7. Click **Submit**

That's it. Particle Man will create three devices and begin populating sensors within a minute.

---

## What happens next

After setup you'll find three new devices under **Settings → Devices & Services → Particle Man**:

- **Particle Man Pollution** — AQI and pollutant sensors
- **Particle Man Pollen** — pollen type and plant sensors
- **Particle Man Diagnostics** — API call tracking

Head to [What's Included](sensors.md) for a plain-language guide to every sensor, or jump to [Dashboard Examples](dashboard.md) to start visualizing the data.

---

## Removing the integration

1. Go to **Settings → Devices & Services → Particle Man**
2. Click the three-dot menu → **Delete**
3. Restart Home Assistant
4. (Optional) Remove the component files via HACS or manually delete `custom_components/particle_man/` from your config directory
