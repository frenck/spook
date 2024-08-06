---
subject: Enhanced integrations
title: Home Assistant Cloud
subtitle: Automate and control your Home Assistant Cloud connection.
thumbnail: ../images/integrations/cloud/example.png
description: Spook enhances the Home Assistant Cloud integration by creating a device for it and adding a series of entities that, for example, provide control over enabling and disabling cloud connections.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/cloud/logo.png
:alt: The Home Assistant Cloud logo
:width: 250px
:align: center
```

<br><br>

The Home Assistant Cloud allows you to effortlessly use your {term}`Home Assistant` with various cloud services like Amazon Alexa and Google Assistant, but also provides remote access to your Home Assistant instance without having to deal with dynamic DNS, SSL certificates, and opening ports on your router.

Spook enhances the Home Assistant Cloud integration by creating a device for it and adding a series of {term}`entities <entity>` that can be used in your dashboards, automations, and scripts.

:::{tip}
The Home Assistant Cloud service is provided by [Nabu Casa](https://www.nabucasa.com). The earnings from the services provided are used to fund Home Assistant development and related projects in the open home community.

Please consider subscribing to the Home Assistant Cloud service to support the development of Home Assistant. 🙏
:::

```{figure} ../images/integrations/cloud/example.png
:name: exapmle
:alt: Screenshot showing a new device that provides control over your Home Assistant Cloud connection.
:align: center

Spook added a device and entities for Home Assistant Cloud.
```

## Devices & entities

Spook adds a single new device with entities for this integration to your Home Assistant instance.

### Switches

#### Alexa

_Default {term}`entity ID <Entity ID>`: `switch.cloud_alexa`_

This allows you to fully enable/disable integrating your instance with Amazon Alexa.

#### Alexa state reporting

_Default {term}`entity ID <Entity ID>`: `switch.cloud_alexa_report_state`_

Allows you to control the state reporting to Alexa from an entity. If you enable state reporting, Home Assistant will send all state changes of exposed entities to Amazon. This allows you to always see the latest states in the Alexa app and use the state changes to create routines.

#### Google Assistant

_Default {term}`entity ID <Entity ID>`: `switch.cloud_google_assistant`_

This allows you to fully enable/disable integrating your instance with Google Assistant.

#### Google Assistant state reporting

_Default {term}`entity ID <Entity ID>`: `switch.cloud_google_assistant_report_state`_

Allows you to control the state reporting to Google Assistant from an entity. If you enable state reporting, Home Assistant will send all state changes of exposed entities to Google. This allows you to always see the latest states in the Google Home app and use the state changes to create routines.

#### Remote

_Default {term}`entity ID <Entity ID>`: `switch.cloud_remote`_

This allows you to enable/disable remote access to your Home Assistant instance from the web.

## Actions

Spook does not provide action enhancements for this integration.

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Disable remote access to your Home Assistant instance when you are home, using an automation; and automatically enable it again when you leave your home.
- Disable Alexa integration when you are not at home using an automation.
- Disable Google Assistant integration when you are not at home using an automation.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
