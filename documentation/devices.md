---
subject: Core extensions
title: Device management
subtitle: Which devices are you rocking? 🎸
date: 2023-06-30T20:36:04+02:00
---

A {term}`device <device>` in {term}`Home Assistant` represents a physical device in your home but can also represent a web service, like one that provides weather information. Devices are logical grouping for entities. Spook provides you with a few services to manage devices.

## Services

The following device management services are added to your Home Assistant instance:

### Disable a device

This service allows you to disable a device on the fly.

```{figure} ./images/devices/disable_device.png
:alt: Screenshot of the Home Assistant disable device service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Disable a device 👻
* - {term}`Service name`
  - `homeassistant.disable_device`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service.
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_device)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.disable_device)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `device_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `dc23e666e6100f184e642a0ac345d3eb`
```

:::{tip} Tip on finding a device ID
:class: dropdown

Not sure what the `device_id` of an your device is? There are a few ways to find it:

Use this service in the developer tools, in the UI select the device you want to add and select the **Go to YAML mode** button. This will show you the device ID in the YAML code.

Alternatively, you can visit the device page in the UI and look at the URL. The device ID is the last part of the URL, and will look something like this: `dc23e666e6100f184e642a0ac345d3eb`.
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.disable_device
data:
  device_id: "dc23e666e6100f184e642a0ac345d3eb"
```

Or multiple devices at once:

```{code-block} yaml
:linenos:
service: homeassistant.disable_device
data:
  device_id:
    - "dc23e666e6100f184e642a0ac345d3eb"
    - "df98a97c9341a0f184e642a0ac345d3b"
```

:::

### Enable a device

This service allows you to enable a device on the fly.

```{figure} ./images/devices/enable_device.png
:alt: Screenshot of the Home Assistant enable device service call in the developer tools.
:align: center
```

```{list-table}
:header-rows: 1
* - Service properties
* - {term}`Service`
  - Enable a device 👻
* - {term}`Service name`
  - `homeassistant.enable_device`
* - {term}`Service targets`
  - No
* - {term}`Service response`
  - No response
* - {term}`Spook's influence`
  - Newly added service.
* - {term}`Developer tools`
  - [Try this service](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_device)
    [![Open your Home Assistant instance and show your service developer tools with a specific service selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=homeassistant.enable_device)
```

```{list-table}
:header-rows: 2
* - Service call data
* - Attribute
  - Type
  - Required
  - Default / Example
* - `device_id`
  - {term}`string <string>` | {term}`list of strings <list>`
  - Yes
  - `dc23e666e6100f184e642a0ac345d3eb`
```

:::{tip} Tip on finding a device ID
:class: dropdown

Not sure what the `device_id` of an your device is? There are a few ways to find it:

Use this service in the developer tools, in the UI select the device you want to add and select the **Go to YAML mode** button. This will show you the device ID in the YAML code.

Alternatively, you can visit the device page in the UI and look at the URL. The device ID is the last part of the URL, and will look something like this: `dc23e666e6100f184e642a0ac345d3eb`.
:::

:::{seealso} Example {term}`service call <service call>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
service: homeassistant.enable_device
data:
  device_id: "dc23e666e6100f184e642a0ac345d3eb"
```

Or multiple devices at once:

```{code-block} yaml
:linenos:
service: homeassistant.enable_device
data:
  device_id:
    - "dc23e666e6100f184e642a0ac345d3eb"
    - "df98a97c9341a0f184e642a0ac345d3b"
```

:::

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for these features. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas and support

If you have an idea on how to further enhance this, for example, by adding a new service, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
