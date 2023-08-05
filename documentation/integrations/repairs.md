---
subject: Enhanced integrations
title: Repairs
subtitle: Can we fix it? No, we are not Bob the Builder. 👷
thumbnail: ../images/integrations/repairs/example.png
description: Spook adds some new services to the repairs integration, which allows you to create your own repairs issues and manage them.
date: 2023-06-30T20:36:04+02:00
---

```{image} https://brands.home-assistant.io/repairs/logo.png
:alt: The Home Assistant repairs icon
:width: 250px
:align: center
```

<br><br>

The {term}`repairs <repair>` {term}`integration <integration>` brings in the repairs dashboads into {term}`Home Assistant`, which informs you about issues found in your Home Assistant instance. These raises repairs issues are provided by other integrations (like Spook 👻 itself), so you can keep your system healthy and in a working state.

The issues raised, are always applying to your situation and system, so you can be sure the issues raised are relevant to you.

Spook enhances the integration, by providing services that allows you to raise your own repairs issues and manage them.

```{figure} ../images/integrations/repairs/example.png
:name: example
:alt: Screenshot of the repairs services Spook adds to Home Assistant, taken from the developer tools.
:align: center

Spook adds a bunch of new services to the repairs integration, so you can create your own.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Services

Spook adds the following new service to your Home Assistant instance:

### Create issue

Create and raise your own issues in the repairs dashboard. For example,
to raise low battery reports for your devices, or to raise an issue when
a device becomes unreachable.

```{figure} ../images/integrations/repairs/create.png
:name: creates
:alt: Screenshot of the repairs create issue service call in the developer tools.
:align: center

Spook adds a service to create your own repairs issues.
```

```{figure} ../images/integrations/repairs/create_result.png
:name: creates_result
:alt: Screenshot of the repairs issue raised by the previous screenshot.
:align: center

The result of the service call from the previous screenshot.
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Repairs: Create issue 👻
* - {term}`Service name`
  - `repairs.create`
* - {term}`Service targets`
  - No targets
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.create)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.create)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `title`
  - {term}`string <string>`
  - Yes
* - `description`
  - {term}`string <string>`
  - Yes
* - `issue_id`
  - {term}`string <string>`
  - No
  - Randomly generated
* - `domain`
  - {term}`string <string>`
  - No
  - Integration domain, defaults to `spook`.
* - `severity`
  - {term}`string <string>`
  - No
  - `warning` (default), `error` or `critical`
* - `persistent`
  - {term}`boolean <boolean>`
  - No
  - `false`
```

Setting an `issue_id` can be helpful, as you can use it to update the issue later on. If you create an issue with the same issue ID again, it will update the issue with the new data. The issue ID can also be used to remove the issue with the `repairs.remove` service.

The `domain` can be set to any integration domains, for example, if you set it to `automation`, the issue will show up as an repair issue for the automation integration. It defaults to the `spook` integration when not provided.

The `persistent` attribute can set to `true` to indicate it should survive a Home Assistant restart. It defaults to `false` when not provided.

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: repairs.create
data:
  title: "Low battery"
  description: |-
    Found a low battery in your home. The following device is low on energy:

    The bed vertical movement sensor.
  issue_id: "low-battery"
```

:::

### Ignore all issues

Adds a single service to ignore all issues currently raised in the repairs dashboard.

```{figure} ../images/integrations/repairs/ignore_all.png
:name: ignore_all
:alt: Screenshot of the repairs ignore all issues service call in the developer tools.
:align: center

Spook can help you ignoring all issues at once.
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Repairs: Ignore all issues 👻
* - {term}`Service name`
  - `repairs.ignore_all`
* - {term}`Service targets`
  - No targets
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.ignore_all)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.ignore_all)
```

:::{tip}
This might seem like a helpful service at times, however, ignoring an issue, is not a solution. It is better to fix the issue, or to remove the integration that is causing the issue, or report an bug.

Every issue raise by Home Assistant (and also Spook), should be solveable, if not, it is a bug and should be reported.
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: repairs.ignore_all
```

:::

### Remove issue

Remove an issue from the repairs integration.

```{figure} ../images/integrations/repairs/remove.png
:name: remove
:alt: Screenshot of the repairs remove issue service call in the developer tools.
:align: center

A service to allow the removal of created issues.
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Repairs: Remove issue 👻
* - {term}`Service name`
  - `repairs.remove`
* - {term}`Service targets`
  - No targets
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.remove)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.remove)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `issue_id`
  - {term}`string <string>`
  - Yes
```

The `issue_id` must be an issue ID you have used with the `repairs.create` service.

:::{note}
This service will not remove issues raised by Home Assistant itself, only issues raised using the the `repairs.create` service.
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: repairs.remove
data:
  issue_id: "low-battery"
```

:::

### Unignore all issues

Adds a single service to unignore all repair issues currently still active (but previously ignored).

```{figure} ../images/integrations/repairs/unignore_all.png
:name: ignore_all
:alt: Screenshot of the repairs unignore all issues service call in the developer tools.
:align: center

Spook can help you unignoring all issues at once.
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Repairs: Unignore all issues 👻
* - {term}`Service name`
  - `repairs.unignore_all`
* - {term}`Service targets`
  - No targets
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.unignore_all)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.unignore_all)
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: repairs.unignore_all
```

:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Create and raising your own issues has lots of possibilities. For example, you could create an issue when a device is low on battery, or when a device is offline for a long time. You could also create an issue when a device is not responding to commands, or when a device is not responding to commands in a certain time frame. The possibilities are endless.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one, or stubled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas and support

If you have an idea on how to futher enhance this integration, for example by adding a new service, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've ran into an bug? Please check the [](../support) page on where to go for help.
