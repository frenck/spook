---
subject: Features
title: Other features
subtitle: Home of the useless but fun. 🤡
date: 2023-08-09T21:29:00+02:00
---

These are some Spook-specific features that don't fit in any of the other categories.
They are not particularly useful, but they are fun to play with (and maybe you actually have a use case for them).

They originally served as the proof of concept for Spook and left them in for the fun of it.

## Actions

Spook offers the following useless actions:

### Boo!

This acti will just always scare Home Assistant, causing this action call to fail. Calling this action in any of your automations will thus cause your automation to stop and error.

```{figure} ./images/spook/boo.png
:alt: Screenshot of the Spook Boo! action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Boo! 👻
* - {term}`Action name`
  - `spook.boo`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.boo)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.boo)
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

This action has no parameters, so you can just call it like this:

```{code-block} yaml
:linenos:
action: homeassistant.boo
```

:::

### Random fail

This action call will randomly fail (and thus randomly stop your automation or script).

```{figure} ./images/spook/random_fail.png
:alt: Screenshot of the Spook random fail action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Random fail 👻
* - {term}`Action name`
  - `spook.random_fail`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.random_fail)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.random_fail)
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

This action has no parameters, so you can just call it like this:

```{code-block} yaml
:linenos:
action: homeassistant.random_fail
```

:::

## Triggers

Spook offers the following triggers that are not tied to a specific integration:

### Cron schedule

Fires on a crontab schedule.

```{list-table}
:header-rows: 1
* - Trigger properties
* - Trigger
  - Cron schedule 👻
* - Trigger name
  - `spook.cron`
* - {term}`Spook's influence <influence of spook>`
  - Newly added trigger
```

```{list-table}
:header-rows: 2
* - Trigger options
* - Attribute
  - Type
  - Required
  - Default / Example
* - `schedule`
  - {term}`string <string>`
  - Yes
  - `0 7 * * 1-5`
```

Home Assistant's own time triggers cover a time of day and a time pattern. Between them they cannot say "every weekday at seven" or "the last Friday of the month". A crontab expression says either in one line, and anybody who has written a crontab already knows the syntax.

Five fields, in the usual order: minute, hour, day of month, month, day of week. Ranges and steps work, and so do the day-of-week extensions, so `MON#2` is the second Monday of the month and `5L` the last Friday.

When it fires, `trigger.schedule` holds the expression and `trigger.now` the local time it fired at.

One crontab rule catches people out, and it is not ours. Give both a day of the month and a day of the week, and cron combines them with "or", not "and". So `0 7 15 * 1` runs at seven on the 15th of the month, and at seven every Monday as well. Leave one of the two as `*` if you only mean the other.

That "or" holds only while both fields are plain lists of days. Let either one start with a `*`, a step like `*/2` included, and the two combine with "and" instead: `0 7 15 * */2` is the 15th, but only when it falls on a Sunday, Tuesday, Thursday or Saturday.

:::{seealso} Example trigger in {term}`YAML`
:class: dropdown

Every weekday at seven in the morning:

```{code-block} yaml
:linenos:
trigger: spook.cron
options:
  schedule: "0 7 * * 1-5"
```

The last Friday of the month, at three in the afternoon:

```{code-block} yaml
:linenos:
trigger: spook.cron
options:
  schedule: "0 15 * * 5L"
```

:::

:::{attention} Known limitations
:class: dropdown

- Nicknames are not supported. `@daily`, `@hourly` and friends are refused: write the five fields out. The automation will not load and will say what is wrong with the expression, which is better than finding out at the hour it was supposed to run.
- Seconds are not a field. Five fields, no more: some cron implementations take a sixth field for seconds, and that form is refused here. The shortest interval is one minute.
- A schedule that can never come round is refused. The 30th of February (`0 0 30 2 *`) is the obvious one. So is `0 0 */20 * 1L`: the `*` makes it an "and", and no 1st or 21st of a month is ever also the last Monday. Neither loads, rather than loading and then waiting forever.
- Schedules follow your Home Assistant time zone, including daylight saving.

:::

### Entity fell silent

Fires when nothing has written to an entity for a while.

```{list-table}
:header-rows: 1
* - Trigger properties
* - Trigger
  - Entity fell silent 👻
* - Trigger name
  - `spook.stale`
* - Targets
  - {term}`Entities <entity>`, {term}`devices <device>`, {term}`areas <area>`, floors and labels
* - {term}`Spook's influence <influence of spook>`
  - Newly added trigger
```

```{list-table}
:header-rows: 2
* - Trigger options
* - Attribute
  - Type
  - Required
  - Default / Example
* - `for`
  - {term}`string <string>`
  - Yes
  - `01:00:00`
```

Home Assistant will tell you an entity went unavailable. Plenty of things die without ever saying so: an integration that quietly stopped polling, a battery device that dropped off the network, an MQTT topic nobody publishes to any more. The state sits there looking perfectly healthy, holding a reading from last Tuesday.

This watches for silence rather than for a value. A sensor that keeps reporting the same 21.5 every minute is alive and is left alone; one that stops reporting altogether fires after the duration you set. Point it at whole areas, floors or labels and the entities underneath are watched one at a time, each firing separately when it falls silent.

When it fires, `trigger.entity_id` names the entity that went quiet, `trigger.last_reported` is when it last spoke, and `trigger.for` is the duration you configured.

:::{seealso} Example trigger in {term}`YAML`
:class: dropdown

Any sensor in the attic that has said nothing for an hour:

```{code-block} yaml
:linenos:
trigger: spook.stale
target:
  area_id: attic
options:
  for: "01:00:00"
```

One specific sensor, with a shorter fuse:

```{code-block} yaml
:linenos:
trigger: spook.stale
target:
  entity_id: sensor.greenhouse_temperature
options:
  for: "00:15:00"
```

:::

:::{attention} Known limitations
:class: dropdown

- Entities that were already silent when the trigger started watching are left alone. Only silence that falls while the automation is loaded counts. Without that, reloading your automations would replay everything that has gone quiet since, which is noise rather than news.
- A duration of zero is refused. It would put the deadline on the moment the entity last spoke, which is always in the past, so the trigger would load and then do nothing at all.
- A target that names nothing is refused for the same reason. An empty target is valid as far as the fields go, and would sit there watching no entities at all.
- Repeating the same value counts as speaking. If you want to know about a sensor whose reading has not moved, that is a different question, and this trigger does not answer it.
- Expanding a device, area or floor covers its primary entities. Configuration and diagnostic entities are left out, the same as every other Home Assistant trigger that takes a target. Name one as an entity and it is always watched, whichever category it is in: `entity_id: sensor.back_door_battery` works even though the area it sits in would skip it.
- An entity with no state yet has nothing to be silent about, so it is skipped until it reports for the first time.

:::

### Integration failed to set up

Fires when a configuration entry has been unable to set itself up for a while.

```{list-table}
:header-rows: 1
* - Trigger properties
* - Trigger
  - Integration failed to set up 👻
* - Trigger name
  - `spook.integration_failed`
* - {term}`Spook's influence <influence of spook>`
  - Newly added trigger
```

```{list-table}
:header-rows: 2
* - Trigger options
* - Attribute
  - Type
  - Required
  - Default / Example
* - `for`
  - {term}`string <string>`
  - Yes
  - `00:15:00`
* - `entry_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - No
  - Every configuration entry
```

An integration that cannot reach its hardware fails to set up, and Home Assistant keeps retrying it on a backoff that tops out at ten minutes. A device switched off overnight therefore fails dozens of times before morning, which is why this trigger waits rather than firing on each attempt. Set `for` to how long you are willing to let something be broken before you want to hear about it, and the ordinary hiccups at start-up sort themselves out well inside it.

Every configuration entry is watched unless you name some in `entry_id`. Each one is reported on its own, and only once per spell of trouble: an entry has to come back before it can be reported again.

When it fires, `trigger.domain` is the integration, `trigger.title` the name of the entry, `trigger.entry_id` its identifier, `trigger.state` the state it is stuck in, `trigger.reason` whatever Home Assistant recorded about why, and `trigger.for` the duration you configured.

:::{seealso} Example trigger in {term}`YAML`
:class: dropdown

Anything at all that has been broken for a quarter of an hour:

```{code-block} yaml
:linenos:
trigger: spook.integration_failed
options:
  for: "00:15:00"
```

One entry you care about more than the rest, with a shorter fuse:

```{code-block} yaml
:linenos:
trigger: spook.integration_failed
options:
  for: "00:05:00"
  entry_id: 01JQ8XW3M4YPKZ7N2VRTGH6BDC
```

:::

:::{attention} Known limitations
:class: dropdown

- The states that count as failure are `setup_error`, `setup_retry`, `migration_error` and `failed_unload`. An entry you disabled yourself sits in `not_loaded` and is not a failure.
- A duration of zero is refused. A deadline of now fires straight away, so zero would report every failure the moment it happened, which is the flapping this trigger exists to sit out.
- Reloading your automations starts the clock again for anything broken at that moment. That is on purpose: an entry stuck in `setup_error` never announces itself a second time, so waiting for a change would mean never hearing about whatever was already broken.
- One report per spell of trouble. If you want to be nagged until somebody fixes it, repeat the action yourself.

:::

## Conditions

Spook offers the following conditions that are not tied to a specific integration:

(triggered-by-a-user)=

### Triggered by a user

Passes when a person set this run going.

```{list-table}
:header-rows: 1
* - Condition properties
* - {term}`Condition`
  - Triggered by a user 👻
* - Condition name
  - `spook.triggered_by_user`
* - {term}`Spook's influence <influence of spook>`
  - Newly added condition
```

```{list-table}
:header-rows: 2
* - Condition options
* - Attribute
  - Type
  - Required
  - Default / Example
* - `person`
  - {term}`list of strings <list>`
  - No
  - Defaults to any user
```

What this can see is the person behind the trigger. Somebody flipping a switch, tapping something in the app, or calling an action from the API leaves their user account on the state change or event that follows, so an automation reacting to it finds them. A template trigger inherits it too, when the change that made the template true was theirs. A schedule, the sun, or an integration acting on its own leaves nobody.

If the `person` attribute is not provided, the condition passes for anybody. Name one or more people to narrow it, and Spook matches against the user account each of them is linked to.

:::{seealso} Example {term}`condition <condition>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
condition: spook.triggered_by_user
```

To only pass when specific people did it:

```{code-block} yaml
:linenos:
condition: spook.triggered_by_user
options:
  person:
    - person.frenck
    - person.joe
```

:::

:::{attention} Known limitations
:class: dropdown

- A person needs a user account linked to them. Linking one is optional on the People page, and a person without one has nothing to match against, so naming them means this condition can never pass.
- **Forcing a run is not attributed to anybody.** Home Assistant hands the caller's account to the automation, but the run itself starts a fresh context carrying only a pointer to the caller's, and nothing resolves that pointer back, so there is nobody for this condition to find.
- **And pressing "Run actions" skips your conditions anyway.** `automation.trigger` defaults to `skip_condition: true`, so the conditions between the trigger and the actions are not evaluated at all and the actions simply run. That is Home Assistant's behaviour for every condition, not something particular to these two. If you want a forced run to be recognised as nobody's doing, the condition has to sit inside the actions, in an `if` or a `choose`, where it is evaluated.
- Where the user comes from depends on the trigger. A state trigger, an event trigger and a template trigger all carry it, as long as a person caused the change behind them. A time trigger or a sun trigger cannot, because there is no change to inherit from and nobody was behind it.
- A long-lived access token counts as the person who created it. An API call authenticated with one looks exactly like that user.
  :::

### Not triggered by a user

Passes when nobody set this run going.

```{list-table}
:header-rows: 1
* - Condition properties
* - {term}`Condition`
  - Not triggered by a user 👻
* - Condition name
  - `spook.not_triggered_by_user`
* - {term}`Spook's influence <influence of spook>`
  - Newly added condition
```

This condition has no options. It passes for anything Spook cannot pin on a person: a schedule, the sun, an integration acting on its own, or a run forced with the Run button.

"Nobody started this" is a different question from "not this particular person", which is why this condition takes no options. To exclude specific people, wrap [](#triggered-by-a-user) in Home Assistant's own **Not** condition:

```{code-block} yaml
:linenos:
condition: not
conditions:
  - condition: spook.triggered_by_user
    options:
      person: person.frenck
```

That passes for anybody who is not Frenck, and also when nobody was behind it at all, which is what "not Frenck" means.

:::{seealso} Example {term}`condition <condition>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
condition: spook.not_triggered_by_user
```

:::

### Cooldown

Passes when this automation or script has not run within a given time.

```{list-table}
:header-rows: 1
* - Condition properties
* - {term}`Condition`
  - Cooldown 👻
* - Condition name
  - `spook.cooldown`
* - {term}`Spook's influence <influence of spook>`
  - Newly added condition
```

```{list-table}
:header-rows: 2
* - Condition options
* - Attribute
  - Type
  - Required
  - Default / Example
* - `duration`
  - duration
  - Yes
  - `00:05:00`
```

A built-in cooldown, so an automation does not re-fire more often than you want it to. An automation that has never run passes, because there is no last run to be too close to.

It replaces the most copy-pasted template condition there is:

```{code-block} jinja
{{ now() - this.attributes.last_triggered >= timedelta(minutes=5) }}
```

:::{seealso} Example {term}`condition <condition>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
condition: spook.cooldown
options:
  duration: "00:05:00"
```

:::

### Chance

Passes a set percentage of the time, chosen at random on every check.

```{list-table}
:header-rows: 1
* - Condition properties
* - {term}`Condition`
  - Chance 👻
* - Condition name
  - `spook.chance`
* - {term}`Spook's influence <influence of spook>`
  - Newly added condition
```

```{list-table}
:header-rows: 2
* - Condition options
* - Attribute
  - Type
  - Required
  - Default / Example
* - `percentage`
  - {term}`float <float>`
  - Yes
  - `20`
```

For when you want a bit of variation rather than the same thing every evening.

:::{seealso} Example {term}`condition <condition>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
condition: spook.chance
options:
  percentage: 20
```

:::

### Triggered by an automation

Passes when another automation set this run going.

```{list-table}
:header-rows: 1
* - Condition properties
* - {term}`Condition`
  - Triggered by an automation 👻
* - Condition name
  - `spook.triggered_by_automation`
* - {term}`Spook's influence <influence of spook>`
  - Newly added condition
```

```{list-table}
:header-rows: 2
* - Condition options
* - Attribute
  - Type
  - Required
  - Default / Example
* - `automation`
  - {term}`list of strings <list>`
  - No
  - Defaults to any automation
```

Home Assistant gives every automation run its own context, and everything that run writes carries it along. So an automation reacting to a change another automation made can find out who did it, and it keeps working when there is a script in between, because the script runs under the automation's context rather than making one of its own.

What Home Assistant does not do is turn a context back into the automation it belongs to, so Spook listens for automations announcing themselves and remembers the mapping for the last few hundred runs. That is far more than enough: the run being asked about happened a fraction of a second earlier.

If the `automation` attribute is not provided, the condition passes for any automation. Name one or more to narrow it.

:::{seealso} Example {term}`condition <condition>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
condition: spook.triggered_by_automation
```

To only pass when specific automations did it:

```{code-block} yaml
:linenos:
condition: spook.triggered_by_automation
options:
  automation:
    - automation.goodnight
    - automation.leaving_home
```

:::

:::{attention} Known limitations
:class: dropdown

- Only automations are recognised. A script running on its own, without an automation having started it, is not an automation and this does not pass for it.
- Spook has to have been running when the other automation ran. It remembers the mapping while your automations are loaded, so a run from before a restart is no longer known.
- It names the automation that started the chain, not the last thing in it. If your goodnight automation calls a script and that script turns off the lights, this reports the automation, which is almost always what you wanted to ask about.
- Only the last few hundred automation runs are remembered. Not a practical limit for a condition being checked right after the run it is asking about, but it is a limit.

:::
