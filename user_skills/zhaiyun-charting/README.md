# 宅运堂 · 家居风水阳宅布局

把传统命理排盘做成可复算的工具，并把解读写成一份精美图文报告的 WorkBuddy 专家。

## 能做什么

- 排八字四柱与紫微斗数命盘，看命局格局、大运与流年流月。
- 用八宅飞星看阳宅某一宫、某一方位的宜忌。
- 按公历换算农历与节气。
- 当用户有具体所问时，把该问题作为报告第二章「此次所问」。

## 怎么用

1. 给出出生时间（公历或农历）、性别，以及想问的事项。
2. 首轮会先按传统规则起一盘初批，精确符号以随后的排盘服务为准；随后询问是否生成精确排盘与报告。
3. 选择「生成详细图文报告（需要允许访问网络）」后，首次会提示是否允许访问网络；允许后生成详细报告。
4. 选择「放弃详细报告」则本轮到此为止。

## 边界

本内容由人工智能生成，仅供娱乐与文化参考。解读依据传统规则，并非科学结论，亦非绝对，不构成医疗、法律或投资决策依据。

不提供情感陪伴；不跨会话保存个人资料；不排六爻、奇门、塔罗。

## 类目

工具 > 信息查询

## 打包（维护者）

核心代码只有一份，品牌差异放在 `brands/`。新增一个表面不同的专家/技能：
加一份 `brands/<brandId>.json`、一张 512×512 头像，然后

```
python -B scripts/package_expert.py --brand <brandId>
python -B scripts/package_skill.py  --brand <brandId>
```

产出全部已登记品牌用 `--all`。字段说明与文案纪律见 `brands/README.md`。

包名规则：**专家包取 `<brandId>`，技能包取 `<brandId>-skill`**，同词根并排可配对。
（存量品牌沿用 `-charting` 后缀，属历史命名不追溯。）

两类包的差异：专家包顶层目录取 `expertName`，内置技能改名 `<skillName>-inner`；
技能包顶层目录取 `skillName`，即市场发布名。两包不同名，避免互相抢用。

某品牌若能力边界或说法与主流程不同，用**侧车目录** `brands/<brandId>/`：`SKILL.md`
与 `agent.md` 是整份替换件（文件在不在即开关）。其中 `SKILL.md` 不手写，而由**配方**
生成——主 `SKILL.md` 在可变区域放成对书签 `<!--@slot:名字-->默认文本<!--/@slot:名字-->`，
`tools/skill_parts/<brandId>/overrides.txt` 按槽位名 replace／append，然后

```
python -B tools/gen_brand_skill_overrides.py            # 全部品牌
python -B tools/gen_brand_skill_overrides.py <brandId>  # 只重生成一个
```

**改了主文件或配方就必须重跑生成器**，否则打包会被对账拦下（见下）。机制细节、
配方格式与约束见 `brands/README.md`。

## 验收

```
python -B tests/test_brand_override.py    # 覆盖机制 + 现有品牌零回归（逐字节比对基线）
python -B tests/test_brand_recipe_sync.py # 配方与成品对账 + 书签卫生 + 配方格式
python -B tests/test_brand_names.py       # 包名规则台账（只记录存量偏离，不阻断）
python -B tests/test_brand_packages.py    # dist 下全部 zip 的结构验收
python -B tests/test_skill_yaml.py        # 用真实 YAML 解析器验收 frontmatter
```
