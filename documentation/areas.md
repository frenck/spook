---
subject: Core extensions
title: Areas management
subtitle: Is there room for one more?
date: 2023-08-09T21:29:00+02:00
---

{term}`Areas <area>` in {term}`Home Assistant` is a logical grouping of {term}`devices <device>` and {term}`entities <entity>` that are meant to match the areas (or rooms) in the physical world: your home.

Spook provides {term}`actions <action>` that allows you to manage and {term}`automate <automation>` the areas in Home Assistant programatically. Great for creating "dynamic" areas, or for creating areas on the fly.

```{figure} ./images/areas/example.png
:alt: Screenshot of the developer actions tools, listing the new actions to manage areas.
:align: center
```

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Create an area

Adds a new area to your Home Assistant instance.

```{figure} ./images/areas/create.png
:alt: Screenshot of the create area action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Create an area 👻
* - {term}`Action name`
  - `homeassistant.create_area`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_area)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_area)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `name`
  - {term}`string <string>`
  - Yes
  - `Living room`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:sofa`
* - `aliases`
  - {term}`string <string>` | {term}`list of strings <list>`
  - No
  - `["Lounge", "Sitting area"]`
```

The use of `aliases` is helpful if you want to create an area with multiple names. For example, if you want to create an area called "Living room", but also want to be able to refer to it as "Sitting area" or "Lounge", you can add those names as aliases. This is used by Home Assistant Assist and Google Assistant.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.create_area
data:
  name: "Living room"
  icon: "mdi:sofa"
  aliases:
    - "Lounge"
    - "Sitting area"
```

:::

### Delete an area

Adds a new area to your Home Assistant instance.

```{figure} ./images/areas/delete.png
:alt: Screenshot of the delete area action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Delete an area 👻
* - {term}`Action name`
  - `homeassistant.delete_area`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_area)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_area)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `area_id`
  - {term}`string <string>`
  - Yes
  - `living_room`
```

:::{tip} Getting an area ID from an area name
:class: dropdown

Not sure what the `area_id` of an area is? The `area_id` field also accepts templates. You can use this template to use the area's name instead:

```yaml
area_id: "{{ area_id('Living room') }}"
```

That template will find the area ID of the area with the name "Living room".
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.delete_area
data:
  area_id: "living_room"
```

Same example, but using the area's name instead of the area ID:

```{code-block} yaml
:linenos:
action: homeassistant.delete_area
data:
  area_id: "{{ area_id('Living room') }}"
```

:::

### Add an alias to an area

Adds one or more aliases to an existing area. This action does not remove existing aliases, but adds the new ones to the existing ones.

As area aliases are used by voice assistants, you could add (and also remove) aliases to an area using {term}`automations <automation>`, which allows you to make them available/unavailable programatically.

```{figure} ./images/areas/add_alias.png
:alt: Screenshot of the add an alias to an area action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Add an alias to an area 👻
* - {term}`Action name`
  - `homeassistant.add_alias_to_area`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_alias_to_area)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_alias_to_area)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `area_id`
  - {term}`string <string>`
  - Yes
  - `living_room`
* - `aliases`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `["Lounge", "Sitting area"]`
```

:::{tip} Getting an area ID from an area name
:class: dropdown

Not sure what the `area_id` of an area is? The `area_id` field also accepts templates. You can use this template to use the area's name instead:

```yaml
area_id: "{{ area_id('Living room') }}"
```

That template will find the area ID of the area with the name "Living room".
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.add_alias_to_area
data:
  area_id: "living_room"
  aliases:
    - "Lounge"
    - "Sitting area"
```

Same example, but using the area's name instead of the area ID:

```{code-block} yaml
:linenos:
action: homeassistant.add_alias_to_area
data:
  area_id: "{{ area_id('Living room') }}"
  aliases:
    - "Lounge"
    - "Sitting area"
```

:::

### Remove an alias from an area

Removes one or more aliases from an existing area. This action will leave the other aliases intact.

As area aliases are used by voice assistants, you could remove (and also add) aliases to an area using {term}`automations <automation>`, which allows you to make them available/unavailable programatically.

```{figure} ./images/areas/remove_alias.png
:alt: Screenshot of the remove an alias to an area action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Add an alias to an area 👻
* - {term}`Action name`
  - `homeassistant.remove_alias_from_area`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_alias_from_area)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_alias_from_area)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `area_id`
  - {term}`string <string>`
  - Yes
  - `living_room`
* - `aliases`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `["Lounge", "Sitting area"]`
```

:::{tip} Getting an area ID from an area name
:class: dropdown

Not sure what the `area_id` of an area is? The `area_id` field also accepts templates. You can use this template to use the area's name instead:

```yaml
area_id: "{{ area_id('Living room') }}"
```

That template will find the area ID of the area with the name "Living room".
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.remove_alias_from_area
data:
  area_id: "living_room"
  aliases:
    - "Lounge"
    - "Sitting area"
```

Same example, but using the area's name instead of the area ID:

```{code-block} yaml
:linenos:
action: homeassistant.remove_alias_from_area
data:
  area_id: "{{ area_id('Living room') }}"
  aliases:
    - "Lounge"
    - "Sitting area"
```

:::

### Set aliases for an area

Sets the aliases for an area. This action will overwrite/remove all existing aliases.

As area aliases are used by voice assistants, you could remove (and also add) aliases to an area using {term}`automations <automation>`, which allows you to make them available/unavailable programatically.

```{figure} ./images/areas/set_aliases.png
:alt: Screenshot of the set aliases to for an area action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Sets aliases for an area 👻
* - {term}`Action name`
  - `homeassistant.set_area_aliases`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.set_area_aliases)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.set_area_aliases)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `area_id`
  - {term}`string <string>`
  - Yes
  - `living_room`
* - `aliases`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `["Lounge", "Sitting area"]`
```

:::{tip} Getting an area ID from an area name
:class: dropdown

Not sure what the `area_id` of an area is? The `area_id` field also accepts templates. You can use this template to use the area's name instead:

```yaml
area_id: "{{ area_id('Living room') }}"
```

That template will find the area ID of the area with the name "Living room".
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.set_area_aliases
data:
  area_id: "living_room"
  aliases:
    - "Lounge"
    - "Sitting area"
```

Same example, but using the area's name instead of the area ID:

```{code-block} yaml
:linenos:
action: homeassistant.set_area_aliases
data:
  area_id: "{{ area_id('Living room') }}"
  aliases:
    - "Lounge"
    - "Sitting area"
```

:::

### Add a device to an area

Adds one or more device(s) to an area. This action will leave the other devices in the area untouched.

```{figure} ./images/areas/add_device.png
:alt: Screenshot of the add a device to an area action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Add a device to an area 👻
* - {term}`Action name`
  - `homeassistant.add_device_to_area`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_device_to_area)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_device_to_area)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `area_id`
  - {term}`string <string>`
  - Yes
  - `living_room`
* - `device_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `dc23e666e6100f184e642a0ac345d3eb`
```

:::{tip} Getting an area ID from an area name
:class: dropdown

Not sure what the `area_id` of an area is? The `area_id` field also accepts templates. You can use this template to use the area's name instead:

```yaml
area_id: "{{ area_id('Living room') }}"
```

That template will find the area ID of the area with the name "Living room".
:::

:::{tip} Finding a device ID
:class: dropdown

Not sure what the `device_id` of an your device is? There are a few ways to find it:

Use this action in the developer tools, in the UI select the device you want to add and select the **Go to YAML mode** button. This will show you the device ID in the YAML code.

Alternatively, you can visit the device page in the UI and look at the URL. The device ID is the last part of the URL, and will look something like this: `dc23e666e6100f184e642a0ac345d3eb`.
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.add_device_to_area
data:
  area_id: "living_room"
  device_id: "dc23e666e6100f184e642a0ac345d3eb"
```

Same example, but using the area's name instead of the area ID:

```{code-block} yaml
:linenos:
action: homeassistant.set_area_aliases
data:
  area_id: "{{ area_id('Living room') }}"
  device_id: "dc23e666e6100f184e642a0ac345d3eb"
```

To add multiple device at once, use a list of device IDs:

```{code-block} yaml
:linenos:
action: homeassistant.add_device_to_area
data:
  area_id: "living_room"
  device_id:
    - "dc23e666e6100f184e642a0ac345d3eb"
    - "df98a97c9341a0f184e642a0ac345d3b"
```

:::

### Remove a device from an area

Removes one or more device(s) from an area. This action will leave the other devices in the area untouched.

```{figure} ./images/areas/remove_device.png
:alt: Screenshot of the add a device to an area action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Remove a device from an area 👻
* - {term}`Action name`
  - `homeassistant.remove_device_from_area`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_device_from_area)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_device_from_area)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `device_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `dc23e666e6100f184e642a0ac345d3eb`
```

:::{note} This action does not need an area ID
:class: dropdown

While this action is area related, it does not need to know the area ID. A device can only be in a single area at a time, so it will remove the device from the area it is in. Hence, it only needs to know the device you want to remove from an area.
:::

:::{tip} Finding a device ID
:class: dropdown

Not sure what the `device_id` of an your device is? There are a few ways to find it:

Use this action in the developer tools, in the UI select the device you want to add and select the **Go to YAML mode** button. This will show you the device ID in the YAML code.

Alternatively, you can visit the device page in the UI and look at the URL. The device ID is the last part of the URL, and will look something like this: `dc23e666e6100f184e642a0ac345d3eb`.
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.remove_device_from_area
data:
  device_id: "dc23e666e6100f184e642a0ac345d3eb"
```

To remove multiple devices at once, use a list of device IDs:

```{code-block} yaml
:linenos:
action: homeassistant.remove_device_from_area
data:
  device_id:
    - "dc23e666e6100f184e642a0ac345d3eb"
    - "df98a97c9341a0f184e642a0ac345d3b"
```

:::

### Add an entity to an area

Adds one or more entities to an area. This action will leave the other entities in the area untouched.

```{figure} ./images/areas/add_entity.png
:alt: Screenshot of the add an entity to an area action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Add an entity to an area 👻
* - {term}`Action name`
  - `homeassistant.add_entity_to_area`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_entity_to_area)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_entity_to_area)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `area_id`
  - {term}`string <string>`
  - Yes
  - `living_room`
* - `entity_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `light.spotlight`
```

:::{tip} Getting an area ID from an area name
:class: dropdown

Not sure what the `area_id` of an area is? The `area_id` field also accepts templates. You can use this template to use the area's name instead:

```yaml
area_id: "{{ area_id('Living room') }}"
```

That template will find the area ID of the area with the name "Living room".
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.add_entity_to_area
data:
  area_id: "living_room"
  entity_id: light.spotlight
```

Same example, but using the area's name instead of the area ID:

```{code-block} yaml
:linenos:
action: homeassistant.add_entity_to_area
data:
  area_id: "{{ area_id('Living room') }}"
  entity_id: light.spotlight
```

To add multiple entities at once, use a list of device IDs:

```{code-block} yaml
:linenos:
action: homeassistant.add_entity_to_area
data:
  area_id: "living_room"
  entity_id:
    - light.spotlight
    - light.ceiling
```

:::

### Remove an entity from an area

Removes one or more device(s) from an area. This action will leave the other devices in the area untouched.

```{figure} ./images/areas/remove_entity.png
:alt: Screenshot of the add a device to an area action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Remove an entity from an area 👻
* - {term}`Action name`
  - `homeassistant.remove_entity_from_area`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_entity_from_area)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_entity_from_area)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `entity_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `light.spotlight`
```

:::{note} This action does not need an area ID
:class: dropdown

While this action is area related, it does not need to know the area ID. An entity can only be in a single area at a time, so it will remove the entity from the area it is in. Hence, it only needs to know the entity you want to remove from an area.
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.remove_entity_from_area
data:
  entity_id: light.spotlight
```

To remove multiple entities at once, use a list of entity IDs:

```{code-block} yaml
:linenos:
action: homeassistant.remove_entity_from_area
data:
  entity_id:
    - light.spotlight
    - light.ceiling
```

:::

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
