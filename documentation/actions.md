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

## Blueprint: Import Blueprint

Downloads and imports an automation/script blueprint, directly from the URL you pass into this action. _#noquestionsasked_

`blueprint.import`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=blueprint.import), [documentation](integrations/blueprint#import-blueprint) 📚

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

`homeassistant.disable_device`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_device), [documentation](devices#disable-a-device) 📚

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

## Entity: Update ID

This action can be used to update the ID of an entity on the fly. _#secret_

`homeassistant.hide_entity`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.update_entity_id), [documentation](entities#update-an-entitys_id) 📚

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

## Ignore all discovered devices & services

Click ignore on all discovered items on the integration dashboard; optionally only for specific integration (like, `bluetooth`). _#talktothehand_

`homeassistant.ignore_all_discovered`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.ignore_all_discovered), [documentation](integrations#ignore-all-discovered-devices-services) 📚

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

## Input select: Select random option

This action selects a random option from the list of options of a select entity. Optionally this can be limited to a set of given options. _#shuffle_

`input_select.random`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.random), [documentation](integrations/input_select#select-random-option) 📚

## Input select: Shuffle options

Shuffles the list of selectable options for an input select entity. _#31254_

`input_select.shuffle`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.shuffle), [documentation](integrations/input_select#shuffle-options) 📚

## Input select: Sort options

Sorts the list of selectable options for an input select entity. _#12345_

`input_select.sort`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.sort), [documentation](integrations/input_select#sort-options) 📚

(integration-disable)=

## Integration: Disable

This action can be used to disable a integration configuration entry (those you see on your integrations dashboard) on the fly. _#bye_

`homeassistant.disable_config_entry`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_config_entry), [documentation](integrations#disable-an-integration) 📚

## Integration: Enable

Be amazed... this action does the reverse of [](#integration-disable). _#mindblown_

`homeassistant.enable_config_entry`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_config_entry), [documentation](integrations#enable-an-integration) 📚

(integration-disable-polling-for-updates)=

## Integration: Disable polling for updates

This action can be used to disable polling for updates on an integration configuration entry (those you see on your integrations dashboard). _#stopit_

`homeassistant.disable_polling`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_polling), [documentation](integrations#disable-polling-for-updates) 📚

## Integration: Enable polling for updates

This action can be used to enable polling for updates on an integration configuration entry (those you see on your integrations dashboard). This service does the reverse of [](#integration-disable-polling-for-updates) _#poking_

`homeassistant.enable_polling`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_polling), [documentation](integrations#enable-polling-for-updates) 📚

## Labels: Create a label

Instantly create a new label in your home. _#LabelMaker_

`homeassistant.create_label`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_label), [documentation](labels#create-a-label) 📚

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

`person.add_device_tracker`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=person.remove_device_tracker), [documentation](integrations/person#remove-a-device-tracker) 📚

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

## Timer: Set duration

Set the duration for a timer entity. _#timeflies_

`timer.set_duration`, [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=timer.set_duration), [documentation](integrations/timer#set-duration) 📚
