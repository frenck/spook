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

Spook adds a Blueprints {term}`device <device>`, holding one update {term}`entity <entity>` for every blueprint you imported from a URL.

### Updates

_Default {term}`entity ID <Entity ID>`: `update.blueprints_<blueprint name>`_

When you import a {term}`blueprint <blueprint>`, Home Assistant writes down where it came from. Nothing ever looks at that address again. The blueprint's author can fix a bug in it a week later and you would have no way of knowing, short of opening the forum topic and reading the YAML yourself.

Spook gives every one of those blueprints an update entity. It follows the address the blueprint came in with, once a day, and tells you when what is there no longer matches what you have. Pressing install fetches it again and writes it over the copy you have, exactly as Home Assistant's own re-import button does, and reloads every {term}`automation <automation>` and {term}`script <script>` using it.

Only blueprints that came from a URL get one. A blueprint you wrote yourself has no source to check against, and the three example blueprints Home Assistant lays down for you are left alone as well: they point at Home Assistant's development branch, which is not the version you are running.

#### About those version numbers

They look like `a1b2c3d`, and that is not Spook being clever. Blueprints have no version. There is nowhere in a blueprint to put one, because the format turns away anything it does not recognise, so no author can add one even if they wanted to.

So Spook uses a fingerprint of the contents instead. Same fingerprint, same blueprint. A different one means something in it changed. It cannot tell you whether that change is newer or better, only that it is not what you have.

Comments and indentation are not part of it. Somebody tidying up their YAML does not count as an update.

#### When an update would break your automations

An input without a default has to be filled in by whoever uses the blueprint. If a new version asks for one your automations do not set, every automation on that blueprint stops loading the moment the file is written, and the version they did work with is gone.

Spook checks before it writes anything. If an update would leave your automations short, it refuses, names the ones affected and the inputs they are missing, and leaves the blueprint alone. You can then either set those inputs first, or import the blueprint yourself from the blueprint page if you are happy to reconfigure things afterwards.

:::{warning}
If you edited an imported blueprint by hand, Spook has no way of telling your changes apart from the author's. It will report an update, because what you have really is no longer what is at the address, and installing it will write over your work.

If you have made a blueprint your own, take the `source_url:` line out of the file. There is then nothing to follow, the update entity goes away on its own, and the blueprint is yours. That is also the way to stop following a blueprint whose author you would rather not track any more.
:::

:::{note}
Community forum topics sometimes hold more than one blueprint, and both of them are imported carrying the address of the topic rather than of the blueprint itself. Following that address can land on the wrong one.

Spook checks that what it finds is at least the same kind of blueprint, an automation for an automation, before offering anything. If it is not, the entity stays quiet rather than offering to replace your blueprint with somebody else's.
:::

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

## Use cases

Some use cases for the enhancements Spook provides for this integration:

- Automatically download and import Blueprints. For example, write a script that automatically downloads the top 10 Blueprints from the Home Assistant community forums.
- Get told when the author of a blueprint you use has changed it, instead of finding out months later that the bug you worked around was fixed all along.
- Put the blueprint update entities in an automation of your own, so a notification goes out when one of them has something new to say.

## Blueprints & tutorials

There are currently no known {term}`blueprints <blueprint>` or tutorials for the enhancements Spook provides for this integration. If you created one or stumbled upon one, [please let us know in our discussion forums](https://github.com/frenck/spook/discussions).

## Feature requests, ideas, and support

If you have an idea on how to further enhance this integration, for example, by adding a new action, entity, or repairs detection; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using these new features? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
