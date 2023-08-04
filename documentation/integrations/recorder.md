---
subject: Enhanced integrations
title: Recorder
subtitle: Records all the spooky things that happen in your home.
thumbnail: ../images/integrations/recorder/example.png
description: Spook enhances the recorder integration, by adding a service that allows to import data into the recorder.
date: 2023-06-30T20:36:04+02:00
---

```{image} https://brands.home-assistant.io/recorder/logo.png
:alt: The Home Assistant recorder icon
:width: 250px
:align: center
```

<br><br>

The recorder {term}`integration <integration>` in {term}`Home Assistant` is responsible for registering and storing everything that happens in your home. It is the backbone of the history and logbook features in Home Assistant, but also stores information in a long-term format to power things like the energy {term}`dashboard <dashboard>` and other graphs you see in Home Assistant.

```{figure} ../images/integrations/recorder/example.png
:name: example
:alt: Screenshot of the recorder import statistics service call in the developer tools.
:align: center

Spook adds a service that allows to import data into the recorder.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Services

Spook adds the following new service to your Home Assistant instance:

### Import Blueprint

Downloads and imports a automation/script Blueprint, directly from the URL you pass into this service.

```{figure} ../images/integrations/recorder/import.png
:name: import
:alt: Screenshot of the recorder import statistics service call in the developer tools.
:align: center

Spook adds a service that allows to import data into the recorder.
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Recorder: Import statistics 👻
* - {term}`Service name`
  - `recorder.import_statistics`
* - {term}`Service targets`
  - No targets
* - {term}`Service response`
  - No response
* - Spook's influence
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=recorder.import_statistics)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `has_mean`
  - {term}`boolean <boolean>`
  - Yes
* - `has_sum`
  - {term}`boolean <boolean>`
  - Yes
* - `name`
  - {term}`string <string>`
  - No
  - `None`
* - `source`
  - {term}`string <string>`
  - Yes
* - `statistic_id`
  - {term}`string <string>`
  - Yes
* - `unit_of_measurement`
  - {term}`string <string>`
  - No
  - `None`
* - `stats`
  - mapping
  - Yes
```

```{list-table}
:header-rows: 2
* - `stats` attribute mapping
* - Attribute
  - Type
  - Required
  - Default / Example
* - `start`
  - datetime string
  - Yes
* - `mean`
  - float
  - No
* - `min`
  - float
  - No
* - `max`
  - float
  - Yes
* - `last_reset`
  - datetime string
  - No
  - `None`
* - `state`
  - float
  - No
* - `sum`
  - float
  - No
```

More information about the mapping/meaning of fields in the long-term statistics can be found on the [Home Assistant data portal](https://data.home-assistant.io/docs/statistics).

:::{seealso} Example service call in YAML
:class: dropdown

```{code-block} yaml
:linenos:
service: recorder.import_statistics
data:
  has_mean: false
  has_sum: true
  statistic_id: sensor.some_energy_sensor
  source: spook
  unit_of_measurement: kWh
  stats:
    end: "2023-07-03 21:00:00+02:00"
    sum: 123123
:::

:::{warning}
Messing with the recorder directly is not recommended. It is very easy to break things and up with very skwed data. Use this service with caution.
:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Manually import data into the recorder, for example, historical data from a previous system, or a energy provider that provides a CSV file with your historical energy usage.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one, or stubled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas and support

If you have an idea on how to futher enhance this integration, for example by adding a new service, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've ran into an bug? Please check the [](../support) page on where to go for help.
```
