# Troubleshooting

---

## Pollen sensors are unavailable or missing

Google's Pollen API has strong coverage in North America and Europe, but does not cover all countries. If you're outside a supported region, pollen sensors will remain unavailable — this is a limitation of the upstream API, not the integration.

**To check:** Look at the Home Assistant logs (`Settings → System → Logs`) for a line like `Pollen API fetch failed`. The error message will indicate whether it's a coverage issue or an API key problem.

If pollen is available in your region but sensors still don't appear, try removing and re-adding the integration to force a clean entity setup.

---

## API key errors / sensors show unavailable

If all sensors go unavailable and the logs show a 400 or 403 error from the Google API:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and confirm both the **Air Quality API** and **Pollen API** are enabled for your project
2. Confirm the API key being used is associated with the correct project
3. Check that the API key has no restrictions that would block requests from a home server (or add your HA server's IP to the allowed list)
4. If you recently created the key, wait a few minutes — Google can take time to propagate new keys

---

## Sensors show stale data

Check the **Last API Update** diagnostic sensor. If it's not updating, check the logs for API errors.

Also verify your update interval in **Configure → Location & Polling**. If it's set to a long interval (e.g. 1440 minutes / 24 hours), updates will be infrequent by design.

---

## API usage counts seem wrong

Usage is estimated locally — it counts calls made by this integration since the last reset, not actual Google billing usage. Counts can get out of sync if:

- The integration was removed and re-added mid-period
- Home Assistant was migrated to a new instance
- The reset day was changed mid-period

To reset counts: disable the integration (`Settings → Devices & Services → Particle Man → disable`), then re-enable it. This clears persistent storage and restarts tracking from today.

---

## The integration doesn't appear after installation

Make sure you restarted Home Assistant after installing via HACS or copying files manually. Custom integrations are not loaded until a restart.

---

## Options / Configure button doesn't save changes

If changes to the options form don't seem to take effect, check that Home Assistant reloaded the integration after saving. You should see a brief "reloading" status in the integration card. If not, manually reload via the three-dot menu on the integration card.

---

## Something else

Open an issue on [GitHub](https://github.com/mnestrud/particle-man/issues) with your HA version, integration version, and the relevant section of your logs.
