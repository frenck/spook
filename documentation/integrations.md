---
subject: Core extensions
title: Integration management
subtitle: Integrate all the things! 🎉
date: 2023-08-09T21:29:00+02:00
---

{term}`Integrations <integration>` in {term}`Home Assistant` are the glue between your Home Assistant instance and the devices, services, and platforms you want to integrate with it. Spook enhances the core of Home Assistant by adding to control those integrations.

## Actions

The following integration management actions are added to your Home Assistant instance:

### Disable an integration

Disable a single instance of an integration by its {term}`config entry <config entry>`.

```{figure} ./images/integration/disable_config_entry.png
:alt: Screenshot of the Home Assistant disable config entry action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Disable an integration 👻
* - {term}`Action name`
  - `homeassistant.disable_config_entry`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_config_entry)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_config_entry)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `config_entry_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `dc23e666e6100f184e642a0ac345d3eb`
```

:::{tip} Finding the config entry ID
:class: dropdown

Not sure what the `config_entry_id` of your integration is?

Use this action in the {term}`developer tools <developer tools>`, in the UI select the device you want to use and select the **Go to YAML mode** button. This will show you the config entry ID in the YAML code.
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.disable_config_entry
data:
  config_entry_id: "dc23e666e6100f184e642a0ac345d3eb"
```

Or multiple at once:

```{code-block} yaml
:linenos:
action: homeassistant.disable_config_entry
data:
  config_entry_id:
    - "dc23e666e6100f184e642a0ac345d3eb"
    - "df98a97c9341a0f184e642a0ac345d3b"
```

:::

### Enable an integration

Enable a single instance of an integration by its {term}`config entry <config entry>`.

```{figure} ./images/integration/enable_config_entry.png
:alt: Screenshot of the Home Assistant enable config entry action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Enable an integration 👻
* - {term}`Action name`
  - `homeassistant.enable_config_entry`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_config_entry)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_config_entry)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `config_entry_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `dc23e666e6100f184e642a0ac345d3eb`
```

:::{tip} Finding the config entry ID
:class: dropdown

Not sure what the `config_entry_id` of your integration is?

Use this action in the {term}`developer tools <developer tools>`, in the UI select the device you want to use and select the **Go to YAML mode** button. This will show you the config entry ID in the YAML code.
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.enable_config_entry
data:
  config_entry_id: "dc23e666e6100f184e642a0ac345d3eb"
```

Or multiple at once:

```{code-block} yaml
:linenos:
action: homeassistant.enable_config_entry
data:
  config_entry_id:
    - "dc23e666e6100f184e642a0ac345d3eb"
    - "df98a97c9341a0f184e642a0ac345d3b"
```

:::

### Disable polling for updates

Disable integration polling of a single integration instance by its {term}`config entry <config entry>`.

Some integrations frequently poll for updates. In some cases, it can be helpful to disable this temporarily. For example, in case you are not at home and want to stop polling on an integration that consumes a paid API.

```{figure} ./images/integration/disable_polling.png
:alt: Screenshot of the Home Assistant disable polling action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Disable polling for updates 👻
* - {term}`Action name`
  - `homeassistant.disable_polling`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_polling)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_polling)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `config_entry_id`
  - {term}`string <string>`
  - Yes
  - `dc23e666e6100f184e642a0ac345d3eb`
```

:::{tip} Finding the config entry ID
:class: dropdown

Not sure what the `config_entry_id` of your integration is?

Use this action in the {term}`developer tools <developer tools>`, in the UI select the device you want to use and select the **Go to YAML mode** button. This will show you the config entry ID in the YAML code.
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.disable_polling
data:
  config_entry_id: "dc23e666e6100f184e642a0ac345d3eb"
```

:::

### Enable polling for updates

Enable integration polling of a single integration instance by its {term}`config entry <config entry>`.

Some integrations frequently poll for updates. In some cases, it can be helpful to enable this just temporarily. For example, in case you are not at home and want to stop polling on an integration that consumes a paid API and want to turn it back on again when you are back.

```{figure} ./images/integration/enable_polling.png
:alt: Screenshot of the Home Assistant enable polling action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Enable polling for updates 👻
* - {term}`Action name`
  - `homeassistant.enable_polling`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_polling)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_polling)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `config_entry_id`
  - {term}`string <string>`
  - Yes
  - `dc23e666e6100f184e642a0ac345d3eb`
```

:::{tip} Finding the config entry ID
:class: dropdown

Not sure what the `config_entry_id` of your integration is?

Use this action in the {term}`developer tools <developer tools>`, in the UI select the device you want to use and select the **Go to YAML mode** button. This will show you the config entry ID in the YAML code.
:::

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.enable_polling
data:
  config_entry_id: "dc23e666e6100f184e642a0ac345d3eb"
```

:::

### Ignore all discovered devices & services

When Home Assistant discovers new devices or services, it will show up on the integration dashboard. You can ignore them one by one, but This action will allow you to ignore all of them at once.

It also supports ignoring all discovered devices from a specific {term}`integration <integration>`. For example, if you want to ignore all discovered devices from the `bluetooth` integration, you could do that periodically with an automation.

```{figure} ./images/integration/ignore_all_discovered.png
:alt: Screenshot of the Home Assistant enable polling action in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Ignore all currently discovered devices 👻
* - {term}`Action name`
  - `homeassistant.ignore_all_discovered`
* - {term}`Action targets`
  - No
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action.
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.ignore_all_discovered)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.ignore_all_discovered)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `domain`
  - {term}`string <string>`
  - No
  - `bluetooth`
```

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: homeassistant.ignore_all_discovered
data:
  domain: "esphome"
```

:::

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for these features. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
