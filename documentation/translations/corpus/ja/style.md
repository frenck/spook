Japanese, the way one Home Assistant user explains something to another.

## Address

Chosen by an agent on 2026-11-25, for Frenck to confirm: polite form (です・ます), and no pronoun for the reader.

- Every sentence in the polite form: "します", "できます", "ありません", "してください". Never the plain form (だ・である) for prose. Home Assistant's frontend ends 2136 of its 2249 Japanese sentences in the polite form (95%), Spook's own strings 1117 of 1279 (87%). Docs in the plain form next to a product in the polite form would sound like two things.
- Polite, not humble. No 敬語 beyond です・ます: no "ございます", "いただけます", "お客様", "させていただきます". The frontend has "ございます" once in 9687 strings. This is a forum post by a peer, not a letter from a shop.
- No word for "you". Japanese leaves the reader out, and so does Home Assistant: "あなた" is in 49 of the frontend's 9687 strings. Write "設定を開きます", not "あなたは設定を開きます". "Your automation" is "オートメーション" or "自分のオートメーション" when the contrast matters. Spook's own strings say "あなた" 76 times; that reads translated, and is not copied.
- Instructions as "〜します" for a step in a list ("**設定**に移動します。"), and "〜してください" where the English asks the reader to do something. Not both in one list.
- "We" is "私たち" only where the English insists on it; usually leave it out. Frenck speaks as "私" where the English has "I" or "my".

## Tone

- Short sentences. One thought each. Break a long English sentence into two Japanese ones rather than chaining "〜て、〜て、〜ので".
- Plain written Japanese, the register of a good technical blog post. No stiff officialese: "〜を行う", "〜を実施する", "〜につきましては", "〜の際には". Write the plain verb: "削除します", not "削除を行います".
- No 四字熟語 for decoration. An idiom only where the English has one. Where Japanese has an equivalent, use it ("cries wolf" is "オオカミ少年"). Where it has none, write the meaning plainly.
- Dry humor stays dry. "That is a bit late." is "それでは少し遅すぎます。", not a joke with a wink. No exclamation marks the English does not have, and no "ね", "よ", "ですよね" to sound friendly.

## Words

- "Select" is "選択します". Never "クリック": the frontend says "選択して" 61 times, Spook never says "クリック". "Tap" is "タップ" only where the English says tap.
- Use the words Home Assistant uses in Japanese: オートメーション, エンティティ, デバイス, エリア, フロア, トリガー, 条件, アクション, 統合, ヘルパー, 状態. The glossary has the list.
- A repair is "修復", because **設定** has **修復**. An integration is "統合", not "インテグレーション". A person is "人", the way the frontend lists them.
- Katakana as the frontend writes it, long vowel marks included: ユーザー, センサー, エディタ, カテゴリー.
- English names and code stay in Latin script: Spook, Home Assistant, YAML, Jinja, HACS, entity IDs. "Bug" is "バグ".
- Never translate "Spook" or "Home Assistant", not as "スプーク" or "ホームアシスタント". Neither takes a counter or an honorific.
- No em-dashes and no en-dashes, and no Japanese dash "――" or "ー" used as a dash. Use "。", "：", "、" or "（）".

## Typography

- Japanese punctuation in Japanese text: 、。（）「」？！. Half-width punctuation only inside code and inside an English name or quote.
- No space between Japanese and Latin letters or digits: "Home Assistantを再起動します", "Spookが修復を作成します", "3個のエンティティ", "YAMLで書きます". The frontend writes it without a space about twice as often as with one (393 against 203 before a letter, 926 against 494 after one; "Home Assistant" directly followed by Japanese 197 times, with a space 144 times). Spook's own strings always put a space; they are copied only inside a bold label.
- Bold labels are copied letter for letter, spaces and half-width colons included ("**オートメーション: スヌーズ 👻**"). No space around a bold label either: "**保存**を選択します".
- Punctuation goes outside bold, never inside it: "**直し方**：", "**ログ**。". Markdown does not close a `**` that follows punctuation when a letter comes right after it, and Japanese has no space there, so "**直し方：**修復" shows its asterisks. The same holds for `_emphasis_` inside a sentence: write `*強調*`.
- Brackets around Japanese are full width: "（オプション）". The frontend writes "（" after Japanese 90 times, "(" 73 times. Inside English or code they stay half width.
- Quotes: 「かぎ括弧」 for a word or phrase quoted in running text. Never inside a component attribute like `alt`, where no quote of any kind is needed.
- The colon in prose is full width, "：". The frontend writes it half width more often (136 against 57), nearly all of those before a placeholder like `{name}`; Japanese prose writes it full width. A native speaker may want this the other way.
- A question mark is full width, "？", like the frontend (155 against 72). A full stop after "？" is not needed.
- Lists of two or three in one sentence use "、" or "と". "・" only between katakana words that belong together.
- Numbers as Arabic digits, half width, like the English. Versions as in the English. Times in `code` are not touched.
- Dates written out are "2026年11月25日".

## Wording that repeats

Sentences that come back on many pages, written one way. Chosen for consistency on 2026-11-25 by an agent, not by a native speaker: the three first translators already wrote each of these the same way on every page.

- "Just want to see it work? Open this action in your Home Assistant with Try this action, and run it once." is "動くところを見たいだけですか？[このアクションを試す](…)から、Home Assistantでこのアクションを開いて、そのまま一度実行できます。"
- "New to repairs? Start with Fix your first repair." is "修復は初めてですか？[最初の修復を直す](…)を見てください。" The link text is the title of that page.
- "How to fix it:" is a bold run-in label with the colon outside the bold: "**直し方**：".
- A table cell "Optional, the …" starts with "任意。".
- Repair headings "Unknown referenced X" are "参照先が不明なX"; "Unknown X" without "referenced" is "不明なX".
