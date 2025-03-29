---
subject: About the project
title: Features previously available in Spook
short_title: Previous features
subtitle: Adieu, goodbye, auf Wiederseh'n!
thumbnail: images/social.png
description: Sometimes features are removed from Spook. Most of the time, this is because the feature is now available in Home Assistant itself. This page is dedicated to those fallen features.
date: 2023-08-09T21:29:00+02:00
---

:::{iframe} https://www.youtube.com/embed/skl6N3zGv-s
:width: 100%
:::

Some features have been removed from Spook over time; this page is dedicated to those fallen features.

```{card}
:header: **Template engine extensions**
:footer: As of Home Assistant 2025.4, these template functions are now available in Home Assistant core.
Spook provided several template functions to enhance Home Assistant's template engine, including:
- `flatten`: Flatten lists of lists
- `md5`: Calculate MD5 hashes
- `sha1`: Calculate SHA1 hashes
- `sha256`: Calculate SHA256 hashes
- `sha512`: Calculate SHA512 hashes
- `shuffle`: Shuffle lists
- `typeof`: Reveal the type of a value
```

```{card}
:header: **Obsolete integration & platform YAML configuration repairs**
:footer: As of Home Assistant 2023.6, Home Assistant will raise repair issues for these cases itself.
Spook looked for YAML configuration of integrations (and older integration platforms) that no longer support being configured via YAML. If it found those, it would raise a repair issue in your repairs dashboard to keep your YAML configuration nice and clean.
```
