---
subject: Reference
title: Provided Home Assistant conditions
short_title: Conditions
subtitle: Asking the questions Home Assistant does not. 🤔
description: Spook provides new conditions to Home Assistant. This reference page lists them all, and points you to the right documentation.
date: 2026-08-22T09:15:00+02:00
---

Spook provides new conditions to Home Assistant. This reference page lists them all and points you to the right documentation for that condition.

## Triggered by a user

Passes when a person is behind what set this off, rather than a schedule, the sun, or an integration acting on its own. _#whodunnit_

`spook.triggered_by_user`, [documentation](other-features#triggered-by-a-user) 📚

## Not triggered by a user

Passes when nobody set this run going. The other half of the same question. _#nobodyhome_

`spook.not_triggered_by_user`, [documentation](other-features#not-triggered-by-a-user) 📚

## Cooldown

Passes when this automation or script has not run within a given time, so it does not re-fire more often than you want it to. _#patience_

`spook.cooldown`, [documentation](other-features#cooldown) 📚

## Chance

Passes a set percentage of the time, chosen at random on every check. For when the same thing every evening gets boring. _#coinflip_

`spook.chance`, [documentation](other-features#chance) 📚
