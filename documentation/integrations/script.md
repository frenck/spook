---
subject: Enhanced integrations
title: Scripts
subtitle: Script kiddies. 🍼
thumbnail: ../images/integrations/script/example.png
description: Spook enhances the script integrations of Home Assistant by raising repairs issues, in case it detects something is wrong with a script, for example, if it is using non-existing entities.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/script/logo.png
:alt: The Home Assistant script icon.
:width: 250px
:align: center
```

<br><br>

A script in {term}`Home Assistant` is a sequence of actions that are executed when the script is started or called via start using a {term}`action <performing actions>`. Scripts are similar to {term}`automations <automation>`, but are not automatically executed when a trigger fires. Scripts are a great way to group a sequence of actions together that can be executed on demand and reused in multiple automations.

Non-working scripts, however, are (just like automations) a source of frustration. And sometimes, it can take you a bit to notice there is an issue with a script. Spook enhances the script integration of Home Assistant by raising repair issues in case it detects something is wrong with a script.

```{figure} ../images/integrations/script/example.png
:name: example
:alt: Screenshot showing a repair raised by Spook for a script.
:align: center

Spook found an issue with a script that is using non-existing entities.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

While Spook is floating around in your Home Assistant instance, it will raise repairs issues if it has found something that is not right.

An entity, device, area, floor or label that only disabled steps (`enabled: false`) name is left alone. A disabled step does nothing, and is usually parked on purpose. Anything a running step names as well is still reported.

### Unknown referenced areas

Scripts are inspected for the use of areas. If a script is targeting an area in one of its actions that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the area that is referenced but not found.

```{figure} ../images/integrations/script/unknown_area.png
:name: Spook found an issue with a script that is using a non-existing area.
:alt: Screenshot showing a repair raised by Spook for a script.
:align: center

Spook found an issue with a script that is using a non-existing area.
```

To resolve the raised issue, you can either remove the reference to the non-existing area or fix the referenced area. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced attributes

Scripts are inspected for the attributes they use: the `attribute` of state and numeric state triggers and conditions, the attribute Spook's own state trigger follows, and attributes named in templates, like `state_attr('light.kitchen', 'brightness')`. If a script uses an attribute its entity does not have, Spook will raise a repair issue. The repairs issue raised will contain the name of the script, the attribute, the entity, and what was most likely meant when Spook is near certain of it.

A trigger waiting on an attribute that never shows up loads fine and never fires, and nothing tells you. That is the ghost this catches.

Many attributes only show up some of the time: a media player that is off drops most of its own, and integrations add their own that come and go. So an attribute is only reported when Spook cannot find it anywhere: not on the entity right now, not as something that kind of entity offers in Home Assistant, and not in anything the recorder remembers the entity having. An entity the recorder does not record is only checked for attributes that differ from a real one in upper and lower case alone, like `Brightness`. An attribute or entity that is only worked out while running, from a variable for example, is not checked. Neither is a template using `states` or `state_attr` when the script gives that name a meaning of its own, as a variable, a field or a response variable.

Spook does not look right after Home Assistant starts, when the recorder is busy, but ten minutes later. After that it looks again once a reload of scripts is done, when a script is added or removed, when the entity registry changes, when an integration loads or its configuration changes, and once a day. An attribute that newly shows up on an entity is picked up the next time it looks.

To resolve the raised issue, edit the script and use an attribute the entity has. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced states

Scripts are inspected for the states they wait for and check: the `to`, `from`, `not_to` and `not_from` of state triggers, the `state` of state conditions, the same options of Spook's own state trigger, and in templates `is_state('light.kitchen', 'on')` and a state compared to text, like `states('light.kitchen') == 'on'`, `states.light.kitchen.state != 'off'` or `states('light.kitchen') in ['on', 'off']`. If a script uses a state its entity is never in, like `On` for a light that is `on` or `off`, Spook will raise a repair issue. The repairs issue raised will contain the name of the script, the state, the entity, and what was most likely meant when Spook is near certain of it.

A trigger waiting for a state that never comes loads fine and never fires, and nothing tells you. That is the ghost this catches.

Only entities whose states are a fixed set are checked: the ones Home Assistant itself lists for that kind of entity (a light, a cover, a lock, an alarm panel, a media player, and so on), or the options the entity offers right now, like a select, a dropdown helper, or a sensor with a fixed list of values. A plain sensor, a number or a text can be anything, so those are not checked, and neither are persons and device trackers, whose states are zone names. Everything the entity was in counts as well: right now, and anything the recorder remembers. An entity whose state is set from outside of its integration, by a REST call or a Python script for example, is not checked either.

For some kinds of entity, Home Assistant itself makes sure the state is one of the set: lights, switches, binary sensors, covers, locks, valves, climate entities, and the like. There, a state that differs from a real one in upper and lower case alone, like `On`, is always reported, and anything else outside of the set when Spook has the whole history of the entity from the recorder. For the rest, the set is what is usual rather than all that is possible: a media player made from a template can be in any state it likes, and a select, a dropdown helper or a sensor with a fixed list of values can get new options while running. Those only get a state reported that differs from a real one in case alone, and only when Spook has the whole history of the entity. The same goes for an entity that works out its state in a way of its own.

With an `attribute`, a state trigger or condition waits for a value of that attribute instead, and those are checked too, in the same issue: like `Heating` for the `hvac_action` of a thermostat, which is `heating`. Only attributes whose values are a fixed set: the ones Home Assistant itself lists for that kind of entity (the action of a thermostat or a humidifier, the device class of a sensor, the repeat mode of a media player, and the like), or whose values the entity offers in another attribute, like the fan modes, preset modes and swing modes of a thermostat, the effects of a light, or the sources of a media player. Home Assistant writes whatever the integration hands it for any of these, so only a value that differs from a real one in how it is written is reported, and only when Spook has the whole history of the entity. That is upper and lower case, or YAML reading what was meant as text as something else: an unquoted `off` is the boolean false, and `2` is a number, while the attribute holds the text `"off"` or `"2"`. Such a value is shown the way YAML read it, with the text that was meant in quotes. Spook's own state trigger is checked the same way when it follows an attribute, with one difference: it makes text of whatever the attribute holds and compares that with the text of its `to`, `from`, `not_to` and `not_from`. So there, only upper and lower case is a slip, like `Heating` for `heating`. An attribute the entity never had is not looked at here: that is an unknown attribute, which the script gets an issue of its own for.

A state or entity that is only worked out while running, from a variable or a template for example, is not checked. In templates, only a comparison with nothing else taking part in it is read: once a filter like `| lower`, a `~` or anything like it is in between, what is compared is no longer the state itself. A template is not read for `states`, `is_state` or `state_attr` either when the script gives that name a meaning of its own, as a variable, a field or a response variable.

Spook looks at the same moments as for unknown attributes: ten minutes after Home Assistant starts, after that again once a reload of scripts is done, when a script is added or removed, when the entity registry changes, when an integration loads or its configuration changes, and once a day.

To resolve the raised issue, edit the script and use a state the entity can be in. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced devices

Scripts are inspected for the use of devices. If a script is using a device that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the device that is referenced but not found.

As with automations, only values shaped like a device ID are considered: thirty-two hexadecimal characters, which is what Home Assistant hands out. An integration taking a `device_id` that means its own hardware, such as RFLink's protocol address, is left alone.

```{figure} ../images/integrations/script/unknown_device.png
:name: Spook found an issue with a script that is using a non-existing device.
:alt: Screenshot showing a repair raised by Spook for a script.
:align: center

Spook found an issue with a script that is using a non-existing device.
```

To resolve the raised issue, you can either remove the reference to the non-existing device or fix the referenced device. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced integration entries

Scripts are inspected for the integration entries they hand their actions. Plenty of integrations have actions that ask which of their integration entries to use, like Nord Pool's prices or Mealie's recipes. If a script hands one an integration entry that does not exist, Spook will raise a repair issue. The same goes for an integration entry of another integration than the action asks for, which happens when a step is copied from an action of another integration. The repairs issue raised will contain the name of the script and the integration entries that go nowhere.

Home Assistant only refuses these when the step runs, so a script that runs once in a while fails exactly then. This usually happens after an integration was removed and added again: that gives it a new integration entry, with a new ID, and every action still holds the old one.

Spook only looks at the fields an action itself says take an integration entry, never at a field because of its name. Only actions that are there right now say what they take, so the actions of an integration that is not loaded are not checked. An integration entry that exists but is not loaded right now, because it is disabled or failed to set up, is not reported either: that is the state of the integration, not a mistake in the script. An integration entry worked out while running, from a template or a variable, is not checked, and neither is a disabled step.

To resolve the raised issue, edit the script and pick the integration entry again in these actions. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced entities

Scripts are inspected for the use of {term}`entities <entity>`. If a script uses an {term}`entity ID <entity id>` that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the entity ID that is referenced but not found.

```{figure} ../images/integrations/script/example.png
:name: Spook found an issue with a script that is using a non-existing entity.
:alt: Screenshot showing a repair raised by Spook for a script.
:align: center

Spook found an issue with a script that is using non-existing entities.
```

An entity spelled out after `states`, like `states.light.kitchen.state`, is not checked when that `states` is not Home Assistant's: when a template defines its own with a macro or `{% set %}`, or the script gives the name a meaning of its own, as a variable, a field or a response variable. Used as a filter, like `'light.kitchen' | states`, it still is Home Assistant's, and still checked. An entity ID in quotes is checked wherever it is, whatever it is handed to.

To resolve the raised issue, you can either remove the reference to the non-existing entity ID or fix the referenced entity ID. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced actions

Scripts are inspected for the use of actions. If a script is using an action that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the action that is referenced but not found.

Actions of an integration you disabled are not reported: switched off on purpose is not gone. Once you enable the integration again, they are checked as usual.

To resolve the raised issue, you can either remove the reference to the non-existing action or restore the integration that provides the action. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown icons

Scripts are inspected for their own icon, and for the icons their actions hand out. Only actions that say they take an icon are looked at, like `group.set`, and the actions of Spook that create areas, labels or helpers. An `mdi:` icon that is not in the Material Design Icons that come with Home Assistant is drawn as an empty spot, without a word. Spook raises a repair issue naming the script and the icons, and suggests the icon you most likely meant when it is nearly certain.

This usually happens with a typo, an icon that was renamed or removed, or one picked from the Material Design Icons website that is newer than the version Home Assistant comes with.

To resolve the raised issue, edit the script and replace these with icons that exist. Spook will automatically remove the repair issue once the issue is fixed.

:::{attention} Known limitations
:class: dropdown

- Only icons starting with `mdi:` are checked. The older `hass:` prefix, and icons from sets you added, like those from HACS, are left alone.
- An icon that is a template is not checked. What it ends up as cannot be known without running it.
- Actions that are turned off are not checked: they never run.
- The list of icons is read from the frontend Home Assistant has installed. A frontend run from a development build is not taken into account, and a frontend without that list means nothing is checked.
  :::

### Unknown referenced floors

Scripts are inspected for the use of {term}`floors <floor>`. If a script is targeting a floor in one of its actions that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the floor that is referenced but not found.

To resolve the raised issue, you can either remove the reference to the non-existing floor or fix the referenced floor. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced labels

Scripts are inspected for the use of {term}`labels <label>`. If a script is targeting a label that does not exist, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the label that is referenced but not found.

To resolve the raised issue, you can either remove the reference to the non-existing label or fix the referenced label. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced conditions

Scripts are inspected for the conditions they use. Conditions are provided by {term}`integrations <integration>`, so a condition that no installed integration can provide cannot be evaluated. A script like that fails validation outright and becomes unavailable, which is why Spook deliberately inspects unavailable scripts: they are the broken ones.

Home Assistant does notice, but it raises a generic issue about the script. Spook names the exact conditions, which is the part you need in order to fix it.

This usually means the integration that provided the condition was removed. To resolve the raised issue, you can either remove the use of these conditions or restore the integration that provides them. Spook will automatically remove the repair issue once the issue is fixed.

### Unknown referenced triggers

Scripts are inspected for the trigger configurations they contain, such as the ones a `wait_for_trigger` step waits on. If no installed integration can provide a trigger a script waits on, the whole script goes down with it: it fails validation and becomes unavailable.

Home Assistant raises a generic issue about the script without saying which trigger caused it. Spook names the trigger.

To resolve the raised issue, you can either remove the use of these triggers or restore the integration that provides them. Spook will automatically remove the repair issue once the issue is fixed.

### Templates that can never pass

Scripts are inspected for templates that, because of how they are written, can never render what Home Assistant needs for them to pass: the `value_template` of template conditions, shorthand template conditions (`condition: "{{ ... }}"`), `wait_template`, and template triggers in a `wait_for_trigger`. Anywhere in the sequence: in an `if`, a `choose`, the `while` or `until` of a `repeat`, a condition step, nested in `and`, `or` or `not`. If one can never pass, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the templates that can never pass.

A template condition passes only when it renders `true` (any case). A `wait_template` is checked like a condition first. After that it ends when its template renders again into something that reads as true, like `on`, `yes` or `1`. One without any Jinja, or made of fixed text alone, is never rendered again, so only `true` ends it. A template trigger fires when its template goes from something that does not read as true to something that does, so one that only ever renders `on` or `yes` never fires.

The shapes this catches are the same as for automations: quotes around the template in a `>-` block, no `{{ }}` at all, YAML pasted into the template field, a YAML `#` comment inside the Jinja, and a condition that can only render `on`, `off` or another fixed text. The [automation section](automation.md#templates-that-can-never-pass) explains each, and what is left alone.

Such a condition loads fine and never passes, a wait like that only ends on its timeout, and nothing tells you. Only the text of the template is read. Anything that depends on a state, a variable or the moment it runs is never judged. A script that failed to load is left alone: Home Assistant reports that one itself. Spook looks again whenever scripts are reloaded, which saving one in the editor does.

To resolve the raised issue, edit the script and make the template render `true` when it should pass. Spook will automatically remove the repair issue once the issue is fixed.

### Removed users

Scripts are inspected for the users they name by their ID, the same way [automations are](automation.md#removed-users): in templates, the ID of a user compared to text, like `context.user_id == '…'` for the user who started the script, or `state_attr('person.frenck', 'user_id') == '…'`, and the `user_id` an event trigger in a `wait_for_trigger` waits for in its `context`. If a script names a user that no longer exists, Spook will raise a repair issue. The repairs issue raised will contain the name of the script and the user IDs it cannot find.

Home Assistant gives every user a random ID and never hands the same one out twice, so an ID no user has belongs to a user that was removed. A template comparing with that ID never matches, and Home Assistant does not tell you.

What is not checked is the same as for automations. A script that gives `context` a meaning of its own, as a variable or a field, is not read either.

To resolve the raised issue, edit the script and use the ID of a user that exists, or remove the check. Spook will automatically remove the repair issue once the issue is fixed.

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
