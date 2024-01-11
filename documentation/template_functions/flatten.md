---
subject: Template function
title: Flatten
subtitle: One function for a flat belly in seconds 🫃🏻
description: Spook enhances the template engine of Home Assistant by adding a flatten function.
date: 2024-01-11T21:20:08+01:00
---

The flatten function provides an easy way to flatten a list of lists into a single list.

```{list-table}
:header-rows: 1
* - Template function properties
* - {term}`Function <template function>`
  - Flatten a lists of lists
* - {term}`Function name <template function>`
  - `flatten`
* - {term}`Returns <template function return value>`
  - A flattened list
* - {term}`Return type <template function return type>`
  - {term}`list of items <list>`
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
    flatten(
        value: Iterable[Any]
        levels: int | None = None,
    ) -> list[Any]
    ````
`````

```{list-table}
:header-rows: 2
* - Function parameters
* - Attribute
  - Type
  - Required
  - Default / Example
* - `items`
  - {term}`list of items <list>`
  - Yes
  - `["a", ["b", ["c"]]]`
* - `levels`
  - None, {term}`integer <integer>`
  - No
  - `None`
```

The `levels` parameter can be used to specify how many levels of lists should be
flattened. By default, all levels are flattened.

## Examples

### Using flatten as a function

```{code-block} python
:linenos:
{{ flatten([1, [2, [3]], 4, [5 , 6]]) }}
```

Returns:

```{code-block} python
[1, 2, 3, 4, 5, 6]
```

### Using flatten as a filter

```{code-block} python
:linenos:
{{ [1, [2, [3]], 4, [5 , 6]] | shuffle }}
```

Returns:

```{code-block} python
[1, 2, 3, 4, 5, 6]
```

### Using a levels

You can define how many levels of lists should be flattened. By default,
if no levels are specified, all levels are flattened.

Example:

```{code-block} python
:linenos:
{{ shuffle([1, [2, [3]]], levels=1) }}
```

Returns:

```{code-block} python
[1, 2, [3]]
```

## Features requests, ideas and support

If you have an idea on how to further enhance the Home Assistant template engine, for example, by adding a new template function; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using this new feature? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
