---
subject: Enhanced integrations
title: Calendar
subtitle: What goes in, must come out. 📅
description: Spook adds actions to change and delete calendar events from automations, finding them by their title.
date: 2026-10-03T21:00:00+02:00
---

```{image} https://brands.home-assistant.io/calendar/icon.png
:alt: The Home Assistant calendar icon
:width: 250px
:align: center
```

<br><br>

The calendar {term}`integration <integration>` brings calendars into {term}`Home Assistant`: a local calendar, CalDAV, Google Calendar, and more.

An automation can put an event in a calendar with `calendar.create_event`, and that is where it ends. Calendars that can delete an event do so only when asked from the calendar panel. Spook adds the actions to change an event, and to take it out again.

Deleting an event goes by its uid, an identifier every event has, and `calendar.get_events` leaves that out of what it returns. So Spook finds events the way an automation can: by their title, in a stretch of time.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Delete event

Delete events from a calendar, found by their title or their uid in a stretch of time.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Calendar: Delete event 👻
* - {term}`Action name`
  - `calendar.delete_event`
* - {term}`Action targets`
  - Yes, `calendar` entities that can delete events
* - {term}`Action response`
  - Optional, the events deleted
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=calendar.delete_event)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=calendar.delete_event)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `summary`
  - {term}`string <string>`
  - No, but this or `uid`
  - Dentist
* - `uid`
  - {term}`string <string>`
  - No, but this or `summary`
  -
* - `start_date_time`
  - {term}`datetime <datetime>`
  - No
  - Now
* - `end_date_time`
  - {term}`datetime <datetime>`
  - No, but this or `duration`
  - 2026-10-04 20:00:00
* - `duration`
  - {term}`time period <time period>`
  - No, but this or `end_date_time`
  - `{"hours": 24}`
* - `whole_series`
  - {term}`boolean <boolean>`
  - No
  - `false`
```

Events are looked for from `start_date_time`, which is now when you leave it out, until `end_date_time` or for `duration`, the same way `calendar.get_events` reads them. Every event in that stretch with exactly that `summary`, or that `uid`, or both, is deleted.

An event that repeats is found occurrence by occurrence, and only the occurrences found are deleted. Set `whole_series` to delete the whole series instead.

When nothing matches, nothing happens. That is not an error: "delete it if it is there" is how an automation tidies up after itself.

The response lists every event deleted, for each calendar, with its `uid`, `recurrence_id`, `summary`, `start` and `end`.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

Take out the reminder an automation put in earlier today:

```{code-block} yaml
:linenos:
action: calendar.delete_event
target:
  entity_id: calendar.family
data:
  summary: Take the bins out
  duration:
    hours: 24
```

:::

:::{attention} Known limitations
:class: dropdown

- A `summary` or a `uid` is required. A stretch of time alone would delete everything in it, which is how a calendar gets emptied by accident.
- The title has to match exactly, including capitals.
- Only calendars that can delete events can be targeted. A read-only calendar, like a holiday feed, refuses the action.
- An event the calendar gives no uid cannot be told apart from any other, so it is left alone.

:::

### Update event

Change events in a calendar, found by their title or their uid in a stretch of time: a new title, a new place, or new times.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Calendar: Update event 👻
* - {term}`Action name`
  - `calendar.update_event`
* - {term}`Action targets`
  - Yes, `calendar` entities that can change events
* - {term}`Action response`
  - Optional, the events changed
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=calendar.update_event)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=calendar.update_event)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `summary`
  - {term}`string <string>`
  - No, but this or `uid`
  - Dentist
* - `uid`
  - {term}`string <string>`
  - No, but this or `summary`
  -
* - `start_date_time`
  - {term}`datetime <datetime>`
  - No
  - Now
* - `end_date_time`
  - {term}`datetime <datetime>`
  - No, but this or `duration`
  - 2026-10-04 20:00:00
* - `duration`
  - {term}`time period <time period>`
  - No, but this or `end_date_time`
  - `{"hours": 24}`
* - `new_summary`
  - {term}`string <string>`
  - No
  - Orthodontist
* - `description`
  - {term}`string <string>`
  - No
  -
* - `location`
  - {term}`string <string>`
  - No
  -
* - `new_start`
  - {term}`datetime <datetime>`
  - No
  - 2026-10-04 15:00:00
* - `new_end`
  - {term}`datetime <datetime>`
  - No
  - 2026-10-04 16:30:00
* - `shift`
  - {term}`time period <time period>`
  - No
  - `{"hours": -1}`
```

Events are found exactly the way [delete event](#delete-event) finds them. Every event found gets the changes you ask for, and keeps everything else it had: Home Assistant hands the calendar a whole event to update, so Spook carries over what you did not change.

To move an event, give it a `new_start`, and it keeps its length, or a `new_start` and a `new_end`, or a `new_end` alone to make it longer or shorter. Or move it by a `shift`, later, or earlier when negative. A time written without a time zone is read as Home Assistant's own.

The response lists every event changed, for each calendar, with its `uid` and its new `summary`, `start` and `end`.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

The dentist runs late again, so move today's appointment an hour on:

```{code-block} yaml
:linenos:
action: calendar.update_event
target:
  entity_id: calendar.family
data:
  summary: Dentist
  duration:
    hours: 24
  shift:
    hours: 1
```

:::

:::{attention} Known limitations
:class: dropdown

- Something to change is required: a new summary, description, location, or new times.
- A `shift` together with a new start or end is refused. Say how to move an event one way.
- An event of a repeating series is changed on its own, never the whole series. Changing a series means changing its first event, and the times of whichever occurrence was found would move the series start along with them.
- Only calendars that can change events can be targeted. A read-only calendar, like a holiday feed, refuses the action.
- An event the calendar gives no uid cannot be told apart from any other, so it is left alone.

:::

## Repairs

Spook has no repair detections for this integration.
