---
subject: Enhanced integrations
title: Cover
subtitle: A little more light, please. 🪟
description: Spook adds actions that move a cover a step further open or closed.
date: 2026-10-04T17:00:00+02:00
---

```{image} https://brands.home-assistant.io/cover/icon.png
:alt: The Home Assistant cover icon
:width: 250px
:align: center
```

<br><br>

The cover {term}`integration <integration>` is how {term}`Home Assistant` controls blinds, shutters, curtains, awnings and garage doors.

Home Assistant can move a cover to a position, but not a bit further. Spook adds the step.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Increase position

Move a cover a step further open, stopping at fully open.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Cover: Increase position 👻
* - {term}`Action name`
  - `cover.increase_position`
* - {term}`Action targets`
  - Yes, `cover` entities that can be set to a position
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=cover.increase_position)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=cover.increase_position)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `step`
  - {term}`integer <integer>`
  - No
  - `10`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: cover.increase_position
target:
  entity_id: cover.living_room_blinds
data:
  step: 20
```

:::

### Decrease position

Move a cover a step further closed, stopping at fully closed.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Cover: Decrease position 👻
* - {term}`Action name`
  - `cover.decrease_position`
* - {term}`Action targets`
  - Yes, `cover` entities that can be set to a position
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=cover.decrease_position)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=cover.decrease_position)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `step`
  - {term}`integer <integer>`
  - No
  - `10`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: cover.decrease_position
target:
  entity_id: cover.living_room_blinds
```

:::

Both actions work the same way:

- Positions are whole percentages, from 0 for fully closed to 100 for fully open, the same as Home Assistant's own.
- The step is the one you give, or ten percent. A cover does not say how far one step is, the way a thermostat does.
- A step that would go past fully open or fully closed stops there.

:::{attention} Known limitations
:class: dropdown

- A cover that can only open and close, like most garage doors, cannot be targeted. There is no position to step.
- A cover that has not reported a position yet is left alone.
- The tilt of the slats is not stepped. That is a different setting, with actions of its own in Home Assistant.

:::

## Repairs

Spook has no repair detections for this integration.
