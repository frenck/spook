---
subject: Core extensions
title: User management
subtitle: Who's in your home? 👤
date: 2026-02-17T00:00:00+00:00
---

A {term}`user <user>` in {term}`Home Assistant` is an account that can log in and control your home. Spook provides you with actions to enable and disable user accounts on the fly.

## Actions

The following user management actions are added to your Home Assistant instance:

### Disable a user

This action allows you to disable a user account on the fly, preventing them from logging in.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Disable a user 👻
* - {term}`Action name`
  - `homeassistant.disable_user`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_user)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_user)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `user_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `bf1f3b59c7a842c8a9de3e1c12345678`
```

:::{tip} Finding a user ID
:class: dropdown

Not sure what the `user_id` of a user is? You can find it in the Home Assistant UI by going to **Settings** → **People** → selecting the person → clicking on the **User** tab. The user ID is displayed on that page.

Alternatively, you can use the **Developer Tools** → **Template** tab and use the following template to list all user IDs:

```{code-block} yaml
{% for state in states.person %}
Name: {{ state.name }}
ID: {{ state.attributes.user_id }}
------------------
{% endfor %}
```

:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.disable_user
data:
  user_id: "bf1f3b59c7a842c8a9de3e1c12345678"
```

Or multiple users at once:

```{code-block} yaml
:linenos:
action: homeassistant.disable_user
data:
  user_id:
    - "bf1f3b59c7a842c8a9de3e1c12345678"
    - "a3c9d12e4f5b678901234567890abcde"
```

:::

### Enable a user

This action allows you to enable a user account on the fly, allowing them to log in again.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Enable a user 👻
* - {term}`Action name`
  - `homeassistant.enable_user`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_user)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_user)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `user_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `bf1f3b59c7a842c8a9de3e1c12345678`
```

:::{tip} Finding a user ID
:class: dropdown

Not sure what the `user_id` of a user is? You can find it in the Home Assistant UI by going to **Settings** → **People** → selecting the person → clicking on the **User** tab. The user ID is displayed on that page.

:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.enable_user
data:
  user_id: "bf1f3b59c7a842c8a9de3e1c12345678"
```

Or multiple users at once:

```{code-block} yaml
:linenos:
action: homeassistant.enable_user
data:
  user_id:
    - "bf1f3b59c7a842c8a9de3e1c12345678"
    - "a3c9d12e4f5b678901234567890abcde"
```

:::

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for these features. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
