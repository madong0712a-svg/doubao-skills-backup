# floorplan_layout_data.md — 户型结构化数据模板（平面俯视图输入）

> 用途：把户型图识别结果落成结构化 JSON，供 `scripts/draw_floorplan.py` 精确绘图。
> **AI 负责设计判断（填这份数据），程序负责精确绘图和计算（跑脚本）。**
> 单位约定（4.3 起）：**JSON 坐标值一律 mm 毫米整数**（1 单位 = 1 mm）；`meta.unit` 只决定
> **图面显示单位**（`mm` 显示整数毫米 / `m` 显示米），显示层换算，自检阈值恒为 mm。
> 标注文字（room/opening/furniture/wall 的 `text`）必须与 `meta.unit` 同单位 —— 第 7 项
> 自检「单位与标注一致性」会逐条比对，不符即 WARN。
> **v4.4 起**：图面版式对齐市面常规户型图（深灰墙体 / 浅灰剪影家具 / 通俗符号 / 中文+拼音房名 /
> 家具尺寸压字）——rooms 新增可选 `pinyin` 字段；`furniture` 标注的 `text` 与 `offset`
> 均降级为可选（省略时脚本按图元实际宽深自动生成「名称 宽×深」并压字），详见 §四与 §6.4。

---

## 一、meta 块（图纸信息）

| 字段 | 必填 | 说明 |
|---|---|---|
| `project` | ✓ | 项目名称，进图题栏 |
| `unit` | ✓ | 图面显示单位：`"mm"`（默认，整数毫米）/ `"m"`（米）。**坐标值恒为 mm 整数，此字段只改显示**；图题栏自动标明 |
| `total_area` | — | 建筑面积（㎡），**仅用户提供时填写**；缺省由程序按 rooms 多边形（墙中线）累加，图题栏标"房间面积合计（墙中线）" |
| `total_area_source` | — | 面积来源说明，进交付 |
| `style` | — | 装修风格，进图题栏 |
| `occupancy` | — | 居住需求（如"三口之家"），进图题栏 |
| `north_angle` | — | 指北针旋转角（度，默认 0） |
| `pending_confirm` | — | **待核实项数组**，非空时图题栏显示"待核实 N 项" |

---

## 二、walls 块（墙体，中心线法）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✓ | 墙编号，门窗通过 `wall` 字段挂接 |
| `role` | ✓ | `exterior`（外墙）/ `loadbearing`（承重墙，斜纹标识）/ `interior`（内隔墙） |
| `p1` `p2` | ✓ | 墙中心线两端点 `[x, y]` |
| `thickness` | ✓ | 墙厚（mm），绘制与自检按半墙厚计算 |

**规则**：墙画中心线，程序自动按 thickness 生成双线墙身并在门窗处断口；承重墙自动加斜纹。**没有可靠依据不得把墙填成 loadbearing**，未确认按 interior + pending_confirm。

---

## 三、openings 块（门窗洞口）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✓ | 编号，尺寸标注通过 `ref` 引用 |
| `wall` | ✓ | 挂接的墙 id |
| `type` | ✓ | `door`（平开门）/ `window`（窗）/ `sliding_door`（推拉门）/ `bay_window`（飘窗） |
| `center` | ✓ | 洞口中心点 `[x, y]`（落在墙中心线上） |
| `width` | ✓ | 洞口宽度（mm） |
| `height` | — | 洞口高度（平面图不显示，记录用） |
| `thickness` | — | 窗/推拉门图例线距（默认 100） |
| `hinge_side` | door 必填 | `p1` / `p2`：铰链在断口靠近墙起点/终点的一端 |
| `open_side` | door 必填 | `1` / `-1`：门扇朝墙法向正侧/负侧开启（决定扫掠区与门弧） |
| `sill` | window 可选 | 窗台高（记录用） |
| `depth` | bay_window 可选 | 飘窗外凸深度（默认 600） |
| `out_side` | bay_window 可选 | 外凸方向 ±1 |

> **open_side 判定法**：墙 p1→p2 方向为 u，法向 n=(-uy, ux)。站在门外看，门朝 n 正方向开填 1，反方向填 -1。

---

## 四、rooms 块（房间净边界）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✓ | 房间编号 |
| `name` | ✓ | 房间名（中文，上图） |
| `polygon` | ✓ | 净边界多边形顶点数组 `[[x,y],...]`（顺时针/逆时针均可） |
| `name_pos` | — | 可选：房间名落点 `[x,y]`（缺省=多边形顶点均值） |
| `pinyin` | — | **v4.5 起不建议使用**：房间名一律纯中文，全图不得出现拼音或中英混排。仅当 `meta.show_pinyin=true` 时才渲染拼音小字（默认关闭） |
| `area_text` | — | 可选：面积标注文字（缺省"中线面积 X.X㎡"；传空串则不显示面积行） |
| `area_pos` | — | 可选：面积标注落点 `[x,y]`（缺省=房间名下方 260） |
| `area_fs` | — | 可选：面积标注字号（缺省 6.5） |

程序自动计算并标注"中线面积 X.X㎡"（rooms 多边形为墙中线模型，**不是净面积**；净面积/建筑面积以实测与产权口径为准，不得用中线面积冒充）。polygon 用**墙中线**即可（房间共墙），家具贴墙判定按半墙厚自动处理。

> **窄房间标注自适应（v4.3.2）**：走廊、阳台等窄房间的面积文字可能溢出压盖墙体——用 `area_text` 缩短（如仅"2.2㎡"）或传空串省略，必要时配合 `area_pos` / `area_fs` 调整；房间名不得被家具图块、其他标注文字或线条压盖，冲突时优先挪标注而非改房间名（v4.3.3 起由第 8 项自检「标注落点归属」强制兜底：名称落点压家具图块或越出房间即 FAIL）。

---

## 五、furniture 块（家具，真实比例）

| 字段 | 必填 | 说明 |
|---|---|---|
| `id` | ✓ | 家具编号，尺寸标注通过 `ref` 引用 |
| `room` | ✓ | 所属房间 id |
| `type` | ✓ | 图例类型（见 §5.1 类型表） |
| `name` | — | 显示名（缺省用类型中文名） |
| `rect` | 二选一 | `[x, y, w, h]` 轴对齐矩形 |
| `rot` | — | 旋转角（度，绕 rect 中心，如床头朝向用 180） |
| `polygon` | 二选一 | 异形家具（L 形台面等）顶点数组 |
| `attach_to` | — | 挂接父件 id（如灶台/水槽挂台面）：同组不判通道净宽 |

### 5.1 家具类型表（type 取值）

`bed` 床 / `sofa` 沙发 / `coffee_table` 茶几 / `tv_stand` 电视柜 / `dining_table` 餐桌 / `chair` 椅 / `wardrobe` 衣柜 / `cabinet` 柜 / `shoe_cabinet` 鞋柜 / `kitchen_counter` 橱柜台面 / `fridge` 冰箱 / `sink` 水槽 / `toilet` 马桶 / `bathroom_sink` 洗手台 / `shower` 淋浴间 / `bathtub` 浴缸 / `washing_machine` 洗衣机 / `desk` 书桌 / `bookshelf` 书柜 / `nightstand` 床头柜 / `plant` 绿植 / `rug` 地毯

**摆放规则**：家具外缘贴墙时 rect 坐标取到"墙中心线 ∓ 半墙厚"（如 200 厚墙中心线 y=1500，家具顶到 y=1400）；程序按 `dist - 半墙厚` 判净距，贴墙=0 属正常，嵌入 >0.5mm 判 FAIL。

---

## 六、dimensions 块（四层标注 + 墙体厚度，数据驱动）

### 6.1 chain —— 第一层 总尺寸/分段链

```json
{"kind": "chain", "axis": "x", "at": 0, "side": "below", "offset": 1200,
 "from": 0, "to": 12000, "segments": [[0, 6900], [6900, 12000]], "show_total": true}
```

| 字段 | 说明 |
|---|---|
| `axis` | `x` 水平尺寸链（沿 y=at 布置）/ `y` 竖直尺寸链（沿 x=at 布置） |
| `at` | 基准线坐标（通常是外墙中心线位置） |
| `side` | `below`/`above`（axis=x）或 `left`/`right`（axis=y） |
| `offset` | 尺寸线离构件距离（mm） |
| `from`/`to` | 总尺寸起止 |
| `segments` | 分段数组 `[[a,b],[b,c],...]`，分段之和必须等于总尺寸 |
| `show_total` | 是否画总计（默认 true） |

### 6.2 room —— 第二层 房间开间×进深

```json
{"kind": "room", "room": "R02", "text": "6900×4800", "at": [3450, 3200]}
```
`at` 缺省取房间形心下方 500。位置紧张必须显式给 `at`。

### 6.3 opening —— 第三层 门窗洞口

```json
{"kind": "opening", "ref": "D02", "text": "门洞 900（距西墙 1300）", "offset": [-1500, 500]}
```
洞口定位距离写进 `text`（AI 核算），程序只画引线+文字。

### 6.4 furniture —— 第四层 家具尺寸（v4.4 起压字，禁引线外挂）

```json
{"kind": "furniture", "ref": "F01"}
{"kind": "furniture", "ref": "F15", "text": "双人床 1800×2000"}
```

| 字段 | 说明 |
|---|---|
| `ref` | 家具 id（必填） |
| `head` | **bed / toilet 必填**（4.6.0） | 朝向锚点：床填**床头所靠墙**（`N`/`S`/`E`/`W`）；马桶填**水箱所贴墙**。**不填则效果图必然画反**——这是 2026-10-19 事故的直接修复项 |
| `against` | 贴墙类必填（4.6.0） | 贴哪面墙（`N`/`S`/`E`/`W`，可数组）。`wardrobe`/`sofa`/`tv_cabinet`/`kitchen_counter`/`basin`/`shower`/`fridge`/`washing_machine` 建议显式给；**L 形房间的 bbox 判定会失准，必须显式给** |
| `text` | 可选：标注文字。**省略时由脚本按图元实际宽深自动生成「名称 宽×深」**（如"双人床 1800×2000"）；显式 `text` 中的「宽×深」必须与图元实际一致（第 7 项自检 7c 比对） |
| `offset` | 可选（v4.4 降级为微调字段）：文字相对家具中心的位移 `[dx,dy]`；默认留空，由脚本压字自适应排版 |

**压字自适应顺序**（渲染端与自检端共用同一落点公式 `furniture_label_layout`）：显式 `offset` → 一行压字（图元内）→ 两行压字（名称行/尺寸行）→ 窄高图元旋转 90°（fs≥4.5pt）→ 紧贴图元下方（避让其他家具与房间名/面积文字（第 9 项自检「标注文字防互撞」几何兜底）、不越出所属房间，步进 60mm×6 次）→ 旋转 4.0pt 兜底 → 默认 offset 兜底。

**v4.6.0 出图前置**：落完 JSON 先跑
`python scripts/make_room_prompts.py 本文件.json --check`
——0 告警才允许出平面图；平面图经用户确认后才允许出效果图。
提示词一律用 `--prompt RX` 生成后逐字复制，**禁止人工转写**。

**硬规则（v4.4）**：家具/家电尺寸数值必须直接压在图元上或其紧邻位置，**不得用引线拉到图外单独标注**；落点不得跨出该家具所属房间（第 8 项自检「标注落点归属」强制，越界即 FAIL）。有尺寸压字的家具块内自动名让位（不双出名）。

### 6.5 corridor —— 通道净宽/功能距离

```json
{"kind": "corridor", "p1": [7550, 8000], "p2": [7550, 9650], "text": "1650", "suffix": "（通道净宽）", "offset": [700, 0]}
```
测量线段即通道净宽；`suffix` 可改（如"（视听距离）""（操作台前净宽）"）。

### 6.6 wall —— 墙体厚度标注（4.3 新增）

```json
{"kind": "wall", "ref": "W01", "at": 0.5, "side": -1, "offset": 500, "text": "墙厚200"}
```

| 字段 | 说明 |
|---|---|
| `ref` | 墙 id |
| `at` | 标注点沿墙位置 0~1（默认 0.5 墙中点） |
| `side` | 引线朝墙法向哪一侧：`1` / `-1`（法向 n=(-uy, ux)，同 open_side 判定） |
| `offset` | 文字离墙中心线距离（mm，默认 500） |
| `text` | 缺省自动生成 `墙厚{thickness}`（按 unit 换算）；自定义文字中的数字须与 `walls[].thickness` 一致 |

**标注范围**：所有 `role=loadbearing` 墙 + 各外墙至少一条；内隔墙同厚可合并说明（如在图题栏或说明行写"内隔墙均为 100"）。墙体**位置**由双线墙身 + 门窗断口体现，厚度由本类型标注。

---

## 七、填写顺序（防错）

1. `meta`（**先定 unit**，全文标注文字同单位）→ 2. `walls`（先外墙后内墙，统一方向）→ 3. `openings`（挂墙）→ 4. `rooms`（净边界，**不要**补 `pinyin`（v4.5 房间名纯中文））→ 5. `furniture`（先大后小，贴墙件算半墙厚）→ 6. `dimensions`（先 chain 后局部；**loadbearing/外墙补 wall 厚度标注**；家具层只写 `ref` 即自动压字，压不下或需微调才写 `text`/`offset`；最后跑一遍脚本看自检）
2. 每步跑一次 `draw_floorplan.py`，FAIL 清零再进下一步；WARN 逐条写进交付检查表
3. 产出第二套方案时**复制 JSON 只改 furniture 与 furniture 层 dimensions**，walls/openings/rooms 原样复制

---

## 八、完整最小示例（骨架）

```json
{
  "meta": {"project": "示例户型", "unit": "mm", "style": "现代简约",
           "occupancy": "三口之家", "north_angle": 0, "pending_confirm": []},
  "walls": [
    {"id": "W01", "role": "exterior", "p1": [0, 0], "p2": [12000, 0], "thickness": 200},
    {"id": "W02", "role": "loadbearing", "p1": [6900, 0], "p2": [6900, 4200], "thickness": 200}
  ],
  "openings": [
    {"id": "D01", "type": "door", "wall": "W02", "center": [6900, 2800],
     "width": 900, "hinge_side": "p1", "open_side": 1},
    {"id": "WIN01", "type": "window", "wall": "W01", "center": [9450, 0],
     "width": 1800, "thickness": 100}
  ],
  "rooms": [
    {"id": "R01", "name": "客厅", "polygon": [[0, 0], [6900, 0], [6900, 4200], [0, 4200]]}
  ],
  "furniture": [
    {"id": "F01", "room": "R01", "type": "sofa", "name": "三人沙发", "rect": [150, 1500, 850, 2100]},
    {"id": "F02", "room": "R01", "type": "tv_stand", "name": "电视柜", "rect": [6400, 1400, 400, 1400]}
  ],
  "dimensions": [
    {"kind": "chain", "axis": "x", "at": 0, "side": "below", "offset": 1200,
     "from": 0, "to": 6900, "segments": [[0, 6900]]},
    {"kind": "room", "room": "R01", "text": "6900×4200", "at": [3450, 2100]},
    {"kind": "opening", "ref": "D01", "text": "门洞 900", "offset": [-1500, 500]},
    {"kind": "furniture", "ref": "F01"},
    {"kind": "furniture", "ref": "F02"},
    {"kind": "wall", "ref": "W01", "at": 0.5, "side": -1, "offset": 500, "text": "墙厚200"},
    {"kind": "wall", "ref": "W02", "at": 0.5, "side": 1, "offset": 500}
  ]
}
```

> 已验证可跑的完整样例（126㎡ 两室两厅一卫、11 项自检全 PASS）随 Skill 冒烟测试留存于工作区 `.workbuddy/scratch/floorplan_test/`。
