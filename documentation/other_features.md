---
subject: Features
title: Other features
subtitle: Home of the useless but fun. 🤡
date: 2023-08-09T21:29:00+02:00
---

These are some Spook-specific features that don't fit in any of the other categories.
They are not particularly useful, but they are fun to play with (and maybe you actually have a use case for them).

They originally served as the proof of concept for Spook and left them in for the fun of it.

## Actions

Spook offers the following useless actions:

### Boo!

This acti will just always scare Home Assistant, causing this action call to fail. Calling this action in any of your automations will thus cause your automation to stop and error.

```{figure} ./images/spook/boo.png
:alt: Screenshot of the Spook Boo! action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Boo! 👻
* - {term}`Action name`
  - `spook.boo`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.boo)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.boo)
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

This action has no parameters, so you can just call it like this:

```{code-block} yaml
:linenos:
action: homeassistant.boo
```

:::

### Random fail

This action call will randomly fail (and thus randomly stop your automation or script).

```{figure} ./images/spook/random_fail.png
:alt: Screenshot of the Spook random fail action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Random fail 👻
* - {term}`Action name`
  - `spook.random_fail`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.random_fail)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.random_fail)
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

This action has no parameters, so you can just call it like this:

```{code-block} yaml
:linenos:
action: homeassistant.random_fail
```

:::
