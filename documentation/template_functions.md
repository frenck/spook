---
subject: Reference
title: Provided Home Assistant template functions, filters, and tests
short_title: Template functions
subtitle: How did those functions break up❓ They stopped calling each other 🥁
thumbnail: images/usage/services_example.png
description: Spook provides quite a lot of new services to Home Assistant. This reference pages lists them all, and points you to the right documentation.
date: 2024-01-09T17:18:01+01:00
---

Spook provides quite a lot of new template functions, filters, and tests to the {term}`Home Assistant` {term}`template engine <template engine>`. This reference page lists them all and points you to the right documentation for each of those {term}`template functions <template function>`.

## Shuffle

Shuffles a list of items.

```
{{ shuffle(["a", "b", "c"]) }}
{{ shuffle(["a", "b", "c"], seed=42) }}
```

[documentation](template_functions/shuffle) 📚
