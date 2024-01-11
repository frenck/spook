---
subject: Template function
title: Unix filename pattern matching
short_title: Pattern matching
subtitle: Did you use the wildcard already? ✱
description: Spook enhances the template engine of Home Assistant by adding a fnmatch function.
date: 2024-01-09T18:54:35+01:00
---

Don't let the name of this function fool you. The `fnmatch` function is a simple, yet, powerful tool to match any text (not just filenames) against a pattern. It is an very easy and powerful way to match text against a pattern, without having to learn <wiki:regular_expressions>.

```{list-table}
:header-rows: 1
* - Template function properties
* - {term}`Function <template function>`
  - Match text or a lists of texts against a pattern
* - {term}`Function name <template function>`
  - `fnmatch`
* - {term}`Returns <template function return value>`
  - If the given text matches the give pattern
* - {term}`Return type <template function return type>`
  - {term}`boolean <boolean>`
* - {term}`Can be used as a filter <template filter function>`
  - Yes
* - {term}`Can be used as a test <template test function>`
  - Yes
* - {term}`Spook's influence <influence of spook>`
  - Newly added template function
* - {term}`Developer tools`
  - [Try this in the template developer tools](https://my.home-assistant.io/redirect/developer_template/)
```

`````{list-table}
:header-rows: 1
* - Signature
* - ````python
    fnmatch(
        self,
        value: str | Iterable[str],
        pattern: str,
        case_sensitive: bool = False,
    ) -> bool
    ````
`````

```{list-table}
:header-rows: 2
* - Function parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `value`
  - {term}`string <string>`, {term}`list of strings <list>`
  - Yes
  - `Spook`
* - `pattern`
  - {term}`string <string>`
  - Yes
  - `sp*k`
* - `case_sensitive`
  - {term}`boolean <boolean>`
  - No
  - `False`
```

By default, this function is not case sensitive. This means that `spook` and `Spook` are considered the same. If you want to make the function case sensitive, set the `case_sensitive` parameter to `True`.

## Patterns

The UNIX shell-style pattern is a relatively simple, easy to learn and use
pattern matching technique, which is _not_ the same as regular expressions.

The following characters are special characters in a pattern:

```{list-table}
:header-rows: 1
* - Character
  - Meaning
* - `*`
  - Matches everything (and multiple characters)
* - `?`
  - Matches any single character
* - `[seq]`
  - Matches any character in sequence
* - `[!seq]`
  - Matches any character not in sequence
```

The sequence of characters in `[seq]` can be a range, for example: `[a-z]` or `[0-9]`, or a list of characters, for example: `[abc]` or `[123]`.

If you want to match any of these special chacters (`*`, `?`, `[` or `]`) literally, you must wrap them in square brackets (`[]`), for example: `[?]`.

This is all technical details you need to know about the pattern matching, but let's look at some examples.

- Pattern `spook` matches `spook`.
- Pattern `sp*k` matches `spook`, `spooook`, but also `spacewalk`, `speak`, and `spank` 😅
- Pattern `[hb]ook` matches `hook` and `book`.
- Pattern `[!hb]ook` matches `cook`, `look` (and many more), but not `hook` or `book`.
- Pattern `t?k` matches `tik`, `tok`, and character in the second position, but not `took`.

Hopefully, this gives you a good idea of how to use the pattern matching. In practice, you probably will end up using the `*` and `?` characters the most.

## Examples

### Using fnmatch as a function

```{code-block} python
:linenos:
{{ fnmatch("Spook", "sp*k") }}
{{ fnmatch("Spook", "spa?k") }}
```

Returns:

```{code-block} python
True
False
```

### Using fnmatch as a filter

```{code-block} python
:linenos:
{{ "Spook" | fnmatch("sp*k") }}
{{ "Spook" | fnmatch("spa?k") }}
```

Returns:

```{code-block} python
True
False
```

### Using fnmatch as a test

```{code-block} python
:linenos:
{% if "Spook" is fnmatch("sp*k") %}
  Spook matches!
{% endif %}
```

### Using fnmatch to match a lists of texts

You can also pass a list of texts to the `fnmatch` function. The function will return `True` if all of the texts in the list matches the pattern. If one of the texts does not match, the function will return `False`.

```{code-block} python
:linenos:
{{ fnmatch(["Spook", "Spook2"], "Sp*") }}
{{ ["Spook", "Ghost"] | fnmatch("Sp*") }}
```

Returns:

```{code-block} python
True
False
```

### Case sensitive matching

By default, the `fnmatch` function is not case sensitive. This means that `spook` and `Spook` are considered the same. If you want to make the function case sensitive, set the `case_sensitive` parameter to `True`.

```{code-block} python
:linenos:
{{ fnmatch("Spook", "sp*k", case_sensitive=True) }}
{{ fnmatch("Spook", "sp*k", case_sensitive=False) }}
```

Returns:

```{code-block} python
False
True
```

## Features requests, ideas and support

If you have an idea on how to further enhance the Home Assistant template engine, for example, by adding a new template function; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using this new feature? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
