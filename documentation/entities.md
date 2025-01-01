---
subject: Core extensions
title: Entity management
subtitle: Everything is an entity, and entities are everything 🪄
date: 2023-08-09T21:29:00+02:00
---

{term}`Entities <entity>` in {term}`Home Assistant` are the building blocks of your home automation. Spook enhances the core of Home Assistant by adding {term}`actions <action>` to control those entities programmatically.

## Actions

The following entity management actions are added to your Home Assistant instance:

### Disable an entity

This action allows you to disable an entity on the fly.

```{figure} ./images/entities/disable_entity.png
:alt: Screenshot of the Home Assistant disable entity action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Disable an entity 👻
* - {term}`Action name`
  - `homeassistant.disable_entity`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_entity)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_entity)
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
  - `"light.living_room"`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.disable_entity
data:
  entity_id: light.living_room
```

Or multiple entities at once:

```{code-block} yaml
:linenos:
action: homeassistant.disable_entity
data:
  entity_id:
    - light.living_room
    - light.kitchen_ceiling
```

:::

### Enable an entity

This action allows you to enable an entity on the fly.

```{figure} ./images/entities/enable_entity.png
:alt: Screenshot of the Home Assistant enable entity action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Enable an entity 👻
* - {term}`Action name`
  - `homeassistant.enable_entity`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_entity)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_entity)
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
  - `"light.living_room"`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.enable_entity
data:
  entity_id: light.living_room
```

Or multiple entities at once:

```{code-block} yaml
:linenos:
action: homeassistant.enable_entity
data:
  entity_id:
    - light.living_room
    - light.kitchen_ceiling
```

:::

### Hide an entity

This action allows you to hide an entity on the fly.

It can be particularly useful when you have a lot of entities, and you want to hide some of them from the generated UI based programmatically.
Hidden entities are also not exposed to external voice assistants, like Google Assistant or Alexa.

```{figure} ./images/entities/hide_entity.png
:alt: Screenshot of the Home Assistant hide entity action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Hide an entity 👻
* - {term}`Action name`
  - `homeassistant.hide_entity`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.hide_entity)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.hide_entity)
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
  - `"light.living_room"`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.hide_entity
data:
  entity_id: light.living_room
```

Or multiple entities at once:

```{code-block} yaml
:linenos:
action: homeassistant.hide_entity
data:
  entity_id:
    - light.living_room
    - light.kitchen_ceiling
```

:::

### Unhide an entity

This action allows you to unhide an entity on the fly.

```{figure} ./images/entities/unhide_entity.png
:alt: Screenshot of the Home Assistant unhide entity action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Unide an entity 👻
* - {term}`Action name`
  - `homeassistant.unhide_entity`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.unhide_entity)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.unhide_entity)
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
  - `"light.living_room"`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.unhide_entity
data:
  entity_id: light.living_room
```

Or multiple entities at once:

```{code-block} yaml
:linenos:
action: homeassistant.unhide_entity
data:
  entity_id:
    - light.living_room
    - light.kitchen_ceiling
```

:::

### Update an entity's ID

This action allows you to update an entity's ID on the fly.

```{figure} ./images/entities/update_entity_id.png
:alt: Screenshot of the Home Assistant update entity ID action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Update an entity's ID 👻
* - {term}`Action name`
  - `homeassistant.update_entity_id`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.update_entity_id)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.update_entity_id)
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
  - `"light.living_room"`
* - `new_entity_id`
  - {term}`string <string>`
  - Yes
  - `"light.dining_room"`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.update_entity_id
data:
  entity_id: light.living_room
  new_entity_id: light.dining_room
```

:::

### Delete all orphaned entities

Mass clean up your Home Assistant by deleting all orphaned entities in one go.

Orphaned entities are entities that are no longer claimed by an integration. This can happen when an integration is removed or when an integration is no longer working. Home Assistant considers an entity only orphaned if it has been unclaimed since the last restart of Home Assistant.

:::{warning}
Entities might have been marked orphaned because an integration is offline or not working since Home Assistant started. Calling This action will delete those entities as well.
:::

```{figure} ./images/entities/delete_all_orphaned_entities.png
:alt: Screenshot of the Home Assistant unhide entity action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Delete all orphaned entities 👻
* - {term}`Action name`
  - `homeassistant.delete_all_orphaned_entities`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_all_orphaned_entities)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_all_orphaned_entities)
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.delete_all_orphaned_entities
```

:::

### List all orphaned database entities

Mass clean up your database with the help of Spook by listing all orphaned database entities in one action.

Orphaned database entities are entities that are no longer claimed by integration but still exist in the database. This can happen when an integration is removed or when an entity is disabled.

```{figure} ./images/entities/list_orphaned_database_entities.png
:alt: Screenshot of the Home Assistant list orphaned database entities action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - List orphaned database entities 👻
* - {term}`Action name`
  - `homeassistant.list_orphaned_database_entities`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - Action response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.list_orphaned_database_entities)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.list_orphaned_database_entities)
```

```{list-table}
:header-rows: 2
* - Action response data
* - Attribute
  - Type
* - `count`
  - {term}`integer <integer>`
* - `entities`
  - {term}`list <list>`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.list_orphaned_database_entities
```

:::

:::{tip} Script to remove entities from database
:class: dropdown

```yaml
alias: Delete orphaned database entities
sequence:
  - action: homeassistant.list_orphaned_database_entities
    response_variable: orphaned
  - action: recorder.purge_entities
    target:
      entity_id: |
        {{ orphaned.entities }}
    data:
      keep_days: 0
mode: single
```

That template will find the area ID of the area with the name "Living room".
:::

### Rename an entity

This action allows you to update an entity friendly_name on the fly.

```{figure} ./images/entities/rename_entity.png
:alt: Screenshot of the Home Assistant rename entity action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Rename an entity 👻
* - {term}`Action name`
  - `homeassistant.rename_entity`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.rename_entity)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.rename_entity)
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
  - `"light.living_room"`
* - `name`
  - {term}`string <string>`
  - Yes
  - `"Living room light"`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.rename_entity
data:
  entity_id: light.living_room
  name: "Living room light"
```

:::

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for these features. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
