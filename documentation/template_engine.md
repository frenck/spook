---
subject: Documentation
title: Template engine
subtitle: Because some like to make Home Assistant even harder for themselves 😅
thumbnail: images/social.png
description: Spook enhances the following Home Assistant integrations by sprinkling some ectoplasmic goodness on top of them.
date: 2024-01-11T21:30:28+01:00
---

{term}`Home Assistant` has a powerful {term}`template engine <template engine>` that allows you to create complex automations and logic. The template engine is based on the [Jinja2](https://jinja.palletsprojects.com/en/3.0.x/) template engine which is enriched with some Home Assistant-specific extensions.

{term}`Templates <template>` can be used in many places in Home Assistant, such as in {term}`automations <automation>`, {term}`scripts <script>`, and {term}`scenes <scene>`, and can even be used to create custom {term}`entities <entity>`.

Spook extends the template engine of Home Assistant Core with even more functionality, making it even more powerful. Most of these make it easier to perform common tasks, while others provide completely new functionality.

## New template functions

## Flatten

Flatten a lists of lists.

```
{{ flatten(["a", ["b", ["c"]]]) }}
{{ flatten(["a", ["b", ["c"]]], levels=1) }}
```

[documentation](template_functions/flatten) 📚

## MD5

Calculate the MD5 hash of a given value.

```
{{ md5("hash me") }}
```

[documentation](template_functions/md5) 📚

## SHA1

Calculate the SHA1 hash of a given value.

```
{{ sha1("hash me") }}
```

[documentation](template_functions/sha1) 📚

## SHA256

Calculate the SHA256 hash of a given value.

```
{{ sha256("hash me") }}
```

[documentation](template_functions/sha256) 📚

## SHA512

Calculate the SHA512 hash of a given value.

```
{{ sha512("hash me") }}
```

[documentation](template_functions/sha512) 📚

### Shuffle

Shuffles a list of items.

```
{{ shuffle(["a", "b", "c"]) }}
{{ shuffle(["a", "b", "c"], seed=42) }}
```

[documentation](template_functions/shuffle) 📚

## Typeof

Reveals the type of a given value.

```
{{ typeof("Spook") }}
{{ now() | typeof }}
```

[documentation](template_functions/typeof) 📚

## Unix file name pattern filtering

Filter a lists of texts against a pattern.

```
{{ fnmatch_filter(["Spook", "Ghost], "Sp*k") }}
{{ fnmatch_filter(["Spook", "Spook2", "Ghost"], "Sp*") }}
```

[documentation](template_functions/fnmatch_filter) 📚

## Unix file name pattern matching

Match text or a lists of texts against a pattern.

```
{{ fnmatch("Spook", "Sp*k") }}
{{ fnmatch(["Spook", "Spook2"], "Sp*") }}
```

[documentation](template_functions/fnmatch) 📚

## Features requests, ideas, and support

If you have an idea on how to further enhance the Home Assistant template engine, for example, by adding a new template function; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using this new feature? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
