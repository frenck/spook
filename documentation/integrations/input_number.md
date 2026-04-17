---
subject: Enhanced integrations
title: Input number
subtitle: Give me your digits. 🔢
thumbnail: ../images/integrations/input_number/example.png
description: Spook adds some new actions to the input number integration, which allows you to create and delete input number helpers on the fly, set the value to the minimum or maximum value, or increase or decrease value by a given amount.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/input_number/logo.png
:alt: The Home Assistant input number icon
:width: 250px
:align: center
```

<br><br>

The input number {term}`helper` in {term}`Home Assistant` allows the user to define values that can be controlled via the frontend and can be used within conditions of an {term}`automation <automation>`. The frontend can display a slider or a numeric input box. Changes to the slider or numeric input box generate state events. These state events can be utilized as automation triggers as well.

Spook adds some new actions to the input number {term}`integration <integration>`, which allows you to create and delete input number helpers on the fly, set the value to the minimum or maximum value, and enhances the existing increase and decrease actions by allowing them to increase/decrease the value by a given amount.

```{figure} ../images/integrations/input_number/example.png
:name: example
:alt: Screenshot of the developer actions tools, listing the new actions for input number.
:align: center

Spook adds many new actions to the input number helper integrations.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Create an input number

```{figure} ../images/integrations/input_number/create.png
:alt: Screenshot of the input number create action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input number: Create an input number 👻
* - {term}`Action name`
  - `input_number.create`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.create)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.create)
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
  - `My input number`
* - `input_number_id`
  - {term}`string <string>`
  - No
  - `my_input_number`
* - `min`
  - {term}`float <float>`
  - No
  - `0`
* - `max`
  - {term}`float <float>`
  - No
  - `100`
* - `initial`
  - {term}`float <float>`
  - No
  - `50`
* - `step`
  - {term}`float <float>`
  - No
  - `1`
* - `mode`
  - {term}`string <string>`
  - No
  - `slider`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:counter`
* - `unit_of_measurement`
  - {term}`string <string>`
  - No
  - `°C`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_number.create
data:
  name: "My counter"
  input_number_id: my_counter
  min: 0
  max: 100
  step: 1
  mode: slider
```

:::

### Delete an input number

:::{note}
Input number helpers that are created and managed using manual YAML configuration cannot be deleted.
:::

```{figure} ../images/integrations/input_number/delete.png
:alt: Screenshot of the input number delete action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input number: Delete an input number 👻
* - {term}`Action name`
  - `input_number.delete`
* - {term}`Action targets`
  - Yes, `input_number` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.delete)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.delete)
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_number.delete
target:
  entity_id: input_number.my_counter
```

:::

### Decrease value

Decrease an input number entity value by a certain amount.

```{figure} ../images/integrations/input_number/decrease.png
:alt: Screenshot of the input number decrease value action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input number: Decrease value 👻
* - {term}`Action name`
  - `input_number.decrement`
* - {term}`Action targets`
  - Yes, `input_number` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Adds an amount to decrement the value with
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.decrement)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.decrement)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `amount`
  - {term}`integer <integer>`
  - No
  - Defaults to configured step value
```

This action already exists but is extended by Spook to add the `amount` attribute. If the `amount` attribute is not provided, the action will use the step value of the input number entity. The `amount` attribute must be a multiple of the step value.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_number.decrement
target:
  entity_id: input_number.my_input_number
data:
    amount: 5
```

:::

### Increase value

Increase an input number entity value by a certain amount.

```{figure} ../images/integrations/input_number/increase.png
:alt: Screenshot of the input number increase value action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input number: Increase value 👻
* - {term}`Action name`
  - `input_number.increment`
* - {term}`Action targets`
  - Yes, `input_number` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Adds an amount to increment the value with
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.increment)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.increment)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `amount`
  - {term}`integer <integer>`
  - No
  - Defaults to configured step value
```

This action already exists but is extended by Spook to add the `amount` attribute. If the `amount` attribute is not provided, the action will use the step value of the input number entity. The `amount` attribute must be a multiple of the step value.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_number.increment
target:
  entity_id: input_number.my_input_number
data:
    amount: 5
```

:::

### Set value to maximum

Set an input number entity to its maximum value.

```{figure} ../images/integrations/input_number/maximum.png
:alt: Screenshot of the input number maximum value action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input number: Set maximum value 👻
* - {term}`Action name`
  - `input_number.max`
* - {term}`Action targets`
  - Yes, `input_number` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.max)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.max)
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_number.max
target:
  entity_id: input_number.my_input_number
```

:::

### Set value to minimum

Set an input number entity to its minimum value.

```{figure} ../images/integrations/input_number/minimum.png
:alt: Screenshot of the input number minimum value action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input number: Set minimum value 👻
* - {term}`Action name`
  - `input_number.min`
* - {term}`Action targets`
  - Yes, `input_number` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.min)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.min)
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_number.min
target:
  entity_id: input_number.my_input_number
```

:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Dynamically create input number helpers from a blueprint or script, without requiring the user to set them up manually beforehand.
- Clean up temporary input number helpers created by an automation or script when they are no longer needed.
- Quickly, with a single action, set the value of an input helper to its maximum or minimum value.
- Instead of having to call the `input_number.decrement` or `input_number.increment` action multiple times, you can now set the amount to increase or decrease the value with.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
