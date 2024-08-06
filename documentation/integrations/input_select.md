---
subject: Enhanced integrations
title: Input select
subtitle: Offers a selection of the finest options.
thumbnail: ../images/integrations/input_select/example.png
description: Spook adds some new actions to the input select integration, which allows to select a random option and to shuffle or sort the list of options in the input select.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/input_select/logo.png
:alt: The Home Assistant input select icon
:width: 250px
:align: center
```

<br><br>

The input select {term}`helper` in {term}`Home Assistant` allows the user to define a list of options that can be controlled via the frontend and can be used within conditions of an {term}`automation <automation>`. The frontend can display a dropdown or a list of buttons. Changes to the dropdown or list of buttons generate state events. These state events can be utilized as automation triggers as well.

Spook adds some new actions to the input select {term}`integration <integration>`, which allows one to select a random option and to shuffle or sort the list of options in the input select.

```{figure} ../images/integrations/input_select/example.png
:name: example
:alt: Screenshot of the developer actions tools, listing the new actions for input select.
:align: center

Spook adds a bunch of new actions to the input select helper integrations.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Select random option

Select a random option from the list of options in the input select.

```{figure} ../images/integrations/input_select/random.png
:alt: Screenshot of the input select random action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input select: Select random option 👻
* - {term}`Action name`
  - `input_select.random`
* - {term}`Action targets`
  - Yes, `input_select` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.random)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.random)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `options`
  - {term}`list of strings <list>`
  - No
  - Defaults to all available options
```

The `options` attribute is a {term}`list of strings <list>`, containing the options to select a random one from. If not provided, all available options configured in the input select are used.

:::{seealso} Example actions in YAML
:class: dropdown

```{code-block} yaml
:linenos:
action: input_select.random
target:
  entity_id: input_select.who_is_cooking_tonight
```

```{code-block} yaml
:linenos:
action: input_select.random
target:
  entity_id: input_select.color
data:
  options:
    - red
    - green
    - blue
```

:::

### Shuffle options

Shuffles the list of available options in the input select and keeps the current
select options selected.

```{figure} ../images/integrations/input_select/shuffle.png
:alt: Screenshot of the input select shuffle action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input select: Shuffle options 👻
* - {term}`Action name`
  - `input_select.shuffle`
* - {term}`Action targets`
  - Yes, `input_select` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.shuffle)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.shuffle)
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_select.shuffle
target:
  entity_id: input_select.who_is_cooking_tonight
```

:::

:::{attention}
Shuffling is not persistent and will be undone once reloaded or Home Assistant restarts.
:::

### Sort options

Sorts the list of available options in the input select and keeps the current
select options selected.

```{figure} ../images/integrations/input_select/sort.png
:alt: Screenshot of the input select sort action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input select: Sort options 👻
* - {term}`Action name`
  - `input_select.sort`
* - {term}`Action targets`
  - Yes, `input_select` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.sort)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.sort)
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_select.sort
target:
  entity_id: input_select.who_is_cooking_tonight
```

:::

:::{attention}
Sorting is not persistent and will be undone once reloaded or Home Assistant restarts.
:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- The shuffle and random abilities can have very fun use cases in automations. For example, select a random person to cook dinner or do chores, or shuffle a sequence of scenes to play.
- The input select entity doesn't allow you to re-order the options. The sort ability allows you to sort the options alphabetically, at least.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
