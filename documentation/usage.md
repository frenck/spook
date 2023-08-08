---
subject: Getting started
title: Using Spook with Home Assistant
subtitle: Spook is oddly familiar.
short_title: Usage
thumbnail: images/usage/services_example.png
description: Spook is oddly familiar, it extends existing Home Assistant functionality, everything you already know about Home Assistant applies. There is just more of it!
date: 2023-06-30T09:31:26+02:00
---

Now you have Spook [installed](installed), you can start using it. It is hard to explain what Spook does, but its experience in using it is best described as: oddly familiar.

As Spook extends existing {term}`Home Assistant` functionality, everything you already know about Home Assistant applies, you might run into an issue raised in the {term}`repairs dashboard <repairs>` by Spook, have more {term}`devices <device>` and {term}`entities <entity>` to play with, some {term}`services <service>` have more options available, and new services will appear when you create new {term}`automations <automation>`.

## Repairs

Spook will constantly float around in your Home Assistant instance, and if it finds potential issues along the way, it will report them to you by creating an issue in the Home Assistant {term}`repairs dashboard <repairs>`.

```{figure} images/usage/repairs_example.png
:name: Spook raised a repair issue
:alt: Screenshot showing an repair issue raised by Spook.
:align: center

This automation is using some entities that do not exist.
```

Spook will always provide you with information on how to fix the issue, and if possible, even provide you with a button to fix it for you.

Maybe Spook has already found something? You can use the {term}`My Home Assistant` button below to open your Home Assistant instance and show your repairs dashboard.

[![Open your Home Assistant instance and show your repairs.](https://my.home-assistant.io/badges/repairs.svg)](https://my.home-assistant.io/redirect/repairs/)

## Services

{term}`Services <service>` are a common way to control Home Assistant, most of the actions you'll use in an automation are calling services. Spook will add new features to existing services that you can use in your {term}`automations <automation>` and {term}`scripts <script>`. It will also add lots of new ones.

Spook reveals himself on each of the services he added or enriched, so you can easily find and identify them in your Home Assistant instance.

```{figure} images/usage/services_example.png
:name: Spook provides lots of new and powerful services.
:alt: Screenshot showing a list of services provided by Spook.
:align: center

On each service Spook added or enriched, he reveals himself 👻.
```

If you like to explore all available services Spook provides and play with them from the comfort of your Home Assistant instance, you can use the {term}`My Home Assistant` button below to open your Home Assistant instance and show your service developer tools. Scroll through the list of services available and you will notice Spook being there.

[![Open your Home Assistant instance and show your service developer tools.](https://my.home-assistant.io/badges/developer_services.svg)](https://my.home-assistant.io/redirect/developer_services/)

Alternatively, you could take a look at our [services reference page](services) to get an instant overview of all services provided by Spook.

## Devices & Entities

Spook will add new {term}`devices <device>` and {term}`entities <entity>` to your Home Assistant instance. Giving you more datapoints to use in your {term}`automations <automation>`, {term}`scripts <script>`, {term}`templates <template>` and {term}`dashboards <dashboard>`.

```{figure} images/usage/device_example.png
:name: Spook also adds new devices & entities to your instance
:alt: Screenshot showing a Home Assistant Cloud device page, added by Spook.
:align: center

Spook added a device and entities for Home Assistant Could.
```

You can find most devices & entities Spook provides, on the Spook integration page. You can use the {term}`My Home Assistant` button below to open your Home Assistant instance and show the Spook integration page.

[![Open your Home Assistant instance and show an integration.](https://my.home-assistant.io/badges/integration.svg)](https://my.home-assistant.io/redirect/integration/?domain=spook)
