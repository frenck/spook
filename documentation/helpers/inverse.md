---
subject: Helpers
title: Inverse
subtitle: Stranger Things, the upside down 🙃
date: 2023-08-21T21:29:00+02:00
---

The inverse {term}`helper <helper>` allows you to invert the behavior of a {term}`switch <switch>` or {term}`binary sensor <binary sensor>` entity. On becomes off, and off becomes on. The world is upside down!

This can be helpful if you use a switch or binary sensor in a non-standard way, or when the manufacturer of a device has decided to use the opposite logic for the switch or binary sensor (Yeah... they exist... 🤦‍♂️).

It not just inverts the state of the source {term}`entity <entity>`, but also does all {term}`actions <performing actions>` in reverse. So if you have an automation performing the turn on action on a switch, it will instead perform the turn off action on the inverted switch.

## Inverting the behavior of an entity

The inverse helper can be used to invert the behavior of a switch or binary sensor entity.

Don't worry! This is really easy and all fully done via the Home Assistant user interface.

Add one directly to your own instance by selecting the {term}`My Home Assistant` button below:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=spook_inverse)

Or add one manually, using the following steps:

1. From the Home Assistant sidebar, select **Settings** and next select **Devices & Services**.
2. Select the **Helpers** tab.
3. On the helpers page, in the bottom right corner, select the **+ Create helper** button.
4. From the list of helpers, select **Inverse 👻**.

```{figure} ../images/helpers/inverse/helper_dialog.png
:alt: Screenshot of the add helper dialog, which lists the inverse helper.
:align: center
```

5. Select the type of entity you want to invert the behavior of.

```{figure} ../images/helpers/inverse/select_entity_type.png
:alt: Screenshot of the inverse helper dialog, which allows you to select the type of entity to invert.
:align: center
```

6. Provide a name for your new inverted entity this helpers provides, and select the entity you want to invert the behavior of in the **Source entity** field.
7. Turn on **Hide source entity**, if you want to hide the source entity from the Home Assistant interface.

```{figure} ../images/helpers/inverse/configure.png
:alt: Screenshot of the inverse helper dialog, configuring the new inverted entity.
:align: center
```

8. Select **Submit**. Done! 🎉

```{figure} ../images/helpers/inverse/done.png
:alt: Screenshot showing the newly inverted switch, created with the procedure described above.
:align: center
```
