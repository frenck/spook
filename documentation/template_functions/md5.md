---
subject: Template function
title: MD5
subtitle: Insecure, useless, still used a darn lot 🙈
description: Spook enhances the template engine of Home Assistant by adding a md5 function.
date: 2024-01-11T21:27:40+01:00
---

The md5 function provides an easy way to calculate the MD5 hash of a given value.

```{list-table}
:header-rows: 1
* - Template function properties
* - {term}`Function <template function>`
  - Calculate the MD5 hash of a given value
* - {term}`Function name <template function>`
  - `md5`
* - {term}`Returns <template function return value>`
  - The MD5 hash
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
    md5(
        value: str
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
  - {term}`string <string>`
  - Yes
  - `hash me`
```

## Examples

### Using md5 as a function

```{code-block} python
:linenos:
{{ md5("hash me") }}
```

Returns:

```{code-block} python
d09dba7d332adb585d176cf807f00f34
```

### Using md5 as a filter

```{code-block} python
:linenos:
{{ "hash me" | md5 }}
```

Returns:

```{code-block} python
d09dba7d332adb585d176cf807f00f34
```

## Features requests, ideas, and support

If you have an idea on how to further enhance the Home Assistant template engine, for example, by adding a new template function; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using this new feature? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
