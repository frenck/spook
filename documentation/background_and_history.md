---
subject: About the project
title: Background and the history of Spook 👻
short_title: Background & History
subtitle: Every story has a beginning.
thumbnail: images/social.png
description: The background and history of Spook, the custom integration that provides a scary powerfull toolbox for Home Assistant.
date: 2023-06-30T13:47:47+02:00
---

Spook is a project created and started by [Franck Nijhof](https://github.com/frenck) (better known as Frenck) on [February the 23rd of 2023](https://github.com/frenck/spook/commit/67803faf19bca7c8543e0865e1dba58755315652).

## About the author

Frenck is a {term}`Home Assistant` enthusiast and has been of the community since 2016. He is a member of the Home Assistant project, and has worked on many Home Assistant related projects since then.

In 2019, Frenck was hired by [Nabu Casa](https://www.nabucasa.com) to work full-time on Home Assistant and related projects.

## How Spook was born

Frenck reviews lots of contributions and is heavily involved in the architectural design of Home Assistant. Some contributions, ideas, or architectural design proposals are not accepted or implemented in Home Assistant.

This is not because they are bad, but because they do not fit the scope of Home Assistant, or maybe because they impose too much of a risk or burden on the Home Assistant project.

Whatever the reason may be for features not being added to Home Assistant, there is still a strong wish for some of these features to exist by the Home Assistant community.

Frenck felt the need to fill this gap and started working on a solution, and Spook was born.

Spook is a {term}`custom integration <integration>` created to fill the gap between Home Assistant and the community's wishes in a way. It is a toolbox of features that are not part of Home Assistant itself, but that are still useful to some.

Along the way, it also became a place for experimental features, that might end up in Home Assistant one day. They are useable but not perfect enough yet.

## Why the name Spook?

Frenck is [Dutch](wiki:The_Netherlands) and grew up with "Casper het vriendelijke spookje", also known as <wiki:Casper_the_Friendly_Ghost>. "Spook" is the Dutch for "ghost".

Casper is scary at first sight, but you quickly get to like him. Which seems fitting for a {term}`custom integration <integration>`, as custom integrations are more likely to break, thus being a little scared of them is not a bad thing.

"Not your homie" is a refence to the livestreams Frenck used to do. He called his viewers "My Home Assistant Homies", or just "Homies". It is thus referring to you, the Home Assistant user, as its friend, its homie. However, "Spook" is not your homie, it is a ghost, a spooky thing, he is suposed to make you think a little about what you are doing before you use it.

Nice little fact, it used to be "homey" at first (to maybe annoy the [Homey](https://homey.app) users a bit in SEO), but I decided not to be that _\*\*badword\*\*_ and to change it back to just "homie".

Lastly, the little ghost logo & use of the emoji. This is great inspiration that I took from the [🍄&nbsp;Mushroom&nbsp;card&nbsp;project](https://github.com/piitaya/lovelace-mushroom) (I love it! ❤️). They use a simple mushroom emoji and you see it everywhere in the Home Assistant community, thus decided to do a similar thing.

## Goals of Spook

The goal of spook is fairly simple: [**be the rebel**](wiki:rebel).

Spook is here to be the rebel, the one that does not care about the rules, the one that does not care about the architectural design, the one that does not care about the philosophy of the {term}`Home Assistant` project.

It aims to:

- Add new services to existing Home Assistant {term}`integrations <integration>`, providing control of features you can use in your {term}`automations <automation>` and {term}`scripts <script>`.
- Inject new features into exiting native {term}`services <service>` of Home Assistant integrations to add new options/functionality to them.
- Add extra/new entities to existing Home Assistant integrations, giving you more datapoints to monitor and control.
- Find and raise issues on your {term}`repairs dashboard <repairs>` found on your Home Assistant instance, to help you keep your instance healthy, clean and tidy.
- And more... nothing is impossible.

Spook will use almost any trick in the book to get the job done. It will use undocumented features, it will use private API's, it will use monkeypatching, it will use workarounds, it will use whatever it takes to get the job done.

While some features are not in Home Assistant (for a reason), you might be opiniated differently. Spook doesn't care, isn't here to judge or be the homie of anyone. And who knows, maybe some features turn out to be great afterall, and end up in Home Assistant one day.