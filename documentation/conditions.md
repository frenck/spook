---
subject: Reference
title: Provided Home Assistant conditions
short_title: Conditions
subtitle: Asking the questions Home Assistant does not. 🤔
description: Spook provides new conditions to Home Assistant. This reference page lists them all, and points you to the right documentation.
date: 2026-08-22T09:15:00+02:00
---

Spook provides new conditions to Home Assistant. This reference page lists them all and points you to the right documentation for that condition.

## Automation: Triggered by a user

Passes when a person set this run going, rather than a schedule, a state change, or another automation. _#whodunnit_

`automation.triggered_by_user`, [documentation](integrations/automation#triggered-by-a-user) 📚

## Automation: Not triggered by a user

Passes when nobody set this run going. The other half of the same question. _#nobodyhome_

`automation.not_triggered_by_user`, [documentation](integrations/automation#not-triggered-by-a-user) 📚

## Cooldown

Passes when this automation or script has not run within a given time, so it does not re-fire more often than you want it to. _#patience_

`spook.cooldown`, [documentation](other-features#cooldown) 📚

## Chance

Passes a set percentage of the time, chosen at random on every check. For when the same thing every evening gets boring. _#coinflip_

`spook.chance`, [documentation](other-features#chance) 📚
