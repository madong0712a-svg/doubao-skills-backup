# BaZi and Zi Wei charting: calculation and report fields

> The calculation service returns reproducible symbols and recomputes the chart from the birth data at render time. This skill writes only the reading.
> This file defines the calculation rules, the reading steps, and the JSON field names. What the chapters contain is defined in `templates/命理报告结构设计-v1.md`. Which sources to read before writing is defined in `SKILL.md`, section "Before writing the reading".

Instructions in this file are English. Every sentence the reader sees in the report is Chinese. That includes `plain`, `advice`, and the Chinese prose inside `term`. English here must not appear in the report.

---

## 1. Where reproducibility comes from

Whether a chart can be reproduced depends on the calendar. The calculation core meets these requirements:

| Requirement | Implementation |
|---|---|
| Stem-branch conversion is reproducible | The service uses the `sxtwl` astronomical calendar library (years -1000 to 3000), not a lookup approximation. The user machine does not install that library |
| Month command follows solar terms | The month pillar is cut at the exact moment of the twelve solar terms (立春, 惊蛰, 清明, and the rest), not on the first day of the lunar month and not on the calendar day the term falls. A birth on a term day but before the term moment belongs to the previous month |
| Year pillar starts at 立春 | The year stem-branch is counted from the exact moment of 立春, and by the same rule |
| True solar time | Beijing time is corrected by longitude and the equation of time, so the double-hour does not slip. The term instant is compared in Beijing time, which is the time base the service reads the terms in; true solar time decides the day pillar and the double-hour, and is not compared against a term moment |
| Longitude from the table | Birthplace longitude comes from the province tables under `references/` in the skill package, one file per province. The client looks it up by administrative code. Do not estimate from memory |
| Luck-cycle start is exact to the solar term | Starting age = actual days to the neighboring solar term ÷ 3 (3 days = 1 year, 1 day = 4 months, 1 double-hour = 10 days). The sequence steps forward or backward from the month pillar |

The same date and birthplace always produce the same chart. That is the checkable floor.

**Birthplace longitude table**: county level, covering mainland China, Hong Kong, Macau, and Taiwan, about 3,200 rows. Each row uses the government seat or the urban center. Longitude keeps one decimal place (0.1 degree is about 24 seconds of true solar time). The skeleton is the Ministry of Civil Affairs code list for divisions at county level and above. Coordinates come mainly from Wikidata (CC0), checked against GeoNames (CC BY 4.0, https://www.geonames.org/). Rows where the two sources differ by more than 0.3 degree were checked by hand. Version and row counts are in `references/geo-index.md`. The chart basis states that the longitude was looked up for a named place in a named edition of the table. Taiwan county and city codes are assigned by this table (71xx00).

---

## 2. BaZi: how it is calculated and labeled

**Charting (deterministic)**

1. True solar time → four pillars (year, month, day, hour stems and branches).
2. Ten gods: the day stem is the reference. Every other stem and branch is classified against it as peer, output, wealth, officer, or resource.
3. Five elements: stems plus hidden stems in the branches (main, middle, and residual qi, weighted). The five-element bars and the ten-god bars each scale to the largest value in that chart, so the longest bar fills the track and the number beside a bar is the raw score or count. The three strength items use their own ranges: season -1 to 2, roots at most 6, support at most 3.
4. Na yin, voids, and the conception yuan.
5. Luck cycles: forward or backward from the year stem's yin-yang and the sex; the solar term sets the start and the sequence.

**Closed results the service returns**

- Season, roots, and support: each has a conclusion, a score, and a basis. Season uses the five-element produce/control table, not subscript increments.
- Day-master strength: a band and a total made from those scores.
- Pattern name: taken from the month command. The service states whether the pattern stem is visible on a stem or is the main qi of the month branch, and lists the ten gods visible on the stems. The rule is month-command patterning.
- Ten-god counts, five-element counts, branch punishments, clashes, combinations, and harms, and each luck cycle's relation to the natal chart.

These are names, scores, and stems and branches. Useful god, favorable and unfavorable elements, and their life meanings are written by this skill from the classics into the reading. Do not write them as an order to change jobs or to invest.

---

## 3. Zi Wei: how it is calculated and labeled

**Charting (deterministic)**

1. Solar date to lunar date → life palace and body palace (count forward from the tiger palace through the birth month, then count the life palace backward to the birth hour).
2. Place the twelve palace stems (five-tiger escape) and the five-element board (na yin of the life palace).
3. Place Zi Wei: birth day ÷ board number (quotient locates, remainder sets advance or retreat). Tian Fu mirrors Zi Wei across the tiger and monkey axis: Tian Fu = (4 − Zi Wei) mod 12, so the two stars share a palace only at 寅 and 申, as the altar chart in `ziwei-quanshu.md` states.
4. Place the fourteen major stars (Zi Wei group backward, Tian Fu group forward).
5. Place assistants and malefics (Wen Chang, Wen Qu, Zuo Fu, You Bi, Lu Cun, Tian Ma, Di Kong, Di Jie, Qing Yang, Tuo Luo, Tian Kui, Tian Yue, Huo Xing, Ling Xing).
6. Fly the four transformations from the birth-year stem (Lu, Quan, Ke, Ji), using the mainstream sanhe table. That stem follows the 立春 boundary above, so it is the same stem the year pillar carries.
7. Set the major limits (start from the board number; yang male and yin female forward, yin male and yang female backward).

**Closed results the service returns**

- Life palace, body palace, five-element board, the star-placement formula, stars in the twelve palaces, which palace each birth-year transformation falls in, and the age span and stars of each major limit.
- Whether a sanhe pattern is hit, and the stars and palaces that hit depends on. A miss is an empty list. Copy engine hits as given. A pattern that appears in `ziwei-quanshu.md` and matches the stars may be written. Do not write a pattern name the book does not have.

Traditional meanings of stars and transformations, what the body palace governs, and the tendency of a major limit are written by this skill into the reading, and point back to those placements.

---

## 4. Eight Mansions and the yearly flying star

- **Eight Mansions**: year and sex give the ming gua (east-four or west-four). If a house gua (sitting mountain) is also given, compare the traditional east-four and west-four groups (same group or different group), list the four favorable and four unfavorable directions by gua name and bearing, and state the traditional comparison. Do not write the comparison as an order to move or to rebuild.
- **Yearly flying star of the three cycles and nine periods**: the year's star enters the center and flies forward through the nine palaces. List the star number in each direction (2024–2043 is the lower cycle; from 1984 the 7 white star enters the center). When the user asks about one palace or one room, state that star's ordinary meaning in the flying-star tradition.
- Flying stars and the ming gua are cultural reference. They do not replace a site survey.

---

## 5. Reading steps

Commands and failure handling follow `SKILL.md` at the skill root. Write the report JSON in this order:

1. **Read the classics and the style samples first.** Which files, and the samples that must already be in the prompt, are in `SKILL.md`, "Before writing the reading". If a book is long, continue by the book's own volumes.
2. **Then read `report_facts`.** Four pillars, five elements, ten gods, strength, pattern name, whether the pattern stem is visible or is main qi, ten gods visible on the stems, branch relations, luck cycles, twelve palaces, four transformations, major limits, and the short bases for the six topics are all here. Do not change those strings, and do not copy a second chart into the JSON.
3. **The reading goes only in `prose`.** Glance, each glance card, strength, pattern, useful-god choice, each luck cycle, Zi Wei life palace, body palace, and four transformations, the six topics, the summary, and the divergences. Except advice sentences and `glance.score`, those leaves are `{term, plain}`. The job of each field is section 6. Diction and sentence-making stay with the two originals embedded in `SKILL.md`. Do not write any report Chinese until those two samples, and the full `score_brief` from the chart response, are in the prompt. If `score_brief` is missing, stop. Do not paraphrase it. `glance.score` and `glance.reason` follow that text.
4. **Luck-cycle count matches.** `prose.dayun` has the same length and order as `report_facts.dayun`. A Zi Wei-only report uses `prose.daxian`, matching `report_facts.daxian`.
5. **The two systems stay side by side.** In a fusion report the service writes the BaZi basis and the Zi Wei basis of each topic separately. The meaning this skill writes must not derive one column from the other. Where they disagree, write `prose.close.divergences`.
6. **The question asked this time.** When the user asked a specific question — work, marriage, moving, a given year, or another question about this chart — add `concern`. The service places it as chapter 2, titled 此次所问, and moves every later chapter down by one. The long explanation goes only there: `topic` names the question; `term`, `plain`, and `advice` explain it. The advice is one choice the reader can carry out. Do not write chapter numbers. If there is no specific question, omit `concern`. Health, money, and personal safety also point to a professional channel.
7. **The pattern name in the glance.** For a BaZi or fusion report, `report_facts` carries `mingge`, the whole-chart name from the seven orthodox patterns. `prose.glance.term` must contain that string unchanged. The month-command name stays as computed and is not renamed. A Zi Wei-only report has no `mingge` line. `prose.glance.score` is a string from 8.0 through 10.0 with at most one decimal. `prose.glance.reason` is `{term, plain}` and is not folded into `glance.term` or `glance.plain`. Both follow `score_brief`.
8. **The boundary statements are already in the last chapter of the HTML template.** Do not rewrite those four sentences in the JSON, and do not add a reading guide.

Which sources to read: `SKILL.md`, "Before writing the reading".

## 6. Report JSON fields

The top level has only `scheme`, `birth`, optional `display`, optional `concern`, and `prose`.

`scheme` is `bazi`, `ziwei`, or `fusion`. It is not `fengshui`. A house question that needs this HTML report uses `fusion`, or `bazi` when only the Four Pillars are in the report. The `fengshui` command is separate and is not a report scheme.

`birth` matches a chart request: `year`, `month`, `day`, `hour`, `minute`, `sex`, optional `current_year`, optional `is_lunar` and `leap_month`, and one birthplace form:

- `is_lunar`: optional boolean, default false. When true, `year`, `month`, and `day` are a lunar date. `leap_month`: optional boolean, default false, valid only together with `is_lunar`; it marks that lunar month as a leap month. The service converts the lunar date to solar; the client does no calendar math. Omit both for a solar date.
- `place_code`: the administrative code chosen while charting. At `render` the client turns it into longitude and the full place name. The JSON does not contain `longitude` or `birth_place`.
- `longitude`: only when the user stated a longitude number. `birth_place` may be added beside it.

If neither is given, the service uses east longitude 120, and the chart basis says so.

`display` may be omitted. Keys are `name`, `reader`, `place`, `era`, each allowed to be an empty string. An empty `name` leaves the name off the cover. An empty `reader` leaves the signature off the last chapter.

`concern` may be omitted. If it appears, `topic`, `term`, `plain`, and `advice` are all required and non-empty. The service places this block as chapter 2, titled 此次所问. The long explanation goes only here.

`prose` keys depend on the scheme. A reading leaf is two non-empty strings, `term` and `plain`. `glance` also has `score` (a string) and `reason` (`{term, plain}`). `advice`, and every `yong` key except `reason`, is a string. `dayun` and `daxian` are arrays of `{term, plain}`.

Reader-visible strings are Chinese. JSON keys stay as written here. The rows below state the job of each passage. Diction and sentence-making stay with the two originals in `SKILL.md`.

### BaZi `bazi`

`glance`, `cards`, `strength`, `pattern`, `yong`, `dayun`, `facets`, `close`.

### Zi Wei `ziwei`

`glance`, `cards`, `ziwei`, `daxian`, `facets`, `close`.

### Fusion `fusion`

`glance`, `cards`, `strength`, `pattern`, `yong`, `dayun`, `ziwei`, `facets`, `close`.

### Keys

| Key | Content |
|---|---|
| glance | `term` names the stem, branch, palace, or star, and the matching point from the classics. `plain` says what this place usually means for temperament, for how the native works, or for this period. The page titles this pair 本命. It is the whole chart, not a second score reason. Quantities already drawn on the chart are not reported again in either. For BaZi and fusion, `term` contains `report_facts.mingge` unchanged. When the user asked a specific question, `plain` adds at most one sentence on that question. The long explanation is not written here. `score` is a string from 8.0 through 10.0 with at most one decimal, written from `score_brief`. `reason` names which placement supports the score and is not folded into `term` or `plain`. The page puts `reason` inside the block titled 总评. The score number stays in `score` |
| cards | Array of `{term, plain}` only. Do not add `tag`, `title`, or other chart fields. BaZi and fusion: `report_facts.cards` has 3 entries; `prose.cards` is those 3 in the same order, plus one final card for the useful god, 4 in all. Zi Wei: `report_facts.cards` has 4 entries, and `prose.cards` is those 4 with no extra card. `term` and `plain` have the jobs in the glance row, for this card. Do not write the plain note as inevitable |
| strength | `{term, plain}`. What the three strength items mean together |
| pattern | `{term, plain}`. Which computed stems and branches the pattern name sits on. Copy the month-command pattern name. The condition must sit on stems and branches already computed |
| yong | `yong`, `xi`, `ji`, and `chou` are names only, for the chips and the glance-card title. Each is one name, or two names joined by `、`. The names are 印绶, 官杀, 比肩, 劫财, 食神, 伤官, 偏财, 正财, 七杀, 正官, 偏印, 正印, 比劫, 食伤, 金, 木, 水, 火, 土, 印, 财, 官, 杀. Do not write a sentence. `method` is a string. `reason` is `{term, plain}` and holds the explanation. Do not write the unfavorable god from the strength balance directly as the conclusion |
| dayun | Exactly 10 entries, the same order as `report_facts.dayun`. Each is only `{term, plain}`: this step's stem-branch and the choice for these ten years. Do not copy `ganzhi` or other chart fields onto the entry, and do not send only the current step. Do not repeat the long relation sentence the service already wrote |
| daxian | Zi Wei only. Same length as `report_facts.daxian`. Each entry is only `{term, plain}`: this step's palace and the choice for these ten years. Do not copy chart fields onto the entry |
| ziwei | `ming`, `shen`, `sihua`. Each is `{term, plain}` with the jobs in the glance row |
| facets | Exactly six keys, these Chinese strings: 事业与工作, 收入与财富, 人际与合作, 家庭与婚恋, 身心状态, 心性与处事. Each has `meaning` (`{term, plain}`, jobs as in the glance row) and `advice` (one choice the reader can carry out) |
| close | `summary` and `divergences`, each `{term, plain}`. `summary` returns to the opening statement. `divergences` sets the disagreements side by side, without merging them or choosing a side |

`report_facts` from `/v1/chart` is for checking. Render recomputes the chart and does not use a chart copied in by the skill. The main items to check are `dayun`, `daxian`, `facets`, `solar`, `marks`, `pillars`, and `palaces`.

## 7. Boundaries

- The chart is reproducible. Strength scores, pattern names, and hit lists are closed lookups. The glance score is written from `score_brief`.
- Useful god, which year is discussed, and topic comparisons are written in the report JSON. They are not a scientific conclusion, and they are not absolute.
- They are not a basis for medical, legal, or investment decisions.
- Health, money, and personal safety must point to a professional channel.
- The HTML template already contains the Chinese sentence that the content is generated by artificial intelligence.
