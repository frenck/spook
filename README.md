# Spook - Not your homey. 

[![GitHub Release][releases-shield]][releases]
![Project Stage][project-stage-shield]
[![License][license-shield]](LICENSE.md)

![Spook - Not your homey](https://raw.githubusercontent.com/frenck/spook/main/logos/logo3.png)

# About

Spook is a custom integration for Home Assistant, which is not your homey.

You should not use this custom integration, nor should you expect it to work.
The integration will break a lot, and will probably not survive the next
Home Assistant upgrade. Heck, it will most likely not even survive its own
next release.

This integration comes with absolutely 0/zero/zip/nada/noppes support,
and has less documentation then the quirks of my partner.

Above all, this integration may just break your setup in an way
that is not recoverable. Nor will it provide you with a tissue
to dry up your tears when you are crying in a fetal position
under your desk after ignoring all of the above.

I've warned you :D

../Frenck

# Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=frenck&repository=spook&category=integration)

You could manually add this repository to HACS, but you shouldn't. You can
also install it manually by copying the `spook` folder into your
`custom_components` folder, but you shouldn't. It might be available on the
HACS store at some point (or not) from which you should not install this
integration.

Just don't.

# Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=spook)

You shouldn't.

# Entities

This integration will provide you with entities you'd absolutely do not need.
All of them are enabled by default to ensure you have a bad time, straight
of the box.
## Sensors

- **Number of integrations in use**: Consider using less integrations. _#lessismore_
- **Number of custom integrations in use**: In this case... _#lessisevenmore_ (delete this one! 🙃)
- **Total number of entities**: To show your friends how big your setup is. _#compensation_
- **Number of entities for each entity type**: So you know how many lightbulbs you have. _#count_
  - Number of `air_quality` entities.
  - Number of `alarm_control_panel` entities.
  - Number of `binary_sensor` entities.
  - Number of `button` entities.
  - Number of `camera` entities.
  - Number of `climate` entities.
  - Number of `cover` entities.
  - Number of `device_tracker` entities.
  - Number of `fan` entities.
  - Number of `humidifier` entities.
  - Number of `light` entities.
  - Number of `lock` entities.
  - Number of `media_player` entities.
  - Number of `number` entities.
  - Number of `remote` entities.
  - Number of `select` entities.
  - Number of `sensor` entities.
  - Number of `siren` entities.
  - Number of `switch` entities.
  - Number of `text` entities.
  - Number of `update` entities.
  - Number of `water_heater` entities.
  - Number of `weather` entities.
- **Number of areas**: In case you forgot how many rooms your house has. _#1_
- **Number of automations**: Because that is such a useful metric. _#robots_
- **Number of devices**: That are in the device registry. _#bling_
- **Number of persons**: How many people are you constantly tracking the location of? _#privacy_
- **Number of scenes**: Maybe you can ask your partner to make a scene... _#fight_
- **Number of suns**: Answers how godlike you are. _#burn_
- **Number of zones**: How many comfort zones you have on a map. _#zoneing_

## Switches

- **Home Assistant Cloud**: Switch to control behavior of Nabu Casa's Home Assistant Cloud. _#love_
  - **Alexa**: Enable/disable Alexa connection. _#amazon_
  - **Google Assistant**: Enable/disable Google Assistant connection. _#bigtech_
  - **Remote**: Enable/disable remote access to the Home Asistant frontend. _#rdp_

# Services

There are quite a few useless and horrible services available for you to explore
and self-descruct your setup with. The developer service tools are great
to get you into such a situation.

[![Open your Home Assistant instance and show your service developer tools.](https://my.home-assistant.io/badges/developer_services.svg)](https://my.home-assistant.io/redirect/developer_services/)

## Service: Import Blueprint

Call it using: [`blueprint.import`](https://my.home-assistant.io/redirect/developer_call_service/?service=blueprint.import)

> Downloads and imports a automation/script Blueprint, directly from the
> URL you pass into this service. _#noquestionsasked_

## Service: Disable a config entry

Call it using: [`homeassistant.disable_config_entry`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_config_entry)

> This service can be used to disable a integration configuration entry (those
> you see on your integrations dashboard) on the fly. _#bye_

## Service: Enable a config entry

Call it using: [`homeassistant.enable_config_entry`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_config_entry)

> Be amazed... this service does the reverse of [`homeassistant.disable_config_entry`](#service-disable-a-config-entry). _#mindblown_

## Service: Disable a device

Call it using: [`homeassistant.disable_device`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_device)

> This service can be used to disable a device on the fly. _#whatever_

## Service: Enable a device

Call it using: [`homeassistant.enable_device`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_device)

> Guess what... this service does the reverse of [`homeassistant.disable_device`](#service-disable-a-device). _#noway_

## Service: Disable an entity

Call it using: [`homeassistant.disable_entity`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_entity)

> This service can be used to disable a entity on the fly. _#rocketship_

## Service: Enable an entity

Call it using: [`homeassistant.enable_entity`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_entity)

> Really... this service does the reverse of [`homeassistant.disable_entity`](#service-disable-an-entity). _#true_

## Service: Hide an entity

Call it using: [`homeassistant.hide_entity`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.hide_entity)

> This service can be used to hide a entity on the fly. _#secret_

## Service: Unhide an entity

Call it using: [`homeassistant.unhide_entity`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.unhide_entity)

> Do the math... this service does the reverse of [`homeassistant.hide_entity`](#service-hide-an-entity). _#reveal_

## Service: Ignore all discovered devices & services

Call it using: [`homeassistant.ignore_all_discovered`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.ignore_all_discovered)

> Click ignore on all discovered items on the integration dashboard; optionally
> only for specific integration (e.g., bluetooth). _#talktothehand_

## Service: Import statistics

Call it using: [`recorder.import_statistics`](https://my.home-assistant.io/redirect/developer_call_service/?service=recorder.import_statistics)

> Advanced service to directly inject historical statistics data into
> >the recorder long-term stats database. _#easy_

## Service: Random fail

Call it using: [`spook.random_fail`](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.random_fail)

> This service call will randomly fail (and thus randomly stop your automation or
> script). Especially combined with `continue_on_error: true` this can be a great
> way add a useless service calls to your automation or script. _#random_

# Entity component services

Spook also extends the services available for entities. These services may
extend the functionality if entity components (like `select`)

[![Open your Home Assistant instance and show your service developer tools.](https://my.home-assistant.io/badges/developer_services.svg)](https://my.home-assistant.io/redirect/developer_services/)

## Services for `input_select` entities: Select random option

Call it using: [`input_select.ramdom`](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.random)

> This service select a random option from the list of options of a select entity.
> Optionally this can be limited to a set of given options. _#shuffle_

## Services for `select` entities: Select random option

Call it using: [`select.ramdom`](https://my.home-assistant.io/redirect/developer_call_service/?service=select.random)

> This service select a random option from the list of options of a select entity.
> Optionally this can be limited to a set of given options. _#random_

# Changelog & Releases

This repository does not keep a change log using [GitHub's releases][releases]
functionality. The format of the log is based on the direction the wind blows.

Releases use a [Semantic Versioning][semver], compatible version number of
`MAJOR.MINOR.PATCH`, as that is required for Home Assistant. In a nutshell,
the version will be incremented based on the following:

- `MAJOR`: If there is almost nothing changed.
- `MINOR`: I have no idea, possibily breaking.
- `PATCH`: I didn't care enough to change more numbers.

# Contributing

We've set up a separate document for our
[contribution guidelines](CONTRIBUTING.md).

# Authors & contributors

The original setup of this repository is by [Franck Nijhof][frenck].

For a full list of all authors and contributors,
check [the contributor's page][contributors].

# Disclaimer

At this point, I guess it goes without saying that this integration is
not affiliated with, endorsed or recommended by Home Assistant project.

**It is not supported by the Home Assistant project.**

If you experience issues with this integration, or as a result
of this integration, please go cry a lot on your own. _#sorrynotsorry_

# License

Copyright (c) 2023 Franck Nijhof

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to copy, modify, merge, publish, distribute, sublicense, and/or sell copies
of the Software, but NOT including the right to run, execute or use the
Software or any executable binaries built from the source code.

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

[contributors]: https://github.com/frenck/spook/graphs/contributors
[frenck]: https://github.com/frenck
[keepchangelog]: http://keepachangelog.com/en/1.0.0/
[license-shield]: https://img.shields.io/badge/license-Passive%20Aggressive%20License-lightgrey.svg
[project-stage-shield]: https://img.shields.io/badge/project%20stage-DESTRUCTIVE-red.svg
[releases-shield]: https://img.shields.io/github/release/frenck/spook.svg
[releases]: https://github.com/frenck/spook/releases
[semver]: http://semver.org/spec/v2.0.0.html
