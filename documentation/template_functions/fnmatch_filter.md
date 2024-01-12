---
subject: Template function
title: Unix file name pattern filtering
short_title: Pattern filter
subtitle: Only let the stars ✱ shine through.
description: Spook enhances the template engine of Home Assistant by adding a fnmatch_filter function.
date: 2024-01-09T19:36:30+01:00
---

Don't let the name of this function fool you. The `fnmatch_filter` function is a simple, yet, powerful tool to filter any list of text (not just lists of file names) against a pattern. It is an very easy and powerful way to filter lists against a pattern, without having to learn <wiki:regular_expressions>.

```{list-table}
:header-rows: 1
* - Template function properties
* - {term}`Function <template function>`
  - Filter a lists of texts against a pattern
* - {term}`Function name <template function>`
  - `fnmatch_filter`
* - {term}`Returns <template function return value>`
  - The filtered list
* - {term}`Return type <template function return type>`
  - {term}`list of strings <list>`
* - {term}`Can be used as a filter <template filter function>`
  - Yes
* - {term}`Can be used as a test <template test function>`
  - No
* - {term}`Spook's influence <influence of spook>`
  - Newly added template function
* - {term}`Developer tools`
  - [Try this in the template developer tools](https://my.home-assistant.io/redirect/developer_template/)
```

`````{list-table}
:header-rows: 1
* - Signature
* - ````python
    fnmatch_filter(
        self,
        value: Iterable[str],
        pattern: str,
        case_sensitive: bool = False,
    ) -> List[str]
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
  - {term}`list of strings <list>`
  - Yes
  - `["Spook", "Ghost"]`
* - `pattern`
  - {term}`string <string>`
  - Yes
  - `sp*k`
* - `case_sensitive`
  - {term}`list of strings <list>`
  - No
  - `False`
```

By default, this function is not case-sensitive. This means that `spook` and `Spook` are considered the same. If you want to make the function case-sensitive, set the `case_sensitive` parameter to `True`.

## Patterns

The UNIX shell-style pattern is a relatively simple, easy to learn
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
  - Matches any character present in this sequence
* - `[!seq]`
  - Matches any character not present in this sequence
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

### Using fnmatch filter as a function

```{code-block} python
:linenos:
{{ fnmatch_filter(["Spook", "Ghost", "Spacewalk"], "sp*k") }}
{{ fnmatch_filter(["Spook", "Ghost", "Spank"], "spa?k") }}
```

Returns:

```{code-block} python
["Spook", "Spacewalk"]
["Spank"]
```

### Using fnmatch filter as a filter

```{code-block} python
:linenos:
{{ ["Spook", "Ghost", "Spacewalk"] | fnmatch_filter("sp*k") }}
{{ ["Spook", "Ghost", "Spank"] | fnmatch_filter("spa?k") }}
```

Returns:

```{code-block} python
["Spook", "Spacewalk"]
["Spank"]
```

### Case-sensitive matching

By default, the `fnmatch_filter` function is not case-sensitive. This means that `spook` and `Spook` are considered the same. If you want to make the function case-sensitive, set the `case_sensitive` parameter to `True`.

```{code-block} python
:linenos:
{{ fnmatch_filter(["Spook", "spook"], "sp*k", case_sensitive=True) }}
{{ fnmatch_filter(["Spook", "spook"], case_sensitive=False) }}
```

Returns:

```{code-block} python
["spook"]
["Spook", "spook"]
```

## Features requests, ideas, and support

If you have an idea on how to further enhance the Home Assistant template engine, for example, by adding a new template function; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using this new feature? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
