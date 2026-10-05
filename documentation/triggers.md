---
subject: Reference
title: Provided Home Assistant triggers
short_title: Triggers
subtitle: For the moments Home Assistant cannot name. ⏰
description: Spook provides new triggers to Home Assistant. This reference page lists them all, and points you to the right documentation.
date: 2026-08-27T21:15:00+02:00
---

Spook provides new triggers to Home Assistant. This reference page lists them all and points you to the right documentation for that trigger.

## All of these happened

Fires when every one of several triggers has fired inside the same window of time, in any order. Home Assistant's own triggers are a list where any one of them is enough; this is the other one. _#and_ _#together_ _#combination_

`spook.all_of`, [documentation](other-features#all-of-these-happened) 📚

## Automation turned off

Fires when an automation is turned off, by somebody or by something, so the one switched off while chasing a problem does not stay off unnoticed. _#automation_ _#disabled_ _#off_

`spook.automation_turned_off`, [documentation](other-features#automation-turned-off) 📚

## Cron schedule

Fires on a crontab schedule, for the times Home Assistant's own time triggers cannot express, like every weekday at seven or the last Friday of the month. _#crontab_

`spook.cron`, [documentation](other-features#cron-schedule) 📚

## Device added

Fires when a new device is added to Home Assistant, like a plug that was just paired, whoever paired it. _#device_ _#new_ _#paired_

`spook.device_added`, [documentation](other-features#device-added) 📚

## Device discovered

Fires when Home Assistant discovers something new it could set up, like a device that just turned up on your network. _#discovery_ _#device_ _#new_ _#network_

`spook.device_discovered`, [documentation](other-features#device-discovered) 📚

## Entity came back

Fires when an entity returns after having been unavailable for a while, so a router rebooting does not read as everything in the house recovering. _#recovered_ _#back_ _#unavailable_

`spook.recovered`, [documentation](other-features#entity-came-back) 📚

## Entity fell silent

Fires when nothing has written to an entity for a while, which catches the device that died quietly instead of going unavailable. _#stale_ _#silent_ _#dead_

`spook.stale`, [documentation](other-features#entity-fell-silent) 📚

## Integration added

Fires when an integration is added to Home Assistant, by you, by somebody else, or by Home Assistant itself. _#integration_ _#config-entry_ _#new_

`spook.integration_added`, [documentation](other-features#integration-added) 📚

## Integration failed to set up

Fires when a configuration entry has been unable to set itself up for a while, past the point where Home Assistant's own retries would have sorted it out. _#integration_ _#broken_ _#config-entry_

`spook.integration_failed`, [documentation](other-features#integration-failed-to-set-up) 📚

## Once it settles

Fires once a trigger has stopped firing for a while, so a burst of them arrives as one. A motion sensor does not report motion once, it reports it twenty times. _#debounce_ _#burst_ _#quiet_

`spook.debounce`, [documentation](other-features#once-it-settles) 📚

## Repair issue created

Fires when a new repair issue turns up, so you hear about one without visiting the repairs page. Can be narrowed by integration and severity. _#repairs_ _#issue_

`spook.repair_issue_created`, [documentation](other-features#repair-issue-created) 📚

## Repair issue resolved

Fires when a repair issue goes away, either fixed or no longer reported. _#repairs_ _#issue_

`spook.repair_issue_removed`, [documentation](other-features#repair-issue-resolved) 📚

## Script started

Fires when a script starts a run, picked in the editor rather than typed into an event trigger, and only for a run the script lets through. _#script_ _#run_ _#started_

`spook.script_started`, [documentation](other-features#script-started) 📚

## Update installed

Fires when an update entity reports a different installed version, whether somebody pressed install, the device updated itself, or it was updated outside of Home Assistant. _#update_ _#firmware_ _#installed_

`spook.update_installed`, [documentation](other-features#update-installed) 📚

## User added

Fires when somebody is given a login to Home Assistant, which an admin would rather hear about than stumble upon. _#user_ _#account_ _#security_

`spook.user_added`, [documentation](other-features#user-added) 📚

## Condition turned true

Fires when a condition goes from false to true, using the same condition building blocks as anywhere else. _#condition_ _#template_

`spook.condition_met`, [documentation](other-features#condition-turned-true) 📚

## Triggers in order

Fires when several triggers happen one after another, in the order given, optionally within a time limit. _#sequence_ _#order_ _#timeout_

`spook.sequence`, [documentation](other-features#triggers-in-order) 📚

## While a condition holds

Fires when a condition turns true and keeps firing on an interval for as long as it stays true, without holding a script run open. _#condition_ _#repeat_ _#reminder_

`spook.while`, [documentation](other-features#while-a-condition-holds) 📚

## Watchdog

Fires when something that was expected to happen does not happen in time, without needing a helper entity and a timer to arrange it. _#absence_ _#timeout_ _#watchdog_

`spook.watchdog`, [documentation](other-features#watchdog) 📚

## Entity will not settle

Fires when an entity changes state more often than it should within a stretch of time, which is how a failing device usually announces itself. _#flapping_ _#device-health_ _#unavailable_

`spook.flapping`, [documentation](other-features#entity-will-not-settle) 📚
