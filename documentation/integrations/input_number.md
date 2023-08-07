---
subject: Enhanced integrations
title: Input number
subtitle: Give me you digits. 🔢
thumbnail: ../images/integrations/input_number/example.png
description: Spook adds some new services to the input number integration, which allows you to set the value to the minimum or maximum value, or increase or decrease value by a given amount.
date: 2023-06-30T20:36:04+02:00
---

```{image} https://brands.home-assistant.io/input_number/logo.png
:alt: The Home Assistant input number icon
:width: 250px
:align: center
```

<br><br>

The input number {term}`helper` in {term}`Home Assistant` allows the user to define values that can be controlled via the frontend and can be used within conditions of an {term}`automation <automation>`. The frontend can display a slider, or a numeric input box. Changes to the slider or numeric input box generate state events. These state events can be utilized as automation triggers as well.

Spook adds some new services to the input number {term}`integration <integration>`, which allows you to set the value to the minimum or maximum value, and enhances the existing increase and decrease services by allowing them to increase/decrease the value by a given amount.

```{figure} ../images/integrations/input_number/example.png
:name: example
:alt: Screenshot of the developer service tools, listing the new services for input number.
:align: center

Spook adds a bunch of new services to the input number helper integrations.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Services

Spook adds the following new service to your Home Assistant instance:

### Decrease value

Decrease an input number entity value by a certain amount.

```{figure} ../images/integrations/input_number/decrease.png
:alt: Screenshot of the input number decrease value service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Input number: Decrease value 👻
* - {term}`Service name`
  - `input_number.decrement`
* - {term}`Service targets`
  - Yes, `input_number` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Adds amount to decrement the value with
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.decrement)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.decrement)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `amount`
  - {term}`integer <integer>`
  - No
  - Defaults to configured step value
```

This service already exists, but is extended by Spook to add the `amount` attribute. If the `amount` attribute is not provided, the service will use the step value of the input number entity. The `amount` attribute must be a multiple of the step value.

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: input_number.decrement
target:
  entity_id: input_number.my_input_number
data:
    amount: 5
```

:::

### Increase value

Increase an input number entity value by a certain amount.

```{figure} ../images/integrations/input_number/increase.png
:alt: Screenshot of the input number increase value service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Input number: Increase value 👻
* - {term}`Service name`
  - `input_number.increment`
* - {term}`Service targets`
  - Yes, `input_number` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Adds amount to increment the value with
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.increment)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.increment)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `amount`
  - {term}`integer <integer>`
  - No
  - Defaults to configured step value
```

This service already exists, but is extended by Spook to add the `amount` attribute. If the `amount` attribute is not provided, the service will use the step value of the input number entity. The `amount` attribute must be a multiple of the step value.

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: input_number.increment
target:
  entity_id: input_number.my_input_number
data:
    amount: 5
```

:::

### Set value to maximum

Set an input number entity to its maximum value.

```{figure} ../images/integrations/input_number/maximum.png
:alt: Screenshot of the input number maximum value service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Input number: Set maximum value 👻
* - {term}`Service name`
  - `input_number.max`
* - {term}`Service targets`
  - Yes, `input_number` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.max)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.max)
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: input_number.max
target:
  entity_id: input_number.my_input_number
```

:::

### Set value to minimum

Set an input number entity to its minimum value.

```{figure} ../images/integrations/input_number/minimum.png
:alt: Screenshot of the input number minimum value service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Input number: Set minimum value 👻
* - {term}`Service name`
  - `input_number.min`
* - {term}`Service targets`
  - Yes, `input_number` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.min)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.min)
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: input_number.min
target:
  entity_id: input_number.my_input_number
```

:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Quickly, with a single service call, set the value of an input helper to its maximum or minimum value.
- Instead of having to call the `input_number.decrement` or `input_number.increment` service multiple times, you can now set the amount to increase or decrease the value with.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one, or stubled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas and support

If you have an idea on how to futher enhance this integration, for example by adding a new service, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've ran into an bug? Please check the [](../support) page on where to go for help.
