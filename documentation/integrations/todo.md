---
subject: Enhanced integrations
title: To-do list
subtitle: First things first. ✅
description: Spook adds an action that moves an item in a to-do list, the way dragging it in the interface does.
date: 2026-10-04T20:00:00+02:00
---

```{image} https://brands.home-assistant.io/todo/icon.png
:alt: The Home Assistant to-do list icon
:width: 250px
:align: center
```

<br><br>

The to-do list {term}`integration <integration>` brings shopping lists and to-do lists into {term}`Home Assistant`: the local one, the shopping list, and those of other services.

A list that can be reordered is reordered by dragging an item in the interface, and that is the only way. Spook adds the action, so an automation can put the most urgent thing at the top.

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Move item

Move an item in a to-do list to the top, the bottom, or after another item.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - To-do list: Move item 👻
* - {term}`Action name`
  - `todo.move_item`
* - {term}`Action targets`
  - Yes, `todo` entities that can be reordered
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Added action
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=todo.move_item)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=todo.move_item)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `item`
  - {term}`string <string>`
  - Yes
  - Take out the bins
* - `after`
  - {term}`string <string>`
  - No, but this or `position`
  - Do the dishes
* - `position`
  - {term}`string <string>`
  - No, but this or `after`
  - `top` or `bottom`
```

The item, and the item to put it after, are found by their title or their uid, the same way `todo.update_item` finds an item.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

Rain is coming, so the bins go first:

```{code-block} yaml
:linenos:
action: todo.move_item
target:
  entity_id: todo.chores
data:
  item: Take out the bins
  position: top
```

:::

:::{attention} Known limitations
:class: dropdown

- Only lists that can be reordered can be targeted. Some lists keep their items in an order of their own, like one sorted by due date.
- An item that is not in the list, or a place after an item that is not, is an error, the same as for `todo.update_item`. So is moving an item after itself.

:::

## Repairs

Spook has no repair detections for this integration.
