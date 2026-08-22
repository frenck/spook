---
subject: Features
title: Conditions
subtitle: Asking the questions Home Assistant does not.
description: Spook provides new conditions for your automations and scripts, for the questions that otherwise need a template. Whether a person started this run, whether it has run recently, and the occasional coin flip.
date: 2026-08-22T09:15:00+02:00
---

Conditions decide whether an automation carries on. {term}`Home Assistant` provides plenty of them, and the ones it does not provide you write as a template, which works and is a bit miserable to read six months later.

Spook adds conditions for a handful of those questions. They work anywhere a condition works: as an automation's own condition, in an `if` or a `choose` inside its actions, and in scripts.

(triggered-by-a-user)=

## Triggered by a user

Passes when a person set this run going. Somebody pressing a button in the interface, tapping something in the app, or calling an action from the API all carry the user account they were made by. A schedule, a state change, or another automation does not.

`automation.triggered_by_user`

```{list-table}
:header-rows: 2
* - Condition options
* - Option
  - Type
  - Required
  - Default / Example
* - `person`
  - {term}`list of strings <list>`
  - No
  - `person.frenck`
```

Leave `person` out to pass for anybody. Name one or more people to narrow it, and Spook matches against the user account each person is linked to.

:::{seealso} Example {term}`condition <condition>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
condition: automation.triggered_by_user
```

To only pass when specific people did it:

```{code-block} yaml
:linenos:
condition: automation.triggered_by_user
options:
  person:
    - person.frenck
    - person.joe
```

:::

:::{attention} Worth knowing
:class: dropdown

- **A person needs a user account linked to them.** People are set up on the People page, and linking an account is optional there. A person without one has nothing to match against, so naming them means this condition can never pass.
- **Where the user comes from depends on the trigger.** An automation does not inherit the context of whatever set it off, so Spook reads the user out of the trigger. A state trigger and an event trigger both carry it. A time trigger, a sun trigger, or a template trigger cannot: nobody was behind them, which is the right answer rather than a limitation.
- **A long-lived access token counts as the person who made it.** An API call authenticated with a token looks exactly like that user, because that is what it is.
  :::

## Not triggered by a user

The other half of the same question: passes when nobody set this run going. A schedule, a state change, or another automation started it rather than a person.

`automation.not_triggered_by_user`

This one takes no options. "Nobody started this" is a different question from "not this particular person", and answering both from one condition gives you a condition nobody can read. To exclude specific people, use [](#triggered-by-a-user) instead.

:::{seealso} Example {term}`condition <condition>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
condition: automation.not_triggered_by_user
```

:::

## Cooldown

Passes when this automation or script has not run within the given time, or has never run at all. A built-in cooldown, so an automation does not re-fire more often than you want it to.

`spook.cooldown`

```{list-table}
:header-rows: 2
* - Condition options
* - Option
  - Type
  - Required
  - Default / Example
* - `duration`
  - duration
  - Yes
  - `00:05:00`
```

This replaces the most copy-pasted template condition there is:

```{code-block} jinja
{{ now() - this.attributes.last_triggered > timedelta(minutes=5) }}
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

:::{attention} Worth knowing
:class: dropdown

It asks about the automation or script the condition is written in, not about anything it calls. An automation that has never run passes, because there is no last run to be too close to.
:::

## Chance

Passes a set percentage of the time, chosen at random on every check. For when you want a bit of variation rather than the same thing every evening.

`spook.chance`

```{list-table}
:header-rows: 2
* - Condition options
* - Option
  - Type
  - Required
  - Default / Example
* - `percentage`
  - {term}`float <float>`
  - Yes
  - `20`
```

:::{seealso} Example {term}`condition <condition>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
condition: spook.chance
options:
  percentage: 20
```

:::

## Use cases

Some use cases for the conditions Spook provides:

- Letting an automation behave differently when you asked for it than when the house decided by itself. Turning the lights off automatically at midnight is fine; turning them off two seconds after somebody deliberately turned them on is not.
- Ignoring your own changes. An automation that reacts to a thermostat being adjusted usually wants to react to the cat, the schedule, or the weather, and not to you standing in front of it.
- Keeping a chatty automation quiet. A door sensor that flaps gets one notification instead of eleven.
- Making the evening lights pick a scene at random, so the house feels less like a timer.

## Feature requests, ideas, and support

If you have an idea for a condition Spook should provide, feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these? Or maybe you've run into a bug? Please check the [](support) page on where to go for help.
