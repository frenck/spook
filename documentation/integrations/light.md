---
subject: Enhanced integrations
title: Light
subtitle: Turn it down a bit, would you 💡
description: Spook adds actions that adjust the lights that are already on, leaving the ones that are off alone, and stepping every light in a group from its own level instead of from the group average.
date: 2026-08-29T14:00:00+02:00
---

```{image} https://brands.home-assistant.io/light/icon.png
:alt: The Home Assistant light icon
:width: 250px
:align: center
```

<br><br>

The light {term}`integration <integration>` is how {term}`Home Assistant` controls anything that lights up a room.

Spook adds actions for adjusting lights, rather than switching them: brightness, color, color temperature and effects. `light.turn_on` does two things at once: it sets a level and it turns the light on. Most of the time somebody adjusting a room means the first without the second, and there is no way to ask for that.

There is a second half to it. A light group is a light like any other, so asking one for a little more brightness has Home Assistant average its members, apply the step to that average, and then set every member to the result. A room with a lamp at 10% and one at 100% ends up with both at 65%: not brighter, just flatter. Spook's actions work through to the members and step each from its own level.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Set brightness

Set the brightness of the lights that are already on.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Light: Set brightness 👻
* - {term}`Action name`
  - `light.set_brightness`
* - {term}`Action targets`
  - Yes, `light` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_brightness)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_brightness)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `brightness_pct`
  - {term}`number <number>`
  - Yes
  - 50
* - `transition`
  - {term}`number <number>`
  - No
  - 2
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

Half brightness in the living room, without waking up whatever is off in there:

```{code-block} yaml
:linenos:
action: light.set_brightness
target:
  area_id: living_room
data:
  brightness_pct: 50
  transition: 2
```

:::

### Increase brightness

Turn up the lights that are already on.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Light: Increase brightness 👻
* - {term}`Action name`
  - `light.increase_brightness`
* - {term}`Action targets`
  - Yes, `light` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.increase_brightness)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=light.increase_brightness)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `step_pct`
  - {term}`number <number>`
  - Yes
  - 10
* - `transition`
  - {term}`number <number>`
  - No
  - 2
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

A dim-up button that does what the one on a Hue remote does:

```{code-block} yaml
:linenos:
action: light.increase_brightness
target:
  entity_id: light.kitchen
data:
  step_pct: 10
```

:::

### Decrease brightness

Turn down the lights that are already on, stopping at the dimmest they go.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Light: Decrease brightness 👻
* - {term}`Action name`
  - `light.decrease_brightness`
* - {term}`Action targets`
  - Yes, `light` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.decrease_brightness)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=light.decrease_brightness)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `step_pct`
  - {term}`number <number>`
  - Yes
  - 10
* - `transition`
  - {term}`number <number>`
  - No
  - 2
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: light.decrease_brightness
target:
  area_id: bedroom
data:
  step_pct: 20
```

:::

### Set color

Set the color of the lights that are already on. Lights that cannot do color are passed over, rather than being turned white the way `light.turn_on` does to them.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Light: Set color 👻
* - {term}`Action name`
  - `light.set_color`
* - {term}`Action targets`
  - Yes, `light` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_color)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_color)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `rgb_color`
  - {term}`list <list>`
  - One of the two
  - [255, 127, 80]
* - `color_name`
  - {term}`string <string>`
  - One of the two
  - coral
* - `transition`
  - {term}`number <number>`
  - No
  - 2
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: light.set_color
target:
  area_id: living_room
data:
  color_name: coral
```

:::

### Set color temperature

Set the color temperature of the lights that are already on, each within the range it can actually reach. Warm white on one lamp is a number another one cannot manage, and a room is rarely all the same model.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Light: Set color temperature 👻
* - {term}`Action name`
  - `light.set_color_temperature`
* - {term}`Action targets`
  - Yes, `light` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_color_temperature)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_color_temperature)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `kelvin`
  - {term}`number <number>`
  - Yes
  - 2700
* - `transition`
  - {term}`number <number>`
  - No
  - 2
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: light.set_color_temperature
target:
  area_id: living_room
data:
  kelvin: 2700
  transition: 2
```

:::

### Set effect

Set an effect on the lights that are already on and actually have it. Effect names are per manufacturer and rarely agree, so a room is usually a mix of lights that know this one and lights that have never heard of it.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Light: Set effect 👻
* - {term}`Action name`
  - `light.set_effect`
* - {term}`Action targets`
  - Yes, `light` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_effect)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_effect)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `effect`
  - {term}`string <string>`
  - Yes
  - Colorloop
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: light.set_effect
target:
  entity_id: light.kitchen
data:
  effect: Colorloop
```

:::

:::{attention} Known limitations
:class: dropdown

- Lights that are off are left alone. These actions adjust, they do not switch: turning the room up should not light up whatever somebody deliberately turned off.
- Decreasing stops at the dimmest a light goes rather than switching it off, so holding a dim-down button leaves the room lit rather than dark.
- A light that cannot do what is being asked is skipped rather than turned on regardless: an on-or-off light has no brightness to set, a white-only light has no color, and a light without a given effect has never heard of it.
  :::

## Repairs

Spook has no repair detections for this integration.
