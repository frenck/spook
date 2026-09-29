---
subject: Enhanced integrations
title: Input datetime
subtitle: A date, a time, or both. Made on the fly.
description: Spook adds actions to the input datetime integration, which allow creating and deleting input datetime helpers from automations and scripts.
date: 2026-09-29T22:00:00+02:00
---

```{image} https://brands.home-assistant.io/input_datetime/logo.png
:alt: The Home Assistant input datetime icon
:width: 250px
:align: center
```

<br><br>

The input datetime {term}`helper` in {term}`Home Assistant` holds a date, a time, or both, that can be set from the frontend or from {term}`automations <automation>`, and used as a trigger. An alarm clock you can put on a dashboard, for example.

Spook adds actions to the input datetime {term}`integration <integration>` to create and delete these helpers from automations and scripts.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Create an input datetime

Creates a new input datetime helper, the same as adding one on the helpers page. Great for a script that needs to remember a moment only for itself: it can make one, and delete it again when it is done.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input datetime: Create an input datetime 👻
* - {term}`Action name`
  - `input_datetime.create`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - Optional, the `entity_id` of the new input datetime
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_datetime.create)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_datetime.create)
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
  - `Wake up`
* - `input_datetime_id`
  - {term}`string <string>`
  - No
  - `wake_up`
* - `has_date`
  - {term}`boolean <boolean>`
  - No
  - `false`
* - `has_time`
  - {term}`boolean <boolean>`
  - No
  - `true`
* - `initial`
  - {term}`string <string>`
  - No
  - `07:30:00`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:alarm`
```

At least one of `has_date` and `has_time` has to be on, and both are off when left out, so give at least one. An initial value has to be something Home Assistant can read as a date, a time, or both; one it cannot is refused before anything is made.

Without an `input_datetime_id`, the entity ID follows the name, as it does in the UI, and gets a number at the end if that name is already taken. With an `input_datetime_id`, you get exactly that entity ID or an error: one that is already taken is refused, rather than quietly given a number at the end.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_datetime.create
data:
  name: "Wake up"
  input_datetime_id: wake_up
  has_time: true
  initial: "07:30:00"
response_variable: created
```

The new input datetime's entity ID is then in `{{ created.entity_id }}`.

:::

### Delete an input datetime

Deletes one or more input datetime helpers made in the UI or with the action above, disabled ones included. Input datetimes set up in YAML can only be removed from the YAML.

Everything in the list is checked first: if one of them cannot be deleted, none of them are.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input datetime: Delete an input datetime 👻
* - {term}`Action name`
  - `input_datetime.delete`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_datetime.delete)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_datetime.delete)
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
  - `input_datetime.wake_up`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_datetime.delete
data:
  entity_id: input_datetime.wake_up
```

:::

## Repairs

Spook has no repair detections for this integration.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Let a script make the date or time it needs, and clean it up again afterwards, so the helpers page only has input datetimes you actually use.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
