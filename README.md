# Spook 👻 Not your homie. <!-- omit from toc -->

[![GitHub Release][releases-shield]][releases]
![Project Stage][project-stage-shield]
[![License][license-shield]](LICENSE.md)
![Project Maintenance][maintenance-shield]
[![Quality Gate Status][sonarcloud-shield]][sonarcloud]

![Spook - Not your homie](https://raw.githubusercontent.com/frenck/spook/main/logos/logo3.png)

# About <!-- omit from toc -->

Spook is a custom integration for Home Assistant, which is not your homie.

You should not use this custom integration, nor should you expect it to work.
The integration will break a lot, and will probably not survive the next
Home Assistant upgrade. Heck, it will most likely not even survive its own
next release.

This integration comes with absolutely 0/zero/zip/nada/noppes support,
and has less documentation than the quirks of my partner.

Above all, this integration may just break your setup in an way
that is not recoverable. Nor will it provide you with a tissue
to dry up your tears when you are crying in a fetal position
under your desk after ignoring all of the above.

I've warned you :D

../Frenck

## Some guidance for the brave <!-- omit from toc -->

- [Entities](#entities)
  - [Buttons](#buttons)
  - [Sensors](#sensors)
- [Services](#services)
  - [Service: Disable an integration](#service-disable-an-integration)
  - [Service: Enable an integration](#service-enable-an-integration)
  - [Service: Disable a device](#service-disable-a-device)
  - [Service: Enable a device](#service-enable-a-device)
  - [Service: Disable an entity](#service-disable-an-entity)
  - [Service: Enable an entity](#service-enable-an-entity)
  - [Service: Hide an entity](#service-hide-an-entity)
  - [Service: Unhide an entity](#service-unhide-an-entity)
  - [Service: Disable polling for updates](#service-disable-polling-for-updates)
  - [Service: Enable polling for updates](#service-enable-polling-for-updates)
  - [Service: Ignore all discovered devices \& services](#service-ignore-all-discovered-devices--services)
  - [Service: Delete all orphaned entities](#service-delete-all-orphaned-entities)
  - [Service: Create area](#service-create-area)
  - [Service: Add an alias to an area](#service-add-an-alias-to-an-area)
  - [Service: Remove an alias from an area](#service-remove-an-alias-from-an-area)
  - [Service: Set area aliases](#service-set-area-aliases)
  - [Service: Add device to area](#service-add-device-to-area)
  - [Service: Remove device from area](#service-remove-device-from-area)
  - [Service: Add entity to area](#service-add-entity-to-area)
  - [Service: Remove entity from area](#service-remove-entity-from-area)
  - [Service: Delete area](#service-delete-area)
  - [Service: Restart Home Assistant (with force option)](#service-restart-home-assistant-with-force-option)
  - [Service: Boo! 👻](#service-boo-)
  - [Service: Random fail](#service-random-fail)
- [Previously part of Spook](#previously-part-of-spook)
  - [Obsolete integration \& platform YAML configuration repairs](#obsolete-integration--platform-yaml-configuration-repairs)
<<<<<<< HEAD
- [Frequently Asked Questions](#frequently-asked-questions)
  - [Is this a serious thing?](#is-this-a-serious-thing)
  - [Why is Spook called Spook?](#why-is-spook-called-spook)
  - [Does this integration break my Home Assistant instance?](#does-this-integration-break-my-home-assistant-instance)
  - [Does Spook do random things to my home?](#does-spook-do-random-things-to-my-home)
  - [Ok, so should I use Spook?](#ok-so-should-i-use-spook)
- [Translating Spook](#translating-spook)
=======
>>>>>>> 5f94401 (Initial stab at adding actual documentation)
- [Changelog \& Releases](#changelog--releases)
- [Contributing](#contributing)
- [Authors \& contributors](#authors--contributors)
- [License](#license)

You shouldn't.

# Entities

This integration will provide you with entities you'd absolutely do not need.
All of them are enabled by default to ensure you have a bad time, straight
of the box.

## Buttons

- **Reload Home Assistant**: Wut, you are still using YAML? _#GodWhy?_
- **Restart Home Assistant**: Have you tried turning it off and on again? _#ITCrowd_

## Sensors

- **Total number of entities**: To show your friends how big your setup is. _#compensation_
- **Number of entities for each entity type**: So you know how many lightbulbs you have. _#count_
  - Number of `air_quality` entities.
  - Number of `alarm_control_panel` entities.
  - Number of `binary_sensor` entities.
  - Number of `button` entities.
  - Number of `camera` entities.
  - Number of `climate` entities.
  - Number of `cover` entities.
  - Number of `date` entities.
  - Number of `datetime` entities.
  - Number of `device_tracker` entities.
  - Number of `fan` entities.
  - Number of `humidifier` entities.
  - Number of `image` entities.
  - Number of `input_boolean` entities.
  - Number of `input_button` entities.
  - Number of `input_number` entities.
  - Number of `input_select` entities.
  - Number of `input_text` entities.
  - Number of `light` entities.
  - Number of `lock` entities.
  - Number of `media_player` entities.
  - Number of `number` entities.
  - Number of `remote` entities.
  - Number of `select` entities.
  - Number of `sensor` entities.
  - Number of `siren` entities.
  - Number of `stt` entities.
  - Number of `switch` entities.
  - Number of `text` entities.
  - Number of `time` entities.
  - Number of `tts` entities.
  - number of `vacuum` entities.
  - Number of `update` entities.
  - Number of `water_heater` entities.
  - Number of `weather` entities.
- **Number of areas**: In case you forgot how many rooms your house has. _#1_
- **Number of automations**: Because that is such a useful metric. _#robots_
- **Number of devices**: That are in the device registry. _#bling_
- **Number of persons**: How many people are you constantly tracking the location of? _#privacy_
- **Number of persistent notifications**: Are you just a persistent as this thing is? _#annoyance_
- **Number of scenes**: Maybe you can ask your partner to make a scene... _#fight_
- **Number of scripts**: More than the average unemployed actor yet? _#hollywood_
- **Number of suns**: Answers how godlike you are. _#burn_
- **Number of zones**: How many comfort zones you have on a map. _#zoneing_
- **Number of integrations in use**: Consider using less integrations. _#lessismore_
- **Number of custom integrations in use**: In this case... _#lessisevenmore_ (delete this one! 🙃)

# Services

There are quite a few useless and horrible services available for you to explore
and self-destruct your setup with. The developer service tools are great
to get you into such a situation.

[![Open your Home Assistant instance and show your service developer tools.](https://my.home-assistant.io/badges/developer_services.svg)](https://my.home-assistant.io/redirect/developer_services/)

## Service: Disable an integration

Call it using: [`homeassistant.disable_config_entry`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_config_entry)

> This service can be used to disable a integration configuration entry (those
> you see on your integrations dashboard) on the fly. _#bye_

## Service: Enable an integration

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

## Service: Disable polling for updates

Call it using: [`homeassistant.disable_polling`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_polling)

> This service can be used to disable polling for updates on an integration
> configuration entry (those you see on your integrations dashboard). _#stopit_

## Service: Enable polling for updates

Call it using: [`homeassistant.enable_polling`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_polling)

> This service can be used to enable polling for updates on an integration
> configuration entry (those you see on your integrations dashboard).
> This service does the reverse of [`homeassistant.disable_polling`](#service-disable-polling) > _#poking_

## Service: Ignore all discovered devices & services

Call it using: [`homeassistant.ignore_all_discovered`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.ignore_all_discovered)

> Click ignore on all discovered items on the integration dashboard; optionally
> only for specific integration (e.g., bluetooth). _#talktothehand_

## Service: Delete all orphaned entities

Call it using: [`homeassistant.delete_all_orphaned_entities`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_all_orphaned_entities)

> Deletes all orphaned entities that no longer have an integration that claim/provide
> them. Please note, if the integration was just removed, it might need a restart
> for Home Assistant to realize they are orphaned. _#annie_

> **WARNING** Entities might have been marked orphaned because an
> integration is offline or not working since Home Assistant started. Calling
> this service will delete those entities as well.

## Service: Create area

Call it using: [`homeassistant.create_area`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_area)

> Instantly create new rooms in your home. _#BobTheBuilder_

## Service: Add an alias to an area

Call it using: [`homeassistant.add_alias_to_area`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_alias_to_area)

> Adds an alias (or multiple aliases) to an area. _#aka_

## Service: Remove an alias from an area

Call it using: [`homeassistant.remove_alias_from_area`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_alias_from_area)

> Removes an alias (or multiple aliases) from an area. _#broom_

## Service: Set area aliases

Call it using: [`homeassistant.set_area_aliases`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.set_area_aliases)

> Sets the aliases for an area. _#useless_

## Service: Add device to area

Call it using: [`homeassistant.add_device_to_area`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_device_to_area)

> Dynamicaly add/move a device to an new area. _#moveit_

## Service: Remove device from area

Call it using: [`homeassistant.remove_device_from_area`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_device_from_area)

> Dynamicaly remove a device from an area. _#poef_

## Service: Add entity to area

Call it using: [`homeassistant.add_entity_to_area`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_entity_to_area)

> Dynamicaly add/move an entity to an area. _#bam_

## Service: Remove entity from area

Call it using: [`homeassistant.remove_entity_from_area`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_entity_from_area)

> Dynamicaly remove an entity from an area. _#AaaaandItIsGone_

## Service: Delete area

Call it using: [`homeassistant.delete_area`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_area)

> Just like that, you made an area of your home dissapear. _#DemolitionMan_

## Service: Restart Home Assistant (with force option)

Call it using: [`homeassistant.restart`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.restart)

> Extends the existing restart service with an "force" option. Because forcing
> is always a good idea. _#hammer_

## Service: Boo! 👻

Call it using: [`spook.boo`](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.boo)

> This service call will just always spook the hell out of Home Assistant.
> Home Assistant will shit its pants and abort the automation or script. _#spooked_

## Service: Random fail

Call it using: [`spook.random_fail`](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.random_fail)

> This service call will randomly fail (and thus randomly stop your automation or
> script). Especially combined with `continue_on_error: true` this can be a great
> way add a useless service calls to your automation or script. _#random_

# Previously part of Spook

Some of the amazing things Spook does, may turn out to be actually pretty good
and have eventually end up into Home Assistant natively, or, became obsolete
because of similar features they added.

So here is a list of things that have been removed from Spook 👻 _#loser_

## Obsolete integration & platform YAML configuration repairs

> Find YAML configuration for an integrations (and older integration platforms)
> that no longer support it.

As of Home Assistant 2023.5 (refined in 2023.6), Home Assistant will raise
repair issues for these cases itself.

<<<<<<< HEAD
# Frequently Asked Questions

In the first few days after putting Spook out, some of the same questions
kept popping up. So, here are some answers to those questions.

## Is this a serious thing?

Yes! It is just not a normal integration, like one that connects to a device or
service, or one that provides a helper of some sort. But it is a serious
integration, that is meant to be used in a serious way.

## Why is Spook called Spook?

I (Frenck) am Dutch. I grew up with "Casper het vriendelijke spookje", also
known as "Casper the friendly ghost". "Spook" is the Dutch for "ghost".

Casper is scary at first sight, but you could really love him in the end. Which
seems fitting for a custom integration, as custom integrations are more likely
to break, thus being a little scared of them is not a bad thing.

"Not your homie" is a refence to my the livestreams I used to do. I called my
viewers "My Home Assistant Homies", or just "Homies". It is thus referring
to you, the Home Assistant user, as my friend, my homie. However, "Spook" is
not your homie, it is a ghost, a spooky thing, he is suposed to make you think
a little about what you are doing before you use it.

Nice little fact, I did use "homey" at first (to maybe annoy the Homey users a
bit in SEO), but I decided not to be that _badword_ and to change it back to
just "homie".

Lastly, the little ghost logo & use of the emoji. This is great inspiration
from the Mushroom card project (I love it!). They use a simple mushroom emoji
and you see it everywhere in the Home Assistant community, thus decided to do
a similar thing.

## Does this integration break my Home Assistant instance?

Well, that is not the goal of course. But, it is a custom integration, so
there is a chance it might break your instance. This applies to any custom
integration, not just Spook.

I'm just sharing what I have, without any warranty. I've decided to be blunt
about it, and make it at least fun to read. I could have written a small
warning, that would have been boring.

## Does Spook do random things to my home?

No. It does not do random things. It is not a chaos testing thing and
it will not turn lights on/off randomly in the night. Unless it is a bug
or broken of course.

## Ok, so should I use Spook?

No! The license doesn't allow that (see below).

# Translating Spook

Spook isn't very good at speaking different languages, but you can help!

As a matter of fact, Spooks translation files are [CC0 licensed](./custom_components/spook/translations/LICENSE.md)!

Translating can be done from your webbrowser, no programming knowledge
is needed!

[![Translation status](https://hosted.weblate.org/widgets/spook/-/integration/open-graph.png)](https://hosted.weblate.org/engage/spook/)

Translation status per language:

[![Translation status](https://hosted.weblate.org/widgets/spook/-/integration/multi-auto.svg)](https://hosted.weblate.org/engage/spook/)

=======
>>>>>>> 5f94401 (Initial stab at adding actual documentation)
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
[project-stage-shield]: https://img.shields.io/badge/project%20stage-SPOOKED-red.svg
[releases-shield]: https://img.shields.io/github/release/frenck/spook.svg
[releases]: https://github.com/frenck/spook/releases
[semver]: http://semver.org/spec/v2.0.0.html
[maintenance-shield]: https://img.shields.io/maintenance/yes/2023.svg
[sonarcloud-shield]: https://sonarcloud.io/api/project_badges/measure?project=frenck_python-elgato&metric=alert_status
[sonarcloud]: https://sonarcloud.io/summary/new_code?id=frenck_python-elgato
