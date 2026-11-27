---
name: byted-mediakit-image
version: 0.2.2
license: MIT
description: 面向现成图片的背景移除、质量优先瘦身、文字识别、画质评估、人脸打码和元信息查询。用户要保留主体并去掉背景、读取图片文字、检查画质、保护人脸隐私或尽量保持画质缩小体积时，按相应目标选择工具。只说“处理图片”或“压缩变小”且目标不清楚时先澄清。
permissions:
- shell
metadata:
  requires:
    bins:
    - mediakit-cli
  product: mediakit-cli-doubao/skill-experiment4s
  domain: image
  capability_count: 6
---

# image MediaKit Skill

## 使用规则

1. 先读取 `../byted-mediakit-shared/SKILL.md`，执行统一前置检查；该 Skill 缺失时停止并报告当前 Skill 包不完整。
2. 只从下表选择 `image` 域工具；相似能力按各工具“能力描述”和参数边界区分。
3. 执行前按需读取对应 reference；参数与结果说明来自同一份已审核文案，完整机器合同以当前 CLI `--schema` 为准。
4. 缺少必填参数、鉴权环境变量或真实输入资源时，向用户索取；通用可选字段只能透传用户明确提供的值，其他可选字段可由明确意图准确确定，但不得伪造。

第一准则（强制，仅适用于本套 MediaKit 工具）：本域仅支持下方工具列表中的 MediaKit 工具，shared 完整白名单与本域列表必须一致。先选定列表内工具，再读取对应 MediaKit 领域 Skill、完整 reference 和该工具的 help/schema。不得使用 mediakit-cli 的 --domain、--domains、全量帮助或领域帮助发现组外 MediaKit 工具。需要清单外 MediaKit 工具时，停止本套 MediaKit 处理流程并说明边界，不发起组外 MediaKit 调用或无关 MediaKit 探测。MediaKit 域间流程只能组合 shared 白名单内的工具，并读取对应领域 Skill 和完整说明；通过本套 MediaKit 执行的前置探测、修复和重试同样不得越过清单。

## 媒体产物直接交付（强制）

工具或 query-task 成功返回仍需交付的视频／图片后，必须立即使用本次 CLI 真实输出链接，按“一句简短完成说明＋对应 RichMediaCard”逐项交付；链接只放在卡片 refs 内，卡片独立成行。不得下载、转存、重新上传、更换资源入口、在卡片外给媒体链接或改用文件交付。多步骤直接复用前一步 CLI 真实链接，最终成片采用最后一步实际结果；取消、去重及展示失败按 shared Skill 的“媒体产物直接交付”细则处理。没有媒体产物的工具结果照常说明。

音频、字幕等其他媒体文件同样使用 CLI 原始结果引用，展示格式按宿主原有规范执行。CLI 的 HTML、画布及其预览截图按原有 CLI 协议执行。

## 图片输入元信息检查

图片域工具内置输入检查，会按目标工具限制在需要时内部探测元信息。正常图片处理直接调用目标工具，不需要主动调用 `probe-image-metadata` 或其他工具进行前置探测。用户明确要求查看图片尺寸、格式或其他元信息时，仍可使用 `probe-image-metadata`；根据其真实结果说明，不影响既有元信息查询能力。

## 澄清与跨域路由

本域仅支持工具列表内的 MediaKit 能力。需求超出清单时，停止本套 MediaKit 处理流程并说明该 Skill 不支持，不调用组外 MediaKit 工具或用列表内工具冒充缺失能力。目标不明确时先澄清。

本 Skill 处理现成图片的背景移除、质量优先瘦身、文字识别、画质评估、人脸打码和元信息查询。用户要去掉背景并保留主体使用 remove-image-background；读取图片文字使用 image-ocr；评估清晰度等画质指标使用 evaluate-image-quality；保护人脸隐私使用 face-blur-image；查询尺寸或格式等元信息使用 probe-image-metadata。尽量保持画质缩小体积时先读取图片体积治理指南，再选择 slim-image；只说“压缩”或“变小”且目标不明确时先澄清。精确文件大小上限或quality数值控制不属于本 Skill 当前工具提供的能力，不能构造不存在的参数。slim-image已有的输出格式参数仍按其reference填写。图片工具内部元信息检查规则保留。视频处理路由到 video，字幕压制路由到 editing，音频处理路由到 audio。从零图片创作不属于本套 MediaKit Skill 的能力，应说明本 Skill 不支持该目标。

## 工具列表

本域的 MediaKit 工具调用仅限下表，并须属于 shared 完整白名单。需要清单外 MediaKit 工具时，停止本套 MediaKit 处理流程并说明该 Skill 的边界，不调用组外 MediaKit 工具。MediaKit 域间流程只允许组合 shared 白名单内的工具，并读取对应领域 Skill 和完整说明。

| 工具 | 说明 | 支持模式 | 命令 | 参考 |
| --- | --- | --- | --- | --- |
| evaluate-image-quality | 用于图像画质评估，对输入图片进行主客观画质和美学评分，适用于质量监控、低质图筛查、内容审核、推荐排序和训练数据清洗。 | Cloud | `mediakit-cli image evaluate-image-quality` | [reference/evaluate-image-quality.md](reference/evaluate-image-quality.md) |
| face-blur-image | 自动检测图片中的所有人脸区域并进行马赛克处理，用于一键保护图片中的人脸隐私。支持社交平台内容审核、街景或监控画面脱敏、新闻媒体素材处理以及 AI 训练数据集脱敏等批量人脸隐私保护场景。 | Cloud | `mediakit-cli image face-blur-image` | [reference/face-blur-image.md](reference/face-blur-image.md) |
| image-ocr | 识别图片中的印刷体或手写体文字并返回文本块内容、位置坐标与置信度。标准版支持简体中文和英文印刷体通用识别；加强版支持印刷体、手写体及 100+ 语种，并支持通用识别与关键词匹配识别。 | Cloud | `mediakit-cli image image-ocr` | [reference/image-ocr.md](reference/image-ocr.md) |
| probe-image-metadata | 支持查询 metadata、avghue、alpha、blurhash 四种图像信息。 | Cloud | `mediakit-cli image probe-image-metadata` | [reference/probe-image-metadata.md](reference/probe-image-metadata.md) |
| remove-image-background | 自动识别并保留通用物体、人像或商品主体，移除背景后生成背景透明的图片；PNG、WebP 可输出透明背景，JPEG 的透明区域会填充为黑色；人像和商品场景还可生成主体描边或裁去多余透明区域。 | Cloud | `mediakit-cli image remove-image-background` | [reference/remove-image-background.md](reference/remove-image-background.md) |
| slim-image | 集智瘦身通过 AI 大幅缩小图片体积，修复毛刺、彩噪和块效应等问题，增强图像边缘与纹理细节，输出更轻量且更清晰的图片。质量优先的图片瘦身工具；用户强调尽量不掉画质、质量优先或高质量缩小体积，且未要求精确体积上限、质量值或格式转换时优先选择。 | Cloud | `mediakit-cli image slim-image` | [reference/slim-image.md](reference/slim-image.md) |
