---
subject: Template function
title: SHA1
subtitle: Insecure, useless, still used a darn lot 🙈
description: Spook enhances the template engine of Home Assistant by adding a sha1 function.
date: 2024-01-11T21:27:40+01:00
---

The sha1 function provides an easy way to calculate the SHA1 hash of a given value.

```{list-table}
:header-rows: 1
* - Template function properties
* - {term}`Function <template function>`
  - Calculate the SHA1 hash of a given value
* - {term}`Function name <template function>`
  - `sha1`
* - {term}`Returns <template function return value>`
  - The SHA1 hash
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
    sha1(
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

### Using sha1 as a function

```{code-block} python
:linenos:
{{ sha1("hash me") }}
```

Returns:

```{code-block} python
3bd28babb1ea84fd20da6ff3abcc0791613d38d2
```

### Using sha1 as a filter

```{code-block} python
:linenos:
{{ "hash me" | sha1 }}
```

Returns:

```{code-block} python
3bd28babb1ea84fd20da6ff3abcc0791613d38d2
```

## Features requests, ideas, and support

If you have an idea on how to further enhance the Home Assistant template engine, for example, by adding a new template function; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using this new feature? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
