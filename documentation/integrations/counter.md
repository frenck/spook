---
subject: Enhanced integrations
title: Counter
subtitle: Keeping count, made on the fly.
description: Spook adds actions to the counter integration, which allow creating and deleting counter helpers from automations and scripts.
date: 2026-09-29T18:00:00+02:00
---

```{image} https://brands.home-assistant.io/counter/logo.png
:alt: The Home Assistant counter icon
:width: 250px
:align: center
```

<br><br>

The counter {term}`helper` in {term}`Home Assistant` keeps count: it goes up or down by a step, can be reset, and can be kept between a minimum and a maximum. Handy for counting how often something happened.

Spook adds actions to the counter {term}`integration <integration>` to create and delete these helpers from automations and scripts.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Create a counter

Creates a new counter helper, the same as adding one on the helpers page. Great for a script that needs to count something only for itself: it can make a counter, and delete it again when it is done.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Counter: Create a counter 👻
* - {term}`Action name`
  - `counter.create`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - Optional, the `entity_id` of the new counter
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=counter.create)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=counter.create)
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
  - `Coffee cups`
* - `counter_id`
  - {term}`string <string>`
  - No
  - `coffee_cups`
* - `initial`
  - {term}`integer <integer>`
  - No
  - `0`
* - `minimum`
  - {term}`integer <integer>`
  - No
  - `0`
* - `maximum`
  - {term}`integer <integer>`
  - No
  - `10`
* - `step`
  - {term}`integer <integer>`
  - No
  - `1`
* - `restore`
  - {term}`boolean <boolean>`
  - No
  - `true`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:coffee`
```

Without a `counter_id`, the entity ID follows the name, as it does in the UI, and gets a number at the end if that name is already taken. With a `counter_id`, you get exactly that entity ID or an error: one that is already taken is refused, rather than quietly given a number at the end.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: counter.create
data:
  name: "Coffee cups"
  counter_id: coffee_cups
  maximum: 10
response_variable: created
```

The new counter's entity ID is then in `{{ created.entity_id }}`.

:::

### Delete a counter

Deletes one or more counter helpers made in the UI or with the action above, disabled ones included. Counters set up in YAML can only be removed from the YAML.

Everything in the list is checked first: if one of them cannot be deleted, none of them are.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Counter: Delete a counter 👻
* - {term}`Action name`
  - `counter.delete`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=counter.delete)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=counter.delete)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `entity_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `counter.coffee_cups`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: counter.delete
data:
  entity_id: counter.coffee_cups
```

:::

## Repairs

Spook has no repair detections for this integration.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Let a script make the counter it needs, and clean it up again afterwards, so the helpers page only has counters you actually use.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
