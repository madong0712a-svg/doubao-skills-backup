---
name: byted-mediakit-video
version: 0.2.2
license: MIT
description: 面向音视频素材中的语音转字幕，以及视频画面文字识别、已有字幕精细擦除、内容理解、画质增强与检测、视频转码和极智超清转码、语义分段、人脸打码、人像或绿幕抠像、暗水印添加和提取、视频元信息查询。根据用户要识别、增强、检测、转换、分段还是移除背景等具体目标选择工具；为现成视频添加字幕应路由到
  editing。目标不明确时先澄清。
permissions:
- shell
metadata:
  requires:
    bins:
    - mediakit-cli
  product: mediakit-cli-doubao/skill-experiment4s
  domain: video
  capability_count: 15
---

# video MediaKit Skill

## 使用规则

1. 先读取 `../byted-mediakit-shared/SKILL.md`，执行统一前置检查；该 Skill 缺失时停止并报告当前 Skill 包不完整。
2. 只从下表选择 `video` 域工具；相似能力按各工具“能力描述”和参数边界区分。
3. 执行前按需读取对应 reference；参数与结果说明来自同一份已审核文案，完整机器合同以当前 CLI `--schema` 为准。
4. 缺少必填参数、鉴权环境变量或真实输入资源时，向用户索取；通用可选字段只能透传用户明确提供的值，其他可选字段可由明确意图准确确定，但不得伪造。

第一准则（强制，仅适用于本套 MediaKit 工具）：本域仅支持下方工具列表中的 MediaKit 工具，shared 完整白名单与本域列表必须一致。先选定列表内工具，再读取对应 MediaKit 领域 Skill、完整 reference 和该工具的 help/schema。不得使用 mediakit-cli 的 --domain、--domains、全量帮助或领域帮助发现组外 MediaKit 工具。需要清单外 MediaKit 工具时，停止本套 MediaKit 处理流程并说明边界，不发起组外 MediaKit 调用或无关 MediaKit 探测。MediaKit 域间流程只能组合 shared 白名单内的工具，并读取对应领域 Skill 和完整说明；通过本套 MediaKit 执行的前置探测、修复和重试同样不得越过清单。

## 音视频元数据前置探测

当目标工具的限制或参数选择依赖视频时长、分辨率、文件大小、封装、视频编码、码率或帧率，而用户没有提供可信元信息时，先使用 `probe-video-metadata`。如果目标操作还依赖独立音频输入或音频流的采样率、声道等属性，按需使用 audio 域的 `probe-audio-metadata`。将探测结果与目标工具 reference 的限制逐项比较；确认超限或不兼容时停止并要求更换或调整输入，不得盲目调用。探测结果不能替代目标工具的专属约束，也不保证后端一定处理成功。

## 媒体产物直接交付（强制）

工具或 query-task 成功返回仍需交付的视频／图片后，必须立即使用本次 CLI 真实输出链接，按“一句简短完成说明＋对应 RichMediaCard”逐项交付；链接只放在卡片 refs 内，卡片独立成行。不得下载、转存、重新上传、更换资源入口、在卡片外给媒体链接或改用文件交付。多步骤直接复用前一步 CLI 真实链接，最终成片采用最后一步实际结果；取消、去重及展示失败按 shared Skill 的“媒体产物直接交付”细则处理。没有媒体产物的工具结果照常说明。

音频、字幕等其他媒体文件同样使用 CLI 原始结果引用，展示格式按宿主原有规范执行。CLI 的 HTML、画布及其预览截图按原有 CLI 协议执行。

## 澄清与跨域路由

本域仅支持工具列表内的 MediaKit 能力。需求超出清单时，停止本套 MediaKit 处理流程并说明该 Skill 不支持，不调用组外 MediaKit 工具或用列表内工具冒充缺失能力。目标不明确时先澄清。

只提供视频而没有说明目标时先澄清。音轨语音识别、画面文字识别、字幕精细擦除、内容理解和画质增强沿用组1的选择规则。用户要求评估画质时使用 assess-video-quality，要求改善画质时使用 enhance-video，不把检测当作增强。用户明确要求转换编码、分辨率、码率或封装时使用 transcode-video；明确要求极智超清或智能降低码率并兼顾主观画质时使用 martencode-video，不编造统一优先级。按完整语义切分视频使用 semantic-segment，不引导其他分段或剪辑工具。视频人脸隐私保护使用 face-blur-video；一般人物主体背景移除使用 matte-portrait-video，绿幕或纯色背景抠像使用 matte-greenscreen-video；要求隐藏数字信息或提取已有暗水印时，分别选择 add-video-invisible-watermark 或 extract-video-invisible-watermark，不能将它们用于擦除水印。字幕压制路由到 editing；单张图片处理路由到 image；音频转码、人声分离、人声片段定位或音频元信息查询路由到 audio。

## 字幕擦除选型

擦除画面中已有字幕时选择 erase-video-subtitle-pro。是否先做 OCR 定位、支持的输入范围及所需确认，沿用其 reference 中“先识别字幕位置，再精细化擦除”的现有规则；不能未经确认就提交 OCR，也不能把 OCR 结果直接当作擦除完成。用户明确要求直接擦除或拒绝定位流程时，按原规则跳过定位阶段。

## 工具列表

本域的 MediaKit 工具调用仅限下表，并须属于 shared 完整白名单。需要清单外 MediaKit 工具时，停止本套 MediaKit 处理流程并说明该 Skill 的边界，不调用组外 MediaKit 工具。MediaKit 域间流程只允许组合 shared 白名单内的工具，并读取对应领域 Skill 和完整说明。

| 工具                                | 说明                                                                                                                                                                                                                                        | 支持模式  | 命令                                                     | 参考                                                                                               |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------ |
| add-video-invisible-watermark     | 用于视频暗水印添加。在不影响视频画面视觉质量与完整性的前提下，将一串数字信息隐藏式地嵌入视频文件中。适用于视频版权保护、内容泄露溯源、文件真实性校验等场景。                                                                                                                                                            | Cloud | `mediakit-cli video add-video-invisible-watermark`     | [reference/add-video-invisible-watermark.md](reference/add-video-invisible-watermark.md)         |
| asr-subtitles                     | 从视频或音频的语音中识别并提取带时间戳的字幕文本；适用于提取视频字幕、语音转字幕、听写对白等诉求。识别对象是音轨中的语音内容，不是画面上已烧录的硬字幕。                                                                                                                                                              | Cloud | `mediakit-cli video asr-subtitles`                     | [reference/asr-subtitles.md](reference/asr-subtitles.md)                                         |
| assess-video-quality              | 用于视频画质检测。                                                                                                                                                                                                                                 | Cloud | `mediakit-cli video assess-video-quality`              | [reference/assess-video-quality.md](reference/assess-video-quality.md)                           |
| enhance-video                     | 用于视频画质增强。利用 AI 算法对输入视频进行分析，并智能执行包括但不限于视频去噪、色彩增强、清晰度提升、瑕疵修复和超分辨率的一系列优化操作。提供 standard 和 professional 两种版本：standard 兼顾处理速度与视频画质，内置高频使用的 10 余种增强算法，适用于视频分发场景的画质增强；professional 提供极致画质增强，内置 30 余种深度 AI 增强算法，适用于影视级视频制作。不同版本会影响增强算法的强度、适用场景与计费。 | Cloud | `mediakit-cli video enhance-video`                     | [reference/enhance-video.md](reference/enhance-video.md)                                         |
| erase-video-subtitle-pro          | 用于字幕擦除（精细化版），对视频字幕进行高质量无痕擦除，并最大程度还原视频画面。                                                                                                                                                                                                  | Cloud | `mediakit-cli video erase-video-subtitle-pro`          | [reference/erase-video-subtitle-pro.md](reference/erase-video-subtitle-pro.md)                   |
| extract-video-invisible-watermark | 从已嵌入暗水印的视频中解析并还原隐藏的数字信息；如果同一视频被多次嵌入暗水印，也能够提取出所有水印信息。                                                                                                                                                                                      | Cloud | `mediakit-cli video extract-video-invisible-watermark` | [reference/extract-video-invisible-watermark.md](reference/extract-video-invisible-watermark.md) |
| face-blur-video                   | 视频人脸打码可自动精准识别视频画面中的人脸区域，并对所有人脸进行模糊或马赛克处理，适用于需要保护人物五官隐私的场景。                                                                                                                                                                                | Cloud | `mediakit-cli video face-blur-video`                   | [reference/face-blur-video.md](reference/face-blur-video.md)                                     |
| martencode-video                  | 极智超清在转码时智能分析视频的场景、动作、内容和纹理，选择最优编码参数，以相对较低码率输出主观画质更优的视频，降低带宽成本并改善用户视觉体验。                                                                                                                                                                   | Cloud | `mediakit-cli video martencode-video`                  | [reference/martencode-video.md](reference/martencode-video.md)                                   |
| matte-greenscreen-video           | 可对绿幕或纯色背景的视频进行抠图，自动识别并保留主体，最终生成背景透明或纯色背景的视频。                                                                                                                                                                                              | Cloud | `mediakit-cli video matte-greenscreen-video`           | [reference/matte-greenscreen-video.md](reference/matte-greenscreen-video.md)                     |
| matte-portrait-video              | 自动识别视频中的人物主体，移除原始背景，并生成背景透明或纯色背景的视频文件，适用于背景替换等后期处理场景。                                                                                                                                                                                     | Cloud | `mediakit-cli video matte-portrait-video`              | [reference/matte-portrait-video.md](reference/matte-portrait-video.md)                           |
| probe-video-metadata              | 探测输入的视频 URL，输出标准化的媒资元信息。                                                                                                                                                                                                                  | Cloud | `mediakit-cli video probe-video-metadata`              | [reference/probe-video-metadata.md](reference/probe-video-metadata.md)                           |
| semantic-segment                  | 综合分析视频的画面、语音和叙事结构，通过镜头切换、语音停顿检测等策略，在保证语义完整、避免将单句从中间切断的前提下，将长视频智能地切分为多个独立的素材片段。                                                                                                                                                            | Cloud | `mediakit-cli video semantic-segment`                  | [reference/semantic-segment.md](reference/semantic-segment.md)                                   |
| transcode-video                   | 视频转码将视频码流转换为另一视频码流，可涉及编码格式、分辨率、码率、I 帧间隔和封装格式转换，用于适应不同业务场景、播放终端和网络环境。                                                                                                                                                                      | Cloud | `mediakit-cli video transcode-video`                   | [reference/transcode-video.md](reference/transcode-video.md)                                     |
| video-ocr                         | 用于视频字幕识别（OCR），识别输入视频画面中的字幕信息，输出带时间戳的结构化文本数据。                                                                                                                                                                                              | Cloud | `mediakit-cli video video-ocr`                         | [reference/video-ocr.md](reference/video-ocr.md)                                                 |
| video-understand-router           | 基于火山方舟视觉大模型，接收单个视频及自然语言指令，并结合视频时长、分析档位、场景和用户偏好自动选择抽帧、音频分析与模型链路，输出结构化理解结果；适用于内容审核、视频检索、标签生成、视频摘要和创作剪辑。                                                                                                                              | Cloud | `mediakit-cli video video-understand-router`           | [reference/video-understand-router.md](reference/video-understand-router.md)                     |
