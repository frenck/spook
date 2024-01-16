---
subject: Features
title: Other features
subtitle: Home of the useless but fun. 🤡
date: 2023-08-09T21:29:00+02:00
---

These are some Spook-specific features that don't fit in any of the other categories.
They are not particularly useful, but they are fun to play with (and maybe you actually have a use case for them).

They originally served as the proof of concept for Spook and left them in for the fun of it.

## Services

Spook offers the following services useless services:

### Boo!

This service will just always scare Home Assistant, causing this service call to fail. Calling this service in any of your automations will thus cause your automation to stop and error.

```{figure} ./images/spook/boo.png
:alt: Screenshot of the Spook Boo! service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Boo! 👻
* - {term}`Service name`
  - `spook.boo`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.boo)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.boo)
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

This service has no parameters, so you can just call it like this:

```{code-block} yaml
:linenos:
service: homeassistant.boo
```

:::

### Random fail

This service call will randomly fail (and thus randomly stop your automation or script).

```{figure} ./images/spook/random_fail.png
:alt: Screenshot of the Spook random fail service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Random fail 👻
* - {term}`Service name`
  - `spook.random_fail`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added service
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.random_fail)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=spook.random_fail)
```

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

This service has no parameters, so you can just call it like this:

```{code-block} yaml
:linenos:
service: homeassistant.random_fail
```

:::
