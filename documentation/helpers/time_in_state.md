---
subject: Helpers
title: Time in state
subtitle: Since when? Spook remembers. ⏱️
date: 2026-10-03T12:00:00+02:00
---

The time in state {term}`helper <helper>` tells you since when an {term}`entity <entity>` has been in its current state. Since when is the front door closed? Since when is the washing machine idle? Or, if you like: when did motion last go on?

Home Assistant already keeps a "last changed" for every entity, but that one starts over every time Home Assistant starts, and every time the entity is unavailable for a moment. A door that stayed shut all week has been "closed for 2 minutes" after a restart. This helper does not forget.

## How it works

The helper is a timestamp sensor. It holds the moment the source entity went into its state, and the Home Assistant interface shows that as "3 hours ago", keeping it current by itself.

- **Restarts:** the moment is kept. When the source is in the same state after a restart, the moment from before stays.
- **Unavailable or unknown:** not counted as a change. A device dropping off the network for a moment, or an integration reloading, does not reset the clock when it comes back in the same state.
- **Attributes:** only the state itself counts. A battery level changing on a door sensor is not the door changing.

## Since it last became a state

Optionally, give the helper one or more states to count. The helper then holds the moment the source last _became_ one of those states, and keeps that moment after the source moves on.

Set a motion sensor as the source with `on` as the state, and you have "last motion": the moment motion was last detected, for as long as no new motion comes in.

## Attributes

| Attribute      | Description                                                                                                                                                                                                                                |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `entity_id`    | The source entity.                                                                                                                                                                                                                         |
| `source_state` | The state of the source entity, as the helper last saw it.                                                                                                                                                                                 |
| `observed`     | `true` when the helper saw the change happen. `false` when the change happened while nobody was looking, like while Home Assistant was down. The moment is then when the helper first noticed it: the real moment is earlier, or the same. |

## Creating a time in state helper

Add one directly to your own instance by selecting the {term}`My Home Assistant` button below:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=spook_time_in_state)

Or add one manually, using the following steps:

1. From the Home Assistant sidebar, select **Settings** and next select **Devices & Services**.
2. Select the **Helpers** tab.
3. On the helpers page, in the bottom right corner, select the **+ Create helper** button.
4. From the list of helpers, select **Time in state 👻**.
5. Provide a name, and select the entity to follow in the **Source entity** field.
6. Optionally, add the states to count in the **Only count becoming these states** field. Leave it empty to count every change.
7. Select **Submit**. Done! 🎉
