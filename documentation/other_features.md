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

One crontab rule catches people out, and it is not ours. Give both a day of the month and a day of the week, and cron combines them with "or", not "and". So `0 7 15 * 1` runs at seven on the 15th of the month, and at seven every Monday as well. Leave one of the two as `*` if you only mean the other. The exception is a day of the month starting with `*`, such as `*/20`, which does combine with "and".

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
