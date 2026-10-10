---
subject: Enhanced integrations
title: Valve
subtitle: Just a little more water. 🚰
description: Spook adds actions that move a valve a step further open or closed.
date: 2026-10-04T18:00:00+02:00
---

```{image} https://brands.home-assistant.io/valve/icon.png
:alt: The Home Assistant valve icon
:width: 250px
:align: center
```

<br><br>

The valve {term}`integration <integration>` is how {term}`Home Assistant` controls water, gas and irrigation valves.

Home Assistant can set a valve to a position, but not a bit further. Spook adds the step, the same way it does for [covers](cover).

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Increase position

Move a valve a step further open, stopping at fully open.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Valve: Increase position 👻
* - {term}`Action name`
  - `valve.increase_position`
* - {term}`Action targets`
  - Yes, `valve` entities that can be set to a position
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=valve.increase_position)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=valve.increase_position)
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
action: valve.increase_position
target:
  entity_id: valve.garden_irrigation
data:
  step: 20
```

:::

### Decrease position

Move a valve a step further closed, stopping at fully closed.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Valve: Decrease position 👻
* - {term}`Action name`
  - `valve.decrease_position`
* - {term}`Action targets`
  - Yes, `valve` entities that can be set to a position
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=valve.decrease_position)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=valve.decrease_position)
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
action: valve.decrease_position
target:
  entity_id: valve.garden_irrigation
```

:::

Both actions work the same way:

- Positions are whole percentages, from 0 for fully closed to 100 for fully open, the same as Home Assistant's own.
- The step is the one you give, or ten percent. A valve does not say how far one step is, the way a thermostat does.
- A step that would go past fully open or fully closed stops there.

:::{attention} Known limitations
:class: dropdown

- A valve that can only open and close, like most shutoff valves, cannot be targeted. There is no position to step.
- A valve that has not reported a position yet is left alone.

:::

## Repairs

Spook has no repair detections for this integration.
