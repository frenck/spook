---
subject: Core extensions
title: Label management
subtitle: If you liked it then you should have put a label on it 🏷️
date: 2024-04-04T08:50:07+02:00
---

{term}`Labels <label>` in {term}`Home Assistant` can be freely created / be made up by you and used to create your own organizational structure by tagging {term}`devices <device>`, {term}`entities <entity>`, or {term}`areas <area>` with one or more labels. Labels can be used to filter items shows in tables in the user interface, or to target {term}`service calls <service call>` in for example {term}`automations <automation>`, or {term}`scripts <script>`.

Spook provides {term}`services <service>` that allows you to manage and {term}`automate <automation>` the areas in Home Assistant programatically. Great for creating "dynamic" labels, or for creating labels on the fly.

```{figure} ./images/labels/example.png
:alt: Screenshot of the developer service tools, listing the new services to manage labels.
:align: center
```

## Services

Spook adds the following new service to your Home Assistant instance:

### Create a label

Adds a new label to your Home Assistant instance.

```{figure} ./images/labels/create.png
:alt: Screenshot of the create label service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Create an label 👻
* - {term}`Service name`
  - `homeassistant.create_label`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_label)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_label)
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
  - `Battery powered`
* - `description`
  - {term}`string <string>`
  - No
  - `Label to tag all battery powered devices`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:battery`
* - `color`
  - {term}`string <string>`
  - No
  - `indigo`
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.create_label
data:
  name: "Battery powered"
  description: "Label to tag all battery powered devices"
  icon: "mdi:battery"
  color: "indigo"
```

:::

### Delete a label

Delete a new label to your Home Assistant instance.

```{figure} ./images/labels/delete.png
:alt: Screenshot of the delete label service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Delete a label 👻
* - {term}`Service name`
  - `homeassistant.delete_label`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_label)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_label)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `label_id`
  - {term}`string <string>`
  - Yes
  - `battery_powered`
```

:::{tip} Getting an label ID from a label name
:class: dropdown

Not sure what the `label_id` of an label is? The `label_id` field also accepts templates. You can use this template to use the label's name instead:

```yaml
label_id: "{{ label_id('Battery powered') }}"
```

That template will find the label ID of the label with the name "Battery powered".
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.delete_label
data:
  label_id: "battery_powered"
```

Same example, but using the label's name instead of the label ID:

```{code-block} yaml
:linenos:
service: homeassistant.delete_label
data:
  label_id: "{{ label_id('Battery powered') }}"
```

:::

### Add a label to an area

Adds one or more labels(s) to an area.

```{figure} ./images/labels/add_to_area.png
:alt: Screenshot of the add a label to an area service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Add a label to an area 👻
* - {term}`Service name`
  - `homeassistant.add_label_to_area`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_label_to_area)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_label_to_area)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `label_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `living_space`
* - `area_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `living_room`
```

:::{tip} Getting an label ID from a label name
:class: dropdown

Not sure what the `label_id` of an label is? The `label_id` field also accepts templates. You can use this template to use the label's name instead:

```yaml
label_id: "{{ label_id('Living space') }}"
```

That template will find the label ID of the label with the name "Living space".
:::

:::{tip} Getting an area ID from an area name
:class: dropdown

Not sure what the `area_id` of an area is? The `area_id` field also accepts templates. You can use this template to use the area's name instead:

```yaml
area_id: "{{ area_id('Living room') }}"
```

That template will find the area ID of the area with the name "Living room".
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.add_label_to_area
data:
  label_id: "living_space"
  area_id: "living_room"
```

Same example, but using the area's and label's name instead of their IDs:

```{code-block} yaml
:linenos:
service: homeassistant.add_label_to_area
data:
  label_id: "{{ label_id('Living space') }}"
  area_id: "{{ area_id('Living room') }}"
```

You can use multiple labels and areas at once. This will cause
each label to be added to each area:

```{code-block} yaml
:linenos:
service: homeassistant.add_label_to_area
data:
  label_id:
    - "living_space"
    - "chill_zone"
  area_id:
    - "living_room"
    - "games_room"
```

:::

### Remove a label from an area

Removes one or more label(s) from an area.

```{figure} ./images/labels/remove_from_area.png
:alt: Screenshot of the remove a label from an area service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Remove a label from an area 👻
* - {term}`Service name`
  - `homeassistant.remove_label_from_area`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_label_from_area)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_label_from_area)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `label_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `living_space`
* - `area_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `living_room`
```

:::{tip} Getting an label ID from a label name
:class: dropdown

Not sure what the `label_id` of an label is? The `label_id` field also accepts templates. You can use this template to use the label's name instead:

```yaml
label_id: "{{ label_id('Living space') }}"
```

That template will find the label ID of the label with the name "Living space".
:::

:::{tip} Getting an area ID from an area name
:class: dropdown

Not sure what the `area_id` of an area is? The `area_id` field also accepts templates. You can use this template to use the area's name instead:

```yaml
area_id: "{{ area_id('Living room') }}"
```

That template will find the area ID of the area with the name "Living room".
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.remove_label_from_area
data:
  label_id: "living_space"
  area_id: "living_room"
```

Same example, but using the area's and label's name instead of their IDs:

```{code-block} yaml
:linenos:
service: homeassistant.remove_label_from_area
data:
  label_id: "{{ label_id('Living space') }}"
  area_id: "{{ area_id('Living room') }}"
```

You can use multiple labels and areas at once. This will cause
each label to be removed from each area:

```{code-block} yaml
:linenos:
service: homeassistant.remove_label_from_area
data:
  label_id:
    - "living_space"
    - "chill_zone"
  area_id:
    - "living_room"
    - "games_room"
```

:::

### Add a label to a device

Adds one or more labels(s) to a device.

```{figure} ./images/labels/add_to_device.png
:alt: Screenshot of the add a label to a device service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Add a label to a device 👻
* - {term}`Service name`
  - `homeassistant.add_label_to_device`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_label_to_device)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_label_to_device)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `label_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `battery_powered`
* - `device_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `dc23e666e6100f184e642a0ac345d3eb`
```

:::{tip} Getting an label ID from a label name
:class: dropdown

Not sure what the `label_id` of an label is? The `label_id` field also accepts templates. You can use this template to use the label's name instead:

```yaml
label_id: "{{ label_id('Battery powered') }}"
```

That template will find the label ID of the label with the name "Battery powered".
:::

:::{tip} Finding a device ID
:class: dropdown

Not sure what the `device_id` of an your device is? There are a few ways to find it:

Use this service in the developer tools, in the UI select the device you want to add and select the **Go to YAML mode** button. This will show you the device ID in the YAML code.

Alternatively, you can visit the device page in the UI and look at the URL. The device ID is the last part of the URL, and will look something like this: `dc23e666e6100f184e642a0ac345d3eb`.
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.add_label_to_device
data:
  label_id: "battery_powered"
  device_id: "dc23e666e6100f184e642a0ac345d3eb"
```

Same example, but using the label's name instead of its ID:

```{code-block} yaml
:linenos:
service: homeassistant.add_label_to_device
data:
  label_id: "{{ label_id('Battery powered') }}"
  device_id: "dc23e666e6100f184e642a0ac345d3eb"
```

You can use multiple labels and devices at once. This will cause
each label to be added to each device:

```{code-block} yaml
:linenos:
service: homeassistant.add_label_to_device
data:
  label_id:
    - "battery_powered"
    - "cr2023"
  device_id:
    - "dc23e666e6100f184e642a0ac345d3eb"
    - "df98a97c9341a0f184e642a0ac345d3b"
```

:::

### Remove a label from a device

Removes one or more label(s) from a device.

```{figure} ./images/labels/remove_from_device.png
:alt: Screenshot of the remove a label from a device service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Remove a label from a device 👻
* - {term}`Service name`
  - `homeassistant.remove_label_from_device`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_label_from_device)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_label_from_device)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `label_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `battery_powered`
* - `device_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `dc23e666e6100f184e642a0ac345d3eb`
```

:::{tip} Getting an label ID from a label name
:class: dropdown

Not sure what the `label_id` of an label is? The `label_id` field also accepts templates. You can use this template to use the label's name instead:

```yaml
label_id: "{{ label_id('Battery powered') }}"
```

That template will find the label ID of the label with the name "Battery powered".
:::

:::{tip} Finding a device ID
:class: dropdown

Not sure what the `device_id` of an your device is? There are a few ways to find it:

Use this service in the developer tools, in the UI select the device you want to add and select the **Go to YAML mode** button. This will show you the device ID in the YAML code.

Alternatively, you can visit the device page in the UI and look at the URL. The device ID is the last part of the URL, and will look something like this: `dc23e666e6100f184e642a0ac345d3eb`.
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.remove_label_from_device
data:
  label_id: "battery_powered"
  device_id: "dc23e666e6100f184e642a0ac345d3eb"
```

Same example, but using the label's name instead of its ID:

```{code-block} yaml
:linenos:
service: homeassistant.remove_label_from_device
data:
  label_id: "{{ label_id('Battery powered') }}"
  device_id: "dc23e666e6100f184e642a0ac345d3eb"
```

You can use multiple labels and devices at once. This will cause
each label to be removed from each device:

```{code-block} yaml
:linenos:
service: homeassistant.remove_label_from_device
data:
  label_id:
    - "battery_powered"
    - "cr2023"
  device_id:
    - "dc23e666e6100f184e642a0ac345d3eb"
    - "df98a97c9341a0f184e642a0ac345d3b"
```

:::

### Add a label to an entity

Adds one or more labels(s) to an entity.

```{figure} ./images/labels/add_to_entity.png
:alt: Screenshot of the add a label to an entity service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Add a label to an entity 👻
* - {term}`Service name`
  - `homeassistant.add_label_to_entity`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_label_to_entity)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_label_to_entity)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `label_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `battery_powered`
* - `entity_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `sensor.outside_temperature`
```

:::{tip} Getting an label ID from a label name
:class: dropdown

Not sure what the `label_id` of an label is? The `label_id` field also accepts templates. You can use this template to use the label's name instead:

```yaml
label_id: "{{ label_id('Battery powered') }}"
```

That template will find the label ID of the label with the name "Battery powered".
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.add_label_to_entity
data:
  label_id: "battery_powered"
  entity_id: sensor.outside_temperature
```

Same example, but using the label's name instead of its ID:

```{code-block} yaml
:linenos:
service: homeassistant.add_label_to_entity
data:
  label_id: "{{ label_id('Battery powered') }}"
  entity_id: sensor.outside_temperature
```

You can use multiple labels and entities at once. This will cause
each label to be added to each device:

```{code-block} yaml
:linenos:
service: homeassistant.add_label_to_entity
data:
  label_id:
    - "battery_powered"
    - "cr2023"
  entity_id:
    - sensor.outside_temperature
    - sensor.inside_temperature
```

:::

### Remove a label from an entity

Removes one or more label(s) from an entity.

```{figure} ./images/labels/remove_from_entity.png
:alt: Screenshot of the remove a label from an entity service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Remove a label from an entity 👻
* - {term}`Service name`
  - `homeassistant.remove_label_from_entity`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_label_from_entity)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_label_from_entity)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `label_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `battery_powered`
* - `entity_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `sensor.outside_temperature`
```

:::{tip} Getting an label ID from a label name
:class: dropdown

Not sure what the `label_id` of an label is? The `label_id` field also accepts templates. You can use this template to use the label's name instead:

```yaml
label_id: "{{ label_id('Battery powered') }}"
```

That template will find the label ID of the label with the name "Battery powered".
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.remove_label_from_entity
data:
  label_id: "battery_powered"
  entity_id: sensor.outside_temperature
```

Same example, but using the label's name instead of its ID:

```{code-block} yaml
:linenos:
service: homeassistant.remove_label_from_entity
data:
  label_id: "{{ label_id('Battery powered') }}"
  entity_id: sensor.outside_temperature
```

You can use multiple labels and devices at once. This will cause
each label to be removed from each entity:

```{code-block} yaml
:linenos:
service: homeassistant.remove_label_from_entity
data:
  label_id:
    - "battery_powered"
    - "cr2023"
  entity_id:
    - sensor.outside_temperature
    - sensor.inside_temperature
```

:::

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new service, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
