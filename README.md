# Spook 👻 Not your homie. <!-- omit from toc -->

[![GitHub Release][releases-shield]][releases]
![Project Stage][project-stage-shield]
[![License][license-shield]](LICENSE.md)

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

## Cool, but why? What is it? <!-- omit from toc -->

So, there a lot of things/features, that will never end up in Home Assistant itself.

This can have various reasons, for example: It is just too random, out of scope,
not matching the Home Assistant philosophy, violating architectural design,
still in early development, experimental, explorative, or just freaking useless.

Spook doesn't care. He is nobodies homie.

So, maybe, that one feature you wanted Home Assistant to have, is in Spook.

However, remember, Spook is not your homie. All stuff in here, is not part of
Home Assistant (or at least not yet) for a reason. So, don't expect it to work,
or to be supported, or well, for starters, to be a good idea.

## Some guidance for the brave <!-- omit from toc -->

- [Installation](#installation)
- [Configuration](#configuration)
- [Entities](#entities)
  - [Sensors](#sensors)
  - [Switches](#switches)
- [Services](#services)

  - [Service: Import Blueprint](#service-import-blueprint)
  - [Service: Disable an integration](#service-disable-an-integration)
  - [Service: Enable an integration](#service-enable-an-integration)
  - [Service: Disable polling for updates](#service-disable-an-integration)
  - [Service: Enable an integration](#service-enable-an-integration)
  - [Service: Disable a device](#service-disable-a-device)
  - [Service: Enable a device](#service-enable-a-device)
  - [Service: Disable an entity](#service-disable-an-entity)
  - [Service: Enable an entity](#service-enable-an-entity)
  - [Service: Hide an entity](#service-hide-an-entity)
  - [Service: Unhide an entity](#service-unhide-an-entity)
  - [Service: Ignore all discovered devices \& services](#service-ignore-all-discovered-devices--services)
  - [Service: Remove all orphaned entities](#service-remove-all-orphaned-entities)
  - [Service: Import statistics](#service-import-statistics)
  - [Service: Create repair issue](#service-create-repair-issue)
  - [Service: Remove repair issue](#service-remove-repair-issue)
  - [Service: Ignore all repair issues](#service-ignore-all-repair-issues)
  - [Service: Unignore all repair issues](#service-unignore-all-repair-issues)

  - [Service: Boo! 👻](#service-boo-)
  - [Service: Random fail](#service-random-fail)

- [Entity services](#entity-services)
  - [Service for `input_number`: Decrease value](#service-for-input_number-decrease-value)
  - [Service for `input_number`: Increase value](#service-for-input_number-increase-value)
  - [Service for `input_number`: Min value](#service-for-input_number-min-value)
  - [Service for `input_number`: Max value](#service-for-input_number-max-value)
  - [Service for `input_select`: Select random option](#service-for-input_select-select-random-option)
  - [Service for `input_select`: Shuffle options](#service-for-input_select-shuffle-options)
  - [Service for `input_select`: Sort options](#service-for-input_select-sort-options)
  - [Service for `number`: Decrease value](#service-for-number-decrease-value)
  - [Service for `number`: Increase value](#service-for-number-increase-value)
  - [Service for `number`: Min value](#service-for-number-min-value)
  - [Service for `number`: Max value](#service-for-number-max-value)
  - [Service for `select`: Select random option](#service-for-select-select-random-option)
- [Repairs](#repairs)
  - [Automations: Find use of non-existing areas, devices and entities](#automations-find-use-of-non-existing-areas-devices-and-entities)
  - [Groups: Detect unknown group members](#groups-detect-unknown-group-members)
  - [Obsolete integration YAML configuration](#obsolete-integration-yaml-configuration)
  - [Scripts: Find use of non-existing areas, devices and entities](#scripts-find-use-of-non-existing-areas-devices-and-entities)
- [Frequently Asked Questions](#frequently-asked-questions)
  - [Is this a serious thing?](#is-this-a-serious-thing)
  - [Why is Spook called Spook?](#why-is-spook-called-spook)
  - [Does this integration break my Home Assistant instance?](#does-this-integration-break-my-home-assistant-instance)
  - [Does Spook do random things to my home?](#does-spook-do-random-things-to-my-home)
  - [Ok, so should I use Spook?](#ok-so-should-i-use-spook)
- [Changelog \& Releases](#changelog--releases)
- [Contributing](#contributing)
- [Authors \& contributors](#authors--contributors)
- [Disclaimer](#disclaimer)
- [License](#license)

# Installation

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=frenck&repository=spook&category=integration)

You can find it in the HACS store by searching for "Spook", but you shoudn't.
You could manually add this repository to HACS, but you shouldn't. You can
also install it manually by copying the `spook` folder into your
`custom_components` folder, but you shouldn't.

Just don't.

# Configuration

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=spook)

You shouldn't.

# Entities

This integration will provide you with entities you'd absolutely do not need.
All of them are enabled by default to ensure you have a bad time, straight
of the box.

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
- **Number of scripts**: More than the average unemployed actor yet? _#hollywood_
- **Number of suns**: Answers how godlike you are. _#burn_
- **Number of zones**: How many comfort zones you have on a map. _#zoneing_
- **Number of integrations in use**: Consider using less integrations. _#lessismore_
- **Number of custom integrations in use**: In this case... _#lessisevenmore_ (delete this one! 🙃)

## Switches

- **Home Assistant Cloud**: Switch to control behavior of Nabu Casa's Home Assistant Cloud. _#love_
  - **Alexa**: Enable/disable Alexa connection. _#amazon_
  - **Alexa state reporting**: Enable/disable Alexa state reporting. _#ping_
  - **Google Assistant**: Enable/disable Google Assistant connection. _#bigtech_
  - **Google Assistant state reporting**: Enable/disable Google Assistant state reporting connection. _#pong_
  - **Remote**: Enable/disable remote access to the Home Asistant frontend. _#rdp_

# Services

There are quite a few useless and horrible services available for you to explore
and self-destruct your setup with. The developer service tools are great
to get you into such a situation.

[![Open your Home Assistant instance and show your service developer tools.](https://my.home-assistant.io/badges/developer_services.svg)](https://my.home-assistant.io/redirect/developer_services/)

## Service: Import Blueprint

Call it using: [`blueprint.import`](https://my.home-assistant.io/redirect/developer_call_service/?service=blueprint.import)

> Downloads and imports a automation/script Blueprint, directly from the
> URL you pass into this service. _#noquestionsasked_

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

## Service: Remove all orphaned entities

Call it using: [`homeassistant.remove_all_orphaned_entities`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_all_orphaned_entities)

> Removes all orphaned entities that no longer have an integration that claim/provide
> them. Please note, if the integration was just removed, it might need a restart
> for Home Assistant to realize they are orphaned. _#annie_

> **WARNING** Entities might have been marked orphaned because an
> integration is offline or not working since Home Assistant started. Calling
> this service will remove those entities as well.

## Service: Import statistics

Call it using: [`recorder.import_statistics`](https://my.home-assistant.io/redirect/developer_call_service/?service=recorder.import_statistics)

> Advanced service to directly inject historical statistics data into
> the recorder long-term stats database. _#easy_

## Service: Create area

Call it using: [`homeassistant.create_area`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_area)

> Instantly create new rooms in your home. _#BobTheBuilder_

## Service: Delete area

Call it using: [`homeassistant.delete_area`](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_area)

> Just like that, you made an area of your home dissapear. _#DemolitionMan_

## Service: Create repair issue

Call it using: [`repairs.create`](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.create)

> Battery empty? Raise a issue in Home Assistant Repairs. Although, you
> should probably just use a notification for this. _#issues_

## Service: Remove repair issue

Call it using: [`repairs.remove`](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.remove)

> Removes a issue from Home Assistant Repairs. Can only remove repair issues
> that have been created using the `repairs.create` service. _#trashit_

## Service: Ignore all repair issues

Call it using: [`repairs.ignore_all`](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.ignore_all)

> Whatever issue is bothering you, just ignore it all and all your
> problems will magically be gone. _#allgood_

## Service: Unignore all repair issues

Call it using: [`repairs.unignore_all`](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.unignore_all)

> Will unignore all issues marked ignored, and shows them all again. _#faceit_

## Service: Boo! 👻

Call it using: [`spook.boo`](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.boo)

> This service call will just always spook the hell out of Home Assistant.
> Home Assistant will shit its pants and abort the automation or script. _#spooked_

## Service: Random fail

Call it using: [`spook.random_fail`](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.random_fail)

> This service call will randomly fail (and thus randomly stop your automation or
> script). Especially combined with `continue_on_error: true` this can be a great
> way add a useless service calls to your automation or script. _#random_

# Entity services

Spook also extends the services available for entities. These services may
extend the functionality if entity components (like `select`) or platform
specific services provided by integrations.

[![Open your Home Assistant instance and show your service developer tools.](https://my.home-assistant.io/badges/developer_services.svg)](https://my.home-assistant.io/redirect/developer_services/)

## Service for `input_number`: Decrease value

Call it using: [`input_number.decrement`](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.decrement)

> Override of the existing service, which provides the option to specify
> the amount to decrease the value by. _#evenlower_

_Under consideration for contributing back to Home Assistant Core._

## Service for `input_number`: Increase value

Call it using: [`input_number.increment`](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.increment)

> Override of the existing service, which provides the option to specify
> the amount to increase the value by. _#moreoptions_

_Under consideration for contributing back to Home Assistant Core._

## Service for `input_number`: Min value

Call it using: [`input_number.min`](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.min)

> Set the value of a `input_number` entity to its minimum value/ _#lowout_

## Service for `input_number`: Max value

Call it using: [`input_number.max`](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.max)

> Set the value of a `input_number` entity to the maximum value. _#maxout_

## Service for `input_select`: Select random option

Call it using: [`input_select.random`](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.random)

> This service select a random option from the list of options of a select entity.
> Optionally this can be limited to a set of given options. _#shuffle_

## Service for `input_select`: Shuffle options

Call it using: [`input_select.shuffle`](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.shuffle)

> Shuffles the list of selectable options for an `input_select` entity.
> Note: This is not persistent and will be undone once reloaded or
> Home Assistant restarts. _#31254_

## Service for `input_select`: Sort options

Call it using: [`input_select.sort`](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.sort)

> Sorts the list of selectable options for an `input_select` entity.
> Note: This is not persistent and will be undone once reloaded or
> Home Assistant restarts. _#12345_

## Service for `number`: Decrease value

Call it using: [`number.decrement`](https://my.home-assistant.io/redirect/developer_call_service/?service=number.decrement)

> Decrease the value of a number entity, either by a single step or by a
> provided amount. _#downboy_

_Under consideration for contributing back to Home Assistant Core._

## Service for `number`: Increase value

Call it using: [`number.increment`](https://my.home-assistant.io/redirect/developer_call_service/?service=number.increment)

> Increase the value of a number entity, either by a single step or by a
> provided amount. _#up #greatmovie_

_Under consideration for contributing back to Home Assistant Core._

## Service for `number`: Min value

Call it using: [`number.min`](https://my.home-assistant.io/redirect/developer_call_service/?service=number.min)

> Set the value of a number entity to its minimum value. _#lowout_

## Service for `number`: Max value

Call it using: [`number.max`](https://my.home-assistant.io/redirect/developer_call_service/?service=number.max)

> Set the value of a number entity to the maximum value. _#maxout_

## Service for `select`: Select random option

Call it using: [`select.random`](https://my.home-assistant.io/redirect/developer_call_service/?service=select.random)

> This service select a random option from the list of options of a select entity.
> Optionally this can be limited to a set of given options. _#random_

# Repairs

Spook will float around your Home Assistant instance, and while it does, it
might be able to find things that need your attention. Spook will notify you
about these things using an Home Assistant repair issue. _#whoyougonnacall_

[![Open your Home Assistant instance and show your repairs.](https://my.home-assistant.io/badges/repairs.svg)](https://my.home-assistant.io/redirect/repairs/)

Currently Spook will detect the following issues:

## Obsolete integration YAML configuration

> Finds YAML configuration for an integrations that no longer support it.
> Unless you like having unneeded shizzle in your YAML, it can be removed
> safely. _#ghostbusters_

## Automations: Find use of non-existing areas, devices and entities

> Finds automations that use non-existing areas, devices or entities in, for
> example, their service calls. _#springcleaning_

_Intention to contribute back to Home Assistant Core once sure no false
postives remain, and it has been extended to catch more situations._

## Groups: Detect unknown group members

> Finds groups that contain references to unknown members (entities). _#aliens_

_Intention to contribute back to Home Assistant Core._

## Riemann sum integral: Detect missing source sensor

> Finds integrals that are missing a source sensor. _#missinglink_

_Intention to contribute back to Home Assistant Core._

## Scripts: Find use of non-existing areas, devices and entities

> Finds scripts that use non-existing areas, devices or entities in, for
> example, their service calls. _#void_

_Intention to contribute back to Home Assistant Core once sure no false
postives remain, and it has been extended to catch more situations._

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
not affiliated with, endorsed or recommended by the Home Assistant project.

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
[project-stage-shield]: https://img.shields.io/badge/project%20stage-SPOOKED-red.svg
[releases-shield]: https://img.shields.io/github/release/frenck/spook.svg
[releases]: https://github.com/frenck/spook/releases
[semver]: http://semver.org/spec/v2.0.0.html
