---
subject: Enhanced integrations
title: Climate
subtitle: A little warmer, please. 🌡️
description: Spook adds actions that turn a thermostat up or down a step, both setpoints at once for one that heats and cools.
date: 2026-10-04T12:00:00+02:00
---

```{image} https://brands.home-assistant.io/climate/icon.png
:alt: The Home Assistant climate icon
:width: 250px
:align: center
```

<br><br>

The climate {term}`integration <integration>` is how {term}`Home Assistant` controls thermostats, heat pumps and air conditioners.

Home Assistant can set a thermostat to a temperature, but not turn it up a step. A "one degree warmer" button has to read the setpoint, add to it, and send it back, which is a template nobody gets right on the first try for a thermostat with two setpoints. Spook adds the step.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Increase temperature

Turn up a thermostat's setpoint a step, within the limits it reports.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Climate: Increase temperature 👻
* - {term}`Action name`
  - `climate.increase_temperature`
* - {term}`Action targets`
  - Yes, `climate` entities with a setpoint
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=climate.increase_temperature)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=climate.increase_temperature)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `step`
  - {term}`float <float>`
  - No
  - The thermostat's own step
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

````{code-block} yaml
:linenos:
action: climate.increase_temperature
target:
  entity_id: climate.living_room
data:\n  step: 1\n```

:::

### Decrease temperature

Turn down a thermostat's setpoint a step, within the limits it reports.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Climate: Decrease temperature 👻
* - {term}`Action name`
  - `climate.decrease_temperature`
* - {term}`Action targets`
  - Yes, `climate` entities with a setpoint
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=climate.decrease_temperature)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=climate.decrease_temperature)
````

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `step`
  - {term}`float <float>`
  - No
  - The thermostat's own step
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: climate.decrease_temperature
target:
  entity_id: climate.living_room
```

:::

Both actions work the same way:

- The step is the one you give, or the thermostat's own step, or half a degree (one degree in Fahrenheit) when it has none, the same fallback the Home Assistant interface uses.
- A thermostat with one setpoint has it moved. A thermostat that heats below one setpoint and cools above another has both moved, so the band between them keeps its width.
- The setpoint stays within the minimum and maximum the thermostat reports. A step that would cross one stops at it, and a band stops whole when either side reaches a limit.
- Adjusting is not switching. A thermostat that is off gets its setpoint moved and stays off.

:::{attention} Known limitations
:class: dropdown

- A thermostat without a setpoint, like one that only does fan speeds, cannot be targeted.
- A thermostat in a mode without a setpoint at that moment, or that has not reported one yet, is left alone.
- A thermostat already past one of its own limits, which some integrations report, is left where it is rather than pulled back, so turning it up never makes it colder.

:::

## Repairs

Spook has no repair detections for this integration.
