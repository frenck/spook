---
subject: Enhanced integrations
title: Input button
subtitle: Press here. Made on the fly.
description: Spook adds actions to the input button integration, which allow creating and deleting input button helpers from automations and scripts.
date: 2026-09-29T21:00:00+02:00
---

```{image} https://brands.home-assistant.io/input_button/logo.png
:alt: The Home Assistant input button icon
:width: 250px
:align: center
```

<br><br>

The input button {term}`helper` in {term}`Home Assistant` is a button to press, from the frontend or from {term}`automations <automation>`. It has no on or off, only the moment it was last pressed, which makes it a trigger you can put on a dashboard.

Spook adds actions to the input button {term}`integration <integration>` to create and delete these helpers from automations and scripts.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Create an input button

Creates a new input button helper, the same as adding one on the helpers page. Great for a script that needs a button only for a while: it can make one, and delete it again when it is done.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input button: Create an input button 👻
* - {term}`Action name`
  - `input_button.create`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - Optional, the `entity_id` of the new input button
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_button.create)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_button.create)
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
  - `Doorbell`
* - `input_button_id`
  - {term}`string <string>`
  - No
  - `doorbell`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:doorbell`
```

Without an `input_button_id`, the entity ID follows the name, as it does in the UI, and gets a number at the end if that name is already taken. With an `input_button_id`, you get exactly that entity ID or an error: one that is already taken is refused, rather than quietly given a number at the end.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_button.create
data:
  name: "Doorbell"
  input_button_id: doorbell
response_variable: created
```

The new input button's entity ID is then in `{{ created.entity_id }}`.

:::

### Delete an input button

Deletes one or more input button helpers made in the UI or with the action above, disabled ones included. Input buttons set up in YAML can only be removed from the YAML.

Everything in the list is checked first: if one of them cannot be deleted, none of them are.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Input button: Delete an input button 👻
* - {term}`Action name`
  - `input_button.delete`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_button.delete)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=input_button.delete)
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
  - `input_button.doorbell`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: input_button.delete
data:
  entity_id: input_button.doorbell
```

:::

## Repairs

Spook has no repair detections for this integration.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Let a script make the button it needs, and clean it up again afterwards, so the helpers page only has buttons you actually use.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
