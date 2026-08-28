---
subject: Reference
title: Provided Home Assistant triggers
short_title: Triggers
subtitle: For the moments Home Assistant cannot name. ⏰
description: Spook provides new triggers to Home Assistant. This reference page lists them all, and points you to the right documentation.
date: 2026-08-27T21:15:00+02:00
---

Spook provides new triggers to Home Assistant. This reference page lists them all and points you to the right documentation for that trigger.

## Cron schedule

Fires on a crontab schedule, for the times Home Assistant's own time triggers cannot express, like every weekday at seven or the last Friday of the month. _#crontab_

`spook.cron`, [documentation](other-features#cron-schedule) 📚

## Entity fell silent

Fires when nothing has written to an entity for a while, which catches the device that died quietly instead of going unavailable. _#stale_ _#silent_ _#dead_

`spook.stale`, [documentation](other-features#entity-fell-silent) 📚

## Integration failed to set up

Fires when a configuration entry has been unable to set itself up for a while, past the point where Home Assistant's own retries would have sorted it out. _#integration_ _#broken_ _#config-entry_

`spook.integration_failed`, [documentation](other-features#integration-failed-to-set-up) 📚

## Repair issue created

Fires when a new repair issue turns up, so you hear about one without visiting the repairs page. Can be narrowed by integration and severity. _#repairs_ _#issue_

`spook.repair_issue_created`, [documentation](other-features#repair-issue-created) 📚

## Repair issue resolved

Fires when a repair issue goes away, either fixed or no longer reported. _#repairs_ _#issue_

`spook.repair_issue_removed`, [documentation](other-features#repair-issue-resolved) 📚

## Condition turned true

Fires when a condition goes from false to true, using the same condition building blocks as anywhere else. _#condition_ _#template_

`spook.condition_met`, [documentation](other-features#condition-turned-true) 📚

## Triggers in order

Fires when several triggers happen one after another, in the order given, optionally within a time limit. _#sequence_ _#order_ _#timeout_

`spook.sequence`, [documentation](other-features#triggers-in-order) 📚
