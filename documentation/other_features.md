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

### Wait for a condition

Waits until a condition is true, and carries on straight away if it already is.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Wait for a condition 👻
* - {term}`Action name`
  - `spook.wait_for_condition`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - Optional response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.wait_for_condition)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.wait_for_condition)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `condition`
  - {term}`condition <condition>`
  - Yes
  - Any condition, built the ordinary way
* - `timeout`
  - {term}`string <string>`
  - No
  - Waits indefinitely when left out
```

Home Assistant can wait for a template to turn true, and it can wait for a trigger. It cannot wait for a condition, so anything you can express with the condition building blocks has to be rewritten as a template before you can wait on it.

Takes one condition or a list of them, and a list means all of them, the same as anywhere else. Which is also what the visual editor sends, so both shapes have to work.

The other half of what this fixes is that it looks first. `wait_for_trigger` always waits for something to happen, so if the thing you are waiting for has already happened you wait forever, which is why people wrap it in an `if`. This checks the condition before waiting, so an automation that arrives late still carries on.

Returns `completed` when it is given a `response_variable`, which says whether the condition arrived or the timeout did.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

Hold the sequence until the back door is shut:

```{code-block} yaml
:linenos:
action: spook.wait_for_condition
data:
  condition:
    condition: state
    entity_id: binary_sensor.back_door
    state: "off"
```

Give up after five minutes, and do something else about it:

```{code-block} yaml
:linenos:
- action: spook.wait_for_condition
  data:
    timeout: "00:05:00"
    condition:
      condition: state
      entity_id: binary_sensor.back_door
      state: "off"
  response_variable: waited
- if: "{{ not waited.completed }}"
  then:
    - action: notify.persistent_notification
      data:
        message: The back door is still open.
```

:::

:::{attention} Known limitations
:class: dropdown

- A template has to still be a template, which rules out the placement you would normally use. A script or automation renders every template in the action data before calling the action, so `{{ is_state(...) }}` arrives as the `true` or `false` it happened to be at that moment, and a constant can never turn; that is refused rather than quietly waited on forever. What can be seen from here is whether any Jinja is left, not where the value came from, so a literal `value_template: true` in a direct call is refused too: by the time it arrives the two are the same thing. A template that still has its Jinja, from the API or the developer tools, is watched like any other condition. Inside a script, wait on a template with `wait_template`, which is what that is for.
- A condition that asks about the run it is in cannot be watched either, and is refused for the same reason: `trigger`, and Spook's own `cooldown`, `quota`, `triggered_by_user`, `not_triggered_by_user` and `triggered_by_automation`. An action call is not a trigger, so their answer would not mean anything.
- The condition is checked again every 30 seconds regardless of anything happening, so the wait can end up to half a minute late. That polling pass is what covers the turns that arrive without a state change: a plain time or sun condition, a `state` condition whose `for:` runs out, a `time` condition whose moment passes. A condition that turns true and false again inside those 30 seconds is missed entirely.
- Without a `timeout` it waits for as long as the script runs. Stopping the automation or script stops the wait with it. A `timeout` of zero means look now and do not wait, so it answers `completed: false` unless the condition is already true.

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

### Repair issue created

Fires when a new repair issue turns up.

```{list-table}
:header-rows: 1
* - Trigger properties
* - Trigger
  - Repair issue created 👻
* - Trigger name
  - `spook.repair_issue_created`
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
* - `domain`
  - {term}`string <string>` | {term}`list of strings <list>`
  - No
  - Defaults to every integration
* - `severity`
  - {term}`string <string>` | {term}`list of strings <list>`
  - No
  - `critical`, `error`, `warning`
```

Home Assistant collects repair issues on the repairs page and waits to be visited. This is for the ones you would rather hear about: an integration reporting it needs attention, or Spook finding a reference to something that no longer exists.

Only genuinely new issues fire it. An integration re-reporting an issue that is already there counts as an update rather than a creation, which is what keeps a repair checked on a schedule from firing on every pass.

When it fires, `trigger.domain` is the integration that reported it, `trigger.issue_id` names the issue, and `trigger.severity`, `trigger.is_fixable`, `trigger.breaks_in_ha_version`, `trigger.learn_more_url` and `trigger.translation_key` carry the rest of what the registry knows.

:::{seealso} Example trigger in {term}`YAML`
:class: dropdown

Anything at all, as soon as it turns up:

```{code-block} yaml
:linenos:
trigger: spook.repair_issue_created
```

Only the serious ones, and only from two integrations:

```{code-block} yaml
:linenos:
trigger: spook.repair_issue_created
options:
  domain:
    - hue
    - zwave_js
  severity:
    - critical
    - error
```

:::

### Repair issue resolved

Fires when a repair issue goes away.

```{list-table}
:header-rows: 1
* - Trigger properties
* - Trigger
  - Repair issue resolved 👻
* - Trigger name
  - `spook.repair_issue_removed`
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
* - `domain`
  - {term}`string <string>` | {term}`list of strings <list>`
  - No
  - Defaults to every integration
```

Something got fixed, or whatever was complaining stopped complaining. Handy for closing a notification you opened when the issue turned up.

When it fires, `trigger.domain` and `trigger.issue_id` say which issue it was.

:::{seealso} Example trigger in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
trigger: spook.repair_issue_removed
options:
  domain: hue
```

:::

:::{attention} Known limitations
:class: dropdown

- There is no severity to filter on, and none in the trigger variables. By the time Home Assistant announces a removal the issue is already out of the registry, so the only things left to say about it are which integration it belonged to and what it was called.
- Ignoring an issue is not resolving it. It stays in the registry, so this does not fire for it.

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

(cooldown)=

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

- The automation asking does not count. Put this inside an `if` or a `choose` in your actions and the run's own context is the nearest one in reach, so without skipping it this would pass for a schedule or a person just as readily. It looks past itself and reports whatever set the run going.
- Only automations are recognised. A script running on its own, without an automation having started it, is not an automation and this does not pass for it.
- Spook has to have been running when the other automation ran. It remembers the mapping while your automations are loaded, so a run from before a restart is no longer known.
- It names the automation that started the chain, not the last thing in it. If your goodnight automation calls a script and that script turns off the lights, this reports the automation, which is almost always what you wanted to ask about.
- Only the last few hundred automation runs are remembered. Not a practical limit for a condition being checked right after the run it is asking about, but it is a limit.

:::

### Repair issue outstanding

Passes while a repair issue is outstanding.

```{list-table}
:header-rows: 1
* - Condition properties
* - Condition
  - Repair issue outstanding 👻
* - Condition name
  - `spook.repair_issue_present`
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
* - `domain`
  - {term}`string <string>` | {term}`list of strings <list>`
  - No
  - Defaults to every integration
* - `severity`
  - {term}`string <string>` | {term}`list of strings <list>`
  - No
  - `critical`, `error`, `warning`
```

For holding something back until the house is in order: not running a nightly job while an integration is complaining, or nagging once a day for as long as anything is wrong.

Leave the options out and any outstanding issue passes it. Name integrations, severities, or both, and all the named parts have to match the same issue.

:::{seealso} Example {term}`condition <condition>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
condition: spook.repair_issue_present
```

Only if something serious is wrong with one of these:

```{code-block} yaml
:linenos:
condition: spook.repair_issue_present
options:
  domain:
    - hue
    - zwave_js
  severity:
    - critical
```

:::

:::{attention} Known limitations
:class: dropdown

- Issues somebody has ignored do not count. Ignoring one is telling Home Assistant to stop bringing it up, and this is not the place to overrule that.
- Nor do issues waiting to be confirmed. Home Assistant keeps issues across a restart so it can remember which were ignored, but marks them as awaiting confirmation until the integration reports them again. Counting those would pass on every startup for anything that has since been fixed.
- An issue with no severity recorded cannot answer a question about severity, so naming severities leaves it out.

:::

### Run allowance left

Passes while this automation has runs to spare.

```{list-table}
:header-rows: 1
* - Condition properties
* - {term}`Condition`
  - Run allowance left 👻
* - Condition name
  - `spook.quota`
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
* - `limit`
  - {term}`integer <integer>`
  - Yes
  - `5`
* - `period`
  - {term}`string <string>`
  - Yes
  - `24:00:00`
```

The counterpart to [Cooldown](#cooldown): that one spaces runs out, this one caps how many there are. Handy for something that is fine now and then but not fifty times a day, like a notification about a door that keeps being opened.

The window rolls. A limit of five over a day means no more than five runs in any twenty-four hours, not five between midnights, so the allowance comes back gradually as the oldest run drops out of the window rather than all at once.

Runs are counted from what actually ran. Home Assistant does not announce an automation whose conditions turned the run down, so an attempt something else held back costs nothing.

:::{seealso} Example {term}`condition <condition>` in {term}`YAML`
:class: dropdown

At most five runs in any twenty-four hours:

```{code-block} yaml
:linenos:
condition: spook.quota
options:
  limit: 5
  period: "24:00:00"
```

Twice an hour, and no more:

```{code-block} yaml
:linenos:
condition: spook.quota
options:
  limit: 2
  period: "01:00:00"
```

:::

:::{attention} Known limitations
:class: dropdown

- The count starts again after a restart. Spook remembers the runs while it is running, and nothing is written down, so a restart hands back a full allowance.
- The limit cannot go above 64. Spook keeps the last 64 runs of each automation, and answering a larger limit would need a longer memory than that. Above 64 runs in a window it is not really an allowance any more.
- The period cannot go above 366 days. Since a restart clears the count anyway, an allowance measured over more than a year is not something this could answer honestly.
- Automations only. Scripts are left out on purpose: Home Assistant announces a script run before deciding whether it is allowed, so a call turned down for already running would spend an allowance on a run that never happened. A condition checked anywhere other than an automation has nothing to count against and passes.
- Only the 256 most recently run automations are followed. Beyond that the least recently used one is forgotten, which hands its allowance back. Not something a normal house will reach, but it is a limit.
- The run doing the asking does not count against itself. A condition sitting inside the actions is checked while the run is already under way, so without that a limit of one would turn down every run.

:::

### Triggers in order

Fires when several triggers happen one after another, in the order given.

```{list-table}
:header-rows: 1
* - Trigger properties
* - Trigger
  - Triggers in order
* - Trigger name
  - `spook.sequence`
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
* - `steps`
  - {term}`trigger <trigger>`
  - Yes
  - Two or more triggers, in the order they have to happen
* - `timeout`
  - {term}`string <string>`
  - No
  - Waits indefinitely when left out
* - `reset`
  - {term}`trigger <trigger>`
  - No
  - Nothing abandons a run when left out
```

Home Assistant fires on one thing happening. It does not fire on one thing happening _after_ another, which is most of what a house actually does: the door opened and then somebody moved in the hall, the washing machine started and then went quiet, the alarm armed and then a window opened. Written by hand that needs a helper entity per step and an automation to set each one.

Only the step being waited for is listening. So a later step firing before an earlier one is not a match, and neither is the same step firing twice. Two steps is the minimum, because one trigger in order is just a trigger.

Once the last step lands the trigger fires and goes back to waiting for the first, so it works as many times as you like.

When it fires, `trigger.steps` holds what each step reported, in order, and `trigger.duration` is how long the whole thing took. The step that completed the sequence is also lifted to the top, so `trigger.entity_id`, `trigger.from_state` and `trigger.to_state` describe the thing that finished it, and `spook.triggered_by_user` and friends find the person behind it there.

:::{seealso} Example trigger in {term}`YAML`
:class: dropdown

Somebody came in through the front door and walked into the hall, within two minutes:

```{code-block} yaml
:linenos:
trigger: spook.sequence
options:
  timeout: "00:02:00"
  steps:
    - trigger: state
      entity_id: binary_sensor.front_door
      to: "on"
    - trigger: state
      entity_id: binary_sensor.hallway_motion
      to: "on"
```

Same again, but disarming the alarm halfway through means it no longer counts:

```{code-block} yaml
:linenos:
trigger: spook.sequence
options:
  timeout: "00:02:00"
  steps:
    - trigger: state
      entity_id: binary_sensor.front_door
      to: "on"
    - trigger: state
      entity_id: binary_sensor.hallway_motion
      to: "on"
  reset:
    - trigger: state
      entity_id: alarm_control_panel.home
      to: disarmed
```

:::

:::{attention} Known limitations
:class: dropdown

- One step is one trigger. A step that should accept either of two things is written as one trigger that matches both, for example a state trigger naming several entities.
- The `timeout` covers the whole run, counted from the first step. There is no per-step deadline.
- A run under way is abandoned when Home Assistant restarts, along with everything else in memory. A sequence half-finished before a restart starts again from the first step.
- The automation's `trigger_variables` do not reach the steps. Home Assistant hands those to a trigger platform, not to a trigger like this one, so a step whose own configuration is written as a template referring to them has nothing to render from. Steps written the ordinary way are unaffected.
- A step Home Assistant refuses to accept disables that automation, and so does a first step it accepts but then cannot listen for. Both are caught while the automation loads, and both say why in the log, rather than leaving it sitting there never firing.
- A later step that cannot be attached is a different matter, because the automation is already running by then. That run stalls where it stands and the log is the only place it says so. Same for a `reset` that cannot be attached: the steps keep working, so nothing else gives it away.
  :::

### While a condition holds

Fires when a condition turns true, and keeps firing on an interval for as long as it stays true.

```{list-table}
:header-rows: 1
* - Trigger properties
* - Trigger
  - While a condition holds
* - Trigger name
  - `spook.while`
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
* - `condition`
  - {term}`condition <condition>`
  - Yes
  - Any condition, built the ordinary way
* - `every`
  - {term}`string <string>`
  - Yes
  - `00:10:00`
```

The nagging trigger. The garage is open and you want to hear about it again in ten minutes, and ten minutes after that, until somebody closes it.

Home Assistant can already do this inside a script, with a `repeat` holding a `while` and a `delay`. What that costs is a script run held open for as long as the garage is open: the automation's `mode` has to allow for it, a reload ends it, and core stops a loop that has gone round ten thousand times. As a trigger none of that applies, because nothing is being held open between one firing and the next.

It fires the moment the condition arrives, not while it already holds, so loading an automation whose condition happens to be true does not set it off. Counting starts again at one each time the condition comes back.

When it fires, `trigger.times` is how many times it has fired this spell, starting at one, and `trigger.every` is the interval. The first firing also carries the state change that made the condition turn, in the same way [Condition turned true](#condition-turned-true) does, so `spook.triggered_by_user` finds the person who caused it there. The firings after that carry nobody, because nobody makes a clock come round.

:::{seealso} Example trigger in {term}`YAML`
:class: dropdown

Remind me every ten minutes while the garage is open and nobody is home:

```{code-block} yaml
:linenos:
trigger: spook.while
options:
  every: "00:10:00"
  condition:
    - condition: state
      entity_id: cover.garage
      state: open
      for: "00:10:00"
    - condition: numeric_state
      entity_id: zone.home
      below: 1
```

:::

:::{attention} Known limitations
:class: dropdown

- The first firing happens the moment the condition turns true, and the interval starts from there. To wait before the first reminder, put a `for:` on the condition itself, as the example does.
- A spell is abandoned when Home Assistant restarts, along with everything else in memory. A condition that is still true after the restart is not a new arrival, so it will not start nagging again until it goes false and true once more.
- Everything [Condition turned true](#condition-turned-true) says about what can and cannot be watched applies here as well, including the 30-second polling pass and the conditions that are refused.
  :::

### Watchdog

Fires when something that was expected to happen does not happen in time.

```{list-table}
:header-rows: 1
* - Trigger properties
* - Trigger
  - Watchdog
* - Trigger name
  - `spook.watchdog`
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
* - `arm`
  - {term}`trigger <trigger>`
  - Yes
  - What starts the watch
* - `expect`
  - {term}`trigger <trigger>`
  - Yes
  - What is expected to follow
* - `within`
  - {term}`string <string>`
  - Yes
  - `00:02:00`
```

Every trigger Home Assistant has fires because something happened. The interesting failures are the other kind: the back door opened and nobody walked into the hall, the washing machine started and never finished, the nightly backup began and never reported in. Written by hand that is a helper entity, a timer, and two automations to keep them in step.

Arming starts a clock. The expected trigger arriving before it runs out calls the watch off and nothing fires. The clock running out is what fires it.

Arming again while already waiting starts the wait over rather than running a second one, because the wait is measured from the arming and the latest one is the one that counts. The expected trigger arriving while nothing is being waited for does nothing at all.

When it fires, `trigger.armed_by` is what the arming trigger reported and `trigger.within` is the wait it was given. Nothing else is carried, and no user: a watchdog fires because nothing happened, at a moment a clock came round, and nobody makes a clock come round. An automation that wants to name the person can read `trigger.armed_by`.

:::{seealso} Example trigger in {term}`YAML`
:class: dropdown

The back door opened and nobody came into the hall within two minutes:

```{code-block} yaml
:linenos:
trigger: spook.watchdog
options:
  within: "00:02:00"
  arm:
    - trigger: state
      entity_id: binary_sensor.back_door
      to: "on"
  expect:
    - trigger: state
      entity_id: binary_sensor.hallway_motion
      to: "on"
```

:::

:::{attention} Known limitations
:class: dropdown

- A watch under way is abandoned when Home Assistant restarts, along with everything else in memory. Something armed before a restart is not waited for after it.
- A watchdog that cannot attach either half is refused, which disables that automation and says why in the log. Half a watchdog would either never start or always fire, and neither is worth leaving running.
- The automation's `trigger_variables` do not reach the arming and expected triggers, for the same reason they do not reach a sequence's steps: Home Assistant hands those to a trigger platform, not to a trigger like this one.
  :::

### Entity will not settle

Fires when an entity changes state more often than it should within a stretch of time.

```{list-table}
:header-rows: 1
* - Trigger properties
* - Trigger
  - Entity will not settle
* - Trigger name
  - `spook.flapping`
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
* - `changes`
  - {term}`integer <integer>`
  - Yes
  - Between 2 and 1000
* - `within`
  - {term}`string <string>`
  - Yes
  - `00:05:00`
```

A sensor that goes on and off and on again, a device that drops off the network and comes back, a binary sensor sitting right on its threshold. Each change on its own looks perfectly fine, and Home Assistant has no way to say "this one has changed five times in five minutes and something is wrong with it".

Changes of state, not writes. An entity reporting the same value over and over is chatty, not unsettled, so attribute changes do not count. Going to `unavailable` and back does count, which is the case this exists for. An entity appearing or disappearing does not: that is not it going back and forth.

The window slides, so this is always about the most recent changes rather than a fresh count every five minutes.

It reports once per spell. Once it has said an entity will not settle it stays quiet until that entity does settle, because a storm of alerts about a storm helps nobody. Settling means the last few changes no longer fall inside the window, and the next time it starts up is news again. A change that still leaves the last few inside the window is the same spell carrying on, however long it has been since the one before it.

When it fires, `trigger.entity_id` names the entity, `trigger.from_state` and `trigger.to_state` are the change that tipped it over, and `trigger.changes` and `trigger.within` are what was asked for.

:::{seealso} Example trigger in {term}`YAML`
:class: dropdown

Tell me about a door sensor that cannot make up its mind:

```{code-block} yaml
:linenos:
trigger: spook.flapping
target:
  entity_id: binary_sensor.back_door
options:
  changes: 5
  within: "00:05:00"
```

Or watch everything with a label, and hear about whichever one starts misbehaving:

```{code-block} yaml
:linenos:
trigger: spook.flapping
target:
  label_id: battery_powered
options:
  changes: 10
  within: "00:15:00"
```

:::

:::{attention} Known limitations
:class: dropdown

- Counting starts when the automation loads. Changes from before that are not known, so an entity that has been flapping all afternoon is reported the next time it changes enough, not immediately.
- Each entity is counted on its own. Ten entities changing twice each is not one entity changing twenty times, which is the point, but it does mean a target full of entities that each flap a little goes unreported.
- What is remembered is the last `changes` moments per entity, and no more, so a large target costs little. That is also why `changes` stops at a thousand: past that it is not describing a flapping entity any more. It is forgotten entirely when Home Assistant restarts or the entity leaves the target.
  :::

(condition-turned-true)=

### Condition turned true

Fires when a condition goes from false to true.

```{list-table}
:header-rows: 1
* - Trigger properties
* - Trigger
  - Condition turned true 👻
* - Trigger name
  - `spook.condition_met`
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
* - `condition`
  - {term}`condition <condition>`
  - Yes
  - Any condition, built the ordinary way
```

A condition is true or false, and the moment it turns is worth reacting to. Home Assistant has a trigger for a template turning true and one for a state arriving, but nothing that takes the condition building blocks, so anything more involved than a single state has to be rewritten as a template.

Takes one condition or a list of them, and a list means all of them, the same as anywhere else. Which is also what the visual editor sends, so both shapes have to work.

Only the turn counts. A condition that is already true when the automation loads is not a change, so this does not fire for it, the same as the template trigger. And going back to false is not a turn either.

When it can tell which change turned the condition, `trigger.entity_id` names that entity and `trigger.from_state` and `trigger.to_state` are what it moved between, the same three the template trigger hands over. Which is also what carries the user through: an automation starts a fresh context, so `spook.triggered_by_user` and friends read the person off `trigger.to_state`.

It can tell only when every part of the condition announces its own turns, which means `state`, `numeric_state` and `zone` conditions without a `for:` and without a `value_template`, plus any `and`, `or` or `not` built out of those. Anything else and all three are empty, because a condition with a part that turns quietly gets discovered by the next unrelated change, and naming that change would be naming the wrong one.

:::{seealso} Example trigger in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
trigger: spook.condition_met
options:
  condition:
    condition: and
    conditions:
      - condition: state
        entity_id: binary_sensor.back_door
        state: "on"
      - condition: numeric_state
        entity_id: sensor.outside_temperature
        below: 5
```

:::

:::{attention} Known limitations
:class: dropdown

- A condition that names entities is noticed the moment one of them changes. That covers `state`, `numeric_state` and `zone` conditions, a `time` condition pointing at an `input_datetime`, and any `and`, `or` or `not` built out of those. A `numeric_state` threshold naming an entity counts as well, so a condition that turns because the line moved rather than the measurement is noticed just as quickly; Home Assistant leaves that entity out of what it reports a condition depends on, so Spook picks it up separately. A template condition names nothing that can be read off the config, and a plain time or sun condition has nothing to name, so those are asked again every 30 seconds.
- Naming the entities is not the same as noticing every turn, because not every turn arrives as a state change. A `state` condition with a `for:` turns true when the duration runs out, and a `time` condition turns true when the clock passes the moment, and neither of those moves an entity. Those are picked up by the 30-second polling pass instead, so up to half a minute late.
- A condition that turns true and false again within those 30 seconds is missed entirely rather than noticed late. If what you are watching flickers, trigger on the thing that flickers.
- A condition that asks about the run it is in cannot be watched, so `trigger`, and Spook's own `cooldown`, `quota`, `triggered_by_user`, `not_triggered_by_user` and `triggered_by_automation`, are refused. Nothing has fired yet at the point this decides whether to fire, so their answer would not mean anything.
- The same goes for a template that reaches for `trigger`, `this`, `repeat` or `wait`. Home Assistant hands those to a running automation or script, and there is no run here to take them from, so such a condition is refused rather than left never firing. A template that merely mentions the word is fine: `sensor.trigger_count` is an entity, not the trigger.
- A condition that cannot be built at all disables that automation and says why in the log, rather than sitting there never firing.
  :::
