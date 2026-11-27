# 平台适配：负面提示词与生成参数（v4.6.1）

> **核心认知：提示词正文与平台无关，但负面提示词和参数必须分平台。**
> 同一句 `Photorealistic interior render of a minimalist second bedroom...`
> 丢给 Midjourney、Stable Diffusion、FLUX，效果完全不同 —— 不是因为正文写得不好，
> 而是因为三个模型对「排除项」和「参数」的处理机制根本不同。

---

## 一、为什么要分平台（本次竞品调研的直接结论）

调研 SkillHub 同赛道技能「效果图提示词神器」时发现：它用 539 行
（`negative_prompts.py` 里的 `PLATFORM_NEGATIVE` dict）专门做**分平台负面词**，
而我方此前后只有一刀切的一串。这是它做对、我方没做的一处。

**不分平台的三个具体后果**：

| 平台 | 负面词机制 | 一刀切的后果 |
|---|---|---|
| Midjourney | **没有 negative prompt 概念**，只能靠 `--no` 参数 | 写一大段负面词它看不见，纯浪费 token；该排除的一项没排除 |
| Stable Diffusion | 负面词**越长越压得住**，短串几乎无效 | 短串压不住 duplicate/clipped furniture，出图最容易出"多一个床头柜" |
| FLUX.1 | 负面词有效但 `schnell` 档只 4 步，长串会拖垮质量 | 长串让 schnell 出图变糊 |
| DALL·E 3 | **会自行扩写提示词**，可能直接忽略排除项 | 排除项形同虚设，且它爱"美化"，最不适合要求严格一致的场景 |

---

## 二、分档口径（三档）

我方负面词统一分三档，由 `make_room_prompts.py` 的 `PLATFORMS` 常量维护：

| 档 | 用于 | 长度 | 内容 |
|---|---|---|---|
| **none** | Midjourney | — | 不用负面词，改用 `--no` 列表 |
| **base** | DALL·E 3 | 短 | 画质 + 解剖畸变 |
| **mid** | FLUX / Ideogram / 通用(auto) | 中 | base + 杂乱/昏暗/低分辨率 |
| **long** | Stable Diffusion | 长 | mid + 水印文字 + **重复/镜像/多余/缺失家具** + 墙体倾斜 + 透视错误 + 去 AI 味 |

**关键设计：long 档专门加了家具一致性类负面词**
（`duplicate, cloned furniture, mirrored furniture, extra furniture,
missing furniture, floating furniture, furniture clipping through walls`）。
这是针对本次「次卧多画一个床头柜」事故的定向补强 —— SD 场景下这类错误
出现频率最高，必须在负面词里点名。

---

## 三、各平台参数速查

### Midjourney v6
```
后缀：--ar 16:9 --v 6 --style raw --q 2
排除：--no <列表>（见 scripts/make_room_prompts.py 的 PLATFORMS['mj']['no_list']）
```
- `--style raw` **必加**：减少 MJ 自作主张的"美化"，让画面更贴字面描述
- `--q 2` 高品质；快速试稿可用 `--q 0.5`
- 宽高比按用途：室内全景 `16:9`、建筑外观 `3:2`、细部特写 `1:1`

### Stable Diffusion（WebUI / ComfyUI）
```
采样器：DPM++ 2M Karras
步数：30
CFG Scale：7
分辨率：1024×768（横向房间）
hires fix：建议开，0.5x upscale
```
- 负面词用 **long 档**，不要手删
- 想要跨房间风格一致：**固定 seed**，只改提示词（见 §五）

### FLUX.1
```
schnell：steps 4，免 guidance   ← 免费档首选（硅基流动免费额度）
dev：    steps 28，guidance 3.5
pro：    steps 25，guidance 3
```
- `schnell` 只用 **mid 档**负面词，长串会掉质量
- schnell 出图快但细节弱，适合试稿；定稿用 dev

### Ideogram
```
风格：Design / General
魔法提示：可开（画面更精致，但更偏离字面 —— 要求严格一致时关掉）
```

### DALL·E 3
```
尺寸：1792×1024（横向）
```
- ⚠️ **它会自行扩写提示词**，排除项可能被忽略
- ⚠️ 不适合"要求严格一致"的场景；本 skill 的方位锁/数量锁在 DALL·E 上
  有效性最低，**优先选 MJ / SD / FLUX**

---

## 四、用法

```bash
# 出图前预审（默认通用档）
python scripts/make_room_prompts.py plan.json --dry-run

# 指定目标平台
python scripts/make_room_prompts.py plan.json --dry-run --platform sd
python scripts/make_room_prompts.py plan.json --dry-run --platform mj

# 单间提示词 + 平台后缀
python scripts/make_room_prompts.py plan.json --prompt R06 --platform mj
```

`--platform` 可选值：`auto` / `mj` / `sd` / `flux` / `ideogram` / `dalle`

---

## 五、跨房间风格一致：靠 seed，不靠运气

同一户型的客厅、主卧、次卧如果各画各的，色调和光感会散。竞品「酷家乐智能设计」
靠**同一个 designId** 从机制上保证一致；文生图没有 designId，替代方案是：

1. **同一户型所有房间固定同一个 seed**
2. 风格段（STYLE: ...）在所有房间提示词中保持**逐字一致**
3. 只改布局段（哪面墙、哪件家具）

本 skill 的提示词由 `render_prompt()` 生成，STYLE 段已是固定文本，
所以只要在调用侧固定 seed 即可。**待 P1-1 `render.py` 出图层落地后，
`--seed` 会成为正式参数。**

---

## 六、维护约定

- 新增平台：在 `scripts/make_room_prompts.py` 的 `PLATFORMS` dict 加一项即可，
  `render_negative_block()` 会自动输出对应文档段
- 调整负面词：改 `NEG_BASE` / `NEG_MID` / `NEG_LONG` 三个常量，不要在各处硬写
- **案例专属排除项不走这里**：`no desk`、`no bathtub` 这类"这个房间没有的东西"
  属于布局事实，写在提示词正文的排除段里，与平台无关
