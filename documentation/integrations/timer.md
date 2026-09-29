---
subject: Enhanced integrations
title: Timer
subtitle: Ready, set, go! ⏲
description: Spook adds a new action to the timer integration, which allows you to set the duration of an existing timer entity.
date: 2023-11-04T02:05:00+02:00
---

```{image} https://brands.home-assistant.io/timer/icon.png
:alt: The Home Assistant timer icon
:width: 250px
:align: center
```

<br><br>

The timer {term}`helper` in {term}`Home Assistant` aims to simplify {term}`automations <automation>` based on (dynamic) durations.

Spook adds a new action to the timer {term}`integration <integration>`, which allows you to set the duration of a timer to a given value.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Create a timer

Creates a new timer helper, the same as adding one on the helpers page. Great for a script that needs a timer only for itself: it can make one, and delete it again when it is done.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Timer: Create a timer 👻
* - {term}`Action name`
  - `timer.create`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - Optional, the `entity_id` of the new timer
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.create)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.create)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `name`
  - {term}`string <string>`
  - Yes
  - `Greenhouse mist`
* - `timer_id`
  - {term}`string <string>`
  - No
  - `greenhouse_mist`
* - `duration`
  - {term}`string <string>`
  - No
  - `00:05:00`
* - `restore`
  - {term}`boolean <boolean>`
  - No
  - `false`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:timer-outline`
```

Without a `timer_id`, the entity ID follows the name, as it does in the UI, and gets a number at the end if that name is already taken. With a `timer_id`, you get exactly that entity ID or an error: one that is already taken is refused, rather than quietly given a number at the end.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: timer.create
data:
  name: "Greenhouse mist"
  timer_id: greenhouse_mist
  duration: "00:05:00"
response_variable: created
```

The new timer's entity ID is then in `{{ created.entity_id }}`.

:::

### Delete a timer

Deletes one or more timer helpers made in the UI or with the action above, disabled ones included. Timers set up in YAML can only be removed from the YAML.

Everything in the list is checked first: if one of them cannot be deleted, none of them are.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Timer: Delete a timer 👻
* - {term}`Action name`
  - `timer.delete`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.delete)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.delete)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `entity_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `timer.greenhouse_mist`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: timer.delete
data:
  entity_id: timer.greenhouse_mist
```

:::

### Set duration

Set the duration for a timer entity.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Timer: Set duration 👻
* - {term}`Action name`
  - `timer.set_duration`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.set_duration)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.set_duration)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `duration`
  - {term}`string <string>`
  - Yes
  - 00:01:00, 60
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: timer.set_duration
data:
  entity_id: timer.my_timer
  duration: "00:15:00"
```

:::

## Repairs

Spook has no repair detections for this integration.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Quickly, with a single action, set the duration of a timer without having to got through the UI.
- Let a script make the timer it needs, and clean it up again afterwards, so the helpers page only has timers you actually use.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
