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

An automation can put an event in a calendar with `calendar.create_event`, and that is where it ends. Calendars that can delete an event do so only when asked from the calendar panel. Spook adds the action to take an event out again.

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

## Repairs

Spook has no repair detections for this integration.
