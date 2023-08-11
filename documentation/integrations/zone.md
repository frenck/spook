---
subject: Enhanced integrations
title: Zone
subtitle: Time to zone out and relax 📍
thumbnail: ../images/integrations/zone/example.png
description: Spook enhances the zone integration, by adding a services that will allow you to dynamically create and update zones.
date: 2023-08-11T19:25:08+02:00
---

```{image} https://brands.home-assistant.io/zone/logo.png
:alt: The Home Assistant zone icon
:width: 250px
:align: center
```

<br><br>

A zone in {term}`Home Assistant` is a virtual representation of a physical space. Think of it as drawing a circle on a map; that circle represents a zone. Zones are used to track the location of people and devices but can also be used to trigger {term}`automations <automation>` based on entering or leaving a zone.

Spook adds new services to the zone integrations that allow you to manage and modify them using automations dynamically.

```{figure} ../images/integrations/zone/example.png
:name: example
:alt: Screenshot of the recorder import statistics service call in the developer tools.
:align: center

Spook adds a service that allows importing data into the recorder.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Services

Spook adds the following new service to your Home Assistant instance:

### Create a zone

Adds a new zone to your Home Assistant instance.

```{figure} ../images/integrations/zone/create.png
:alt: Screenshot of the zone create service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Zone: Create a zone 👻
* - {term}`Service name`
  - `zone.create`
* - {term}`Service targets`
  - No targets
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=zone.create)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=zone.create)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `name`
  - {term}`string <string>`
  - Yes
  - `Statue of Liberty`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:map-marker`
* - `latitude`
  - {term}`float <float>`
  - Yes
  - `40.6892494`
* - `longitude`
  - {term}`float <float>`
  - Yes
  - -74.0445004
* - `radius`
  - {term}`float <float>`
  - No
  - 100
```

The `radius` attribute must be entered in meters.

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: zone.create
data:
  name: "Statue of Liberty"
  icon: mdi:human-female-dance
  latitude: 40.6892494
  longitude: -74.0445004
  radius: 250
```

:::

### Update a zone

Updates properties of an existing zone.

:::{note}
Zones that are created and managed using manual YAML configuration cannot be updated.
:::

```{figure} ../images/integrations/zone/update.png
:alt: Screenshot of the zone update service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Zone: Update a zone 👻
* - {term}`Service name`
  - `zone.update`
* - {term}`Service targets`
  - No targets
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=zone.update)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=zone.update)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `entity_id`
  - {term}`string <string>`
  - Yes
  - `zone.statue_of_liberty`
* - `name`
  - {term}`string <string>`
  - No
  - `Statue of Liberty`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:map-marker`
* - `latitude`
  - {term}`float <float>`
  - No
  - `40.6892494`
* - `longitude`
  - {term}`float <float>`
  - No
  - -74.0445004
* - `radius`
  - {term}`float <float>`
  - No
  - 100
```

The `radius` attribute must be entered in meters. Only the parameters that are provided will be updated. Other parameters will remain unchanged.

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: zone.update
data:
  entity_id: zone.statue_of_liberty
  name: "Statue of Liberty, New York"
  radius: 250
```

:::

### Delete a zone

Deletes a zone from Home Assistant

:::{note}
Zones that are created and managed using manual YAML configuration cannot be deleted.
:::

```{figure} ../images/integrations/zone/delete.png
:alt: Screenshot of the zone delete service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Zone: Delete a zone 👻
* - {term}`Service name`
  - `zone.delete`
* - {term}`Service targets`
  - No targets
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=zone.delete)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=zone.delete)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `entity_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `zone.statue_of_liberty`
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: zone.delete
data:
  entity_id: zone.statue_of_liberty
```

Or delete multiple at ones:

```{code-block} yaml
:linenos:
service: zone.delete
data:
  entity_id:
    - zone.central_park
    - zone.statue_of_liberty
```

:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- You could use these services to dynamically create and update zones around a car or a person using automations. Using these you could tell who is close to the car or notify if you are near a certain person.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas and support

If you have an idea on how to further enhance this integration, for example, by adding a new service, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
