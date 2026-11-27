# 可施工性约束

> **"不提供施工图"不等于"不校验可施工性"。**
> 本技能输出的是房源空间想象示意图，但经纪人拿给客户看、客户真照着装修，是最现实的失败路径。
> 一个物理上做不出的方案，比一张不够好看的图 damaging得多——前者会砸招牌，后者只是效果一般。

---

## 一、核心原则

**宁可用保守布局，不可画出物理上做不出的方案。**

不确定净尺寸时，**取保守值**（按最小可装尺寸反推），并在交付时标注"该空间尺寸需现场复核"。

---

## 二、最小可装尺寸对照表

> 数值是**行业常规下限**，非绝对值。实际还受管井位置、烟道位置、门洞位置影响。
> 判定时以"扣除管井后的净尺寸"为准，不以图纸标注的轴线尺寸为准。

### 厨房

| 项 | 最小尺寸 | 说明 |
|---|---|---|
| 单排橱柜 | 净宽 ≥ **1500mm** | 柜体 600 + 通道 900 |
| 双排橱柜 | 净宽 ≥ **2400mm** | 两排柜 1200 + 中间通道 1200 |
| L 型转角 | 两边均 ≥ **1500mm** | 转角台面需 900 见方 |
| 岛台 | 需四周均留 **900mm** 环形通道，且总净宽 ≥ **3000mm** | 小户型几乎不可能 |
| 冰箱位 | 预留 ≥ **600mm** 宽、≥ **600mm** 深 | 开门需 900mm 前方空间 |
| 吊柜 | 距台面 **700mm**（高）或**600mm**（矮） | 过高会压抑、难取放 |
| 烟道 | 灶具与烟道水平距离 ≤ **750mm** | 超了排烟效果差 |

### 卫生间

| 项 | 最小尺寸 | 说明 |
|---|---|---|
| 单人台盆柜 | 宽 ≥ **600mm** | |
| 马桶中心距墙 | ≥ **400mm**（舒适 ≥450mm） | 净宽不足 1500 时极紧张 |
| 淋浴区 | 短边 ≥ **800mm**（舒适 900+） | 太窄无法转身 |
| 干湿分离玻璃门 | 开门后净剩 ≥ **600mm** 通过空间 | |
| 三件套（盆+马桶+淋浴） | 净宽 ≥ **2200mm**、净深 ≥ **1400mm** | 小于此不建议三件套 |

### 卧室

| 项 | 最小尺寸 | 说明 |
|---|---|---|
| 床两侧通道 | 单侧 ≥ **550mm**（舒适 600mm） | |
| 床尾到对面墙 | ≥ **750mm** | |
| 1.5m 床 + 双侧通道 + 衣柜 | 净宽 ≥ **3300mm** | 净宽 <3000 时只能 1.2m 床 |
| 通顶衣柜进深 | **600mm** | 低于 550mm 挂不了长衣 |
| 衣柜开门后通道 | ≥ **700mm** | |

### 客厅 / 餐厅

| 项 | 最小尺寸 | 说明 |
|---|---|---|
| 沙发与电视墙距离 | **2500–3500mm** | 低于 2500 观看距离过近 |
| 电视柜深度 | **450–500mm** | |
| 餐桌四周通道 | 单侧 ≥ **600mm**（舒适 750mm） | 靠墙一侧 ≥ 400mm |
| 圆形餐桌直径 | 4 人 ≥ **800mm**，6 人 ≥ **1100mm** | |
| 主通道宽度 | ≥ **900mm** | 单人侧身通过的最小值 |

### 通用

| 项 | 最小尺寸 | 说明 |
|---|---|---|
| 通行净宽 | ≥ **750mm** | 两人错身需 900mm+ |
| 门洞净宽 | ≥ **800mm**（卧室 ≥850mm） | |
| 柜门前开启 | ≥ **600mm** | |
| 插座距地 | 开关 1300mm，插座 300mm（厨卫 1300mm 防溅） | |

---

## 三、房间识别清单里的判定列

在 `templates/room_inventory.md` 的房间表中，每行必须给出净尺寸与判定结果：

```markdown
| 房间 | 净尺寸 | 最小可装尺寸 | 可施工性判定 | 处理方式 |
|---|---|---|---|---|
| 厨房 | 2250×1490 | 单排 ≥1500，双排 ≥2400 | ❌ 不可双排 | 强制 L 型单排 + 高柜补收纳 |
| 卫生间 | 1700×2850 | 三件套 ≥2200 宽 | ⚠️ 紧张 | 做二件套（盆+马桶），淋浴用浴帘 |
| 主卧 | 3110×2850 | 1.5m 床需 ≥3300 宽 | ⚠️ 紧张 | 用 1.35m 床或床侧靠墙单通道 |
| 客厅 | 5550×3400 | 沙发-电视 ≥2500 | ✅ 可行 | 标准布局 |
```

判定三档：

| 判定 | 含义 | 处理 |
|---|---|---|
| ✅ 可行 | 满足常规布局最小尺寸 | 按常规方案生成 |
| ⚠️ 紧张 | 满足下限但不舒适 | **采用保守布局**，交付时标注"需现场复核" |
| ❌ 不可 | 低于下限 | **必须改布局**，按第四节改写提示词 |

---

## 四、不可施工时的提示词改写片段

> 插入到【户型结构】段之后、【风格迁移】段之前。
> 只在判定为 ⚠️ 或 ❌ 时插入，不要无脑全加。

## ⭐ 3.1 有效写法：正向 + 负面两段夹击（回归实测定稿）

> **实测结论：只写"保守布局"压不住，只写"不要X"也压不住。**
> 三张空间（厨房/主卧/卫生间）在加入两段夹击后**全部命中**，此前用软约束时全部失败。

### 必备三要素

| 要素 | 写法 | 例子 |
|---|---|---|
| **数量词**（正面） | `ONE` / `ONLY TWO` / `single row only` | `ONE single row of cabinets along the back wall only` |
| **CRITICAL CONSTRAINT 标记**（负面） | 独立成段，带"违反则失败"语义 | `CRITICAL CONSTRAINT — this kitchen is too narrow for two rows:` |
| **absolutely NO 逐项点名** | 每项换行，绝不合并列举 | `absolutely NO opposing tall cabinets, NO island, NO peninsula counter` |

### 完整示例（厨房，回归实测通过的版本）

```
【可施工性硬约束】
ONE single row of cabinets along the back wall only — matte warm white
handleless base cabinets, light grey stone countertop with a single integrated
sink and a single two-burner hob ON THE SAME countertop. One narrow tall
cabinet at the near end next to the doorway for the refrigerator.

CRITICAL CONSTRAINT — this kitchen is too narrow for two rows of cabinets:
absolutely NO opposing tall cabinets on the opposite wall,
NO double-row galley layout,
NO back-to-back stove,
NO kitchen island,
NO breakfast bar,
NO peninsula counter.
The walkway in front of the single cabinet row is under 900mm.
Do not widen the room, do not draw a large open kitchen.

小窗提示：该厨房只有一扇普通平窗，
不要落地窗、不要阳台门、不要飘窗。
```

### 三张空间的实测对照

| 空间 | 软约束（3.0 初版） | 两段夹击（3.1） |
|---|---|---|
| 厨房 1.9m | ❌ 双排橱柜 + 大玻璃窗 | ✅ 单排一字型 + 小平窗 |
| 主卧 3.1m | ❌ 1.8m 大床居中两侧留通道 | ✅ 1.35m 床靠单墙、单通道 |
| 卫生间 1.7m | ❌ 三件套含玻璃淋浴房 | ✅ 二件套 + 浴帘 |

**通用兜底句**（每个空间末尾都可加）：
`Do not widen the room, do not draw a large open space.`

---

## 五、各场景改写片段（两段夹击定稿版，照抄即可）

> 以下片段全部按「数量词 + CRITICAL CONSTRAINT + absolutely NO」三要素写好，
> 直接替换即可生效。中文行仅供人工理解，**实际喂给模型时用英文段**。

### 5.1 厨房不可双排（1.9m 净宽，回归实测通过）

```
【可施工性硬约束 · 厨房】
ONE single row of cabinets along the back wall only — a single integrated sink
and a single two-burner hob ON THE SAME countertop. One narrow tall cabinet at
the near end next to the doorway for the refrigerator.

CRITICAL CONSTRAINT — this kitchen is too narrow for two rows of cabinets:
absolutely NO opposing tall cabinets on the opposite wall,
NO double-row galley layout,
NO back-to-back stove,
NO kitchen island,
NO breakfast bar,
NO peninsula counter.
The walkway in front of the single cabinet row is under 900mm.
Do not widen the room, do not draw a large open kitchen.

该厨房只有一扇普通平窗：不要落地窗、不要阳台门、不要飘窗。
```

### 5.2 卫生间做不了三件套（1.7m 净宽，回归实测通过）

```
【可施工性硬约束 · 卫生间】
ONLY TWO fixtures are present: a floating vanity with an integrated basin and a
wall-hung toilet. The shower is separated by a simple fabric curtain on a rail.

CRITICAL CONSTRAINT — this width fits only two fixtures:
absolutely NO separate walk-in shower enclosure,
NO frameless glass shower partition,
NO shower cabin,
NO bathtub.
Do not try to show a basin, a toilet and a full shower cubicle together.

该房间无窗：不要落地窗、不要阳台门、不要侧窗、不要飘窗。
```

### 5.3 卧室放不下 1.5m 床（3.1m 净宽，回归实测通过）

```
【可施工性硬约束 · 卧室】
A 1.35 meter wide bed pushed AGAINST one side wall so that only ONE single
walkway of about 600mm remains on the other side. The wardrobe opposite the bed
has SLIDING doors.

CRITICAL CONSTRAINT — the room is too narrow for a wide bed with walkways on
both sides:
absolutely NO 1.8 meter king-size bed,
NO bed centered with two walkways,
NO large upholstered headboard spanning the whole wall.
The bed must read as a narrow 1350mm bed placed against a wall.

该房间是普通平窗：不要落地窗、不要阳台门、不要飘窗。
```

### 5.4 客厅不放得下大沙发（净宽 3.0m）

```
【可施工性硬约束 · 客厅】
A 2 meter small sofa against the wall. The viewing distance from sofa to TV wall
is about 2.5 meters.

CRITICAL CONSTRAINT — this living room is not an open great room:
absolutely NO three-seat large sofa,
NO L-shaped sectional,
NO chaise longue,
NO oversized open-plan living space.
```

### 5.5 层高限制（图纸未标层高时）

```
【可施工性硬约束 · 层高】
The ceiling height is not marked on the plan; treat it as the standard 2.8 meter
clear height. A plain flat ceiling with a small perimeter drop of no more than
300mm.

CRITICAL CONSTRAINT — do not draw a full dropped ceiling:
absolutely NO full-room stepped ceiling,
NO complex cove lighting shapes,
NO double-layer ceiling with light strips.
Full-height cabinets simply reach the ceiling.
```

---

## 六、模型不遵守尺寸时的兜底

**已实测：即使在提示词中明确写出净尺寸，模型仍可能画出超出净宽的布局。**
（用软约束时三张全部失败，改两段夹击后全部命中。）

这是模型的能力边界，不是提示词写得不够。按以下顺序处理：

| 步骤 | 动作 |
|---|---|
| 1 | 用第五节的「两段夹击」写法强化一次（数量词 + CRITICAL CONSTRAINT + absolutely NO） |
| 2 | 仍不可施工 → 降低布局复杂度：**改用该空间最保守的那套方案**（如厨房从 L 型退到一字型） |
| 3 | 仍不可施工 → **如实告知用户**："该空间尺寸下，此布局存在不确定性，需现场复核"，不硬凑 |
| 4 | 连续 2 张不可施工 → 停止重出，交付其余房间，该房间标注"需人工复核" |

**禁止**：为了凑出一张"看起来对"的图而反复重出；或明知不可施工却不告知用户。

---

## 七、与合规规则的关系

| 规则 | 归属 | 说明 |
|---|---|---|
| 不虚构精确尺寸 | **提示词/文案层** | 不得对客户宣称"客厅 4.2 米"这类具体数字 |
| 可施工性校验 | **本文件** | 用尺寸**推导布局合理性**，但不把尺寸数字写给客户 |

两者不冲突：**用尺寸决定怎么画，但不把尺寸当卖点说。**

---

## 八、交付时的表述

判定为 ⚠️ 或 ❌ 的房间，在交付报告里加一句：

```
厨房：图纸标注约 2250×1490，此尺寸下采用单排 L 型布局。
实际管井与烟道位置需现场复核，布局可行性以现场测量为准。
```

**不得出现**："绝对可行""保证能装""百分百没问题"。


---

## §7 选型与人体工学约束（v4.1 追加）

来源：行业常见踩坑经验汇总（111 条要点，已去标识处理）。取值规则：现行规范 > 行业通行做法 > 经验判断。

| 空间 | 约束项 | 数值 / 口径 |
|---|---|---|
| 卫生间 | 马桶移位距离 | ≤50cm，每 10cm 留 1cm 坡度；超 30cm 选直冲 |
| 卫生间 | 马桶两侧留空 | 马桶宽 36cm，两侧各留 20cm，旁边留电源 |
| 卫生间 | 干湿分离门槛 | 长度 ≥2.5m |
| 卫生间 | 浴室柜高度 | 身高 >1.6m 按 85–90cm；悬空柜离地 40cm |
| 卫生间 | 智能马桶预留 | 改水电时预留插座；内置水箱+增压泵、双水路、即热、停电可冲、IPX4 |
| 厨房 | 台面高低台 | 炒菜区 78–80cm、洗切区 88–90cm |
| 厨房 | 吊柜深度 | 40cm |
| 厨房 | 水槽单槽 | 深 ≥20cm、宽 ≥36cm，304 不锈钢 |
| 厨房 | 台下盆加固 | 底部 ≥10 个卡扣 |
| 厨房 | 灶具开孔 | 四角圆角，开孔前宽后窄 |
| 玄关 | 鞋柜深度 | 35–40cm；下方留 18cm；中部留 40cm 洞口 |
| 卧室 | 衣柜进深 | 62cm |
| 卧室 | 挂衣区分配 | 上衣区 80cm、裤子区 ≥95cm |
| 卧室 | 门洞 | 高 2.2m、宽 88cm、板厚 4.5cm |
| 全屋 | 柜体背板 | 靠墙 ≥9mm；背板后悬空处 18mm |
| 全屋 | 沙发选型 | 直排 + 单人椅，不画 L 型 / 肥大型 |
| 全屋 | 层高与吊顶 | 层高 ≤2.9m 不做无主灯吊顶；双眼皮吊顶深 30cm、错层 4cm |
| 全屋 | 灯色温 | 统一 3500K；同一空间灯具色温差 ≤500K |
| 全屋 | 柜体材质 | 多层实木板 / 欧松板 ENF 级，不画颗粒板 / 密度板 |
| 全屋 | 亮光/柔光分区 | 卫生间柔光防滑砖；客厅/厨房/阳台 800×800 亮光砖 |

### 判定不通过的兜底顺序（沿用 §5 四步）
强化句式 → 重生成 → 改最保守方案 → **如实告知用户该处存在不确定性，不硬凑**

### 规范优先声明
凡"规范要求"与"行业经验说法"冲突，一律取规范。经验可加严规范，不得低于规范。
⚠️ 具体条目：**厨房地面防水按 GB 50327 必须施工**，四周墙面防水层高度 ≥0.3m，不得以"无地漏""用不到"为由省略。
