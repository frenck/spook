French, as written in France, the way one Home Assistant user explains something to another.

## Address

Decided by Frenck, 2026-11-25: "vous", the way Home Assistant does in French.

- "Vous", always: "vous", "votre", "vos". Never "tu". This is the one exception to "informal address" in the shared style guide: Home Assistant's French interface says "vous" everywhere, and so do Spook's own French strings. Docs that say "tu" next to a product that says "vous" would sound like two things.
- "Vous" here is not stiff. It is the "vous" one Home Assistant user uses with another on a forum: plain, direct, no "veuillez", no "nous vous invitons à".
- Instructions in the imperative: "Allez dans **Paramètres**", "Sélectionnez **Enregistrer**".
- "We" stays "nous", or "on" where spoken French would say it. Frenck speaks as "je" where the English has "I" or "my".

## Tone

- Short sentences. French invites long ones with "afin de", "lequel" and two subordinate clauses: do not accept the invitation. Two short sentences beat one long one.
- No administrative French: "veuillez", "afin de", "par le biais de", "il convient de", "s'avérer", "procéder à". Write "pour", "avec", "il faut", the plain verb.
- No noun chains where a verb works: "pour réparer l'automatisation", not "pour la réalisation de la réparation de l'automatisation".
- Dry humor stays dry. "That is a bit late." is "C'est un peu tard.", not a joke with a wink. No exclamation marks the English does not have.
- Spoken constructions are fine where the English is casual: "Ça arrive", "c'est", "rien de plus".

## Words

- "Select" is "sélectionnez". Never "cliquez".
- Use the words Home Assistant uses in French: automatisation, entité, appareil, pièce, étage, déclencheur, condition, action, intégration, état. The glossary has the list.
- Home Assistant's French interface calls an area "pièce", not "zone" or "espace". A repair is a "correction", because Settings has **Corrections**. A helper is an "entrée", because that is what the interface calls helpers.
- English words French Home Assistant users use stay English: blueprint, script, bug, YAML.
- "Spook" is masculine and takes no article: "Spook signale", "Spook est installé". Never "le Spook", and never "le fantôme" for the product.
- "Home Assistant" is masculine and takes no article: "Home Assistant redémarre", "la version de Home Assistant". Never "le Home Assistant", never "HA".
- No em-dashes and no en-dashes. Use a full stop, a colon, a comma or brackets.

## Typography

- A non-breaking space (U+00A0) before `:`, `;`, `!` and `?`, the way Home Assistant's French interface does it: "Rien ? Alors c'est propre." Not before a colon inside code, a link or a token.
- Quotes: « guillemets » with a non-breaking space inside: « comme ceci ». Never inside a component attribute like `alt`, where no quote of any kind is needed.
- Apostrophes straight, like the interface: "l'automatisation", "c'est".
- A sentence after a colon starts lowercase, unless it is a name.
- Capitals only at the start of a sentence and for names. Not in the middle of a title: "Mettre à jour Spook", not "Mettre À Jour Spook".
- Numbers and versions as in the English. Times in `code` are not touched.

## Wording that repeats

Sentences that come back on every action page, written one way. Chosen for consistency on 2026-11-25 by an agent, not by a native speaker: the variant most pages used, unless the note says otherwise.

- "Just want to see it work?" is "Vous voulez juste la voir marcher ?". "La", because it is the action. "Le" was used on almost as many pages.
- "Run" for an action is "lancer", not "exécuter": one verb for "run". "Ready to run once" is "prête à être lancée une fois".
- "New to repairs?" is "Les corrections, c'est nouveau pour vous ?".
