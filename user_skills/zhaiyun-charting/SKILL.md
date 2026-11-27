---
name: zhaiyun-charting
description: 看风水、看阳宅、调方位：排命卦定宅卦，用八宅与流年飞星看已入住的房子，书桌、床位、灶位、办公桌、入户门与各房间的方位宜忌，给调整方向。当用户说摆位，或问搬进来以后总觉得不太顺、办公桌正对着门、想把书桌挪个方向、卧室怎么布置、今年哪几个方位要留神时，都应当使用本技能。
version: 1.1.15
display_name: 家居风水阳宅布局
display_name_en: Home Feng Shui and Flying Stars
agent_created: true
examples_zh:
  - 我家坐北朝南，2020年入住，12楼西户。男主人1985年3月8日上午9点生，出生地杭州。搬进来以后总觉得不太顺，帮我看下卧室床位和书房书桌摆哪个方位合适。
  - 我的办公室坐东朝西，办公桌正对着门。我1988年11月2日下午3点生，男，出生地成都。帮我看办公桌该朝哪个方向，今年的流年飞星落在哪一宫。
  - 1990年6月18日上午10点生，女，出生地武汉。今年打算重新装修再搬家，帮我看下住宅方位宜忌和合适的乔迁时间。
examples_en:
  - My home sits north and faces south; we moved in during 2020, 12th floor, west side. The owner is male, born 8 March 1985 at 9 in the morning in Hangzhou. Things have felt off since we moved in. Read which positions suit the bed in the main bedroom and a desk in the study.
  - My office sits east and faces west, and my desk points straight at the door. I am male, born 2 November 1988 at 3 in the afternoon in Chengdu. Tell me which direction the desk should face, and which palace this year's flying star lands in.
  - Born 18 June 1990 at 10 am, female, birthplace Wuhan. I plan to renovate and move this year. Read the orientation of my home and a suitable timing for the move.
description_zh: 看家居风水与阳宅布局的吉凶方位，书桌、床位、灶位与办公桌的朝向宜忌，入户门与各房间吉凶，以及流年飞星的落宫与装修动工的方位取舍；配合八字看喜用方位与事业财运。输出图文报告。
description_en: Works out the ming gua and the Eight Mansions of a home and reads its feng shui and layout, covering which positions and orientations suit a desk, a bed, a stove or an office desk, which directions favour the entrance, the living room and each room, where the yearly flying stars land, and what that means for renovation, moving or building work. It also reads a birth chart for a person's favoured directions, career, wealth and yearly luck, and converts between solar and lunar dates and solar terms. Produces an illustrated reading report. For entertainment and cultural reference only, not absolute.
category: 工具>信息查询
author: 商徵科技
---

# Home feng shui and flying stars

This skill does two things: it asks the calculation service for reproducible symbols, then writes the reading as JSON for the service to fill into the HTML template. When the user asked a specific question, the service places that question as chapter 2, titled 此次所问, and moves the later chapters down by one. The service recomputes the chart from the birth time. The skill writes only what the symbols mean, and a choice the reader can carry out. It is not emotional companionship, and it does not state a traditional saying as something that must happen.

This is the home and orientation edition. The ming gua, the Eight Mansions of the dwelling, and this year's flying stars lead the reading: which position and orientation suit a desk, a bed, a stove or an office desk, which directions favour the entrance and the living room, and what the year says about renovation, moving or building work. The birth chart is read only for a person's favoured directions and the luck cycles that bear on the move.

Instructions in this file are English. They tell the model what to do. They must not appear in the report. Every sentence the reader sees — `plain`, `advice`, and the Chinese prose in `term` — is Chinese.

When uploading to the skill store, choose the category **工具>信息查询**. Do not choose the deep-synthesis anthropomorphic category, and do not choose leisure alone.

## When to use

Use this skill when the user wants a home or an office read for its feng shui and layout: which positions and orientations suit a desk, a bed, a stove, or an office desk; which directions favour the entrance, the living room and each room; where this year's flying star lands and what that means for renovation, moving or building work; or which direction suits a person by ming gua. A birth chart is read here for the person's favoured directions and the luck cycles around the move, not as the main subject. If the user asks only about the history of a classic or a symbol rule and gives neither a birth time nor a facing direction, explain the rule. Do not cast a chart.

## Runtime limits

1. **No emotional companionship.** Do not build a companion relationship, comfort the user, encourage dependence, or call yourself the user's personal master. In the current turn you may say that the remark follows traditional rules. The turn ends there.
2. **No cross-session file.** Do not write birth time, name, or other personal data into memory or a file. One call handles only the current input.
3. **Symbols in the report come from the service.** In the report JSON, four pillars, ten gods, luck cycles, twelve palaces, four transformations, flying stars, season score, and the month-command pattern name must come from the calculation service. Do not compute them by hand to fill the report, and do not rename the month-command pattern. The service recomputes the chart from the birth data when it renders. Whole-chart pattern names and points come from the classics in this package, and the condition must match stems, branches, or stars already computed. Do not write a pattern name the classics do not have. Copy the Zi Wei engine's hit list as given. The useful god follows the matching line in the classics. Do not write the unfavorable god from the strength balance directly as the conclusion. The useful-god note, the choice for each luck cycle, the six topics, and the question asked this time are written by this skill into `prose`. Every sentence must point back to a stem, branch, palace, or star in `report_facts`. The one exception is the preliminary reading: that chat annotation may reckon the symbols by hand, and it must say that the service overrides the reckoning.
4. **The report reading appears only in the report JSON.** The preliminary reading is the one annotation allowed in the conversation, and only before the report exists. After the HTML exists, give the path and keep the opening label. Do not write a second set of conclusions in the chat.
5. **Reference, not necessity.** You may write a tendency, a point to watch, and a time placement, and say that this is a reference under traditional rules for the user to decide. Do not write that wealth, disaster, or success is guaranteed. Do not write 注定. Do not write a year of marriage, funeral, or illness. Do not close with a sermon. A classic's spirit or a "harms the parent / harms the spouse" line goes into the report only when the chart has a matching placement. Do not present the reading as a medical diagnosis, a buy or sell order, or a legal opinion. Health, money, and personal safety also point to a professional channel.
6. **Do not invent a system this engine does not have.** This skill does not cast Liu Yao, Qi Men, or tarot. If the user names one of those, state the scope and answer the same question with the BaZi, Zi Wei, or flying stars already computed. Do not invent a hexagram or a spread.
7. **The two systems stay side by side.** In a fusion report, do not derive one column from the other. Where they disagree, write `prose.close.divergences`. Do not merge them or choose a side.
8. **Visible label.** The HTML template already contains 「本内容由人工智能生成，仅供娱乐与文化参考」. Keep that sentence when you refer to the report. The reading follows traditional rules. It is not a scientific conclusion, it is not absolute, and it is not a basis for a medical, legal, or investment decision.

## Layout

Charting is done by the calculation service. This skill ships one standard-library client. Do not install Python 3.11 or `sxtwl` on the user's machine. `SKILL_DIR` below means this skill's root, the directory that contains this file.

```
SKILL_DIR/
  ├─ SKILL.md
  ├─ scripts/chart.py
  ├─ references/methodology.md
  ├─ references/yuanhai-ziping.md       渊海子平
  ├─ references/ditian-sui.md           滴天髓
  ├─ references/ditian-sui-chanwei.md   滴天髓阐微
  ├─ references/ziwei-quanshu.md        紫微斗数全书
  ├─ references/zhaijing.md             宅经
  ├─ references/voice-bazi.md           BaZi style archive
  ├─ references/voice-ziwei.md          Zi Wei style archive
  ├─ references/geo-index.md            birthplace longitude index
  ├─ references/geo-11-北京.tsv          one table per province, keyed by province code
  └─ templates/命理报告结构设计-v1.md
```

> The platform allows only two directory levels inside a skill package. No file may sit deeper than two levels under the skill root.

For calculation rules and JSON field names, read `references/methodology.md`. What the chapters contain, including chapter 2 when the user asked a specific question, is `templates/命理报告结构设计-v1.md`. Before writing the reading, follow the section below. The style samples are embedded there. A file name is not a substitute for that text.

## Do not write inside the skill package

**Do not create or modify any file under `SKILL_DIR`.**

The platform hashes the whole package to decide whether the user changed the skill. Therefore:

- Write report JSON and HTML outside the skill directory.
- Always pass `-B` when calling the client.
- Use the system temp directory for temporary files.
- **Keep the report JSON in the system temp directory, and delete it once the report is generated.** The file exists only to hand the reading to the service. After the service returns the HTML and you have shown the report, remove the temporary JSON. Keep it only when the call failed, so the same file can be retried unchanged.
- Do not write the user's birth time or name into the skill directory, a memory file, or a cross-session archive.

## Calculation service

Run `scripts/chart.py` with the `python` already on `PATH`. The script only sends HTTP requests. It does not import a calendar library.

The service address is `DEFAULT_API_BASE` in `scripts/chart.py`. The environment variable `YIXUE_API_BASE` may override it, for local debugging only. In a package published to users, `DEFAULT_API_BASE` must already be a public address.

If the script exits non-zero, stop charting and do not take another path. When stderr carries 「计算服务不可用，停止排盘」, say that the calculation service is unavailable. When stderr reports an argument error, correct the arguments once and run the same command again; if it fails again, stop. The preliminary reading already given in this turn stands. If render returns a missing field, stderr names the section. Fill that field from the field table and render again. Do not compute the chart by hand.

Forbidden bypasses:

- Do not call `install_binary`, create a virtualenv, or run `pip`.
- Do not install Python 3.11 or `sxtwl` on the user's machine.
- Do not look for the `py` launcher or `uv`, do not download an embeddable Python, and do not compile from source.
- Do not switch calendar libraries, and do not guess stems and branches from memory to fill the report JSON, to assemble HTML, or to replace a failed service call. The preliminary reading may reckon them, and it must say the service overrides that reckoning.
- Do not assemble HTML yourself. The page comes only from `render`.

The birth time appears only in the current request body. Do not write it into the skill directory, memory, or a log.

## Asking the user

Whenever this turn needs the user to supply something or to make a choice, use the host's `AskUserQuestion` tool. **Never end a turn on a plain-text question.** A turn ends either with a result already delivered, or with a card.

A user who asked for something, and who then sees only a question with no card and no result, cannot tell that apart from a broken service. That is the failure this section exists to prevent.

- Put the real choices in the options. Give two to four of them, and let the card's built-in custom input cover anything else. Say in the question which field the user should type into. Do not add an option whose only job is to point at that field, and do not set a placeholder on it. The missing-birthplace card in 「One request」 is the exception: it offers exactly one option, and its question text is the fixed sentence given there, with nothing added.
- Never pick for the user and never fill a missing item with a guess. The one default this skill may take is the default longitude in the section 「One request」, and only after the user has been asked.
- If the answer that comes back carries no usable value, take the documented default, finish the turn with what that yields, and record the default where the report says where the longitude came from. Do not ask a second time in plain text.
- If the user answers in the next message with the value itself, use it. The point is that a card was shown, not which field the text arrived in.
- If `AskUserQuestion` is not available in the current session, do not stop and wait for a typed reply on the critical path. Take the documented default, finish the turn, and say which default was used. The one place that still waits is the report card in the section below, which carries its own fallback.

## Preliminary reading, then offer the report

The chart engine runs on a server, not on the user's machine. So the first time this skill reaches it in a conversation, the platform shows the user a security prompt about reaching an external network address. A user who reads that as a warning may stop there. The preliminary reading comes first, in this turn, with no script and no HTTP. The card below says what the prompt is.

When the user wants a chart and the birth data is enough to reckon one (year, month, day, hour, and sex), do two things in this order, in the same turn. Do not call `scripts/chart.py`. Do not reach the calculation service.

First, write a preliminary reading by reckoning the chart yourself, from the birth data and the question asked. It is a traditional first annotation in the language of the two originals later in this file, not a general essay and not a process note. It is not the reproducible chart. Where it differs from the service, the service wins. Deliver it as a complete answer. It is not a preamble to a tool call.

**Read before writing.** The language is the two originals later in this file. Read them and write in their language. A path to the voice archives does not count. The text of the originals must be in the prompt.

For the judgment, read one main book per system. Do not read the whole set of classics for this step:

- BaZi: read only `references/ditian-sui-chanwei.md`. It already contains the 《滴天髓》 text and the 原注, and it is the book for strength and the useful god. Do not read `references/yuanhai-ziping.md` or `references/ditian-sui.md` for this preliminary.
- Zi Wei: read only `references/ziwei-quanshu.md`.
- House gua or flying stars only: read only `references/zhaijing.md`.
- A question that would use scheme `fusion` (work, marriage, moving, or both systems): read `references/ditian-sui-chanwei.md` and `references/ziwei-quanshu.md`. Do not add the other two BaZi books.

If a book is long, continue by that book's own volumes, and read the volumes that bear on this month command and on the question asked. Do not replace those volumes with a summary you already know. Do not wait to finish all of `ditian-sui-chanwei.md` before the first sentence. Also read sections 2–4 of `references/methodology.md`, so the names of the ten gods, the month-command pattern, the palaces, the four transformations, and the flying stars match the engine. The section 「Before writing the reading」 still requires the full BaZi set plus the Zi Wei book when writing the report. This shorter list applies only here.

**Reckon for this reading only.** The ming gua from the birth year, the house gua from the dwelling's facing, and this year's centre star and where it flies. Where the question is about a person's favoured direction, also the year, month, day, and hour pillars and the luck-cycle step that holds the present age. Read `references/zhaijing.md` for the orientation rule; its twenty-four roads are not this engine's algorithm, so do not apply them here. Use traditional rules. Do not refuse to reckon in order to stay safe. The classics supply the judgment and the useful-god rule. They are not a calendar table. This reckoning is not the reproducible chart.

**A double-hour boundary.** When the clock time sits near the boundary of two double-hours and no birthplace was given, write both hour pillars and say which one waits on the birthplace longitude. Do not lock one of them. Do not end the turn by asking for the birthplace in plain text. The birthplace card stays in 「One request」, after the user chooses 「生成详细图文报告（需要允许访问网络）」.

**How it should read.** Write in the language of the BaZi sample and the Zi Wei sample headed `#### BaZi sample` and `#### Zi Wei sample`, later in this file. Read those two originals and follow them. Do not replace them with a rule for diction, rhythm, or which words to use. Open on the dwelling, its facing, and the ming gua that bears on it. Give the symbols reckoned above in a small table, then what they say about the question, including the time they place, and one choice the reader can carry out. Three to six short paragraphs. The reading is the body. Do not open with a process note, a disclaimer, or a list of places to look. Do not write 注定. Do not write a year of marriage, funeral, or illness. Do not write that a position must be changed or that leaving it as it is brings a fixed outcome.

**Close, one short paragraph, after the reading.** Three points, in the reader's language, not as headings: the pillars and stars in the illustrated report are recomputed by the service from the birth time, and they override this sketch where they differ; when the system asks about network access, allow it so the report can be generated; the standing boundary, that this is entertainment and cultural reference, not absolute, and not a basis for a medical, legal, or investment decision. Do not paste the card notice below into the reading.

Second, offer the report. After the preliminary reading, use the host's `AskUserQuestion` tool, under the header 「网络提示」, put the notice below in full into the question text, and offer exactly two options: 「生成详细图文报告（需要允许访问网络）」 and 「放弃详细报告」. Wait for the user to answer. Do not run the script in the same turn as the card.

- 「放弃详细报告」: end the turn. Do not call the calculation service.
- 「生成详细图文报告（需要允许访问网络）」: go to the section 「One request」 and follow its steps.

Never pick for the user.

**The preliminary reading is already the deliverable for this turn.** It was written and delivered before this card. That is the whole point of writing it first: a turn that ends here has still produced a complete answer. Do not treat this card as the turn's only output, and do not describe the turn as unfinished.

**When no answer comes back, do not leave the turn empty.** This is the rule that matters most under an automated or non-interactive run:

- If `AskUserQuestion` is not available in the current session (for example a print or batch run), do not stop and do not send a plain-text question. Instead, take the documented default — chart the default east longitude 120 as if 「按默认东经 120 度排盘」 had been chosen — and go to the section 「One request」 in this same turn. The report then records that the longitude came from the default. The preliminary reading still stands ahead of it.
- If `AskUserQuestion` is available but no answer arrives within the session's own limit, do not wait past the point where the turn can still finish usefully. Take the same default, go to 「One request」, and finish. Say that the default longitude was used because no birthplace answer arrived.
- Only an explicit 「放弃详细报告」 ends the turn without a report. Absence of an answer is not that choice, and it must not be read as one.

A turn that ends with the preliminary reading delivered, or with the preliminary reading plus a report, is complete. A turn that ends with only a question and no reading is the failure this whole section exists to prevent.

> 生成详细图文报告需要访问网络地址，遇到提示时请选择「本次会话内始终允许」，后面的排盘和生成命理报告才能正常进行。

Show the card once, before the first service call only. Do not repeat it on later calls, and do not put it in the report JSON or the HTML. When the user only asks about a classic or a symbol rule and no chart is cast, do not show it. If the year, month, day, hour, or sex is still missing, ask for it with a card first, the way the section 「Asking the user」 requires, and do not show the report card yet. A missing birthplace does not block this reading or this card. The birthplace card stays in 「One request」.

## One request

When the user chose 「生成详细图文报告（需要允许访问网络）」 in the card, follow the steps below.

1. No birth time, only a question about symbol rules: do not chart. Explain the rule.
2. **Set the birthplace.** True solar time depends on longitude. One degree is four minutes. Near a double-hour boundary that changes the hour pillar. Take longitude only from the table in this package. Do not estimate from memory.
   - Read `references/geo-index.md`, decide the province, then read only that province's table under `references/` (each province has its own file, named by province code — for example `references/geo-11-北京.tsv` for Beijing, `references/geo-31-上海.tsv` for Shanghai). If the province is unclear (for example only 「朝阳区」 was given), search all the province tables for the place name.
   - Each row is code, full name, aliases (former names and variant spellings), longitude, latitude. The user's place name may have a typo, a short name, or an old name. Match it against the full name and the aliases.
   - When one match is reasonable, take that row's **code**, and say in the conversation which province, city, and district supplied the longitude.
   - **When no birthplace was given at all, ask for it with a card.** Under the header 「出生地」, put this sentence in full into the question text and add nothing else: 「请输入出生地以便校准确定真太阳时」. Do not explain the double-hour boundary, name a longitude, or list provinces on this card. The birthplace or a longitude number is typed in the card's built-in custom input. Offer exactly one option: 「按默认东经 120 度排盘」, which charts without a birthplace and makes the report say the longitude came from the default. Do not offer 「我输入出生地」 or any second option. Do not set a placeholder on the custom input. If that input comes back with a place name or a longitude number, use it under the rules in this step. Then wait. **This ask must not be sent as plain text.**
   - When several candidates remain (the same county name twice, or a typo that fits more than one place), put the candidates in a card, up to three of them, and let the user choose. Do not choose for the user. Use the fourth slot for 「按默认东经 120 度排盘」 when one is free.
   - If the table has no match, put a card asking for the parent division or for a longitude number. If the answer carries no place, take the default longitude and note it in the report.
   - If the user states a longitude number, use that number. Do not look it up.
   - Pass only the code to the script. The script reads longitude from the table. Do not copy the table's longitude into the command or the JSON. In one conversation, charting, flowing year, flowing month, and the report JSON all use the same code.
3. Birth time is given: request the calculation JSON. The whole stdout is symbols, plus one English field, `score_brief`. The stderr line 「计算完成。标准输出是可复算符号，不是解读。」 is not a conclusion. Copy `score_brief` in full before writing any report Chinese. Do not paraphrase it, and do not summarize it. If it is missing or empty, stop. Do not write the report.

```bash
python -B "$SKILL_DIR/scripts/chart.py" year month day hour minute sex --place-code code
python -B "$SKILL_DIR/scripts/chart.py" year month day hour minute sex longitude   # only if the user stated a longitude
python -B "$SKILL_DIR/scripts/chart.py" year month day hour minute sex --lunar --place-code code    # when the user's date is a lunar date
# add --leap when that lunar month is a leap month; add --year YEAR when a base year is required
```

`sex` is 男 or 女. Without `--lunar` the date is solar; with `--lunar` the year, month, and day are read as a lunar date, and `--leap` marks the leap month (only valid together with `--lunar`). The service converts the lunar date to solar; the client does no calendar math and needs no extra library. An impossible lunar date — a leap month that does not exist, or a day past that month's length — is rejected with 400. Do not chart the same birth data twice. Request again only when the date, sex, or birthplace changes. If neither a code nor a longitude is given, the service uses east longitude 120, and the chart basis says where the longitude came from.

4. Choose the scheme from the question. Write the report JSON to a randomly named file in the system temporary directory, for example `yixue-report-<12 random characters>.json`. Do not write it into the skill directory, and do not leave it in the user's project tree. Keep it only until the report has been generated, then delete it. Field names follow section 6 of `references/methodology.md`.
   - BaZi only: `scheme` is `bazi`.
   - Zi Wei only: `scheme` is `ziwei`.
   - Both, or a question about work, marriage, or moving: `scheme` is `fusion`.
   - `scheme` is never `fengshui`. A house question that needs the HTML report uses `fusion`, or `bazi` when the report is Four Pillars only. The `fengshui` command below is not a report scheme.
   - In `birth`, write the `place_code` chosen while charting, not a longitude number. Write `longitude` only when the user stated one.
5. Do not copy stems, branches, or stars into the JSON. The service recomputes them from `birth`. `prose.dayun` is exactly 10 entries, in the same order as `report_facts.dayun`. Each entry is only `{term, plain}`. Do not copy `ganzhi` or other chart fields onto an entry, and do not send only the current step. For a Zi Wei-only report, `prose.daxian` must match `report_facts.daxian`, and each entry is only `{term, plain}`. `prose.cards` is only `{term, plain}`. BaZi and fusion `report_facts.cards` have 3 entries; `prose.cards` is those 3 plus one final useful-god card, 4 in all. Zi Wei `report_facts.cards` has 4 entries, and `prose.cards` is those 4 with no extra card. The six topic keys are fixed. This skill writes the meaning and the advice, and points back to `report_facts.facets`. A reading leaf is `{term, plain}`. `prose.glance` also has `score` and `reason`. `score` is a string from 8.0 through 10.0 with at most one decimal. `reason` is `{term, plain}` and is not folded into `glance.term` or `glance.plain`. Both follow the `score_brief` copied from the calculation JSON. For a BaZi or fusion report, `prose.glance.term` must contain the `命格` string from the calculation, unchanged. The shape is section 6 of methodology.
6. Send that JSON to render. The HTML is written next to the JSON, named `图文报告-Type-Date.html`, where Type is 八字, 紫微, or 八字紫微 and Date is YYYY-MM-DD (for example `图文报告-八字-2026-10-12.html`), so a new report never overwrites an earlier one. Show the user that file; never surface the temporary JSON name.

```bash
python -B "$SKILL_DIR/scripts/chart.py" render /tmp/yixue-report-xxxxxxxxxxxx.json
```

7. The chart is already in this conversation, and the user asks about one year or one month: run only the command below. Write the question into `concern.topic`. Write the returned stems, branches, and palace into `concern.term`. Write the Chinese reading into `concern.plain`, and one choice into `concern.advice`. The service places that block as chapter 2, titled 此次所问. The matching luck-cycle step still gets its own ten-year choice. Do not put this long answer into that step. Do not let the calculation service pick a "key year". Keep the birthplace code from charting.

```bash
python -B "$SKILL_DIR/scripts/chart.py" liunian year month day hour minute sex year --place-code code
python -B "$SKILL_DIR/scripts/chart.py" liuyue year month day hour minute sex year month-branch --place-code code
```

The flowing-year life palace is the palace whose natal branch receives the tai sui branch. The flowing-month life palace is the palace whose natal branch receives the month-builder branch. `month-branch` is the earthly-branch index: 子 is 0, 丑 is 1, 寅 is 2, 申 is 8, and 亥 is 11. Do not send 12, and do not send a solar month number. The four transformations fly from the flowing year or month stem. Name the palace with the natal palace name.

8. The user asks only for the house gua, one palace, or one room: run flying stars only. Do not fill the ming gua or the nine palaces from the BaZi or Zi Wei calculation. The house gua must be one of 坎, 坤, 震, 巽, 乾, 兑, 艮, 离.

```bash
python -B "$SKILL_DIR/scripts/chart.py" fengshui birth-year sex [house-gua] [--year flying-star-year]
```

`minggua` and `flying` in the calculation JSON are only the ming gua and the center star of that year. A question about one room still follows the `fengshui` response.

## Report and delivery

- The fixed boundary statements are already in the last chapter of the HTML template. Do not rewrite those four sentences in the JSON, and do not add a reading guide.
- Write the reading only after the classics named below have been read, the two style samples in the next section are in the prompt, and the chart response's `score_brief` is in the prompt in full. Every sentence points back to `report_facts`.
- Open the HTML for the user. In the conversation, give the report path and keep the artificial-intelligence label.

## Before writing the reading

Read the classical sources in full before writing `prose`. If a book is long, continue by the book's own volumes. Do not replace the text with a summary.

- BaZi report: read `references/yuanhai-ziping.md`, `references/ditian-sui.md`, and `references/ditian-sui-chanwei.md`.
- Zi Wei report: read `references/ziwei-quanshu.md`.
- Fusion report: read all of the above.
- House gua or flying stars only: read `references/zhaijing.md`. The reading still points only at the ming gua, house gua, and nine stars already computed. The twenty-four roads in `zhaijing.md` are not this engine's Eight Mansions or flying-star algorithm. Do not apply them to this chart.

Judgments follow the classics just read. The month-command pattern name stays as the calculation service wrote it. Do not rename it. The reader-facing pattern name is the calculation service's `命格`. Copy that string into `prose.glance.term`. The glance also carries `score` and `reason`, written only after `score_brief` from the calculation JSON is in this prompt in full.

### Language of the report

Do not write any Chinese report sentence until both originals headed `#### BaZi sample` and `#### Zi Wei sample`, and the full `score_brief` from the calculation JSON, are part of this prompt. If either original is missing, stop and load it. If `score_brief` is missing, stop. Do not paraphrase it. A path to `references/voice-bazi.md` or `references/voice-ziwei.md` does not count. Those files are the archives. The text below is the same 原文, included here so it is in the prompt.

The two originals below are the language. Read them and write in their language. BaZi Chinese follows the BaZi sample. Zi Wei Chinese follows the Zi Wei sample. Do not turn their wording into a list of phrases to use or to avoid. The life in each original belongs to that case, not to this reader. The report chapters, the JSON fields, the ban on 注定, and the ban on inventing a year of marriage, funeral, or illness stay as written above. Do not write chapter numbers in the prose.

Every sentence the reader sees in the report body is Chinese. The English in this file, every JSON field name, and every internal script or file name is instruction for you alone; none of it may reach the report. Do not put an English word, a field name, or an internal file name into `plain`, `advice`, or the Chinese prose in `term`. Keep an English token only when the reader wrote it first, in the opening message, as their own word — a product, a brand, a model such as iPhone, a personal-trait term such as ENFP, or a romanized name. The `score_brief` in the calculation response is an English note for you alone: take its meaning, and write that meaning in the Chinese of the two originals in this file, never in its English words.

One concept has no Chinese word in the two originals: the score's tier. Write it with the Chinese word 档 — the chart summary already writes 档 for the strength level — as in 故评分居上档. That is one concept given its name, not the list of phrases to use or to avoid that the rule above forbids.

The preliminary reading uses the same two originals. It may name the symbols it reckoned.

### What each passage is for

State the job of the passage. Diction and sentence-making stay with the two originals below.

- **Technical note (`term`).** Name the stem, branch, palace, or star at this place, and the matching point from the classics. Quantities already drawn on the chart are not reported again here.
- **Plain note (`plain`).** What this place usually means for the native's temperament, for how the native works, or for this period.
- **Useful god, favorable, unfavorable, and opposing (`yong`, `xi`, `ji`, `chou`).** Names only, for the chips and the glance-card title. Each value is one of 印绶, 官杀, 比肩, 劫财, 食神, 伤官, 偏财, 正财, 七杀, 正官, 偏印, 正印, 比劫, 食伤, 金, 木, 水, 火, 土, 印, 财, 官, 杀, or two of those joined by `、`. Do not write a sentence. The explanation goes in the technical note and the plain note.
- **Strength and pattern.** What the three strength items mean together. Which computed stems and branches the pattern name sits on.
- **Luck cycle and major limit.** This step's stem-branch or palace, and the choice for these ten years. A BaZi or fusion report writes exactly 10 luck-cycle entries, in the order of `report_facts.dayun`; a Zi Wei report writes the same 10 as `prose.daxian`, in the order of `report_facts.daxian`. Each entry is only `{term, plain}`.
- **Advice.** One choice the reader can carry out.
- **Opening of the glance (`glance.term`, `glance.plain`).** What the whole chart is, and what that usually means for the native. The page titles this block 本命. It is not a second score reason. When the user asked a specific question, `plain` adds at most one sentence on that question. The long explanation is not written here.
- **This question (`concern`).** Only when the user asked a specific question. `topic` names it. `term`, `plain`, and `advice` are the long explanation. When the question is about a dwelling, a room, or a direction, this chapter carries that reading, namely the facing and the position at stake, what the flying stars place there this year, and one adjustment the reader can choose, following the ming gua and the year's flying stars the service computed. The page makes this chapter 2, titled 此次所问, and moves the later chapters down by one. Do not repeat the long explanation in a topic card or a luck-cycle step. If there is no specific question, omit `concern`.
- **Score reason.** Which placement supports the score. The page puts this inside the block titled 总评. The score itself goes only in `glance.score`.
- **Chapter openings.** Do not explain to the reader how the report was made, how a later passage will cite this one, or how a bar's length is calculated.

#### BaZi sample

The archive is `references/voice-bazi.md`. The original follows.

## 原文

这是一例全国劳模、人大代表、华东某企业集团董事长英雄造时的乾造。我2003年7月5日为其作了30页的命理批注，现将整理后的内容择录如下，意在抛砖引玉，并奉献给所有热爱祖国民族文化的人们。

农历出生年份：
命主（生于）一九五二年九月初七日戌时
（生地）山东

### 一、四柱八字命局式

| 年 | 月 | 日 | 时 |
|---|---|---|---|
| 壬 | 庚 | 甲 | 甲 |
| 辰 | 戌 | 辰 | 戌 |

### 二、大运式

| 大运 | 辛亥 | 壬子 | 癸丑 | 甲寅 | 乙卯 | 丙辰 | 丁巳 |
|---|---|---|---|---|---|---|---|
| 虚岁 | 5—14 | 15—24 | 25—34 | 35—44 | 45—54 | 55—64 | 65—74 |

### 三、简述乾造

辨识该造四柱纯阳，似有参天之势，唯在兄弟比肩中天高人峰。细看月、时二戌土燥，甲木遇二支不盛，虽可焚火敷荣，然因身弱疲敝终难遂志。喜有庚金偏官透干致奇，甲木不但可得斧凿际遇威震一方，又遇暗化水印名利双收，成就荫家之功。又见局间辰戌双击，中隐几度大起大落，患得患失，拼搏不已和驿马东西南北的阅历，演绎了一段英雄造时、生命内容十分丰富的四柱命例。

这个乾造和大运使人不难看出，命主前辈多属奔波在外之人，应该是从事营运的商人，虽多有产业则荡然少存，而母性多在家操持。

命主出生在农村，己为长兄则不失姊妹四人，日子还过得去。庚子年就读乡小，十四岁前有较好的受教育环境，及至丙午年火炎土燥而辍学。继之杂学于乡里，直到戊申年从军。庚戌年复员后，利用公职环境深造，可拥有专业文化水准。

命主癸丑年经母辈媒妁，与当地乡里女子结婚，生有一男两女后，于丙寅年离异。而后丁卯年另娶一妻，生有一子。实事求是的讲，命主乾造妻妾遍野，纯阳的八字又逢辰戌双斗，注定妒争二婚，也无它议。

无可厚非的说，命主虚25——34岁癸丑大运的确不错，印前官后干支注定了命主的天时、地利、人和。除有较稳定的基层职务和收入，家和人安的环境可保持十年。

到命主虚35——44岁甲寅运段，恰逢大环境为他提供了可以张扬个性的绝好时机，凭借自己的实力和优势，丁卯年伤掉原来的公职官星，追禄营造私营实业，大刀阔斧的借刃创造经济效益，出人头地的峥嵘一方，乐善好施的繁荣地方经济……短短的十年，不仅创建了本人上亿元的资产，而且带动一方脱离贫困，成为妇孺皆知的赫然人物。

进入虚45——54岁乙卯大运，是命主风云际会的精品命段，皆因自己强而又强，释放生命意义极致鼎沸。在不断发展生地产业的同时，还在生地西、北方创建了近十个企业，使企业经济增值了三、四倍之多。追求发展中大胆的重用人才，把私有制的企业规模和质量不断推向新高峰。

乙亥、丙子、庚辰、辛巳、壬午流年，命主屡得嘉奖，分别获市、省级多项殊荣，还于壬午年成为全国劳模、人大代表，受到国家党政领导的肯定。

命主进入虚55——64岁丙辰大运，前五年食神盖头尚可悦目赏心，而后五年间隐有西、北方产业败落，外室倾覆的危险，而且伤官透出，对个人身体亦十分不利，当巩固生地发展和内家基础而不失根本。

下一段干支丁巳，主虚65——74岁运段，显然不妙。皆因运逢伤官猖獗，土燥伤根。命主已无力精华，灾事绵绵，原有的心脑血管遗病，极易导致中风、瘫痪，病期很久。当提前考虑急流勇退，安享晚年为宜。

### 四、简论乾造

该造甲干生逢深秋，界于深秋、盛夏和春末之间，浅见生不逢令，干弱少扶，难有身强遗福之论。然一路水、木、土、火大运干支亲缘有情，结合原命局的辰支用神，把命主造化的有声有色。逢印而得贵，逢官有誉声，逢比而自强，逢劫多业绩，逢财勇可取，逢食伤官推……却原来是个运造骄子。

且细观干支，甲嫁乙妹事庚金变敌为友，庚金还报壬水而亲甲，甲木暗得福也。唯局中两戌减了命造分数，何为？皆因命主生秋不令，当坐辰支固根乘龙，不容秋土倾陷之毁。也就因两戌之患，甲干才有了离异之苦，壬子年丧母之哀，壬申年次子病亡之痛，还有丙戌年后的无妄之乱……初因自己所为，根在造化必然。

写到此处，孟子"天降大任于斯人也，必先苦其心志，劳其筋骨，饿其体肤，空乏其身，曾益其所不能……"的古论，也许能使人从这例乾造，杜知一些告白。


#### Zi Wei sample

The archive is `references/voice-ziwei.md`. The original follows.

## 原文

### 一、命主基本介紹

命主是一位女性，本身是台灣人，嫁到國外去，使用視訊方式諮詢，想了解整個運限的發展，目前剛踏入第四大限，走子田線，如對紫微斗數有些概念或是常看我的解盤案例，就能知道對於踩入的宮位將是這十年最在乎的事，因此大部份的人會判斷命主諮詢重點應該是家庭或子女，但是命主在整個諮詢時間中，將近六成時間都在問事業，想回台灣繼續發展，其餘時間才問適合生小孩的年份以及婚姻狀態，關於這一點我先快速解釋一下原因，詳細內容在分析第四大限時，會有更細膩的解說。

當一個人的生年盤的三方四正屬於較活潑的星曜，或是比較容易暴衝的星曜，走到較平穩的大限環境時，雖然會有些綁手綁腳，企圖心伸展不開的感受，同時也會想要一份安定感，比如生年盤三方四正是殺破狼，走到雙數大限時（如：第二大限、第四大限⋯⋯），所遇到的環境都離不開機月同梁，也許同時遇到太陽、巨門，會有些小差異，整體而言，此時的環境是安穩的，就算有煞忌坐或沖，整體感受上變動不大，偶而來些煞忌反而比較有趣，這也是那些活潑星曜的優勢，相反的，當生年盤是機月同梁，走到雙數大限會遇到殺破廉貪這樣變動性高的環境，好處是能將自己的內在潛力激發出來，壞處是不太能適應這樣劇烈的變化，命主就類似這樣的情況，雖然踩入子田線，但是整體環境給予滿滿的衝勁，大限四化加持後，也有不錯的發展機會，無奈自己先天個性不太喜歡如此大的變動，內心還是希望照顧家人為主，所以才會不知如何是好，這也是老天爺給大家的功課，十年平穩，十年變動，人類也才能不斷的進步，這個十年一半的人穩定過日子，另一半的人勇於突破創新，下個十年就相反過來，所謂一陰一陽才能生生不息。

我又離題太遠了，回到命主身上，我們先來看看命主生年盤，了解先天的個性。

### 二、本命盤分析

1. 命宮：天同，個性較為與世無爭，但畢竟是福星，也許就是這份知足常樂，讓自己減少很多不必要的鬥爭。
2. 遷移宮：太陰（權），在外展現細膩、母性光輝的特質，加上化權加持，在外的同性、異性人緣確實幫助不少。
3. 財帛宮：巨門、火星，巨門理財方式較為保守，這算是好事，但火星在同宮，常會有衝動性消費，買了後常會檢討自己的不理智而後悔。
4. 官祿宮：天機（忌）、鈴星，天鉞，天機代表善變，化忌後更為明顯，加上鈴星的影響，在追求人生價值的態度上，常常因為自己想太多而一直變來變去，還好有顆天鉞星，適時的有貴人出來幫她一把。

解釋一下這組天同坐卯/酉位，對宮太陰的星盤特色：天同星化氣為福，個性隨和，樂於助人，只是在卯/酉位的亮度不夠，展現出來反而有些欠缺鬥志，雖不與人交惡，但也不會過度參與人際交際。

對宮太陰星五行亦屬水，在外展對人溫柔、細膩照顧，也是人人喜歡的好個性。

天同、太陰五行皆屬水，桃花緣旺盛，但夫妻宮坐天梁星，對待感情卻是格外務實，與本性截然不同，這也是此格局的特別之處。

官祿宮坐天機星，對於追求人生價值上，常常變來變去，也容易讓人感覺穩定性不高，與天同太陰想要安定，容易產生相互矛盾。

財帛宮坐巨門星，理財觀念趨於保守，同時在遇到得財機會時，也會考慮較多。

用星盤組合加上命主的官祿宮情況，就不難發現命主對於人生追求的價值觀是一直在改變的，也可以說想要每項事情都做的完美，這是受到太陰化權的影響，那為何走到第四大限子田線時，是想要追求事業而不是穩定家庭呢？ 我們繼續看下去。

### 三、運線盤分析

第四大限走子田線，甲干，廉貞化祿再大限命宮，破軍化權在大限遷移宮，武曲化科再大限官祿宮，太陽化忌再大限僕役宮，眼尖的看倌應該發現這是三吉嘉會的格局，祿、權、科在大線命宮的三方四正，這樣的格局用在照顧家人或是當個家庭主婦也是非常好的，只是這個運限的三方四正的星曜都不是屬於穩定性高的性質，此時再遇到太陽化忌在大限僕役宮疊本命福德宮，內心的空虛感會受到同輩的朋友所激發，命主也回饋她在台灣的女性好朋友，有好幾位都是未婚，事業或工作都做得有聲有色，每當看到他們在社群軟體上貼出吃喝玩樂的照片，或是在沙攤上大膽展現自己的好身材，獲得破萬人的愛心或留言，她就覺得好羨慕，在幾年前都沒有這樣感覺，怎麼這二年突然開始對人生價值有些改觀？ 其實答案就在以下分析中。

1. 第四大限命宮：廉貞（大限祿）、天相、右弼（生年科），廉貞化祿時相對穩定，所謂廉貞清白格，只是這個「清白」是自己訂定的，不是世俗眼光，加上天相也是人際星曜，在不遇到煞忌時，人際狀況確實很不錯，加上右弼化科，更是魅力十足。
2. 第四大限遷移宮：破軍（大限權）、生年擎羊，這邊就很明顯想要追求夢想，破軍這位將星拿到權力，旁邊在送他一把擎羊大刀，這股在魄力就是想要有自己的事業或完成夢想最主要的影響關鍵點。
3. 第四大限財帛宮：紫微、天府，這邊也很明顯，在消費上想要面子又要裡子，而這是大限盤，代表現象，只要走到甲年對宮有祿存，或是庚年祿存正坐，財運真的很不錯。
4. 第四大限官祿宮：武曲（大限科）、生年陀羅，這裡我也覺得很棒，別害怕陀羅，咱們的武曲也屬金，一起鑽出辰戌位的天羅地網，而且武曲還化科，工作能力務實又能鑽研，機會不請自來。

看完第四大限的三方四正解釋後，各位應該就能了解命主雖然走到子田線，卻不想當家庭主婦，反而來諮詢事業，想必已經有人邀約創業了，那為何還是在猶豫呢？ 別忘了命主本命盤是天同坐命對宮太陰，本性還是喜歡安穩的生活，但遇到大限的影響，整體環境逼著她要有所改變，確實也有足夠的運氣，可創造一番事業，就看命主自己敢不敢了。

### 四、結論與建議

1. 創業或是工作都很適合這個大限，但不一定要回到台灣，從命主的生年盤來看，應該只是掛念原生家庭的家人，不是因為回到台灣發展會比較好，我請命主先跟老公商量一下，也許留在本地發展對於夫妻感情會有幫助。
2. 這個大限自己也要注意桃花問題，尤其是在職場上，原因是大限命宮有顆右弼化科，很容易招來一些有婦之夫，加上廉貞化祿，這個魅力不容小覷。
3. 如果有考慮生小孩，要有心理準備，因為這個大限只有幾個流年比較有機會，所以在那一年的工作需要放慢腳步，之後也將成為標準的職業婦女，工作和家庭都要兼顧，會很辛苦，從大限疾厄宮就能看出精神思慮上的問題滿明顯的，提醒命主考慮清楚是否要承受這樣的壓力。

最後來到勸世文時間，命主信奉天主教，所以我就單純的請命主多多佈施，在本地、在台灣都可以同時捐款，畢竟這個大限的財運不錯，有能力時，多多幫助人，為自己種一份福田。


## Important statements

- Four pillars, twelve palaces, four transformations, luck cycles, major limits, flying stars, strength scores, and the month-command pattern name are computed by the algorithm. They can be reproduced and checked.
- Whole-chart pattern names and points, the useful god, the glance score and its reason, which year is discussed, palace meanings, and topic comparisons are written into the report JSON. The glance score follows `score_brief`. They are **not a scientific conclusion, and they are not absolute**.
- They are **not a basis for a medical, legal, or investment decision**, and they do not replace the corresponding professional opinion.
