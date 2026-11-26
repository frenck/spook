Spook's docs are written by one person, Frenck, and they sound like him. A translation sounds like him too, in the reader's language. Not like a manual, and not like a translation.

## How it sounds

- Direct. Say the thing. Short sentences, one thought each.
- Peer to peer. The reader is somebody who runs Home Assistant at home, not a customer and not a student. Never lecture, never reassure for no reason.
- Address the reader the way Home Assistant does in that language, as one user to another. Informal where the language allows it. The style guide of the language says which word (French uses "vous", the way Home Assistant does).
- Dry. The humor that is there is understated. Keep it that way.
- Honest. When the English says something is a bug, a limit or "a bit late", the translation says so as plainly. A warning stays as strong as it was.
- Natural. Write what a Home Assistant user in that country would say to another one. Follow the meaning of a sentence, not its word order. Split or reorder inside a sentence when the language wants it. Never add or drop a sentence, a step or a list item.

## Humor

- Translate a joke only when it works in the language. A flat, plain line beats a forced joke.
- Never add a joke the English does not have. Never explain one.
- Puns in subtitles ("Ready? Set? Action! 🎬"): keep the intent and the dryness. When the pun dies, write a plain line.
- Hashtags like `_#BobTheBuilder_` stay as written, unless the `jokes.yml` of the language has a local one.
- Quotes from films, songs and memes ("Who you gonna call?") stay in English when people in that country know them in English.
- The ghost emoji 👻 always stays. So does every other emoji, as often as in the English.

## Words

- "Home Assistant" in full. Never "HA" or "HASS".
- Spook is a name. It stays "Spook", capitalized, in every language.
- No marketing words. Nothing is "powerful", "seamless" or "delightful" unless the English is making fun of it.
- No em-dashes and no en-dashes. Use a full stop, a colon, a comma or brackets.
- "Select" is never "click". The style guide of the language has the word.
- No abbreviations like "e.g." or "etc." or what the language has for them. Write "like", "for example", "and so on" in that language.

## What is on the screen

- Bold text that names something on the screen (`**Add action**`) is not yours to translate. You are given the exact label Home Assistant or Spook shows in the language. Use it letter for letter, in bold.
- Bold text you are given no label for: when it is something on the screen, keep the English. When it is emphasis (`**How to fix it:**`), translate it.
- In running text, use the words Home Assistant uses in that language for its own things: automation, entity, area, trigger. The glossary has them. A reader should not have to learn a second vocabulary.
- When Home Assistant and Spook's own strings use different words for the same thing, Home Assistant wins. Spook's translations are volunteer work on Weblate; a word that is off there gets fixed there, not worked around here. The exceptions are in the glossary of the language, each with its reason.

## Good enough, then better

A translation will not be right everywhere, and does not have to be on day one. Readers report what reads wrong (every translated page has a link for it), and a report becomes a fix in this corpus: a glossary entry, a style rule, a correction. When in doubt, pick the plain, likely choice and move on. Do not stall on one word.

- Names of entity states, options and attributes in `code` are data. They stay as they are.

## What is not text

- `code`, code blocks, and everything in `⟦tokens⟧` stay exactly as they are. Move a token with the words it belongs to.
- Keep the Markdown as it is: the same headings, lists, tables, bold and blank lines, in the same order.
- Text inside `:term[...]` is translated, in the form the sentence needs.
- Link text is translated. The link is a token.
