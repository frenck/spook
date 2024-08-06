---
subject: Reference
title: Provided Home Assistant template functions, filters, and tests
short_title: Template functions
subtitle: How did those functions break up❓ They stopped calling each other 🥁
thumbnail: images/usage/services_example.png
description: Spook provides quite a lot of new actions to Home Assistant. This reference pages lists them all, and points you to the right documentation.
date: 2024-01-11T21:30:28+01:00
---

Spook provides quite a lot of new template functions, filters, and tests to the {term}`Home Assistant` {term}`template engine <template engine>`. This reference page lists them all and points you to the right documentation for each of those {term}`template functions <template function>`.

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

## Shuffle

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
