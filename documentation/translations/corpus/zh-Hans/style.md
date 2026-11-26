Simplified Chinese, as written in mainland China, the way one Home Assistant user explains something to another.

## Address

Decided by Frenck, 2026-11-25: "你". The one place where the docs do not follow the interface: Chinese documentation talks to the reader as a peer.

- "你", always. Never "您". Spook's own Chinese strings say "你" (about 200 times, "您" three times), so the repairs and the docs sound like one thing. Home Assistant's frontend mostly says "您": that is the product being polite to a customer, and the docs are one user talking to another. Do not mix the two on one page.
- Instructions as plain imperatives, without "请" unless the English has "please": "前往**设置**", "选择**保存**".
- "We" is "我们". Frenck speaks as "我" where the English has "I" or "my".

## Tone

- Short sentences. One thought each. Break a long English sentence into two Chinese ones rather than stacking "的" three deep.
- Plain written Chinese, the register of a good technical forum post. No officialese: "进行……操作", "予以", "鉴于", "兹". Write the plain verb: "删除", not "进行删除操作".
- No 四字成语 for decoration. An idiom only where the English has one, like "cries wolf", which is "喊“狼来了”".
- Dry humor stays dry. "That is a bit late." is "这有点晚了。", not a joke with a wink. No exclamation marks the English does not have, and no "哦", "啦", "呢" to sound friendly.

## Words

- "Select" is "选择". Never "点击" or "单击".
- Use the words Home Assistant uses in Chinese: 自动化, 实体, 设备, 区域, 楼层, 触发条件, 条件, 动作, 集成, 状态. The glossary has the list.
- A trigger is "触发条件", not "触发器": that is what the automation editor shows (**添加触发条件**). An action is "动作", not "操作". A helper is "辅助元素".
- English names and code stay in Latin script: Spook, Home Assistant, YAML, Jinja, entity IDs. "Bug" may stay "bug".
- "Spook" and "Home Assistant" have no measure word and no article. Never translate either, not as "幽灵" or "家庭助理".
- No em-dashes and no en-dashes, and no Chinese dash "——" either. Use "。", "：", "，" or "（）".

## Typography

- Full-width punctuation in Chinese text: ，。：；？！（）. Half-width punctuation only inside code and inside an English name.
- Quotes: “双引号” for a quote in running text, like the interface. Never inside a component attribute like `alt`, where no quote of any kind is needed.
- A space between Chinese and Latin letters or digits, the way the interface writes it: "重启 Home Assistant", "Spook 会创建一条修复", "3 个实体". No space between Chinese and full-width punctuation, and no space around bold labels that are Chinese themselves.
- Punctuation goes outside bold, never inside it: "**怎么修复**：", "**保存**。". Markdown does not close a `**` that follows punctuation when a character comes right after it, and Chinese has no space there, so "**怎么修复：**从修复里" shows its asterisks. A bold label that starts with punctuation, like "**+ 创建辅助元素**", takes a space in front of it: "选择 **+ 创建辅助元素**". The same holds for `_emphasis_` inside a sentence: write `*强调*`. The pipeline fixes what it can, and its check stops what it cannot.
- Numbers as Arabic digits, like the English. Versions as in the English. Times in `code` are not touched.
- Dates written out are "2026 年 11 月 25 日".
