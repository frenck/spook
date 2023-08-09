---
subject: Enhanced integrations
title: Number
subtitle: Elmo likes numbers too!
thumbnail: ../images/integrations/number/example.png
description: Spook adds some new services to the number integration, which allows you to set the value to the minimum or maximum value, and adds services to increase and decrease services the number value by a given amount.
date: 2023-06-30T20:36:04+02:00
---

```{image} https://brands.home-assistant.io/number/logo.png
:alt: The Home Assistant number icon
:width: 250px
:align: center
```

<br><br>

The number {term}`integration <integration>` provides numeric inputs to control {term}`devices & services <device>`. It differs from the [input number](input_number) helper in that the user does not directly create it but rather by other integrations.

Spook adds some new services to the number {term}`integration <integration>`, which allows you to set the value to the minimum or maximum value, and adds services to increase and decrease services the number value by a given amount.

```{figure} ../images/integrations/number/example.png
:name: example
:alt: Screenshot of the developer service tools, listing the new services for number.
:align: center

Spook adds a bunch of new services to the number helper integrations.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Services

Spook adds the following new service to your Home Assistant instance:

### Decrease value

Decrease a number entity value by a certain amount.

```{figure} ../images/integrations/number/decrease.png
:alt: Screenshot of the number decrease value service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Number: Decrease value 👻
* - {term}`Service name`
  - `number.decrement`
* - {term}`Service targets`
  - Yes, `number` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=number.decrement)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=number.decrement)
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

If the `amount` attribute is not provided, the service will use the step value of the number entity. The `amount` attribute must be a multiple of the step value.

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: number.decrement
target:
  entity_id: number.my_number
data:
    amount: 5
```

:::

### Increase value

Increase a number entity value by a certain amount.

```{figure} ../images/integrations/number/increase.png
:alt: Screenshot of the number increase value service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Number: Increase value 👻
* - {term}`Service name`
  - `number.increment`
* - {term}`Service targets`
  - Yes, `number` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=number.increment)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=number.increment)
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

If the `amount` attribute is not provided, the service will use the step value of the number entity. The `amount` attribute must be a multiple of the step value.

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: number.increment
target:
  entity_id: number.my_number
data:
    amount: 5
```

:::

### Set value to maximum

Set an number entity to its maximum value.

```{figure} ../images/integrations/number/maximum.png
:alt: Screenshot of the number maximum value service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Number: Set maximum value 👻
* - {term}`Service name`
  - `number.max`
* - {term}`Service targets`
  - Yes, `number` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=number.max)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=number.max)
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: number.max
target:
  entity_id: number.my_number
```

:::

### Set value to minimum

Set an number entity to its minimum value.

```{figure} ../images/integrations/number/minimum.png
:alt: Screenshot of the number minimum value service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Number: Set minimum value 👻
* - {term}`Service name`
  - `number.min`
* - {term}`Service targets`
  - Yes, `number` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=number.min)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=number.min)
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: number.min
target:
  entity_id: number.my_number
```

:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Quickly, with a single service call, set the value of a number entity to its maximum or minimum value.
- Add the ability to increase or decrease the value of a number entity with a single service call instead of having to call the `number.set_value` service using a template that does calculations on the current state.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas and support

If you have an idea on how to further enhance this integration, for example, by adding a new service, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
