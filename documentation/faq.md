---
subject: About the project
title: Frequently asked questions (FAQ)
short_title: Frequently asked questions
subtitle: You've got questions? We've got answers!
thumbnail: images/social.png
description: Answer to the most frequently asked questions about Spook for Home Assistant.
date: 2023-08-09T21:29:00+02:00
---

Some of the same questions keep popping up. So, here are some answers to the most common questions about Spook 👻.

```{card}
:header: **Is this a serious thing?**

**Yes!** It absolutely is.

It is just not a normal {term}`integration`, like one that connects to a {term}`device` or {term}`service`, or one that provides a {term}`helper <helper>` of some sort. But it is a serious integration that is meant to be used in a serious way.
```

```{card}
:header: **Does this integration break my Home Assistant instance??**

Well, that is not the goal of course. But it is a {term}`custom integration <integration>`, so there is a chance it might break your instance. This applies to any custom integration, not just Spook.

I'm just sharing what I have [without any warranty](license).
```

```{card}
:header: **Does Spook do random things to my home?**

No. It does not do random things. It is not a [chaos testing](wiki:Chaos_engineering) thing, and it will not turn lights on/off randomly in the night. Unless it is a bug or broken of course.
```

```{card}
:header: **I want to suggest a new feature for Spook**

Oh! Lovely, please [share your idea on our discussion forums](https://github.com/frenck/spook/discussions)! Maybe it is something that can be added to Spook 👻 in the future.
```

```{card}
:header: **Why is Spook called Spook?**

"Spook" is the [Dutch](wiki:The_Netherlands) term for "ghost", as was inspired
by <wiki:Casper_the_Friendly_Ghost>. Check out the [](background_and_history) for a more detailed version of the story.
```

```{card}
:header: **What is going on with the version numbers of Spook?**

This repository keeps a change log using [GitHub's releases](https://github.com/frenck/spook/releases) functionality.

Releases are based on [Semantic Versioning](https://semver.org/spec/v2.0.0.html), and use the format of `MAJOR.MINOR.PATCH`. In a nutshell, the version will be incremented based on the following:

- `MAJOR`: Incompatible or major changes.
- `MINOR`: Backwards-compatible new features and enhancements.
- `PATCH`: Backwards-compatible bug fixes and package updates.

The version change you see on upgrade will thus tell you what type of changes you can expect.

All versions before v1.0.0 have been different and were random version numbers. From v1.0.0 and forwards, the versioning is based on the above.
```

```{card}
:header: **I'm waiting for the next release because of \<insert any reason\>. Got an ETA?**

Sorry, no ETA. This is a pet project on which I work in my spare time. I will release a new version when I feel like it.
```
