---
subject: Getting started
title: Using Spook with Home Assistant
subtitle: Spook is oddly familiar.
short_title: Usage
thumbnail: images/usage/services_example.png
description: Spook is oddly familiar, it extends existing Home Assistant functionality, everything you already know about Home Assistant applies. There is just more of it!
date: 2023-08-09T21:29:00+02:00
---

Now you have Spook [installed](installation); you can start using it. It is hard to explain what Spook does, but its experience in using it is best described as: _oddly familiar_ 🙂.

As Spook extends existing {term}`Home Assistant` functionality, everything you already know about Home Assistant applies. You might run into an issue raised in the {term}`repairs dashboard <repairs>` by Spook, have more {term}`devices <device>` and {term}`entities <entity>` to play with, some {term}`actions <action>` have more options available, and new actions will appear when you create new {term}`automations <automation>`.

## Repairs

Spook will constantly float around in your Home Assistant instance, and if it finds potential issues along the way, it will report them to you by creating an issue in the Home Assistant {term}`repairs dashboard <repairs>`.

```{figure} images/usage/repairs_example.png
:name: Spook raised a repair issue
:alt: Screenshot showing an repair issue raised by Spook.
:align: center

This automation uses some entities that do not exist.
```

Spook will always provide you with information on how to fix the issue and, if possible, even provide you with a button to fix it for you.

Maybe Spook has already found something? You can use the {term}`My Home Assistant` button below to open your Home Assistant instance and show your repairs dashboard.

[![Open your Home Assistant instance and show your repairs.](https://my.home-assistant.io/badges/repairs.svg)](https://my.home-assistant.io/redirect/repairs/)

## Actions

{term}`Actions <actions>` are a common way to control Home Assistant. Most of the {term}`actions <action>` you'll use in an automations. Spook will add new features to existing actions that you can use in your {term}`automations <automation>` and {term}`scripts <script>`. It will also add lots of new ones.

Spook reveals himself on each of the action he added or enriched, so you can easily find and identify them in your Home Assistant instance.

```{figure} images/usage/services_example.png
:name: Spook provides lots of new and powerful actions.
:alt: Screenshot showing a list of actions provided by Spook.
:align: center

On each action Spook added or enriched, he reveals himself 👻.
```

If you like to explore all available actions Spook provides and play with them from the comfort of your Home Assistant instance, you can use the {term}`My Home Assistant` button below to open your Home Assistant instance and show your actions {term}`developer tools <developer tools>`. Scroll through the list of actions available and you will notice Spook being there.

[![Open your Home Assistant instance and show your actions developer tools.](https://my.home-assistant.io/badges/developer_services.svg)](https://my.home-assistant.io/redirect/developer_services/)

Alternatively, take a look at our [actions reference page](actions) to get an instant overview of all actions provided by Spook.

## Devices & Entities

Spook will add new {term}`devices <device>` and {term}`entities <entity>` to your Home Assistant instance. Giving you more data points to use in your {term}`automations <automation>`, {term}`scripts <script>`, {term}`templates <template>`, and {term}`dashboards <dashboard>`.

```{figure} images/usage/device_example.png
:name: Spook also adds new devices & entities to your instance
:alt: Screenshot showing a Home Assistant Cloud device page, added by Spook.
:align: center

Spook added a device and entities for {term}`Home Assistant Cloud`.
```

You can find most devices & entities Spook provides, on the Spook integration page. You can use the {term}`My Home Assistant` button below to open your Home Assistant instance and show the Spook integration page.

[![Open your Home Assistant instance and show an integration.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=spook)
