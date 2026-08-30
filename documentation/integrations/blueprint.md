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
:alt: Screenshot of the Blueprint import action on the Tools page.
:align: center

Spook adds an action to import Blueprints directly from an URL.
```

## Devices & entities

Spook adds a Blueprints {term}`device <device>`, holding one update {term}`entity <entity>` for every {term}`automation <automation>` or {term}`script <script>` blueprint you imported from a URL.

### Updates

_Default {term}`entity ID <Entity ID>`: `update.blueprints_<blueprint name>`_

When you import a {term}`blueprint <blueprint>`, Home Assistant writes down where it came from. Nothing ever looks at that address again. The blueprint's author can fix a bug in it a week later and you would have no way of knowing, short of opening the forum topic and reading the YAML yourself.

Spook gives every one of those blueprints an update entity. It follows the address the blueprint came in with, roughly once a day, and tells you when what is there no longer matches what you have. Roughly, because each round picks its own moment for the next one somewhere in the following few hours: a fixed hour would have every installation that restarted after the same release knocking on the community forum together, every day, for ever. Pressing install fetches it again and writes it over the copy you have, exactly as Home Assistant's own re-import button does, and reloads every {term}`automation <automation>` and {term}`script <script>` using it.

Only blueprints that came from a URL get one. A blueprint you wrote yourself has no source to check against, and the three example blueprints Home Assistant lays down for you are left alone as well: they point at Home Assistant's development branch, which is not the version you are running.

Only automation and script blueprints, too. Those are the only two kinds whose users Home Assistant can list, and without that list there is no way to tell whether an update would leave one of them unable to load. An install button that cannot promise that is worse than no button at all, so template blueprints are left out until there is a way to check them.

#### What the update dialog tells you

Every other update dialog in Home Assistant shows you release notes. This one cannot, because there are none: a blueprint has no changelog, and the author is under no obligation to say anything anywhere.

So the dialog carries the next best thing. The address the blueprint came from, as a link, always, so you can go and read what actually changed before deciding. And a warning, because an update dialog looks the same whatever is behind it, and this one deserves a second thought: an author improving their blueprint and it still suiting the {term}`automations <automation>` you built on it are two different things. Inputs get renamed. Behaviour gets rethought.

If Spook already knows something is wrong, it says so there too. Automations the update would leave short, named. A blueprint that says it needs a newer Home Assistant than the one you are running. Or a source that has stopped leading to this blueprint at all, which is the answer to "why does this one never have an update".

The warning is advice, and an update that is otherwise fine still installs. The rest are refusals: Spook will not write a blueprint that would leave an automation or script short of an input, one that would not load once it has been built, or one that says it needs a Home Assistant you are not running.

Matter and ZHA put much the same warning in front of a firmware update, for much the same reason.

#### About those version numbers

They look like `a1b2c3d4`, and that is not Spook being clever. Blueprints have no version. There is nowhere in a blueprint to put one, because the format turns away anything it does not recognise, so no author can add one even if they wanted to.

So Spook uses a fingerprint of the contents instead. Same fingerprint, same blueprint. A different one means something in it changed. It cannot tell you whether that change is newer or better, only that it is not what you have.

Comments and indentation are not part of it. Somebody tidying up their YAML does not count as an update.

#### When an update would break your automations

An input without a default has to be filled in by whoever uses the blueprint. If a new version asks for one your automations do not set, every automation on that blueprint stops loading the moment the file is written, and the version they did work with is gone.

Spook checks before it writes anything, using Home Assistant's own reckoning of what an input needs rather than a second opinion that could drift from it. If an update would leave your automations short, it refuses, names the ones affected and the inputs they are missing, and leaves the blueprint alone. You can then either set those inputs first, or import the blueprint yourself from the blueprint page if you are happy to reconfigure things afterwards.

A blueprint that says it needs a newer Home Assistant than the one you are running is refused for the same reason: writing it would break every automation on it, on a version that was never going to work.

And so is one that would simply not run. A blueprint can be perfectly valid as a blueprint while what comes out of it is not something Home Assistant will take, because the blueprint format has nothing whatever to say about triggers, actions or a script's sequence. Spook builds every automation and script that uses the blueprint against the new version first and puts each one through the same validation a reload would, so a blueprint that would take them all out never reaches the disk.

:::{warning}
If you edited an imported blueprint by hand, Spook has no way of telling your changes apart from the author's. It will report an update, because what you have really is no longer what is at the address, and installing it will write over your work.

If you have made a blueprint your own, take the `source_url:` line out of the file. There is then nothing to follow, the update entity goes away on its own, and the blueprint is yours. That is also the way to stop following a blueprint whose author you would rather not track any more.
:::

:::{note}
Community forum topics sometimes hold more than one blueprint, and every one of them is imported carrying the address of the topic rather than of the blueprint itself. Home Assistant takes the first it finds at that address, so following it can land on a different blueprint entirely.

Blueprints carry no identity of their own, so the most that can be asked is that what comes back is the same kind of blueprint and still goes by the same name. If it does not, Spook leaves it alone and says why in the dialog, rather than offering to write somebody else's blueprint over yours.

The cost of that is an author who renames their blueprint: Spook stops following it, and the dialog will tell you what the address leads to now. Re-import it from the blueprint page and it picks up again.
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
* - {term}`Tools`
  - [Try this action](https://my.home-assistant.io/redirect/developer_call_service/?service=blueprint.import)
    [![Open your Home Assistant instance and show the Actions tool with a specific action selected.](https://my.home-assistant.io/badges/developer_call_service.svg)](https://my.home-assistant.io/redirect/developer_call_service/?service=blueprint.import)
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
