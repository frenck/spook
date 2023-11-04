---
subject: Enhanced integrations
title: Input number
subtitle: Give me your digits. 🔢
thumbnail: ../images/integrations/input_number/example.png
description: Spook adds some new services to the input number integration, which allows you to set the value to the minimum or maximum value, or increase or decrease value by a given amount.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/timer/logo.png
:alt: The Home Assistant timer icon
:width: 250px
:align: center
```

<br><br>

The timer {term}`helper` in {term}`Home Assistant` aims to simplify {term}`automations <automation>` based on (dynamic) durations.

Spook adds a new service to the timer {term}`integration <integration>`, which allows you to set the duration of a timer to a given value.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Services

Spook adds the following new service to your Home Assistant instance:

### Set duration

Set the duration for a timer entity.


```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Timer: Set duration 👻
* - {term}`Service name`
  - `timer.set_duration`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.set_duration)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.set_duration)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `duration`
  - {term}`string <string>`
  - Yes
  - 00:01:00, 60
```

This service already exists but is extended by Spook to add the `amount` attribute. If the `amount` attribute is not provided, the service will use the step value of the input number entity. The `amount` attribute must be a multiple of the step value.

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: timer.set_duration
data:
  entity_id: timer.my_timer
  duration: "00:15:00"
```

:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Quickly, with a single service call, set the duration of a timer without having to got through the UI.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas and support

If you have an idea on how to further enhance this integration, for example, by adding a new service, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
