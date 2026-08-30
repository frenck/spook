---
subject: Enhanced integrations
title: Automations 🤖
short_title: Automations
subtitle: The breathing (mechanical) heart of Home Assistant.
thumbnail: ../images/integrations/automation/example.png
description: Spook enhances the automation integrations of Home Assistant by raising repairs issues, in case it detects something is wrong with an automation, for example, if it is using non-existing entities.
date: 2024-02-10T15:58:22+01:00
---

```{image} https://brands.home-assistant.io/automation/logo.png
:alt: The Home Assistant automation icon
:width: 250px
:align: center
```

<br><br>

Automations are the heart of {term}`Home Assistant`. It is what makes Home Assistant a home automation platform. It is the glue that binds all the other {term}`integrations <integration>` together, and it is what makes your home smart and comfortable.

Non-working automations, however, are a source of frustration. And sometimes, it can take you a bit to notice there is an issue with an automation. Spook enhances the automation integration of Home Assistant by raising repairs issues in case it detects something is wrong with an automation.

```{figure} ../images/integrations/automation/example.png
:name: example
:alt: Screenshot showing a repair raised by Spook for an automation.
:align: center

Spook found an issue with an automation that is using non-existing entities.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Snooze

Turns an automation off for a while, and turns it back on when the time is up.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Automation: Snooze 👻
* - {term}`Action name`
  - `automation.snooze`
* - {term}`Action targets`
  - Yes, `automation` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=automation.snooze)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=automation.snooze)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `duration`
  - {term}`string <string>`
  - Yes
  - `01:00:00`
```

Turning an automation off is the only way to make it stop for an hour, and an automation turned off stays off: past the restart, past the weekend, until somebody notices. The usual way around that is a helper entity and a second automation to turn the first one back on, which is two moving parts for something that should be one.

This is that, in one action. It survives a restart of Home Assistant, because the time it is due back is written down rather than left in a timer that dies with the process.

The other way round, holding one on for a while, is [Turn on for](#turn-on-for).

Turning the automation back on yourself cancels the snooze. Saying so is a clearer statement of what you want than a wake-up time set earlier, so Spook takes it that way and forgets the rest.

:::{seealso} Example actions in {term}`YAML`
:class: dropdown

Quiet the doorbell for an hour:

```{code-block} yaml
:linenos:
action: automation.snooze
target:
  entity_id: automation.doorbell_announce
data:
  duration: "01:00:00"
```

Everything in the bedroom, until the morning:

```{code-block} yaml
:linenos:
action: automation.snooze
target:
  area_id: bedroom
data:
  duration: "08:00:00"
```

:::

:::{attention} Known limitations
:class: dropdown

- An automation that is already off is left alone, and Spook says so in the log. Waking it would turn on something you turned off, which is not what snoozing asks for.
- Snoozing one that is already asleep moves its wake-up time rather than starting a second one.
- The automation is off while it sleeps, so anything reading its state sees exactly that. There is no third state between on and off.
  :::

### Turn on for

Turns an automation on for a while, and turns it back off when the time is up.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Automation: Turn on for 👻
* - {term}`Action name`
  - `automation.turn_on_for`
* - {term}`Action targets`
  - Yes, `automation` entities
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=automation.turn_on_for)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=automation.turn_on_for)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `duration`
  - {term}`string <string>`
  - Yes
  - `01:00:00`
```

The other way round from [Snooze](#snooze), and the same trap in reverse: an automation turned on stays on, so "just for tonight" needs somebody to remember. Guest mode you switch on in December and find again in March, holiday lighting that outlives the holiday, a debug automation left running.

This is that, in one action, and it survives a restart of Home Assistant for the same reason: the time it is due back off is written down rather than left in a timer that dies with the process.

Turning the automation off yourself cancels the run, the same way turning one on cancels a snooze.

:::{seealso} Example actions in {term}`YAML`
:class: dropdown

Guest mode, for the weekend:

```{code-block} yaml
:linenos:
action: automation.turn_on_for
target:
  entity_id: automation.guest_mode
data:
  duration: "48:00:00"
```

The party lighting, until the party is over:

```{code-block} yaml
:linenos:
action: automation.turn_on_for
target:
  entity_id: automation.disco_floor
data:
  duration: "04:00:00"
```

:::

:::{attention} Known limitations
:class: dropdown

- An automation that is already on is left alone, and Spook says so in the log. Turning it off later would switch off something you switched on, which is not what this asks for.
- Asking again for one already running moves the time it goes off rather than starting a second one.
- The automation is on while it runs, so anything reading its state sees exactly that. There is no third state between on and off.
  :::

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

### Unknown referenced areas

Automations are inspected for the use of areas. If an automation is targeting an area in one of its actions that do not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the automation and the area that is referenced but not found.

```{figure} ../images/integrations/automation/unknown_areas.png
:name: Spook found an issue with an automation that is using a non-existing area.
:alt: Screenshot showing a repair raised by Spook for an automation.
:align: center

Spook found an issue with an automation that is using a non-existing area.
```

To resolve the raised issue, you can either remove the reference to the non-existing area or fix the referenced area. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced devices

Automations are inspected for the use of devices. If an automation is using a device that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the automation and the device that is referenced but not found.

```{figure} ../images/integrations/automation/unknown_device.png
:name: Spook found an issue with an automation that is using a non-existing device.
:alt: Screenshot showing a repair raised by Spook for an automation.
:align: center

Spook found an issue with an automation that is using a non-existing device.
```

To resolve the raised issue, you can either remove the reference to the non-existing device or fix the referenced device. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced entities

Automations are inspected for the use of {term}`entities <entity>`. If an automation is using an {term}`entity ID <entity id>` that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the automation and the entity ID that is referenced but not found.

```{figure} ../images/integrations/automation/example.png
:name: Spook found an issue with an automation that is using a non-existing entity.
:alt: Screenshot showing a repair raised by Spook for an automation.
:align: center

Spook found an issue with an automation that is using non-existing entities.
```

To resolve the raised issue, you can either remove the reference to the non-existing entity ID or fix the referenced entity ID. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced actions

Automations are inspected for the use of actions. If an automation is using a action that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the automation and the action that is referenced but not found.

To resolve the raised issue, you can either remove the reference to the non-existing actions. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced floors

Automations are inspected for the use of {term}`floors <floor>`. If an automation is targeting a floor in one of its actions that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the automation and the floor that is referenced but not found.

To resolve the raised issue, you can either remove the reference to the non-existing floor or fix the referenced floor. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced labels

Automations are inspected for the use of {term}`labels <label>`. If an automation is targeting a label that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the automation and the label that is referenced but not found.

To resolve the raised issue, you can either remove the reference to the non-existing label or fix the referenced label. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced conditions

Automations are inspected for the conditions they use. Conditions are provided by {term}`integrations <integration>`, so a condition that no installed integration can provide cannot be evaluated. An automation like that fails validation outright and becomes unavailable, which is why Spook deliberately inspects unavailable automations: they are the broken ones.

Home Assistant does notice, but it raises a generic issue about the automation. Spook names the exact conditions, which is the part you need in order to fix it.

This usually means the integration that provided the condition was removed. To resolve the raised issue, you can either remove the use of these conditions or restore the integration that provides them. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced triggers

Automations are inspected for the triggers they use. Like conditions, triggers come from integrations, and if no installed integration can provide a trigger, the whole automation goes down with it: it fails validation and becomes unavailable.

So this is not a silent failure, it is a nameless one. Home Assistant raises a generic issue about the automation without saying which trigger caused it. Spook names the trigger.

To resolve the raised issue, you can either remove the use of these triggers or restore the integration that provides them. Spook will automatically remove the repair issue once the issue is fixed.

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
