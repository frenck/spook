---
subject: Enhanced integrations
title: Recorder
subtitle: Records all the spooky things that happen in your home.
thumbnail: ../images/integrations/recorder/example.png
description: Spook enhances the recorder integration, by adding an action that allows to import data into the recorder.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/recorder/logo.png
:alt: The Home Assistant recorder icon
:width: 250px
:align: center
```

<br><br>

The recorder {term}`integration <integration>` in {term}`Home Assistant` is responsible for registering and storing everything that happens in your home. It is the backbone of the history and logbook features in Home Assistant but it also keeps information in a long-term format to power things like the energy {term}`dashboard <dashboard>` and other graphs you see in Home Assistant.

```{figure} ../images/integrations/recorder/example.png
:name: example
:alt: Screenshot of the recorder import statistics action in the developer tools.
:align: center

Spook adds an action that allows importing data into the recorder.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Import statistics

Manually import long-term statistics into the recorder database of Home Assistant.

```{figure} ../images/integrations/recorder/import.png
:alt: Screenshot of the recorder import statistics action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Recorder: Import statistics 👻
* - {term}`Action name`
  - `recorder.import_statistics`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=recorder.import_statistics)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=recorder.import_statistics)
```

```{list-table}
:header-rows: 2
* - Action data parameters
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
  - {term}`float <float>`
  - No
* - `min`
  - {term}`float <float>`
  - No
* - `max`
  - {term}`float <float>`
  - Yes
* - `last_reset`
  - datetime string
  - No
  - `None`
* - `state`
  - {term}`float <float>`
  - No
* - `sum`
  - {term}`float <float>`
  - No
```

More information about the mapping/meaning of fields in long-term statistics can be found on the [Home Assistant data portal](https://data.home-assistant.io/docs/statistics).

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: recorder.import_statistics
data:
  has_mean: false
  has_sum: true
  statistic_id: sensor.some_energy_sensor
  source: recorder
  unit_of_measurement: kWh
  stats:
    - start: "2023-07-03 21:00:00+02:00"
      sum: 123123
```

:::

:::{warning}
Messing with the recorder directly is not recommended. It is very easy to break things end up with very skewed data. Use this action with caution.
:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Manually import data into the recorder, for example, historical data from a previous system or an energy provider that provides a CSV file with your historical energy usage.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
