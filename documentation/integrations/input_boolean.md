---
subject: Enhanced integrations
title: Input boolean
subtitle: To be, or not to be. Created on the fly.
description: Spook adds actions to the input boolean integration, which allow creating and deleting input boolean helpers from automations and scripts.
date: 2026-09-29T16:00:00+02:00
---

```{image} https://brands.home-assistant.io/input_boolean/logo.png
:alt: The Home Assistant input boolean icon
:width: 250px
:align: center
```

<br><br>

The input boolean {term}`helper` in {term}`Home Assistant` is a toggle: on or off, controlled from the frontend or from {term}`automations <automation>`, and usable as a trigger or condition.

Spook adds actions to the input boolean {term}`integration <integration>` to create and delete these helpers from automations and scripts.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Create an input boolean

Creates a new input boolean (toggle) helper, the same as adding one on the helpers page. Great for a script that needs a flag only for itself: it can make one, and delete it again when it is done.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input boolean: Create an input boolean 👻
* - {term}`Action name`
  - `input_boolean.create`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - Optional, the `entity_id` of the new input boolean
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_boolean.create)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_boolean.create)
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
  - `Guest mode`
* - `input_boolean_id`
  - {term}`string <string>`
  - No
  - `guest_mode`
* - `initial`
  - {term}`boolean <boolean>`
  - No
  - `false`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:account-multiple`
```

Without an `input_boolean_id`, the entity ID follows the name, as it does in the UI, and gets a number at the end if that name is already taken. With an `input_boolean_id`, you get exactly that entity ID or an error: one that is already taken is refused, rather than quietly given a number at the end.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_boolean.create
data:
  name: "Guest mode"
  input_boolean_id: guest_mode
  initial: false
response_variable: created
```

The new input boolean's entity ID is then in `{{ created.entity_id }}`.

:::

### Delete an input boolean

Deletes one or more input boolean helpers made in the UI or with the action above, disabled ones included. Input booleans set up in YAML can only be removed from the YAML.

Everything in the list is checked first: if one of them cannot be deleted, none of them are.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input boolean: Delete an input boolean 👻
* - {term}`Action name`
  - `input_boolean.delete`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_boolean.delete)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_boolean.delete)
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
  - `input_boolean.guest_mode`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_boolean.delete
data:
  entity_id: input_boolean.guest_mode
```

:::

## Repairs

Spook has no repair detections for this integration.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Let a script make the flag it needs, and clean it up again afterwards, so the helpers page only has toggles you actually use.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
