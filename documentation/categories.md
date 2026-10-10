---
subject: Core extensions
title: Category management
subtitle: A place for everything, and everything in its place 🗂️
date: 2026-09-29T12:00:00+02:00
---

Categories in {term}`Home Assistant` let you sort your {term}`automations <automation>`, {term}`scripts <script>`, scenes, and {term}`helpers <helper>` into groups on their own pages in the user interface. Each of those pages has its own set of categories, and something can be in one category per page.

Spook adds actions to manage categories, and to put things in them, from your own {term}`automations <automation>` and {term}`scripts <script>`. Great for filing new automations away automatically, or for tidying up in bulk.

## Actions

Spook adds the following new actions to your Home Assistant instance:

:::{tip} Categories by name
Home Assistant never shows you the ID of a category, and it is a random one. So wherever an action below asks for a `category_id`, you can give the name of the category instead.
:::

### Create a category

Adds a new category to your Home Assistant instance. The `scope` says which page it is for: `automation`, `script`, `scene`, or `helpers`.

The action responds with the ID of the new category, in case you want to use it right away.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Create a category 👻
* - {term}`Action name`
  - `homeassistant.create_category`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - Optional, the `category_id` of the new category
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_category)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.create_category)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `scope`
  - {term}`string <string>`
  - Yes
  - `automation`
* - `name`
  - {term}`string <string>`
  - Yes
  - `Lighting`
* - `icon`
  - {term}`string <string>`
  - No
  - `mdi:lightbulb`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.create_category
data:
  scope: automation
  name: Lighting
  icon: mdi:lightbulb
response_variable: category
```

:::

### Update a category

Updates an existing category. Anything you leave out keeps the value it already has. Setting `icon` to `null` clears it.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Update a category 👻
* - {term}`Action name`
  - `homeassistant.update_category`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.update_category)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.update_category)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `scope`
  - {term}`string <string>`
  - Yes
  - `automation`
* - `category_id`
  - {term}`string <string>`
  - Yes
  - `Lighting`
* - `name`
  - {term}`string <string>`
  - No
  - `Lights`
* - `icon`
  - {term}`string <string>` or `null`
  - No
  - `mdi:lightbulb-group`
```

:::{note}
You need to give at least one thing to change. A call with only a `scope` and `category_id` is refused, so a misspelled parameter cannot pass for a successful update.
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.update_category
data:
  scope: automation
  category_id: Lighting
  name: Lights
```

:::

### Delete a category

Deletes a category. Everything that was in it is left without a category on that page.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Delete a category 👻
* - {term}`Action name`
  - `homeassistant.delete_category`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_category)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_category)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `scope`
  - {term}`string <string>`
  - Yes
  - `automation`
* - `category_id`
  - {term}`string <string>`
  - Yes
  - `Lighting`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.delete_category
data:
  scope: automation
  category_id: Lighting
```

:::

### Add a category to an entity

Puts one or more automations, scripts, scenes, or helpers in a category. Which page the category belongs to follows from the entity: an automation gets an automation category, a script a script category, and so on. Anything else counts as a helper.

Since something can only be in one category per page, this replaces the category it was in before.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Add a category to an entity 👻
* - {term}`Action name`
  - `homeassistant.add_category_to_entity`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_category_to_entity)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.add_category_to_entity)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `category_id`
  - {term}`string <string>`
  - Yes
  - `Lighting`
* - `entity_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `automation.porch_lights`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.add_category_to_entity
data:
  category_id: Lighting
  entity_id:
    - automation.porch_lights
    - automation.garden_lights
```

:::

### Remove a category from an entity

Takes one or more automations, scripts, scenes, or helpers out of a category. Anything that is in a different category is left alone.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Remove a category from an entity 👻
* - {term}`Action name`
  - `homeassistant.remove_category_from_entity`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_category_from_entity)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.remove_category_from_entity)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `category_id`
  - {term}`string <string>`
  - Yes
  - `Lighting`
* - `entity_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `automation.porch_lights`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.remove_category_from_entity
data:
  category_id: Lighting
  entity_id: automation.porch_lights
```

:::

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
