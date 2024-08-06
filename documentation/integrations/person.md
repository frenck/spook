---
subject: Enhanced integrations
title: Person
subtitle: Now it gets personal 😱
thumbnail: ../images/integrations/person/example.png
description: Spook adds some new actions to the person integration, which allows you to change device trackers attached to persons in Home Assistant on the fly.
date: 2023-09-22T10:47:44+02:00
---

```{image} https://brands.home-assistant.io/person/logo.png
:alt: The Home Assistant person icon
:width: 250px
:align: center
```

<br><br>

The person {term}`integration <integration>` in {term}`Home Assistant` allows you to track the location of people in your household. It is a collection of device trackers that are grouped together to represent the current location of a person. Additionally, a person may have a user account attached to it, which allows the person to log in to the Home Assistant.

Spook adds some new actions to the person {term}`integration <integration>`, that allows you to dynamically change the device trackers attached to a person in Home Assistant.

```{figure} ../images/integrations/person/example.png
:name: example
:alt: Screenshot of the developer actions tools, listing the new actions for persons.
:align: center

Spook adds some new actions to the person integration.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Add a device tracker

Adds a device tracker to a person.

```{figure} ../images/integrations/person/add_device_tracker.png
:alt: Screenshot of the person add device tracker action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Person: Add a device tracker 👻
* - {term}`Action name`
  - `person.add_device_tracker`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=person.add_device_tracker)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=person.add_device_tracker)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `entity_id`
  - {term}`string <string>`
  - Yes
  - `person.frenck`
* - `device_tracker`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `device_tracker.iphone`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: person.add_device_tracker
data:
    entity_id: person.frenck
    device_tracker: device_tracker.iphone
```

To add multiple device trackers at once, use a list:

```{code-block} yaml
:linenos:
action: person.add_device_tracker
data:
    entity_id: person.frenck
    device_tracker:
      - device_tracker.iphone
      - device_tracker.ipad
```

:::

### Remove a device tracker

Removes a device tracker from a person.

```{figure} ../images/integrations/person/remove_device_tracker.png
:alt: Screenshot of the person remove device tracker action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Person: Remove a device tracker 👻
* - {term}`Action name`
  - `person.remove_device_tracker`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=person.remove_device_tracker)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=person.remove_device_tracker)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `entity_id`
  - {term}`string <string>`
  - Yes
  - `person.frenck`
* - `device_tracker`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `device_tracker.iphone`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: person.remove_device_tracker
data:
    entity_id: person.frenck
    device_tracker: device_tracker.iphone
```

To remove multiple device trackers at once, use a list:

```{code-block} yaml
:linenos:
action: person.remove_device_tracker
data:
    entity_id: person.frenck
    device_tracker:
      - device_tracker.iphone
      - device_tracker.ipad
```

:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Adding/removing temporary device trackers that represent a location of a person. For example, if you have a tracker in a car, you could temporary attach it to a person if you know that person took that car.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
