---
subject: Helpers
title: Calibration
subtitle: Nobody is perfect, sensors included. 🌡️
date: 2026-10-03T16:00:00+02:00
---

The calibration {term}`helper <helper>` corrects a sensor that reads off. A temperature sensor that is always a degree too high, a humidity sensor a few percent too low, or a power plug that measures 10% too much: the helper gives you a new sensor with the corrected value.

## How it works

The helper takes the value of the source sensor, multiplies it by the **factor**, and adds the **offset**:

```text
corrected = value × factor + offset
```

Most of the time, an offset is all you need. A sensor showing 21.3 °C while it is really 19.8 °C gets an offset of `-1.5`, and leaves the factor at `1`. The factor is for sensors that are off by a percentage instead: a plug measuring 10% too much gets a factor of `0.9`.

- The new sensor takes the unit, device class and state class of the source. Graphs and long-term statistics work the same as for the source.
- When the source is unavailable, unknown, or not a number, the calibrated sensor is unavailable. It does not make up a number.
- The new sensor is added to the same device as the source.

The offset is in the unit the source reports in. If you change the unit of the source later on, like from °C to °F, change the offset too.

## Creating a calibration helper

Add one directly to your own instance by selecting the {term}`My Home Assistant` button below:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=spook_calibration)

Or add one manually, using the following steps:

1. From the Home Assistant sidebar, select **Settings** and next select **Devices & Services**.
2. Select the **Helpers** tab.
3. On the helpers page, in the bottom right corner, select the **+ Create helper** button.
4. From the list of helpers, select **Calibration 👻**.
5. Provide a name, and select the sensor to correct in the **Source entity** field.
6. Fill in the **Offset**, and if needed the **Factor**.
7. Select **Submit**. Done! 🎉

Want to see only the corrected sensor? Hide the source sensor in its entity settings.
