---
subject: Reference
title: Provided Home Assistant services
short_title: Services
subtitle: At your service. 🫡
thumbnail: images/usage/services_example.png
description: Spook provides quite a lot of new services to Home Assistant. This reference pages lists them all, and points you to the right documentation.
date: 2023-06-30T09:31:26+02:00
---

Spook provides quite a lot of new services to Home Assistant. This reference pages lists them all, and points you to the right documentation for that service.

## Areas: Create an area

Instantly create new rooms in your home. _#BobTheBuilder_

`homeassistant.create_area`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_area), [documentation](areas#create-an-area) 📚

## Areas: Delete an area

Just like that, you made an area of your home dissapear. _#DemolitionMan_

`homeassistant.delete_area`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_area), [documentation](areas#delete-an-area) 📚

## Areas: Add an alias to an area

Adds an alias (or multiple aliases) to an area. _#aka_

`homeassistant.add_alias_to_area`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_alias_to_area), [documentation](areas#add-an-alias-to-an-area)

## Areas: Remove an alias from an area

Removes an alias (or multiple aliases) from an area. _#broom_

`homeassistant.remove_alias_from_area`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_alias_from_area), [documentation](areas#remove-an-alias-from-an-area)

## Areas: Set aliases for an area

Sets the aliases for an area. _#useless_

`homeassistant.set_area_aliases`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.set_area_aliases), [documentation](areas#set-aliases-for-an-area)

## Areas: Add a device to an area

Dynamicaly add/move a device to an new area. _#moveit_

`homeassistant.add_device_to_area`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_device_to_area), [documentation](areas#add-a-device-to-an-area)

## Areas: Remove a device from an area

Dynamicaly remove a device from an area. _#poef_

`homeassistant.remove_device_from_area`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_device_from_area), [documentation](areas#remove-a-device-from-an-area)

## Areas: Add an entity to an area

Dynamicaly add/move an entity to an area. _#bam_

`homeassistant.add_entity_to_area`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_entity_to_area), [documentation](areas#add-an-entity-to-an-area)

## Areas: Remove an entity from an area

Dynamicaly remove an entity from an area. _#AaaaandItIsGone_

`homeassistant.remove_entity_from_area`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_entity_from_area), [documentation](areas#remove-an-entity-from-an-area)

## Blueprint: Import Blueprint

Downloads and imports a automation/script Blueprint, directly from the URL you pass into this service. _#noquestionsasked_

`blueprint.import`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=blueprint.import), [documentation](integrations/blueprint#import-blueprint) 📚

## Boo!

This service call will just always spook the hell out of Home Assistant. Home Assistant will shit its pants and abort the automation or script. _#spooked_

`spook.boo`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.boo), [documentation](other-features#boo) 📚

## Input number: Decrease value

Override of the existing service, which provides the option to specify the amount to decrease the value by. _#evenlower_

`input_number.decrement`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.decrement), [documentation](integrations/input_number#decrease-value) 📚

## Input number: Increase value

Override of the existing service, which provides the option to specify the amount to increase the value by. _#moreoptions_

`input_number.increment`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.increment), [documentation](integrations/input_number#increase-value) 📚

## Input number: Set maximum value

Set the value of an input number entity to the maximum value. _#maxout_

`input_number.max`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.max), [documentation](integrations/input_number#set-value-to-maximum) 📚

## Input number: Set minimum value

Set the value of an input number entity to the maximum value.

`input_number.min`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_number.min), [documentation](integrations/input_number#set-value-to-minimum) 📚

## Input select: Select random option

This service select a random option from the list of options of a select entity. Optionally this can be limited to a set of given options. _#shuffle_

`input_select.random`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.random), [documentation](integrations/input_select#select-random-option) 📚

## Input select: Shuffle options

Shuffles the list of selectable options for an input select entity. _#31254_

`input_select.shuffle`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.shuffle), [documentation](integrations/input_select#shuffle-options) 📚

## Input select: Sort options

Sorts the list of selectable options for an input select entity. _#12345_

`input_select.sort`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=input_select.sort), [documentation](integrations/input_select#sort-options) 📚

## Number: Decrease value

Decrease the value of a number entity, either by a single step or by a provided amount. _#downboy_

`number.decrement`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=number.decrement), [documentation](integrations/number#decrease-value) 📚

## Number: Increase value

Increase the value of a number entity, either by a single step or by a provided amount. _#up #greatmovie_

`number.increment`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=number.increment), [documentation](integrations/number#increase-value) 📚

## Number: Set maximum value

Set the value of a number entity to the maximum value. _#maxout_

`number.max`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=number.max), [documentation](integrations/number#set-value-to-maximum) 📚

## Number: Set minimum value

Set the value of a number entity to its minimum value. _#lowout_

`number.min`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=number.min), [documentation](integrations/number#set-value-to-minimum) 📚

## Random fail

This service call will randomly fail (and thus randomly stop your automation or script). Especially combined with `continue_on_error: true` this can be a great way add a useless service calls to your automation or script. _#random_

`spook.random_fail`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.random_fail), [documentation](other-features#random-fail) 📚

## Recorder: Import statistics

Advanced service to directly inject historical statistics data into the recorder long-term stats database. _#easy_

`recorder.import_statistics`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=recorder.import_statistics), [documentation](integrations/recorder#import-blueprint) 📚

## Repairs: Create issue

Battery empty? Raise a issue in Home Assistant Repairs. Although, you should probably just use a notification for this. _#issues_

`repairs.create`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.create), [documentation](integrations/repairs#create-issue) 📚

## Repairs: Ignore all issues

Whatever issue is bothering you, just ignore it all and all your problems will magically be gone. _#allgood_

`repairs.ignore_all`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.ignore_all), [documentation](integrations/repairs#ignore-all-issues) 📚

## Repairs: Remove issue

Removes a issue from Home Assistant Repairs. Can only remove repair issues that have been created using the `repairs.create` service. _#trashit_

`repairs.remove`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.remove), [documentation](integrations/repairs#remove-issue) 📚

## Repairs: Unignore all issues

Will unignore all issues marked ignored, and shows them all again. _#faceit_

`repairs.unignore_all`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.unignore_all), [documentation](integrations/repairs#unignore-all-issues) 📚

## Select : Select random option

This service select a random option from the list of options of a select entity. Optionally this can be limited to a set of given options. _#random_

`select.random`, [try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=select.random), [documentation](integrations/select#select-random-option) 📚
