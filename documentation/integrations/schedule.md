---
subject: Enhanced integrations
title: Schedule
subtitle: A week of time blocks, made and cleaned up on the fly.
description: Spook adds actions to the schedule integration, which allow creating and deleting schedule helpers from automations and scripts.
date: 2026-10-11T12:00:00+02:00
---

```{image} https://brands.home-assistant.io/schedule/logo.png
:alt: The Home Assistant schedule icon
:width: 250px
:align: center
```

<br><br>

The schedule {term}`helper` in {term}`Home Assistant` is on during the time blocks you give it for each day of the week, and off the rest of the time. Heating that follows the working week, for example.

Spook adds actions to the schedule {term}`integration <integration>` to create and delete these helpers from automations and scripts.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Create a schedule

Creates a new schedule helper, the same as adding one on the helpers page. Great for a script or a blueprint that sets up the week it needs itself.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Schedule: Create a schedule 👻
* - {term}`Action name`
  - `schedule.create`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - Optional, the `entity_id` of the new schedule
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=schedule.create)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=schedule.create)
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
  - `Heating`
* - `schedule_id`
  - {term}`string <string>`
  - No
  - `heating`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:radiator`
* - `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday`
  - {term}`list <list>`
  - No
  - `[{"from": "07:00:00", "to": "09:00:00"}]`
```

Each day takes a list of time blocks. A block has a `from` and a `to` time, and optionally `data`: values the schedule shows as attributes while that block is on. A `to` of `24:00:00` runs until midnight. Blocks on the same day cannot overlap, and each has to end after it starts; a schedule that breaks either is refused before anything is made. A day left out is off all day.

Without a `schedule_id`, the entity ID follows the name, as it does in the UI, and gets a number at the end if that name is already taken. With a `schedule_id`, you get exactly that entity ID or an error: one that is already taken is refused, rather than quietly given a number at the end.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: schedule.create
data:
  name: "Heating"
  schedule_id: heating
  monday:
    - from: "06:30:00"
      to: "08:30:00"
      data:
        temperature: 21
    - from: "17:00:00"
      to: "22:00:00"
  saturday:
    - from: "09:00:00"
      to: "24:00:00"
response_variable: created
```

The new schedule's entity ID is then in `{{ created.entity_id }}`.

:::

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

- Let a script or a blueprint make the schedule it needs, with its whole week of time blocks, without a trip to the helpers page.
- Clean up schedules that are no longer needed from a script, so the helpers page only has schedules you actually use.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
