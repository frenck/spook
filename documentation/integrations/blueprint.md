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

Spook adds one update {term}`entity <entity>` for every {term}`automation <automation>` or {term}`script <script>` blueprint you imported from a URL. No {term}`device <device>`: a blueprint is a file, and the updates page reads a row by the device it belongs to, so putting them all on one would leave every row saying the same thing.

### Updates

_Default {term}`entity ID <Entity ID>`: `update.<blueprint name>`_

When you import a {term}`blueprint <blueprint>`, Home Assistant writes down where it came from. Nothing ever looks at that address again. The blueprint's author can fix a bug in it a week later and you would have no way of knowing, short of opening the forum topic and reading the YAML yourself.

Spook gives every one of those blueprints an update entity. It follows the address the blueprint came in with, roughly once a day, and tells you when what is there no longer matches what you have. Roughly, because each round picks its own moment for the next one somewhere in the following few hours: a fixed hour would have every installation that restarted after the same release knocking on the community forum together, every day, for ever. Pressing install fetches it again and writes it over the copy you have, exactly as Home Assistant's own re-import button does, and reloads every {term}`automation <automation>` and {term}`script <script>` using it.

The dialog offers to keep a copy of the file first, and it is worth ticking. Installing writes over the blueprint you have, and if you ever edited that blueprint yourself, your edits are what gets written over.

Only blueprints that came from a URL get one. A blueprint you wrote yourself has no source to check against, and the three example blueprints Home Assistant lays down for you are left alone as well: they point at Home Assistant's development branch, which is not the version you are running.

Only automation and script blueprints, too. Those are the only two kinds whose users Home Assistant can list, and without that list there is no way to tell whether an update would leave one of them unable to load. An install button that cannot promise that is worse than no button at all, so template blueprints are left out until there is a way to check them.

Delete a blueprint, or take the source address back out of it, and the update {term}`entity <entity>` goes with it. Blueprints raise no events, so nothing notices at the moment it happens: the next round does. One deleted while Home Assistant was stopped is caught the next time Spook starts, so you are not left with an entity in the list and no blueprint behind it.

#### Where the copies go

Beside the blueprint itself, in the same folder, with the date and time it was put there added to the filename:

```{code-block} text
config/blueprints/automation/frenck/motion_light.yaml
config/blueprints/automation/frenck/motion_light.yaml.2026-08-31_204512.bak
config/blueprints/automation/frenck/motion_light.yaml.2026-08-24_091133.bak
```

So a copy sits next to the blueprint it belongs to, wherever in `blueprints/` that blueprint lives. The time is your own rather than UTC, so it reads by the same clock you do. The newest three per blueprint are kept, and installing a fourth update lets go of the oldest.

To go back to one, rename it over the blueprint it is a copy of and reload your {term}`automations <automation>` or {term}`scripts <script>`. Nothing about a `.bak` file is special to Home Assistant, so whatever you already use to reach your configuration folder will do: the File editor or Studio Code Server add-ons, Samba, SSH. There is no action for it, because putting one back is a rename and the file is already sitting there.

The extension deliberately does not end in `.yaml`. Home Assistant reads every `.yaml` file under the blueprint folders as a blueprint, so a copy named that way would turn up in your blueprint list, and be given an update entity of its own.

#### What the update dialog tells you

Every other update dialog in Home Assistant shows you release notes. This one cannot, because there are none: a blueprint has no changelog, and the author is under no obligation to say anything anywhere.

So the dialog carries the next best thing. The address the blueprint came from, as a link, always, so you can go and read what actually changed before deciding. And a warning, because an update dialog looks the same whatever is behind it, and this one deserves a second thought: an author improving their blueprint and it still suiting the {term}`automations <automation>` you built on it are two different things. Inputs get renamed. Behaviour gets rethought.

It also tells you what changed, which is Spook comparing the two files rather than the author saying anything:

```{code-block} text
**Compared with the copy you have:**
- **New settings**: Wait time
- What it does **changed**
```

What an author did, and what you get told:

```{list-table}
:header-rows: 1
:widths: 40 60

* - What the author did
  - What the dialog says
* - Tidied up the description
  - Its description **changed**
* - Added an input
  - **New settings**: Wait time
* - Renamed an input, kept its label
  - **New settings**: Motion sensor (`motion_sensor`), **Settings taken away**: Motion sensor (`motion_entity`)
* - Put a selector on an input
  - **Settings changed**: Motion sensor
* - Changed what it does
  - What it does **changed**
* - Changed when it fires
  - When it runs **changed**
* - Changed the mode
  - How it handles overlapping runs **changed**
* - Moved two settings around, or gathered them into sections
  - **The settings are arranged differently**
* - Said it no longer needs a particular Home Assistant
  - It **no longer asks** for a particular Home Assistant version
* - Rewrote it, 80 things changed
  - **New settings**: 80, What it does **changed**, When it runs **changed**
```

Settings are named as their author named them, up to three of them. Past that you get the count, because eighty names is a wall rather than a release note, and they are all in the blueprint for whoever wants to read them.

The rename in that table is the one this exists for. An author who changes the key an input is stored under and leaves its label alone gives you two settings that read exactly the same, while whatever you filled in sits under the old key and the new version never looks there. So the key comes along whenever a label on its own would not tell them apart.

And if Spook cannot read the copy you have at that moment, it says so instead of saying nothing, because saying nothing reads as "nothing changed".

Underneath that, what is built on the {term}`blueprint <blueprint>`, because an update writes over a file other things are running on and which ones is not written down anywhere you can see:

```{code-block} text
**The following 2 automations are using this blueprint:**

- [Hallway light](/config/automation/edit/hallway)
- [Porch light](/config/automation/edit/porch)
```

Each one links to its editor, so you can go and look at what an update is about to reach before you install it. An {term}`automation <automation>` written in YAML without an `id:` has no editor to open, so that one links to the overview page instead. And when nothing is built on it you get told that too, in as many words, because it means you can install without reading any further.

And underneath that, the difference itself, folded away because most people want the sentence above it:

```{code-block} text
@@ -7,11 +7,14 @@
       name: Motion sensor
     light_target:
       name: Light
+    wait_time:
+      name: Wait time
+      default: 120
 trigger:
 - platform: state
   entity_id: !input motion_entity
   to: 'on'
 action:
-- service: light.turn_on
+- service: light.toggle
   entity_id: !input light_target
 mode: restart
```

Both sides go through Home Assistant's own YAML writer before being compared. Without that, the file on your disk (written by Home Assistant) and the one just fetched (in its author's layout) differ in indentation and quoting before they differ in anything that matters: eleven lines of that on an eighteen-line {term}`blueprint <blueprint>` that had not changed at all, and hundreds of those on a large one. What is left after writing both out the same way is only what moved. Past a hundred lines it stops and says how many more there were, because all of it travels to your browser whether you open it or not. And a {term}`blueprint <blueprint>` past a few thousand lines is not compared line by line at all: the work grows with the square of the length, which on a real one of 36,000 lines came to ten seconds, all of it to build something that would then be cut to a hundred lines anyway.

**What an update is going to cost you comes first**, above everything else, because people do not read to the bottom for a headline. What changed and what is built on the {term}`blueprint <blueprint>` are still there underneath, as context.

The colour is the whole of the message. **Orange is your decision**: what is listed will stop loading, and Spook is telling you so and installing it anyway if you say so. **Red is Spook's**: it will not write this one at all.

There is exactly one red case. A {term}`blueprint <blueprint>` that says it needs a newer Home Assistant than you are running cannot work on your installation no matter what you do to your {term}`automations <automation>`, so writing it would break everything on it with no way out but upgrading Home Assistant.

Everything else is orange, including an update that adds a setting nobody has filled in yet. Those {term}`automations <automation>` do stop loading, and that is worth saying loudly, but updating first and filling the new setting in afterwards is a perfectly ordinary way round and which way round you want is not Spook's to decide. Nothing is lost either: a stopped automation keeps its configuration and its ID, its editor opens it as normal, and you fill in what the new version asks for. Ticking **Create backup** first means you can put the {term}`blueprint <blueprint>` back as well.

Matter and ZHA put much the same warning in front of a firmware update, for much the same reason.

#### About those version numbers

They look like `a1b2c3d4`, and that is not Spook being clever. Blueprints have no version. There is nowhere in a blueprint to put one, because the format turns away anything it does not recognise, so no author can add one even if they wanted to.

So Spook uses a fingerprint of the contents instead. Same fingerprint, same blueprint. A different one means something in it changed. It cannot tell you whether that change is newer or better, only that it is not what you have.

The fingerprint is taken from what a blueprint says, not from how the file is laid out. Home Assistant does not keep the bytes it downloaded: it parses a blueprint and writes it back out in its own formatting, and that formatting is free to differ between installations and Home Assistant releases. Line width, quoting, whether an emoji is written out or escaped, all of it. None of that changes what the blueprint does, so none of it changes the fingerprint. Neither does the address it came from, which Home Assistant stores inside the blueprint on the way in, nor the order of the settings it fills in for a selector the author left blank: `multiple`, `reorder` and the like are Home Assistant's doing, not the blueprint's.

Comments and indentation are not part of it either, since neither survives being parsed. Reordering any other key is, though. Home Assistant renders some of them in the order they are written, a `variables:` block among them, so moving two keys around can change what a blueprint does. Spook keeps that order rather than trying to work out which mappings are the executable ones, because guessing wrong there would mean missing a real update rather than mentioning an extra one.

#### When an update would break your automations

An input without a default has to be filled in by whoever uses the blueprint. If a new version asks for one your automations do not set, every automation on that blueprint stops loading the moment the file is written, and the version they did work with is gone.

Spook checks before it writes anything, using Home Assistant's own reckoning of what an input needs rather than a second opinion that could drift from it. If an update would leave your {term}`automations <automation>` short it names them, and the settings each one is missing, above everything else in the dialog. It still installs if you ask it to: those {term}`automations <automation>` stop loading, and they keep everything you set and their editors still open, so you fill the new setting in and they come back.

It checks the other way round too. A {term}`blueprint <blueprint>` can be perfectly valid as a blueprint while what comes out of it is not something Home Assistant will take, because the blueprint format has nothing whatever to say about triggers, actions or a script's sequence. So every {term}`automation <automation>` and {term}`script <script>` on the blueprint is built against the new version and put through the same validation a reload would, and anything that would not load is named the same way. That one is for the blueprint's author to fix rather than you: no setting you fill in will change it.

And where it cannot tell, it says so separately. Reading what an {term}`automation <automation>` supplies to a blueprint relies on something Home Assistant does not offer publicly, and when that is out of reach Spook has nothing to go on. Those are listed as not known rather than as broken, because an {term}`automation <automation>` nothing can be read about may be perfectly fine.

A {term}`blueprint <blueprint>` that says it needs a newer Home Assistant than the one you are running is the one thing Spook refuses outright. Writing it would break every {term}`automation <automation>` on it, on a version that was never going to work, and nothing you do to your own {term}`automations <automation>` gets you out of that.

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
