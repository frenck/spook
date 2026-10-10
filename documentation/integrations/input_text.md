---
subject: Enhanced integrations
title: Input text
subtitle: A few words, made on the fly.
description: Spook adds actions to the input text integration, which allow creating and deleting input text helpers from automations and scripts.
date: 2026-09-29T20:00:00+02:00
---

```{image} https://brands.home-assistant.io/input_text/logo.png
:alt: The Home Assistant input text icon
:width: 250px
:align: center
```

<br><br>

The input text {term}`helper` in {term}`Home Assistant` holds a piece of text that can be changed from the frontend or from {term}`automations <automation>`, optionally kept to a length or a pattern, or hidden like a password.

Spook adds actions to the input text {term}`integration <integration>` to create and delete these helpers from automations and scripts.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Create an input text

Creates a new input text helper, the same as adding one on the helpers page. Great for a script that needs to hold on to some text only for itself: it can make one, and delete it again when it is done.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input text: Create an input text 👻
* - {term}`Action name`
  - `input_text.create`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - Optional, the `entity_id` of the new input text
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_text.create)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_text.create)
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
  - `Last message`
* - `input_text_id`
  - {term}`string <string>`
  - No
  - `last_message`
* - `initial`
  - {term}`string <string>`
  - No
  - `Hello`
* - `min`
  - {term}`integer <integer>`
  - No
  - `0`
* - `max`
  - {term}`integer <integer>`
  - No
  - `100`
* - `pattern`
  - {term}`string <string>`
  - No
  - `[a-z ]*`
* - `mode`
  - {term}`string <string>`
  - No
  - `text`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:message-text`
* - `unit_of_measurement`
  - {term}`string <string>`
  - No
  - `words`
```

The minimum length has to stay below the maximum, and an initial value has to fit between them; a call that does not is refused.

Without an `input_text_id`, the entity ID follows the name, as it does in the UI, and gets a number at the end if that name is already taken. With an `input_text_id`, you get exactly that entity ID or an error: one that is already taken is refused, rather than quietly given a number at the end.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_text.create
data:
  name: "Last message"
  input_text_id: last_message
  max: 255
response_variable: created
```

The new input text's entity ID is then in `{{ created.entity_id }}`.

:::

### Delete an input text

Deletes one or more input text helpers made in the UI or with the action above, disabled ones included. Input texts set up in YAML can only be removed from the YAML.

Everything in the list is checked first: if one of them cannot be deleted, none of them are.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input text: Delete an input text 👻
* - {term}`Action name`
  - `input_text.delete`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_text.delete)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_text.delete)
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
  - `input_text.last_message`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_text.delete
data:
  entity_id: input_text.last_message
```

:::

## Repairs

Spook has no repair detections for this integration.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Let a script make the text helper it needs, and clean it up again afterwards, so the helpers page only has input texts you actually use.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
