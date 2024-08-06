---
subject: Core extensions
title: Devices & entities
subtitle: Can I haz more devices and entities? 😁
date: 2023-08-09T21:29:00+02:00
---

Besides all new {term}`actions <action>` for {term}`Home Assistant` itself, Spook will also add a bunch of {term}`devices <device>` and {term}`entities <entity>` that are all about Home Assistant. Basically, turning Home Assistant itself into its own integration, providing entities you can monitor and control.

```{figure} ./images/devices_entities/example.png
:alt: Screenshot showing a new device that provides control over your Home Assistant itself.
:align: center

Spook added devices and entities for Home Assistant itself.
```

## Devices & entities

Spook adds a single new device with entities for this integration to your Home Assistant instance.

### Buttons

#### Reload Home Assistant

_Default {term}`entity ID <Entity ID>`: `button.homeassistant_reload`_

Reload all Home Assistant configuration with a single click of a button. This might be useful if you have a management dashboard of some kind.

#### Restart Home Assistant

_Default {term}`entity ID <Entity ID>`: `button.homeassistant_restart`_

Restart Home Assistant with a single click of a button. This might be useful if you have a management dashboard of some kind.

### Sensors

#### Total number of entities

_Default {term}`entity ID <Entity ID>`: `sensor.entities`_

The total number of entities in your system (including this one).

#### Total number of entities per entity type

For each entity type, a sensor is created that counts the number of entities of that type. The default {term}`entity ID <Entity ID>` is listed after each sensor below.

- Number of `air_quality` entities (`sensor.air_quality`)
- Number of `alarm_control_panel` entities (`sensor.alarm_control_panels`)
- Number of `binary_sensor` entities (`sensor.binary_sensors`)
- Number of `button` entities (`sensor.buttons`)
- Number of `calendar` entities (`sensor.calendars`)
- Number of `camera` entities (`sensor.cameras`)
- Number of `climate` entities (`sensor.climate`)
- Number of `cover` entities (`sensor.covers`)
- Number of `date` entities (`sensor.dates`)
- Number of `datetime` entities (`sensor.datetimes`)
- Number of `device_tracker` entities (`sensor.device_trackers`)
- Number of `fan` entities (`sensor.fans`)
- Number of `humidifier` entities (`sensor.humidifiers`)
- Number of `image` entities (`sensor.images`)
- Number of `light` entities (`sensor.lights`)
- Number of `lock` entities (`sensor.locks`)
- Number of `media_player` entities (`sensor.media_players`)
- Number of `number` entities (`sensor.numbers`)
- Number of `remote` entities (`sensor.remotes`)
- Number of `select` entities (`sensor.selects`)
- Number of `sensor` entities (`sensor.sensors`)
- Number of `siren` entities (`sensor.sirens`)
- Number of `stt` entities (`sensor.stt`)
- Number of `switch` entities (`sensor.switches`)
- Number of `text` entities (`sensor.texts`)
- Number of `time` entities (`sensor.times`)
- Number of `tts` entities (`sensor.tts`)
- number of `vacuum` entities (`sensor.vacuums`)
- Number of `update` entities (`sensor.update`)
- Number of `water_heater` entities (`sensor.water_heaters`)
- Number of `weather` entities (`sensor.weather`)

#### Total number of helpers per type

For each helpers with their own domain, a sensor is created that counts the number of helpers. The default {term}`entity ID <Entity ID>` is listed after each sensor below.

- Number of `input_boolean` helpers (`sensor.input_booleans`)
- Number of `input_button` helpers (`sensor.input_buttons`)
- Number of `input_datetime` helpers (`sensor.input_datetimes`)
- Number of `input_number` helpers (`sensor.input_numbers`)
- Number of `input_select` helpers (`sensor.input_selects`)
- Number of `input_text` helpers (`sensor.input_texts`)

#### Other counters

But wait, there are more counters! The following sensors are also added:

- Number of areas (`sensor.areas`)
- Number of automations (`sensor.automations`)
- Number of custom integrations in use (`sensor.custom_integrations`)
- Number of devices (`sensor.devices`)
- Number of integrations in use (`sensor.integrations`)
- Number of persistent notifications (`sensor.persistent_notifications`)
- Number of persons (`sensor.persons`)
- Number of scenes (`sensor.scenes`)
- Number of scripts (`sensor.scripts`)
- Number of suns (`sensor.suns`)
- Number of zones (`sensor.zones`)

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for these features. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
