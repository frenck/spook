---
subject: Core extensions
title: Miscellaneous
subtitle: Oh, there is some more stuff here. 🦄
date: 2023-06-30T20:36:04+02:00
---

Some other miscellaneous core features that didn't fit elsewhere in the documentation.

Maybe I'm just bad at structuring the documentation? If you have any suggestions, please let me know!

## Services

The following miscellaneous services are added to your Home Assistant instance:

### Restart

Restarts Home Assistant. Spook extends the existing restart service with an "force" option to force Home Assistant to restart immediately, ignoring all safety guards.

:::{note}
Restarting Home Assistant will interrupt all running automations, scripts, and
integrations. It is recommended to use this service only when necessary.
:::

```{figure} ./images/misc/restart.png
:alt: Screenshot of the Home Assistant restart service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Restart 👻
* - {term}`Service name`
  - `homeassistant.restart`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Extends the existing restart service with a "force" option.
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.restart)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.restart)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `force`
  - {term}`boolean <boolean>`
  - no
  - `false`
```

:::{warning}
When enabling `force`, by setting it to `true`, Home Assistant will restart immediately, ignoring all safety guards. This means it will ignore **everything**. It will not check your configuration, and it will even interrupt database migrations and just kill Home Assistant to restart it as fast as possible. This is not recommended and should only be used when absolutely necessary.
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.restart
data:
  force: false
```

:::
