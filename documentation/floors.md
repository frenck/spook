---
subject: Core extensions
title: Floors management
subtitle: Floors brings Home Assistant to a whole new level 🤪
date: 2024-04-04T08:44:57+02:00
---

{term}`Floors <floor>` in {term}`Home Assistant` is a logical grouping of {term}`areas <area>` that are meant to match floors (or levels) in the physical world: your home. Floors are used to group areas together that are on the same floor in your home. Floors give a better overview of your home and can be used to target {term}`actions <performing actions>` to a specific floor, like turning off all the lights on the first floor.

Spook provides that allows you to manage and {term}`automate <automation>` the floors in Home Assistant programatically. Great for creating "dynamic" floors, or for creating floors on the fly.

```{figure} ./images/floors/example.png
:alt: Screenshot of the developer action tools, listing the new actions to manage floors.
:align: center
```

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Create a floor

Adds a new floor to your Home Assistant instance.

```{figure} ./images/floors/create.png
:alt: Screenshot of the create floor action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Create a floor 👻
* - {term}`Action name`
  - `homeassistant.create_floor`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_floor)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_floor)
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
  - `First floor`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:floor-1`
* - `level`
  - {term}`integer <integer>`
  - No
  - `1`
* - `aliases`
  - {term}`string <string>` | {term}`list of strings <list>`
  - No
  - `["ground floor", "downstairs"]`
```

The use of `aliases` is helpful if you want to create an floor with multiple names. For example, if you want to create an floor called "First floor", but also want to be able to refer to it as "Ground floor" or "Downstairs", you can add those names as aliases. This is used by Home Assistant Assist.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.create_floor
data:
  name: "First floor"
  icon: "mdi:floor-1"
  level: 1
  aliases:
    - "Ground floor"
    - "Downstairs"
```

:::

### Delete a floor

Delete a floor from your Home Assistant instance.

```{figure} ./images/floors/delete.png
:alt: Screenshot of the delete flor action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Delete a floor 👻
* - {term}`Action name`
  - `homeassistant.delete_floor`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_floor)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_floor)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `floor_id`
  - {term}`string <string>`
  - Yes
  - `first_floor`
```

:::{tip} Getting an floor ID from a floor name
:class: dropdown

Not sure what the `floor_id` of a floor is? The `floor_id` field also accepts templates. You can use this template to use the floor's name instead:

```yaml
floor_id: "{{ floor_id('First floor') }}"
```

That template will find the floor ID of the floor with the name "First floor".
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.delete_floor
data:
  floor_id: "first_floor"
```

Same example, but using the floor's name instead of the floor ID:

```{code-block} yaml
:linenos:
action: homeassistant.delete_floor
data:
  floor_id: "{{ floor_id('First floor') }}"
```

:::

### Add an alias to a floor

Adds one or more aliases to an existing floor. This action does not remove existing aliases, but adds the new ones to the existing ones.

As floor aliases are used by voice assistants, you could add (and also remove) aliases to a floor using {term}`automations <automation>`, which allows you to make them available/unavailable programatically.

```{figure} ./images/floors/add_alias.png
:alt: Screenshot of the add an alias to a floor action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Add an alias to a floor 👻
* - {term}`Action name`
  - `homeassistant.add_alias_to_floor`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_alias_to_floor)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_alias_to_floor)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `floor_id`
  - {term}`string <string>`
  - Yes
  - `first_floor`
* - `aliases`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `["Ground floor", "Downstairs"]`
```

:::{tip} Getting an floor ID from a floor name
:class: dropdown

Not sure what the `floor_id` of a floor is? The `floor_id` field also accepts templates. You can use this template to use the floor's name instead:

```yaml
floor_id: "{{ floor_id('First floor') }}"
```

That template will find the floor ID of the floor with the name "First floor".
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.add_alias_to_floor
data:
  floor_id: "first_floor"
  aliases:
    - "Ground floor"
    - "Downstairs"
```

Same example, but using the floor's name instead of the floor ID:

```{code-block} yaml
:linenos:
action: homeassistant.add_alias_to_floor
data:
  floor_id: "{{ floor_id('First floor') }}"
  aliases:
    - "Ground floor"
    - "Downstairs"
```

:::

### Remove an alias from a floor

Removes one or more aliases from an existing floor. This action will leave the other aliases intact.

As floor aliases are used by voice assistants, you could remove (and also add) aliases to a floor using {term}`automations <automation>`, which allows you to make them available/unavailable programatically.

```{figure} ./images/floors/remove_alias.png
:alt: Screenshot of the remove an alias to a floor action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Add an alias to a floor 👻
* - {term}`Action name`
  - `homeassistant.remove_alias_from_floor`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_alias_from_floor)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_alias_from_floor)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `floor_id`
  - {term}`string <string>`
  - Yes
  - `first_floor`
* - `aliases`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `["Ground floor", "Downstairs"]`
```

:::{tip} Getting an floor ID from a floor name
:class: dropdown

Not sure what the `floor_id` of a floor is? The `floor_id` field also accepts templates. You can use this template to use the floor's name instead:

```yaml
floor_id: "{{ floor_id('First floor') }}"
```

That template will find the floor ID of the floor with the name "First floor".
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.remove_alias_from_floor
data:
  floor_id: "first_floor"
  aliases:
    - "Ground floor"
    - "Downstairs"
```

Same example, but using the floor's name instead of the floor ID:

```{code-block} yaml
:linenos:
action: homeassistant.remove_alias_from_floor
data:
  floor_id: "{{ floor_id('First floor') }}"
  aliases:
    - "Ground floor"
    - "Downstairs"
```

:::

### Set aliases for a floor

Sets the aliases for a floor. This action will overwrite/remove all existing aliases.

As floor aliases are used by voice assistants, you could remove (and also add) aliases to a floor using {term}`automations <automation>`, which allows you to make them available/unavailable programatically.

```{figure} ./images/floors/set_aliases.png
:alt: Screenshot of the set aliases to for a floor action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Sets aliases for a floor 👻
* - {term}`Action name`
  - `homeassistant.set_floor_aliases`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.set_floor_aliases)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.set_floor_aliases)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `floor_id`
  - {term}`string <string>`
  - Yes
  - `first_floor`
* - `aliases`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `["Ground floor", "Downstairs"]`
```

:::{tip} Getting an floor ID from a floor name
:class: dropdown

Not sure what the `floor_id` of a floor is? The `floor_id` field also accepts templates. You can use this template to use the floor's name instead:

```yaml
floor_id: "{{ floor_id('First floor') }}"
```

That template will find the floor ID of the floor with the name "First floor".
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.set_floor_aliases
data:
  floor_id: "first_floor"
  aliases:
    - "Ground floor"
    - "Downstairs"
```

Same example, but using the floor's name instead of the floor ID:

```{code-block} yaml
:linenos:
action: homeassistant.set_floor_aliases
data:
  floor_id: "{{ floor_id('First floor') }}"
  aliases:
    - "Ground floor"
    - "Downstairs"
```

:::

### Add an area to a floor

Adds one or more area(s) to a floor. This action will leave the other areas on the floor untouched.

```{figure} ./images/floors/add_area.png
:alt: Screenshot of the add an area to a floor action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Add an area to a floor 👻
* - {term}`Action name`
  - `homeassistant.add_area_to_floor`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_area_to_floor)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_area_to_floor)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `floor_id`
  - {term}`string <string>`
  - Yes
  - `first_floor`
* - `area_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `living_room`
```

:::{tip} Getting an floor ID from a floor name
:class: dropdown

Not sure what the `floor_id` of a floor is? The `floor_id` field also accepts templates. You can use this template to use the floor's name instead:

```yaml
floor_id: "{{ floor_id('First floor') }}"
```

That template will find the floor ID of the floor with the name "First floor".
:::

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
action: homeassistant.add_area_to_floor
data:
  floor_id: "first_floor"
  area_id: "living_room"
```

Same example, but using the floor's and area's name instead of their IDs:

```{code-block} yaml
:linenos:
action: homeassistant.add_area_to_floor
data:
  floor_id: "{{ floor_id('First floor') }}"
  area_id: "{{ area_id('Living room') }}"
```

To add multiple areas at once, use a list of area IDs:

```{code-block} yaml
:linenos:
action: homeassistant.add_area_to_floor
data:
  floor_id: "first_floor"
  area_id:
    - "living_room"
    - "kitchen"
```

:::

### Remove an area from a floor

Removes one or more area(s) from a floor. This action will leave the other area on the floor untouched.

```{figure} ./images/floors/remove_area.png
:alt: Screenshot of the add a device to an area action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Remove an area from a floor 👻
* - {term}`Action name`
  - `homeassistant.remove_area_from_floor`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_area_from_floor)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_area_from_floor)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `area_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `living_room`
```

:::{note} This action does not need a floor ID
:class: dropdown

While this action is floor related, it does not need to know the floor ID. An are can only be on a single floor at a time, so it will remove the area from the floor it is in. Hence, it only needs to know the are you want to remove from a floor.
:::

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
action: homeassistant.remove_area_from_floor
data:
  area_id: "living_room"
```

To remove multiple areas at once, use a list of area IDs:

```{code-block} yaml
:linenos:
action: homeassistant.remove_area_from_floor
data:
  area_id:
    - "living_room"
    - "kitchen"
```

:::

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
