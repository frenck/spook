---
subject: Core extensions
title: Entity management
subtitle: Everything is an entity, and entities are everything 🪄
date: 2023-08-09T21:29:00+02:00
---

{term}`Entities <entity>` in {term}`Home Assistant` are the building blocks of your home automation. Spook enhances the core of Home Assistant by adding {term}`services <service>` to control those entities programmatically.

## Services

The following entity management services are added to your Home Assistant instance:

### Disable an entity

This service allows you to disable an entity on the fly.

```{figure} ./images/entities/disable_entity.png
:alt: Screenshot of the Home Assistant disable entity service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Disable an entity 👻
* - {term}`Service name`
  - `homeassistant.disable_entity`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service.
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_entity)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_entity)
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
  - `"light.living_room"`
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.disable_entity
data:
  entity_id: light.living_room
```

Or multiple entities at once:

```{code-block} yaml
:linenos:
service: homeassistant.disable_entity
data:
  entity_id:
    - light.living_room
    - light.kitchen_ceiling
```

:::

### Enable an entity

This service allows you to enable an entity on the fly.

```{figure} ./images/entities/enable_entity.png
:alt: Screenshot of the Home Assistant enable entity service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Enable an entity 👻
* - {term}`Service name`
  - `homeassistant.enable_entity`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service.
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_entity)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_entity)
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
  - `"light.living_room"`
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.enable_entity
data:
  entity_id: light.living_room
```

Or multiple entities at once:

```{code-block} yaml
:linenos:
service: homeassistant.enable_entity
data:
  entity_id:
    - light.living_room
    - light.kitchen_ceiling
```

:::

### Hide an entity

This service allows you to hide an entity on the fly.

It can be particularly useful when you have a lot of entities, and you want to hide some of them from the generated UI based programmatically.
Hidden entities are also not exposed to external voice assistants, like Google Assistant or Alexa.

```{figure} ./images/entities/hide_entity.png
:alt: Screenshot of the Home Assistant hide entity service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Hide an entity 👻
* - {term}`Service name`
  - `homeassistant.hide_entity`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service.
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.hide_entity)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.hide_entity)
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
  - `"light.living_room"`
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.hide_entity
data:
  entity_id: light.living_room
```

Or multiple entities at once:

```{code-block} yaml
:linenos:
service: homeassistant.hide_entity
data:
  entity_id:
    - light.living_room
    - light.kitchen_ceiling
```

:::

### Unhide an entity

This service allows you to unhide an entity on the fly.

```{figure} ./images/entities/unhide_entity.png
:alt: Screenshot of the Home Assistant unhide entity service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Unide an entity 👻
* - {term}`Service name`
  - `homeassistant.unhide_entity`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service.
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.unhide_entity)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.unhide_entity)
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
  - `"light.living_room"`
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.unhide_entity
data:
  entity_id: light.living_room
```

Or multiple entities at once:

```{code-block} yaml
:linenos:
service: homeassistant.unhide_entity
data:
  entity_id:
    - light.living_room
    - light.kitchen_ceiling
```

:::

### Update an entity's ID

This service allows you to update an entity's ID on the fly.

```{figure} ./images/entities/update_entity_id.png
:alt: Screenshot of the Home Assistant update entity ID service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Update an entity's ID 👻
* - {term}`Service name`
  - `homeassistant.update_entity_id`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service.
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.update_entity_id)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.update_entity_id)
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
  - `"light.living_room"`
* - `new_entity_id`
  - {term}`string <string>`
  - Yes
  - `"light.dining_room"`
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.update_entity_id
data:
  entity_id: light.living_room
  new_entity_id: light.dining_room
```

:::

### Delete all orphaned entities

Mass clean up your Home Assistant by deleting all orphaned entities in one go.

Orphaned entities are entities that are no longer claimed by an integration. This can happen when an integration is removed or when an integration is no longer working. Home Assistant considers an entity only orphaned if it has been unclaimed since the last restart of Home Assistant.

:::{warning}
Entities might have been marked orphaned because an integration is offline or not working since Home Assistant started. Calling this service will delete those entities as well.
:::

```{figure} ./images/entities/delete_all_orphaned_entities.png
:alt: Screenshot of the Home Assistant unhide entity service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Delete all orphaned entities 👻
* - {term}`Service name`
  - `homeassistant.delete_all_orphaned_entities`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service.
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_all_orphaned_entities)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.delete_all_orphaned_entities)
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.delete_all_orphaned_entities
```

:::

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for these features. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas and support

If you have an idea on how to further enhance this, for example, by adding a new service, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
