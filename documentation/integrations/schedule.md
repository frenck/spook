---
subject: Enhanced integrations
title: Schedule
subtitle: A week of time blocks, cleaned up on the fly.
description: Spook adds an action to the schedule integration, which allows deleting schedule helpers from automations and scripts.
date: 2026-10-11T12:00:00+02:00
---

```{image} https://brands.home-assistant.io/schedule/logo.png
:alt: The Home Assistant schedule icon
:width: 250px
:align: center
```

<br><br>

The schedule {term}`helper` in {term}`Home Assistant` is on during the time blocks you give it for each day of the week, and off the rest of the time. Heating that follows the working week, for example.

Spook adds an action to the schedule {term}`integration <integration>` to delete these helpers from automations and scripts.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new action to your Home Assistant instance:

### Delete a schedule

Deletes one or more schedule helpers made in the UI, disabled ones included. Schedules set up in YAML can only be removed from the YAML.

Everything in the list is checked first: if one of them cannot be deleted, none of them are.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Schedule: Delete a schedule 👻
* - {term}`Action name`
  - `schedule.delete`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=schedule.delete)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=schedule.delete)
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
  - `schedule.heating`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: schedule.delete
data:
  entity_id: schedule.heating
```

:::

## Repairs

Spook has no repair detections for this integration.

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Clean up schedules that are no longer needed from a script, so the helpers page only has schedules you actually use.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
