Brazilian Portuguese, as written in Brazil, the way one Home Assistant user explains something to another.

## Address

- "Você", always, with the verb in the third person: "você pode", "seu", "sua". Never "tu" and never "o senhor". Home Assistant's Brazilian interface says "você" too, and so do Spook's own strings.
- Instructions in the imperative as Brazil writes it: "Vá em **Configurações**", "Selecione **Salvar**".
- "We" stays "nós", mostly in the verb only. Frenck speaks as "eu" where the English has "I" or "my".
- Leave out "você" where the sentence is clear without it. Three times in one sentence is too many.

## Tone

- Short sentences. One thought each.
- No bureaucratic Portuguese: "efetuar", "realizar o procedimento", "mediante", "no que tange a", "a fim de", "solicitamos que". Write "fazer", "com", "sobre", "para", the plain verb.
- No gerund chains ("vamos estar verificando"). Write the verb: "vamos verificar".
- Dry humor stays dry. "That is a bit late." is "Isso é um pouco tarde.", not a joke with a wink. No exclamation marks the English does not have.

## Words

- "Select" is "selecione". Never "clique".
- Use the words Home Assistant uses in Brazil: automação, entidade, dispositivo, área, andar, gatilho, condição, ação, integração, estado. The glossary has the list.
- A trigger is "gatilho", the word of the automation editor (**Adicionar gatilho**). Spook's own strings say "gatilho" too. Never "acionador".
- English words Brazilian Home Assistant users use stay English, as the interface has them: dashboard, blueprint, template, helper, script, logs, bug.
- Turning an automation on and off is "ligar" and "desligar", like the action **Ligar por**: "uma automação desligada", "quando você liga uma de novo". Enabling and disabling an integration, a device, an entity, a user or a step is "ativar" and "desativar", like the actions **Ativar** and **Desativar**. A toggle in a dialog is "ative", like "ative **Restaurar**". Chosen for consistency on 2026-11-25 by an agent, not by a native speaker.
- "Spook" is masculine and takes the article, like every name of a thing in Brazilian Portuguese: "o Spook avisa", "do Spook", "pelo Spook". Spook's own strings do the same.
- "Home Assistant" is masculine and takes the article: "o Home Assistant reinicia", "a versão do Home Assistant", "no Home Assistant". The interface writes it like that.
- No em-dashes and no en-dashes. Use a full stop, a colon, a comma or brackets.

## Typography

- Quotes: "straight double quotes", like the interface. Never inside a component attribute like `alt`, where no quote of any kind is needed.
- No space before `:`, `;`, `?` or `!`.
- A sentence after a colon starts lowercase, unless it is a name.
- Capitals only at the start of a sentence and for names. Not in every word of a title.
- Numbers and versions as in the English. Times in `code` are not touched.

## Wording that repeats

Sentences that come back on many pages, written one way. Chosen for consistency on 2026-11-25 by an agent, not by a native speaker: three translators worked in parallel, and the wording drifted. Each is the variant most pages used, unless the note says otherwise. Not yet read by a native speaker.

- "Just want to see it work? Try this action opens it in your Home Assistant, ready to run once." is "Só quer ver funcionando? [Experimente esta ação] abre a ação no seu Home Assistant, pronta para executar uma vez.": "executar", the word of Home Assistant's own **Executar ação**.
- "New to repairs?" is "Primeira vez com reparos?".
- "How to fix it:" is "**Como resolver:**", and the sentence after it starts lowercase, as after any colon.
- The badge alt text describes what the badge does, in the third person: "Abre sua instância do Home Assistant e mostra …", never "Abra … e mostre".
- "You find it wherever you add an action, marked with a 👻." is "Você a encontra em qualquer lugar onde adiciona uma ação, marcada com um 👻.", and "them" is "Você as encontra …, marcadas com um 👻.".
- "Mind that it really deletes." is "Atenção: ela exclui de verdade.".
- "Let us know, and we'll add it to the list! 🙏" is "[Conte para nós], e a gente coloca na lista! 🙏". "Let us know" alone is "Conte para nós".
- "Run by hand, these actions need a user that is an administrator." is "Executadas à mão, essas ações precisam de um usuário que seja administrador.".
- "This one Spook can fix for you, straight from the repair." is "Este o Spook consegue resolver para você, direto do reparo.".
- "Add one directly to your own instance" is "Adicione um direto na sua instância".
- "Actions of an integration you disabled are not reported: switched off on purpose is not gone. Once you enable the integration again, they are checked as usual." is "Ações de uma integração que você desativou não são relatadas: desligado de propósito não é sumido. Assim que você ativar a integração de novo, elas são verificadas normalmente.": "ativar", the future subjunctive "assim que" asks for. A repair that "reports" something "relata", never "aponta".
- "An attribute is an extra detail an entity carries next to its state." is "Um atributo é um dado extra que uma entidade carrega junto com o estado.".
- "This is one check, shared by every helper built on another entity. The Home Assistant page explains it in full." is "Esta é uma verificação só, compartilhada por todos os helpers construídos sobre outra entidade. A página do Home Assistant explica tudo.": three variants, one each; "construídos" is the plain word for "built".
- "A frontend run from a development build" is "um frontend executado a partir de uma versão de desenvolvimento", and the icon site is "o site dos Material Design Icons".
