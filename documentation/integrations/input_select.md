---
subject: Enhanced integrations
title: Input select
subtitle: Offers a selection of the finest options.
thumbnail: ../images/integrations/input_select/example.png
description: Spook adds some new services to the input select integration, which allows to select a random option and to shuffle or sort the list of options in the input select.
date: 2023-06-30T20:36:04+02:00
---

```{image} https://brands.home-assistant.io/input_select/logo.png
:alt: The Home Assistant input select icon
:width: 250px
:align: center
```

<br><br>

The input select {term}`helper` in {term}`Home Assistant` allows the user to define a list of options that can be controlled via the frontend and can be used within conditions of an {term}`automation <automation>`. The frontend can display a dropdown, or a list of buttons. Changes to the dropdown or list of buttons generate state events. These state events can be utilized as automation triggers as well.

Spook adds some new services to the input select {term}`integration <integration>`, which allows to select a random option and to shuffle or sort the list of options in the input select.

```{figure} ../images/integrations/input_select/example.png
:name: example
:alt: Screenshot of the developer service tools, listing the new services for input select.
:align: center

Spook adds a bunch of new services to the input select helper integrations.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Services

Spook adds the following new service to your Home Assistant instance:

### Select random option

Select a random option from the list of options in the input select.

```{figure} ../images/integrations/input_select/random.png
:name: random
:alt: Screenshot of the input select random service call in the developer tools.
:align: center

Spook adds a brand new service to select a random option from the list of options.
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Input select: Select random option 👻
* - {term}`Service name`
  - `input_select.random`
* - {term}`Service targets`
  - Yes, `input_select` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.random)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `options`
  - list of strings
  - No
  - Defaults to all available options
```

The `options` attribute is a list of strings, containing the options to select a random one from. If not provided, all available options configured in the input select are used.

:::{seealso} Example service calls in YAML
:class: dropdown

```{code-block} yaml
:linenos:
service: input_select.random
target:
  entity_id: input_select.who_is_cooking_tonight
```

```{code-block} yaml
:linenos:
service: input_select.random
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

Shuffles the list of available options in the input select, keept the current
select options selected.

```{figure} ../images/integrations/input_select/shuffle.png
:name: shuffle
:alt: Screenshot of the input select shuffle service call in the developer tools.
:align: center

Spook adds a brand new service to select shuffle the options of an input select.
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Input select: Shuffle options 👻
* - {term}`Service name`
  - `input_select.shuffle`
* - {term}`Service targets`
  - Yes, `input_select` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.shuffle)
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: input_select.shuffle
target:
  entity_id: input_select.who_is_cooking_tonight
```

:::

:::{attention}
Shuffling is not persistent and will be undone once reloaded or Home Assistant restarts.
:::

### Sort options

Sorts the list of available options in the input select, keept the current
select options selected.

```{figure} ../images/integrations/input_select/sort.png
:name: sort
:alt: Screenshot of the input select sort service call in the developer tools.
:align: center

Spook adds a brand new service to select sort the options of an input select.
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Input select: Sort options 👻
* - {term}`Service name`
  - `input_select.sort`
* - {term}`Service targets`
  - Yes, `input_select` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.sort)
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: input_select.sort
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
- The input select entity, doesn't allow you to recorder the options. The sort ability allows you to sort the options alphabetically at least.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one, or stubled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas and support

If you have an idea on how to futher enhance this integration, for example by adding a new service, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've ran into an bug? Please check the [](../support) page on where to go for help.
