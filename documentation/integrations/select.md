---
subject: Enhanced integrations
title: Select
subtitle: Selecting from the selection using a selector.
thumbnail: ../images/integrations/select/example.png
description: Spook adds a new service to the select integration, which allows to select a random option from the list of options.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/select/logo.png
:alt: The Home Assistant select logo
:width: 250px
:align: center
```

<br><br>

The select {term}`integration <integration>` provides a way to select a value from a list of options. It differs from the [input select](input_select) helper in that the user does not directly create it but rather by other integrations.

Spook extends the select integration with an option to select a random option from the options offered by the select {term}`entity <entity>`.

```{figure} ../images/integrations/select/example.png
:name: example
:alt: Screenshot of the developer service tools, showing the new random service for select.
:align: center

Spook adds a new random select service to the select integration.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Services

Spook adds the following new service to your Home Assistant instance:

### Select random option

Select a random option from the list of options in the input select.

```{figure} ../images/integrations/select/example.png
:alt: Screenshot of the select random service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Select: Select random option 👻
* - {term}`Service name`
  - `select.random`
* - {term}`Service targets`
  - Yes, `select` entities
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=select.random)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=select.random)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `options`
  - {term}`list of strings <list>`
  - No
  - Defaults to all available options
```

The `options` attribute is a {term}`list of strings <list>` containing the options to select a random one from. If not provided, all available options configured in the input select are used.

:::{seealso} Example service calls in YAML
:class: dropdown

```{code-block} yaml
:linenos:
service: select.random
target:
  entity_id: select.effect
```

```{code-block} yaml
:linenos:
service: select.random
target:
  entity_id: select.color
data:
  options:
    - red
    - green
    - blue
```

:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- The random select can be useful, for example, choosing a random preset or playlist from a list of options. This can add some surprise factor to some automations.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new service, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
