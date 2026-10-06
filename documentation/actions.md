---
subject: Reference
title: Provided Home Assistant actions
short_title: Actions
subtitle: Ready? Set? Action! 🎬
thumbnail: images/usage/services_example.png
description: Spook provides quite a lot of new actions to Home Assistant. This reference pages lists them all, and points you to the right documentation.
date: 2023-08-09T21:29:00+02:00
---

Spook provides quite a lot of new actions to Home Assistant. This reference page lists them all and points you to the right documentation for that action.

## Areas: Create an area

Instantly create new rooms in your home. _#BobTheBuilder_

`homeassistant.create_area`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_area), [documentation](areas#create-an-area) 📚

## Areas: Delete an area

Just like that, you made an area of your home disappear. _#DemolitionMan_

`homeassistant.delete_area`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_area), [documentation](areas#delete-an-area) 📚

## Areas: Add an alias to an area

Adds an alias (or multiple aliases) to an area. _#aka_

`homeassistant.add_alias_to_area`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_alias_to_area), [documentation](areas#add-an-alias-to-an-area)

## Areas: Remove an alias from an area

Removes an alias (or multiple aliases) from an area. _#broom_

`homeassistant.remove_alias_from_area`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_alias_from_area), [documentation](areas#remove-an-alias-from-an-area)

## Areas: Set aliases for an area

Sets the aliases for an area. _#useless_

`homeassistant.set_area_aliases`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.set_area_aliases), [documentation](areas#set-aliases-for-an-area)

## Areas: Add a device to an area

Dynamically add/move a device to a new area. _#moveit_

`homeassistant.add_device_to_area`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_device_to_area), [documentation](areas#add-a-device-to-an-area)

## Areas: Remove a device from an area

Dynamically remove a device from an area. _#poef_

`homeassistant.remove_device_from_area`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_device_from_area), [documentation](areas#remove-a-device-from-an-area)

## Areas: Add an entity to an area

Dynamically add/move an entity to an area. _#bam_

`homeassistant.add_entity_to_area`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_entity_to_area), [documentation](areas#add-an-entity-to-an-area)

## Areas: Remove an entity from an area

Dynamically remove an entity from an area. _#AaaaandItIsGone_

`homeassistant.remove_entity_from_area`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_entity_from_area), [documentation](areas#remove-an-entity-from-an-area)

## Automation: Snooze

Turns an automation off for a while, and turns it back on when the time is up. It survives a restart, so a snooze does not quietly become a disable. _#automation_ _#quiet_ _#temporary_

`automation.snooze`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=automation.snooze), [documentation](integrations/automation#snooze) 📚

## Automation: Turn on for

Turns an automation on for a while, and turns it back off when the time is up. It survives a restart, so "just for tonight" does not quietly become forever. _#automation_ _#temporary_

`automation.turn_on_for`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=automation.turn_on_for), [documentation](integrations/automation#turn-on-for) 📚

## Blueprint: Import Blueprint

Downloads and imports an automation/script blueprint, directly from the URL you pass into this action. _#noquestionsasked_

`blueprint.import`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=blueprint.import), [documentation](integrations/blueprint#import-blueprint) 📚

## Calendar: Delete event

Deletes events from a calendar, found by their title or uid in a stretch of time, and hands back what it deleted. _#calendar_ _#tidyup_

`calendar.delete_event`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=calendar.delete_event), [documentation](integrations/calendar#delete-event) 📚

## Calendar: Update event

Changes events in a calendar, found by their title or uid in a stretch of time: rename, move, or give them a place. Hands back what it changed. _#calendar_ _#reschedule_

`calendar.update_event`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=calendar.update_event), [documentation](integrations/calendar#update-event) 📚

## Climate: Increase temperature

Turns a thermostat's setpoint up a step, within its limits, both setpoints for one that heats and cools. _#climate_ _#warmer_

`climate.increase_temperature`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=climate.increase_temperature), [documentation](integrations/climate#increase-temperature) 📚

## Climate: Decrease temperature

Turns a thermostat's setpoint down a step, within its limits, both setpoints for one that heats and cools. _#climate_ _#colder_

`climate.decrease_temperature`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=climate.decrease_temperature), [documentation](integrations/climate#decrease-temperature) 📚

## Cover: Increase position

Moves a cover a step further open, stopping at fully open. _#cover_ _#blinds_ _#open_

`cover.increase_position`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=cover.increase_position), [documentation](integrations/cover#increase-position) 📚

## Cover: Decrease position

Moves a cover a step further closed, stopping at fully closed. _#cover_ _#blinds_ _#close_

`cover.decrease_position`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=cover.decrease_position), [documentation](integrations/cover#decrease-position) 📚

## Group: Add members

Adds entities to a group while the house is running, which the interface only lets you do by hand. _#roomforonemore_

`group.add_members`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=group.add_members), [documentation](integrations/group#add-members-to-a-group) 📚

## Group: Remove members

Takes entities out of a group while the house is running. Naming something that is not in it does nothing, so it also clears out a member that no longer exists. _#youdonthavetogohome_

`group.remove_members`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=group.remove_members), [documentation](integrations/group#remove-members-from-a-group) 📚

## Group: Set members

Replaces a group's members with the ones you give it. _#allchange_

`group.set_members`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=group.set_members), [documentation](integrations/group#set-the-members-of-a-group) 📚

## Light: Set brightness

Sets the brightness of lights that are already on, and leaves the ones that are off alone. _#light_ _#adjust_

`light.set_brightness`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_brightness), [documentation](integrations/light#set-brightness) 📚

## Light: Increase brightness

Turns up the lights that are already on, stepping each from its own level instead of the group average. _#light_ _#adjust_

`light.increase_brightness`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.increase_brightness), [documentation](integrations/light#increase-brightness) 📚

## Light: Decrease brightness

Turns down the lights that are already on, stopping at the dimmest they go rather than switching them off. _#light_ _#adjust_

`light.decrease_brightness`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.decrease_brightness), [documentation](integrations/light#decrease-brightness) 📚

## Light: Set color

Sets the color of lights that are already on, and passes over the ones that cannot do color. _#light_ _#adjust_

`light.set_color`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_color), [documentation](integrations/light#set-color) 📚

## Light: Set color temperature

Sets the color temperature of lights that are already on, each within the range it can actually reach. _#light_ _#adjust_

`light.set_color_temperature`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_color_temperature), [documentation](integrations/light#set-color-temperature) 📚

## Light: Set effect

Sets an effect on the lights that are already on and actually have it. _#light_ _#adjust_

`light.set_effect`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=light.set_effect), [documentation](integrations/light#set-effect) 📚

## Media player: Increase volume

Turns a media player's volume up by exactly the step you give, stopping at full volume. _#media_player_ _#louder_

`media_player.increase_volume`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=media_player.increase_volume), [documentation](integrations/media_player#increase-volume) 📚

## Media player: Decrease volume

Turns a media player's volume down by exactly the step you give, stopping at silent. _#media_player_ _#quieter_

`media_player.decrease_volume`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=media_player.decrease_volume), [documentation](integrations/media_player#decrease-volume) 📚

## Valve: Increase position

Moves a valve a step further open, stopping at fully open. _#valve_ _#open_

`valve.increase_position`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=valve.increase_position), [documentation](integrations/valve#increase-position) 📚

## Valve: Decrease position

Moves a valve a step further closed, stopping at fully closed. _#valve_ _#close_

`valve.decrease_position`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=valve.decrease_position), [documentation](integrations/valve#decrease-position) 📚

## Water heater: Increase temperature

Turns a water heater's setpoint up a step, within its limits. _#water_heater_ _#warmer_

`water_heater.increase_temperature`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=water_heater.increase_temperature), [documentation](integrations/water_heater#increase-temperature) 📚

## Water heater: Decrease temperature

Turns a water heater's setpoint down a step, within its limits. _#water_heater_ _#colder_

`water_heater.decrease_temperature`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=water_heater.decrease_temperature), [documentation](integrations/water_heater#decrease-temperature) 📚

## Wait for a condition

Waits until a condition is true, and carries on straight away if it already is. Takes the ordinary condition building blocks, so it needs no template. _#wait_ _#condition_

`spook.wait_for_condition`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.wait_for_condition), [documentation](other-features#wait-for-a-condition) 📚

## Boo!

This action call will just always spook the hell out of Home Assistant. Home Assistant will shit its pants and abort the automation or script. _#spooked_

`spook.boo`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.boo), [documentation](other-features#boo) 📚

## Delete all orphaned entities

Deletes all orphaned entities that no longer have an integration that claim/provide them. Please note, if the integration was just removed, it might need a restart for Home Assistant to realize they are orphaned. _#annie_

`homeassistant.delete_all_orphaned_entities`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_all_orphaned_entities), [documentation](entities#delete-all-orphaned-entities) 📚

(device-disable)=

## Device: Disable

This action can be used to disable a device on the fly. _#whatever_

`homeassistant.disable_device`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_device), [documentation](devices#disable-a-device) 📚

## Device: Enable

Guess what... this action does the reverse of [](#device-disable). _#noway_

`homeassistant.enable_device`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_device), [documentation](devices#enable-a-device) 📚

(entity-disable)=

## Entity: Disable

This action can be used to disable a entity on the fly. _#rocketship_

`homeassistant.disable_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_entity), [documentation](entities#disable-an-entity) 📚

## Entity: Enable

Really... this action does the reverse of [](#entity-disable). _#true_

`homeassistant.enable_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_entity), [documentation](entities#enable-an-entity) 📚

(entity-hide)=

## Entity: Hide

This action can be used to hide a entity on the fly. _#secret_

`homeassistant.hide_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.hide_entity), [documentation](entities#hide-an-entity) 📚

## Entity: Unhide

Do the math... this action does the reverse of [](#entity-hide). _#reveal_

`homeassistant.unhide_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.unhide_entity), [documentation](entities#unhide-an-entity) 📚

## Entity: Rename

This action can be used to rename an entity on the fly. _#LookMaNewName_

`homeassistant.rename_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.rename_entity), [documentation](entities#rename-an-entity) 📚

## Entity: Set icon

Give an entity another icon, or its own back. _#newlook_

`homeassistant.set_entity_icon`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.set_entity_icon), [documentation](entities#set-the-icon-of-an-entity) 📚

## Entity: Add an alias

Another name a voice assistant knows an entity by. _#akaalias_

`homeassistant.add_alias_to_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_alias_to_entity), [documentation](entities#add-an-alias-to-an-entity) 📚

## Entity: Remove an alias

One name fewer for an entity to answer to. _#nevercallmethat_

`homeassistant.remove_alias_from_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_alias_from_entity), [documentation](entities#remove-an-alias-from-an-entity) 📚

## Entity: Set aliases

All the names an entity answers to, in one go. _#akaalias_

`homeassistant.set_entity_aliases`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.set_entity_aliases), [documentation](entities#set-aliases-for-an-entity) 📚

(entity-expose-to-assistants)=

## Entity: Expose to assistants

Lets your voice assistants see an entity that was hidden from them. _#saymyname_

`homeassistant.expose_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.expose_entity), [documentation](entities#expose-an-entity-to-assistants) 📚

## Entity: Stop exposing to assistants

Takes an entity back out of a voice assistant's reach. This action does the reverse of [](#entity-expose-to-assistants). _#neverheardofher_

`homeassistant.unexpose_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.unexpose_entity), [documentation](entities#stop-exposing-an-entity-to-assistants) 📚

## Entity: Update ID

This action can be used to update the ID of an entity on the fly. _#secret_

`homeassistant.update_entity_id`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.update_entity_id), [documentation](entities#update-an-entitys-id) 📚

## Floors: Create a floor

Instantly create a new floor in your home. _#StackItUp_

`homeassistant.create_floor`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_floor), [documentation](floors#create-a-floor) 📚

## Floors: Delete a floor

Just like that, a whole floor is gone. _#Illusionist_

`homeassistant.delete_floor`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_floor), [documentation](floors#delete-a-floor) 📚

## Floors: Add an alias to a floor

Adds an alias (or multiple aliases) to a floor. _#aka_

`homeassistant.add_alias_to_floor`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_alias_to_floor), [documentation](floors#add-an-alias-to-a-floor) 📚

## Floors: Remove an alias from a floor

Removes an alias (or multiple aliases) from a floor. _#broom_

`homeassistant.remove_alias_from_floor`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_alias_from_floor), [documentation](floors#remove-an-alias-from-a-floor) 📚

## Floors: Set aliases for a floor

Sets the aliases for a floor. _#useless_

`homeassistant.set_floor_aliases`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.set_floor_aliases), [documentation](floors#set-aliases-for-a-floor) 📚

## Floors: Add an area to a floor

Dynamically add/move an area to a new floor. _#moveit_

`homeassistant.add_area_to_floor`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_area_to_floor), [documentation](floors#add-an-area-to-a-floor) 📚

## Floors: Remove an area from a floor

Dynamically remove an area from a floor. _#poef_

`homeassistant.remove_area_from_floor`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_area_from_floor), [documentation](floors#remove-an-area-from-a-floor) 📚

## List all orphaned database entities

Hands back every entity your recorder still has rows for but which no longer exists, so you can look before you delete. _#showmethebodies_

`homeassistant.list_orphaned_database_entities`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.list_orphaned_database_entities), [documentation](entities#list-all-orphaned-database-entities) 📚

## Ignore all discovered devices & services

Click ignore on all discovered items on the integration dashboard; optionally only for specific integration (like, `bluetooth`). _#talktothehand_

`homeassistant.ignore_all_discovered`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.ignore_all_discovered), [documentation](integrations#ignore-all-discovered-devices-services) 📚

## Counter: Create

Creates a counter helper without a trip to the helpers page. _#outofthinair_

`counter.create`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=counter.create), [documentation](integrations/counter#create-a-counter) 📚

## Counter: Delete

Deletes counter helpers made in the UI, or with `counter.create`. _#countmeout_

`counter.delete`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=counter.delete), [documentation](integrations/counter#delete-a-counter) 📚

## Humidifier: Increase humidity

Turns a humidifier's target humidity up a step, within its limits. _#humidifier_ _#wetter_

`humidifier.increase_humidity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=humidifier.increase_humidity), [documentation](integrations/humidifier#increase-humidity) 📚

## Humidifier: Decrease humidity

Turns a humidifier's target humidity down a step, within its limits. _#humidifier_ _#drier_

`humidifier.decrease_humidity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=humidifier.decrease_humidity), [documentation](integrations/humidifier#decrease-humidity) 📚

## Input boolean: Create

Creates an input boolean helper without a trip to the helpers page. _#outofthinair_

`input_boolean.create`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_boolean.create), [documentation](integrations/input_boolean#create-an-input-boolean) 📚

## Input boolean: Delete

Deletes input boolean helpers made in the UI, or with `input_boolean.create`. _#flipoff_

`input_boolean.delete`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_boolean.delete), [documentation](integrations/input_boolean#delete-an-input-boolean) 📚

## Input button: Create

Creates an input button helper without a trip to the helpers page. _#outofthinair_

`input_button.create`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_button.create), [documentation](integrations/input_button#create-an-input-button) 📚

## Input button: Delete

Deletes input button helpers made in the UI, or with `input_button.create`. _#unpressed_

`input_button.delete`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_button.delete), [documentation](integrations/input_button#delete-an-input-button) 📚

## Input datetime: Create

Creates an input datetime helper without a trip to the helpers page. _#outofthinair_

`input_datetime.create`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_datetime.create), [documentation](integrations/input_datetime#create-an-input-datetime) 📚

## Input datetime: Delete

Deletes input datetime helpers made in the UI, or with `input_datetime.create`. _#outoftime_

`input_datetime.delete`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_datetime.delete), [documentation](integrations/input_datetime#delete-an-input-datetime) 📚

## Input number: Create

Creates an input number helper without going anywhere near the helpers page. _#outofthinair_

`input_number.create`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.create), [documentation](integrations/input_number#create-an-input-number) 📚

## Input number: Delete

Removes an input number helper you created earlier. _#nevermind_

`input_number.delete`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.delete), [documentation](integrations/input_number#delete-an-input-number) 📚

## Input number: Decrease value

Override of the existing action, which provides the option to specify the amount to decrease the value by. _#evenlower_

`input_number.decrement`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.decrement), [documentation](integrations/input_number#decrease-value) 📚

## Input number: Increase value

Override of the existing action, which provides the option to specify the amount to increase the value by. _#moreoptions_

`input_number.increment`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.increment), [documentation](integrations/input_number#increase-value) 📚

## Input number: Set maximum value

Set the value of an input number entity to the maximum value. _#maxout_

`input_number.max`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.max), [documentation](integrations/input_number#set-value-to-maximum) 📚

## Input number: Set minimum value

Set the value of an input number entity to the maximum value.

`input_number.min`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.min), [documentation](integrations/input_number#set-value-to-minimum) 📚

## Input select: Create

Creates an input select helper without a trip to the helpers page. _#outofthinair_

`input_select.create`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.create), [documentation](integrations/input_select#create-an-input-select) 📚

## Input select: Delete

Deletes input select helpers made in the UI, or with `input_select.create`. _#nochoice_

`input_select.delete`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.delete), [documentation](integrations/input_select#delete-an-input-select) 📚

## Input select: Select random option

This action selects a random option from the list of options of a select entity. Optionally this can be limited to a set of given options. _#shuffle_

`input_select.random`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.random), [documentation](integrations/input_select#select-random-option) 📚

## Input select: Reverse options

Reverses the order of the selectable options for an input select entity, back to front, so a list that grows at the end has its newest at the top. _#reverse_ _#order_

`input_select.reverse`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.reverse), [documentation](integrations/input_select#reverse-options) 📚

## Input select: Shuffle options

Shuffles the list of selectable options for an input select entity. _#31254_

`input_select.shuffle`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.shuffle), [documentation](integrations/input_select#shuffle-options) 📚

## Input select: Sort options

Sorts the list of selectable options for an input select entity. _#12345_

`input_select.sort`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.sort), [documentation](integrations/input_select#sort-options) 📚

(integration-disable)=

## Input text: Create

Creates an input text helper without a trip to the helpers page. _#outofthinair_

`input_text.create`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_text.create), [documentation](integrations/input_text#create-an-input-text) 📚

## Input text: Delete

Deletes input text helpers made in the UI, or with `input_text.create`. _#nomorewords_

`input_text.delete`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_text.delete), [documentation](integrations/input_text#delete-an-input-text) 📚

## Integration: Disable

This action can be used to disable an integration entry (those you see on your integrations dashboard) on the fly. _#bye_

`homeassistant.disable_config_entry`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_config_entry), [documentation](integrations#disable-an-integration) 📚

## Integration: Enable

Be amazed... this action does the reverse of [](#integration-disable). _#mindblown_

`homeassistant.enable_config_entry`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_config_entry), [documentation](integrations#enable-an-integration) 📚

(integration-disable-polling-for-updates)=

## Integration: Disable polling for updates

This action can be used to disable polling for updates on an integration entry (those you see on your integrations dashboard). _#stopit_

`homeassistant.disable_polling`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_polling), [documentation](integrations#disable-polling-for-updates) 📚

## Integration: Enable polling for updates

This action can be used to enable polling for updates on an integration entry (those you see on your integrations dashboard). This service does the reverse of [](#integration-disable-polling-for-updates) _#poking_

`homeassistant.enable_polling`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_polling), [documentation](integrations#enable-polling-for-updates) 📚

## Categories: Create a category

Make a new category for automations, scripts, scenes, or helpers. _#FileIt_

`homeassistant.create_category`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_category), [documentation](categories#create-a-category) 📚

## Categories: Update a category

Rename a category, or give it another icon, without emptying it first. _#Relabel_

`homeassistant.update_category`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.update_category), [documentation](categories#update-a-category) 📚

## Categories: Delete a category

The category goes, and whatever was in it is left loose. _#Unfiled_

`homeassistant.delete_category`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_category), [documentation](categories#delete-a-category) 📚

## Categories: Add a category to an entity

Puts automations, scripts, scenes, or helpers in a category. _#FileIt_

`homeassistant.add_category_to_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_category_to_entity), [documentation](categories#add-a-category-to-an-entity) 📚

## Categories: Remove a category from an entity

Takes automations, scripts, scenes, or helpers out of a category. _#Unfile_

`homeassistant.remove_category_from_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_category_from_entity), [documentation](categories#remove-a-category-from-an-entity) 📚

## Labels: Create a label

Instantly create a new label in your home. _#LabelMaker_

`homeassistant.create_label`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_label), [documentation](labels#create-a-label) 📚

## Labels: Update a label

Changes a label without deleting it first, so it stays on everything it was on. _#facelift_

`homeassistant.update_label`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.update_label), [documentation](labels#update-a-label) 📚

## Labels: Delete a label

Just like that, a whole label is gone. _#RipItOff_

`homeassistant.delete_label`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_label), [documentation](labels#delete-a-label) 📚

## Labels: Add a label to an area

Adds a label (or multiple labels) to an area. _#TagIt_

`homeassistant.add_label_to_area`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_label_to_area), [documentation](labels#add-a-label-to-an-area) 📚

## Labels: Remove a label from an area

Removes a label (or multiple labels) from an area. _#UntagIt_

`homeassistant.remove_label_from_area`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_label_from_area), [documentation](labels#remove-a-label-from-an-area) 📚

## Labels: Add a label to a device

Adds a label (or multiple labels) to a device. _#TagIt_

`homeassistant.add_label_to_device`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_label_to_device), [documentation](labels#add-a-label-to-a-device) 📚

## Labels: Remove a label from a device

Removes a label (or multiple labels) from a device. _#UntagIt_

`homeassistant.remove_label_from_device`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_label_from_device), [documentation](labels#remove-a-label-from-a-device) 📚

## Labels: Add a label to an entity

Adds a label (or multiple labels) to an entity. _#TagIt_

`homeassistant.add_label_to_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_label_to_entity), [documentation](labels#add-a-label-to-an-entity) 📚

## Labels: Remove a label from an entity

Removes a label (or multiple labels) from an entity. _#UntagIt_

`homeassistant.remove_label_from_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_label_from_entity), [documentation](labels#remove-a-label-from-an-entity) 📚

## Number: Decrease value

Decrease the value of a number entity, either by a single step or by a provided amount. _#downboy_

`number.decrement`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=number.decrement), [documentation](integrations/number#decrease-value) 📚

## Number: Increase value

Increase the value of a number entity, either by a single step or by a provided amount. _#up #greatmovie_

`number.increment`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=number.increment), [documentation](integrations/number#increase-value) 📚

## Number: Set maximum value

Set the value of a number entity to the maximum value. _#maxout_

`number.max`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=number.max), [documentation](integrations/number#set-value-to-maximum) 📚

## Number: Set minimum value

Set the value of a number entity to its minimum value. _#lowout_

`number.min`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=number.min), [documentation](integrations/number#set-value-to-minimum) 📚

## Person: Add a device tracker

Adds a device tracker to a person. _#bigbrother_

`person.add_device_tracker`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=person.add_device_tracker), [documentation](integrations/person#add-a-device-tracker) 📚

## Person: Remove a device tracker

Removes a device tracker from a person. _#privacy_

`person.remove_device_tracker`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=person.remove_device_tracker), [documentation](integrations/person#remove-a-device-tracker) 📚

## Random fail

This action call will randomly fail (and thus randomly stop your automation or script). Especially combined with `continue_on_error: true` this can be a great way to add useless action to your automation or script. _#random_

`spook.random_fail`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.random_fail), [documentation](other-features#random-fail) 📚

## Recorder: Import statistics

Advanced action to directly inject historical statistics data into the recorder's long-term stats database. _#easy_

`recorder.import_statistics`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=recorder.import_statistics), [documentation](integrations/recorder#import-statistics) 📚

## Repairs: Create issue

Battery empty? Raise an issue in Home Assistant Repairs. Although, you should probably just use a notification for this. _#issues_

`repairs.create`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.create), [documentation](integrations/repairs#create-issue) 📚

## Repairs: Ignore all issues

Whatever issue is bothering you, just ignore it all, and all your problems will magically be gone. _#allgood_

`repairs.ignore_all`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.ignore_all), [documentation](integrations/repairs#ignore-all-issues) 📚

## Repairs: List issues

What is still broken, as a list, for an automation or a dashboard of your own. _#todolist_

`repairs.list`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.list), [documentation](integrations/repairs#list-issues) 📚

## Repairs: Remove issue

Removes an issue from Home Assistant Repairs. Can only remove repair issues that have been created using the `repairs.create` action. _#trashit_

`repairs.remove`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.remove), [documentation](integrations/repairs#remove-issue) 📚

## Repairs: Unignore all issues

Will unignore all issues marked ignored and shows them all again. _#faceit_

`repairs.unignore_all`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.unignore_all), [documentation](integrations/repairs#unignore-all-issues) 📚

## Restart

Extends the existing restart action with a "force" option. Because forcing is always a good idea. _#hammer_

`homeassistant.restart`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.restart), [documentation](misc#restart) 📚

## Select: Select random option

This action selects a random option from the list of options of a select entity. Optionally this can be limited to a set of given options. _#random_

`select.random`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=select.random), [documentation](integrations/select#select-random-option) 📚

## Sensor: Set display precision

Sets how many decimals a sensor shows, on as many sensors as you like at once. _#decimated_

`sensor.set_display_precision`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=sensor.set_display_precision), [documentation](integrations/sensor#set-display-precision) 📚

## Timer: Create

Creates a timer helper without a trip to the helpers page. _#outofthinair_

`timer.create`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.create), [documentation](integrations/timer#create-a-timer) 📚

## Timer: Delete

Deletes timer helpers made in the UI, or with `timer.create`. _#timesup_

`timer.delete`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.delete), [documentation](integrations/timer#delete-a-timer) 📚

## Timer: Set duration

Set the duration for a timer entity. _#timeflies_

`timer.set_duration`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.set_duration), [documentation](integrations/timer#set-duration) 📚

## To-do list: Move item

Moves an item in a to-do list to the top, the bottom, or after another item, the way dragging it in the interface does. _#todo_ _#reorder_

`todo.move_item`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=todo.move_item), [documentation](integrations/todo#move-item) 📚

++(user-disable)=

## User: Disable

This action can be used to disable a user account on the fly, preventing them from logging in. _#lockout_

`homeassistant.disable_user`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_user), [documentation](users#disable-a-user) 📚

## User: Enable

Guess what... this action does the reverse of [](#user-disable). _#welcome_

`homeassistant.enable_user`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_user), [documentation](users#enable-a-user) 📚

(zone-create)=

## Zone: Create

Creates a zone on the fly, wherever you like. _#roomforonemore_

`zone.create`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=zone.create), [documentation](integrations/zone#create-a-zone) 📚

## Zone: Update

Moves a zone, or resizes it, without touching the map yourself. This action changes a zone made by [](#zone-create), or any other zone you created in the UI. _#movingday_

`zone.update`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=zone.update), [documentation](integrations/zone#update-a-zone) 📚

## Zone: Delete

Makes a zone disappear. _#offthemap_

`zone.delete`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=zone.delete), [documentation](integrations/zone#delete-a-zone) 📚
