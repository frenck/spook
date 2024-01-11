---
subject: Template function
title: Typeof
short_title: Typeof
subtitle: "Also tired of playing: Guess Who?"
description: Spook enhances the template engine of Home Assistant by adding a typeof function.
date: 2024-01-09T19:55:04+01:00
---

The `typeof` function is inspired by the <wiki:JavaScript> `typeof` operator. It reveals the {term}`type <template function return type>` of the given value.

This is mostly useful when you are debugging or playing with templates in the developer tools of Home Assistant. However it might be useful is some other cases as well.

```{list-table}
:header-rows: 1
* - Template function properties
* - {term}`Function <template function>`
  - Reveals the type of a given value
* - {term}`Function name <template function>`
  - `typeof`
* - {term}`Returns <template function return value>`
  - The type of the given value
* - {term}`Return type <template function return type>`
  - {term}`string <string>`
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
    typeof(
        self,
        value: Any,
    ) -> str
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
  - Anything
  - Yes
  - `Spook`
```

## Examples

### Using typeof as a function

```{code-block} python
:linenos:
{{ typeof("Spook") }}
{{ typeof(True) }}
```

Returns:

```{code-block} python
str
bool
```

### Using typeof as a filter

```{code-block} python
:linenos:
{{ "Spook" | typeof }}
{{ True | typeof }}
```

Returns:

```{code-block} python
str
bool
```

## Features requests, ideas and support

If you have an idea on how to further enhance the Home Assistant template engine, for example, by adding a new template function; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using this new feature? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
