---
subject: Enhanced integrations
title: Water heater
subtitle: A shower too cold, a bath too hot. 🛁
description: Spook adds actions that turn a water heater up or down a step.
date: 2026-10-04T15:00:00+02:00
---

```{image} https://brands.home-assistant.io/water_heater/icon.png
:alt: The Home Assistant water heater icon
:width: 250px
:align: center
```

<br><br>

The water heater {term}`integration <integration>` is how {term}`Home Assistant` controls boilers, heat pump water heaters and other things that keep water hot.

Home Assistant can set a water heater to a temperature, but not turn it up a step. Spook adds the step, the same way it does for [thermostats](climate).

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Increase temperature

Turn up a water heater's setpoint a step, within the limits it reports.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Water heater: Increase temperature 👻
* - {term}`Action name`
  - `water_heater.increase_temperature`
* - {term}`Action targets`
  - Yes, `water_heater` entities with a setpoint
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=water_heater.increase_temperature)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=water_heater.increase_temperature)
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
  - The water heater's own step
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: water_heater.increase_temperature
target:
  entity_id: water_heater.boiler
data:
  step: 2
```

:::

### Decrease temperature

Turn down a water heater's setpoint a step, within the limits it reports.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Water heater: Decrease temperature 👻
* - {term}`Action name`
  - `water_heater.decrease_temperature`
* - {term}`Action targets`
  - Yes, `water_heater` entities with a setpoint
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=water_heater.decrease_temperature)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=water_heater.decrease_temperature)
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
  - The water heater's own step
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: water_heater.decrease_temperature
target:
  entity_id: water_heater.boiler
```

:::

Both actions work the same way:

- The step is the one you give, in Home Assistant's unit, or the water heater's own step, or half a degree (one degree in Fahrenheit) when it has none, the same fallback the Home Assistant interface uses.
- The setpoint stays within the minimum and maximum the water heater reports. A step that would cross one stops at it.
- Everything is worked out in the water heater's own unit, so one in Fahrenheit is stepped in whole Fahrenheit degrees and meets its own limits exactly.
- Adjusting is not switching. A water heater that is off gets its setpoint moved and stays off.

:::{attention} Known limitations
:class: dropdown

- A water heater without a setpoint, like one that can only be switched on and off, cannot be targeted.
- A water heater that has not reported a setpoint yet is left alone.
- A setpoint already past one of the water heater's own limits, which some integrations report, is left where it is rather than pulled back.

:::

## Repairs

Spook has no repair detections for this integration.
