---
subject: Enhanced integrations
title: Blueprints
subtitle: Don't be a blueprint. Be an original.
thumbnail: ../images/integrations/blueprint/example.png
description: Spook enhances the Home Assistant Blueprint integration with new features to use in automations or scripts.
date: 2023-08-09T21:29:00+02:00
---

```{image} https://brands.home-assistant.io/blueprint/logo.png
:alt: The Home Assistant Blueprint icon
:width: 250px
:align: center
```

<br><br>

A {term}`blueprint <blueprint>` in {term}`Home Assistant` is a reusable {term}`automation <automation>` or {term}`script <script>`, most often shared and created by the community, that can be imported into your Home Assistant instance.

They are a great way to learn how to automate your home and an inspiration for new automation ideas, or just an easy way to get started. Blueprints are a great method to share your automation creations with others, so that others can apply them to their own homes.

```{figure} ../images/integrations/blueprint/example.png
:name: example
:alt: Screenshot of the Blueprint import action in the developer tools.
:align: center

Spook adds an action to import Blueprints directly from an URL.
```

## Devices & entities

Spook does not provide any new devices or entities for this integration.

## Actions

Spook adds the following new actions to your Home Assistant instance:

### Import blueprint

Downloads and imports an automation/script blueprint, directly from the URL you pass into this action.

```{list-table}
:header-rows: 1
* - Action properties
* - {term}`Action`
  - Blueprint: Import blueprint 👻
* - {term}`Action name`
  - `blueprint.import`
* - {term}`Action targets`
  - No targets
* - {term}`Action response`
  - No response
* - {term}`Spook's influence <influence of spook>`
  - Newly added action
* - {term}`Developer tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=blueprint.import)
    [![Open your Home Assistant instance and show your actions developer tools with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=blueprint.import)
```

```{list-table}
:header-rows: 2
* - Action data parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `url`
  - {term}`string <string>`
  - Yes
  - Any URL to a Blueprint
```

The `url` attribute is the URL to the blueprint you want to import. This can be any URL as long as it is a valid blueprint.

:::{seealso} Example {term}`action <performing actions>` in {term}`YAML`
:class: dropdown

```{code-block} yaml
:linenos:
action: blueprint.import
data:
  url: "https://community.home-assistant.io/t/your-blueprint-url"
```

:::

:::{warning}
It is recommended to import blueprints via the Home Assistant UI. The UI will show you a preview of the blueprint, allowing you to view any errors or warnings before importing it.
:::

## Repairs

Spook has no repair detections for this integration.

## Uses cases

Some use cases for the enhancements Spook provides for this integration:

- Automatically download and import Blueprints. For example, write a script that automatically downloads the top 10 Blueprints from the Home Assistant community forums.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Features requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
