---
subject: Helpers
title: Inverse
subtitle: Stranger Things, the upside down 🙃
date: 2023-08-21T21:29:00+02:00
---

The inverse {term}`helper <helper>` allows you to invert the behavior of a {term}`switch <switch>`, {term}`binary sensor <binary sensor>`, cover, or valve entity. On becomes off, and off becomes on. Open becomes closed. The world is upside down!

This can be helpful if you use a switch or binary sensor in a non-standard way, or when the manufacturer of a device has decided to use the opposite logic for it (Yeah... they exist... 🤦‍♂️). Blinds with the motor mounted on the other side, a projector screen that opens by coming down: same story.

It not just inverts the state of the source {term}`entity <entity>`, but also does all {term}`actions <performing actions>` in reverse. So if you have an automation performing the turn on action on a switch, it will instead perform the turn off action on the inverted switch.

## What can be inverted

- An inverted **switch** can be made of a switch, an on/off toggle helper (`input_boolean`), or a light. Turning the inverted switch on turns the source off, with the source's own actions: a light is turned off as a light.
- An inverted **binary sensor** can read a binary sensor, an on/off toggle helper, or a light.
- An inverted **cover** or **valve** is made of a cover or a valve, as explained below.

A light inverted as a switch is only on or off: its brightness, colors and effects stay with the light itself.

## Inverting a cover

A cover can be backwards in two ways, and the inverse helper lets you turn around either one, or both:

- **Inverse opening, closing and position** (on by default): opening becomes closing and the other way around, and a position becomes its opposite. A cover that is 30% open is shown as 70% open, and telling the inverse to go to 70% sends the source to 30%.
- **Inverse tilt** (off by default): the same for the tilt of the slats. Handy for blinds that open and close fine, but tilt the wrong way.

The position decides whether the inverted cover is closed, not the state of the source. A cover counts as closed only at exactly 0%, and as open at anything above that. So the inverted cover is closed only when the source is all the way open. A cover that cannot report its position only knows open or closed, and has just that turned around.

## Inverting a valve

A valve works the same way as a cover, without the tilt: opening becomes closing, a position becomes its opposite, and the inverted valve is closed only when the source is all the way open. There are no extra options, as a valve only moves one way.

## Inverting the behavior of an entity

The inverse helper can be used to invert the behavior of a switch, binary sensor, cover, or valve entity.

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
