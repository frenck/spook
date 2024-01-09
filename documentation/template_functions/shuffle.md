---
subject: Template function
title: Shuffle 🔀
short_title: Shuffle
subtitle: In case you are not random enough already.
description: Spook enhances the template engine of Home Assistant by adding a shuffle function.
date: 2024-01-09T17:18:15+01:00
---

The shuffle function provides an easy way to randomly shuffle any list of items. Either fully random, or with a seed to make the randomization reproducable.

```{list-table}
:header-rows: 1
* - Template function properties
* - {term}`Function <template function>`
  - Randomly shuffles a list of items
* - {term}`Function name <template function>`
  - `shuffle`
* - {term}`Returns <template function return value>`
  - The shuffled list
* - {term}`Return type <template function return type>`
  - {term}`list of items <list>`
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
    shuffle(
        items: list[Any],
        seed: [None, int, float, str] = None
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
  - `["a", "b", "c"]`
* - `seed`
  - None, {term}`integer <integer>`, {term}`float <float>`, {term}`string <string>`
  - No
  - `None`
```

The `items` parameter can be a {term}`list of anything <list>`. The items in the list will be randomly shuffled and returned.

## Examples

### Using the shuffle function as a function

```{code-block} python
:linenos:
{{ shuffle([1, 2, 3]) }}
```

Returns:

```{code-block} python
[2, 3, 1]
```

Calling the function above multiple times, will always return the list in a different random order.

### Using the shuffle function as a filter

```{code-block} python
:linenos:
{{ [1, 2, 3] | shuffle }}
```

Returns:

```{code-block} python
[3, 2, 1]
```

### Using a seed

A seed can be used to initialize the random number generator. The same seed will always result in the same randomization, like a randomization with a memory. This is useful if you want to have more reproducable control over the randomization.

Example:

```{code-block} python
:linenos:
{{ shuffle([1, 2, 3], seed=1) }}
```

Returns:

```{code-block} python
[2, 3, 1]
```

Calling the function above multiple times, will always return the list in the same random order.

The seed can, of course, also be used when using shuffle as a filter:

```{code-block} python
:linenos:
{{ [1, 2, 3] | shuffle(seed=1) }}
```

Returns:

```{code-block} python
[2, 3, 1]
```

### Shuffle anything

The examples above, use a list of numbers that get shuffled, but shuffle can be used on any list of items.

```{code-block} python
:linenos:
{{ shuffle(["Not", "your", "homie", 1, 2, 3]) }}
```

Returns:

```{code-block} python
["homie", 2, "Not", 3, 1, "your"]
```

## Features requests, ideas and support

If you have an idea on how to further enhance the Home Assistant template engine, for example, by adding a new template function; feel free to [let us know in our discussion forums](https://github.com/frenck/spook/discussions).

Are you stuck using this new feature? Or maybe you've run into a bug? Please check the [](../support) page on where to go for help.
