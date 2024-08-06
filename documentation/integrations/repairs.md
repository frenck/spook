---
subject: Enhanced integrations
title: Repairs
subtitle: Can we fix it? No, we are not Bob the Builder. 👷
thumbnail: ../images/integrations/repairs/example.png
description: Spook adds some new actions to the repairs integration, which allows you to create your own repairs issues and manage them.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/repairs/logo.png
:alt: The Home Assistant repairs icon
:width: 250px
:align: center
```

<br><br>

The {term}`repairs <repairs>` {term}`integration <integration>` brings the repairs dashboards into {term}`Home Assistant`, which informs you about issues found in your Home Assistant instance. Other integrations (like Spook 👻 itself) provide these raised repair issues, so you can keep your system healthy and in a working state.

The issues raised always apply to your situation and system, so you can be sure the issues raised are relevant to you.

Spook enhances the integration by providing actions that allow you to raise and manage your own repair issues.

```{figure} ../images/integrations/repairs/example.png
:name: example
:alt: Screenshot of the repairs actions Spook adds to Home Assistant, taken from the developer tools.
:align: center

Spook adds many new actions to the repairs integration so that you can create your own.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

```{figure} ../images/integrations/repairs/devices_entities.png
:alt: Screenshot of the the new Repairs device and its entities in the Home Assistant UI.
:align: center
```

### Buttons

#### Ignore all

_Default {term}`entity ID <Entity ID>`: `button.ignore_all_issues`_

Adds a button to ignore all issues currently raised in the repairs dashboard.

:::{tip}
This might sometimes seem helpful; however, ignoring an issue is not a solution. It is better to fix the issue, remove the integration that is causing it, or report a bug.

Every issue raised by Home Assistant (and also Spook) should be solvable. If not, it is a bug and should be reported.
:::

#### Unignore all

_Default {term}`entity ID <Entity ID>`: `button.unignore_all_issues`_

Adds a button to unignore all repair issues currently still active (but previously ignored).

### Events

#### Repair

_Default {term}`entity ID <Entity ID>`: `event.repair`_

This event entity triggers when a new repair issue is raised, or an existing one is updated or removed.

### Sensors

#### Active issues

_Default {term}`entity ID <Entity ID>`: `sensor.active_issues`_

This sensor shows the number of active issues currently raised in the repairs dashboard.

#### Ignored issues

_Default {term}`entity ID <Entity ID>`: `sensor.ignored_issues`_

This sensor shows the number of ignored issues currently raised in the repairs dashboard.

#### Total issues

_Default {term}`entity ID <Entity ID>`: `sensor.issues`_

This sensor shows the total number of issues known to the repairs dashboard.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Create issue

Create and raise your own issues in the repairs dashboard. For example,
to raise low battery reports for your devices or to raise an issue when
a device becomes unreachable.

```{figure} ../images/integrations/repairs/create.png
:alt: Screenshot of the repairs create issue action in the developer tools.
:align: center
```

```{figure} ../images/integrations/repairs/create_result.png
:alt: Screenshot of the repairs issue raised by the previous screenshot.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Repairs: Create issue 👻
* - {term}`Action name`
  - `repairs.create`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.create)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.create)
```

```{list-table}
:header-rows: 2
* - Action data parameters
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
  - `warning` (default), `error`, or `critical`
* - `persistent`
  - {term}`boolean <boolean>`
  - No
  - `false`
```

Setting an `issue_id` can be helpful, as you can use it to update the issue later on. If you create an issue with the same issue ID again, it will update the issue with the new data. The issue ID can also be used to remove the issue with the `repairs.remove` action.

The `domain` can be set to any integration domain. For example, if you set it to `automation`, the issue will show up as a repair issue for the automation integration. It defaults to the `spook` integration when not provided.

The `persistent` attribute can be set to `true` to indicate it should survive a Home Assistant restart. It defaults to `false` when not provided.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: repairs.create
data:
  title: "Low battery"
  description: |-
    Found a low battery in your home. The following device is low on energy:

    The bed vertical movement sensor.
  issue_id: "low-battery"
```

:::

### Ignore all issues

Adds a single action to ignore all issues currently raised in the repairs dashboard.

```{figure} ../images/integrations/repairs/ignore_all.png
:alt: Screenshot of the repairs ignore all issues action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Repairs: Ignore all issues 👻
* - {term}`Action name`
  - `repairs.ignore_all`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.ignore_all)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.ignore_all)
```

:::{tip}
This might sometimes seem helpful; however, ignoring an issue is not a solution. It is better to fix the issue, remove the integration that is causing it, or report a bug.

Every issue raised by Home Assistant (and also Spook) should be solvable. If not, it is a bug and should be reported.
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: repairs.ignore_all
```

:::

### Remove issue

Remove an issue from the repairs integration.

```{figure} ../images/integrations/repairs/remove.png
:alt: Screenshot of the repairs remove issue action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Repairs: Remove issue 👻
* - {term}`Action name`
  - `repairs.remove`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.remove)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.remove)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `issue_id`
  - {term}`string <string>`
  - Yes
```

The `issue_id` must be an issue ID you have used with the `repairs.create` action.

:::{note}
This action will not remove issues raised by Home Assistant itself, only issues raised using the `repairs.create` action.
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: repairs.remove
data:
  issue_id: "low-battery"
```

:::

### Unignore all issues

Adds a single action to unignore all repair issues currently still active (but previously ignored).

```{figure} ../images/integrations/repairs/unignore_all.png
:alt: Screenshot of the repairs unignore all issues action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Repairs: Unignore all issues 👻
* - {term}`Action name`
  - `repairs.unignore_all`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.unignore_all)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=repairs.unignore_all)
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: repairs.unignore_all
```

:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Creating and raising your own issues has lots of possibilities. For example, you could create an issue when a device is low on battery or when a device is offline for a long time. You could also create an issue when a device is not responding to commands or when a device is not responding to commands in a certain time frame. The possibilities are endless.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
