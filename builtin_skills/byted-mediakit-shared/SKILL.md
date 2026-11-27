---
name: byted-mediakit-shared
version: 0.2.2
license: MIT
description: MediaKit 提供现成素材的字幕识别、擦除与压制，视频理解、画质增强与检测、转码、语义分段、人脸打码、抠像及暗水印添加和提取，图片背景移除、瘦身、文字识别、画质评估与人脸打码，音频转码、人声分离和人声片段定位，以及音视频和图片元信息查询。用户明确提出这些处理目标时，先加载本
  Skill，再按对象和目标选择 audio、editing、image 或 video。仅提供素材或媒体类型、未说明处理目标时先澄清。
permissions:
- shell
metadata:
  requires:
    bins:
    - mediakit-cli
  product: mediakit-cli-doubao/skill-experiment4s
  domain: shared
  capability_count: 0
---

# MediaKit 媒体处理入口

## 第一准则：MediaKit 工具范围封闭（最高优先级，强制遵守）

1. 本准则仅约束本套 MediaKit Skill 所管理的 MediaKit 工具及其说明。下方「允许工具列表」是本套 MediaKit 的完整白名单。调用这些工具前须读取所属 MediaKit 领域 Skill 和完整 reference；该准则优先于本套 MediaKit 的路由、前置检查、错误恢复和示例。
2. 未列出的 MediaKit 工具不得加载说明、读取参数或执行调用。名称相似、mediakit-cli 能执行、模型已有知识、历史上下文、其他实验组或用户点名，均不能扩展本套 MediaKit 白名单。清单、领域说明或 reference 缺失或冲突时停止本套 MediaKit 流程，不猜测或补回工具。
3. 禁止用 mediakit-cli 的 --domain、--domains、全量 --help 或领域级 --help 发现组外 MediaKit 工具。先从白名单选定工具，再读取所属 MediaKit 领域 Skill 和完整 reference；仅可读取该已选 MediaKit 工具的 --help、--schema 核对参数，不得从其他入口补回清单外的 MediaKit 工具。
4. MediaKit 域间流程仅可组合本表列出的工具，并读取对应领域 Skill 和完整说明。通过本套 MediaKit 执行的前置探测、修复和重试同样须在白名单内。
5. 每次 MediaKit 执行前核对该 MediaKit 处理流程需要的工具。需求超出清单时，停止本套 MediaKit 处理流程并说明该 Skill 不支持；不提交组外 MediaKit 调用，不先做无关 MediaKit 探测，不用已允许的 MediaKit 工具冒充缺失能力。目标不明确时先澄清。
6. 下方 mediakit-cli shared query-task 仅查询本套白名单工具返回的真实 task_id，不计业务工具数。mediakit-cli --version 可用于版本检查。CLI 内部输入适配不增加公开 MediaKit 业务能力。

## 允许工具列表（完整封闭清单）

本套 MediaKit Skill 的工具调用范围以以下 26 项为完整白名单。清单外 MediaKit 工具不得加载说明、读取参数或执行调用；遇到超出范围的需求时，停止本套 MediaKit 处理流程并说明该 Skill 的边界。MediaKit 域间流程只能组合本表列出的工具，并读取对应领域 Skill 和完整说明。

| 领域 | 允许的业务工具 | 完整说明 |
| --- | --- | --- |
| video | `mediakit-cli video erase-video-subtitle-pro` | [erase-video-subtitle-pro](../byted-mediakit-video/reference/erase-video-subtitle-pro.md) |
| video | `mediakit-cli video asr-subtitles` | [asr-subtitles](../byted-mediakit-video/reference/asr-subtitles.md) |
| video | `mediakit-cli video video-ocr` | [video-ocr](../byted-mediakit-video/reference/video-ocr.md) |
| video | `mediakit-cli video video-understand-router` | [video-understand-router](../byted-mediakit-video/reference/video-understand-router.md) |
| video | `mediakit-cli video enhance-video` | [enhance-video](../byted-mediakit-video/reference/enhance-video.md) |
| video | `mediakit-cli video probe-video-metadata` | [probe-video-metadata](../byted-mediakit-video/reference/probe-video-metadata.md) |
| video | `mediakit-cli video face-blur-video` | [face-blur-video](../byted-mediakit-video/reference/face-blur-video.md) |
| video | `mediakit-cli video transcode-video` | [transcode-video](../byted-mediakit-video/reference/transcode-video.md) |
| video | `mediakit-cli video add-video-invisible-watermark` | [add-video-invisible-watermark](../byted-mediakit-video/reference/add-video-invisible-watermark.md) |
| video | `mediakit-cli video assess-video-quality` | [assess-video-quality](../byted-mediakit-video/reference/assess-video-quality.md) |
| video | `mediakit-cli video martencode-video` | [martencode-video](../byted-mediakit-video/reference/martencode-video.md) |
| video | `mediakit-cli video matte-portrait-video` | [matte-portrait-video](../byted-mediakit-video/reference/matte-portrait-video.md) |
| video | `mediakit-cli video semantic-segment` | [semantic-segment](../byted-mediakit-video/reference/semantic-segment.md) |
| video | `mediakit-cli video matte-greenscreen-video` | [matte-greenscreen-video](../byted-mediakit-video/reference/matte-greenscreen-video.md) |
| video | `mediakit-cli video extract-video-invisible-watermark` | [extract-video-invisible-watermark](../byted-mediakit-video/reference/extract-video-invisible-watermark.md) |
| image | `mediakit-cli image remove-image-background` | [remove-image-background](../byted-mediakit-image/reference/remove-image-background.md) |
| image | `mediakit-cli image probe-image-metadata` | [probe-image-metadata](../byted-mediakit-image/reference/probe-image-metadata.md) |
| image | `mediakit-cli image slim-image` | [slim-image](../byted-mediakit-image/reference/slim-image.md) |
| image | `mediakit-cli image image-ocr` | [image-ocr](../byted-mediakit-image/reference/image-ocr.md) |
| image | `mediakit-cli image evaluate-image-quality` | [evaluate-image-quality](../byted-mediakit-image/reference/evaluate-image-quality.md) |
| image | `mediakit-cli image face-blur-image` | [face-blur-image](../byted-mediakit-image/reference/face-blur-image.md) |
| audio | `mediakit-cli audio probe-audio-metadata` | [probe-audio-metadata](../byted-mediakit-audio/reference/probe-audio-metadata.md) |
| audio | `mediakit-cli audio separate-voice` | [separate-voice](../byted-mediakit-audio/reference/separate-voice.md) |
| audio | `mediakit-cli audio detect-voice-activity` | [detect-voice-activity](../byted-mediakit-audio/reference/detect-voice-activity.md) |
| audio | `mediakit-cli audio transcode-audio` | [transcode-audio](../byted-mediakit-audio/reference/transcode-audio.md) |
| editing | `mediakit-cli editing add-subtitle-to-video` | [add-subtitle-to-video](../byted-mediakit-editing/reference/add-subtitle-to-video.md) |

### 允许的共享命令（不计入业务工具数量）

| 允许命令 | 用途与限制 | 完整说明 |
| --- | --- | --- |
| `mediakit-cli shared query-task` | 查询白名单工具已返回的真实 task_id，包括等待成功终态；不能用于组外任务。 | [任务查询](reference/query_task.md) |

MediaKit 用于处理现成的音视频和图片素材。当前提供字幕识别、擦除与压制，视频理解、增强、检测、转码、分段、隐私保护、抠像和暗水印处理，图片背景移除、瘦身、文字识别、画质评估与人脸打码，音频转码、人声分离和人声片段定位，以及各类素材元信息查询。

## 鉴权

- Cloud 调用所需鉴权、日志标识与端点配置由当前运行环境注入；缺失或不可用时停止执行。
- 不在命令、Skill、配置文件或输出中写入鉴权值。

## 能力范围

MediaKit 用于处理现成的音视频和图片素材。当前提供字幕识别、擦除与压制，视频理解、增强、检测、转码、分段、隐私保护、抠像和暗水印处理，图片背景移除、瘦身、文字识别、画质评估与人脸打码，音频转码、人声分离和人声片段定位，以及各类素材元信息查询。

## 能力选择与优先加载

| 用户目标 | 优先加载 |
| --- | --- |
| 语音转字幕；识别或擦除视频画面字幕；理解、增强、检测或转码视频；语义分段；视频人脸打码；人像或绿幕抠像；暗水印添加或提取；视频元信息查询 | byted-mediakit-video |
| 图片背景移除、质量优先瘦身、文字识别、画质评估、人脸打码或元信息查询 | byted-mediakit-image |
| 音频元信息查询、音频转码、人声与背景声分离或人声片段起止时间定位 | byted-mediakit-audio |
| 把已有字幕文件或带时间信息的文本压制到现成视频中 | byted-mediakit-editing |

只说明媒体类型而没有说明目标时，先澄清。一个请求包含多个阶段时，按实际目标选择领域，并只组合当前工具列表中明确可用的能力。语音转字幕后再添加字幕，可按需组合 video 与 editing；不能把字幕识别、画面字幕读取、字幕擦除和字幕压制当作同一操作。

上述音频和视频处理能力不恢复剪辑、拼接、混音、合流或滤镜。

## 可用性检查

仅检查 CLI 版本；不得执行领域枚举、全量帮助或领域帮助。

```bash
mediakit-cli --version
```

## 媒体产物直接交付（强制）

1. 本 Skill 的媒体产物必须使用本次 CLI 成功结果中真实、可消费的输出链接交付。同步结果直接读取实际输出字段；异步提交仅有 task_id 时先查询原任务，只有成功终态的真实媒体结果可交付。不得把输入素材地址、任务 ID、示例或推测地址当作产物。
2. 面向用户的视频和图片交付，必须是一句简短的已完成说明，紧接对应 RichMediaCard。refs 仅使用 CLI 此次真实返回、当前卡片可消费的资源引用，不新增宿主未声明的字段。卡片表达式独立成行，不放代码块、行内代码、引号或 Markdown 链接，不转义标签。
3. 视频和图片的资源地址只作为卡片内部引用。禁止在卡片外输出裸 URL、Markdown 媒体链接、下载链接栏或文件路径；不得用文字总结替代卡片，不为发卡额外要求 present_files。默认不附生成参数、Prompt、工具名、日志、任务 ID 或未经验证的质量结论。
4. 禁止为了交付下载媒体、转存、重新上传、缩短／拼接／改写链接，或通过其他工具和本地文件替代 CLI 的真实输出入口。用户已提供的本地输入与 CLI 自身的输入上传适配不属于产物转存，保留原有能力；CLI 所需技术读取与宿主卡片读取也不因此被禁用。
5. 多步骤处理中，仍需交付的每个成功视频／图片结果立即逐项展示；后续 CLI 操作直接使用前一步真实输出地址作为输入，不先下载为本地文件。完成已确认后期后，最终成片使用最后一次实际处理结果交付，不能拿早期片段或输入地址代替。
6. 编辑、剪辑或纯技术处理配文使用“已经为你完成……”并概括实际改动；新生成使用“已经为你生成……”。片段标明序号，最终拼接结果说明为完整视频，不将处理原片说成重新生成，不重复已确认规格。
7. 不新增审片、评分、自动修复或重生；已确认的后续制作照既定授权执行。查询真实任务状态、检查资源入口以及原本所需的前置技术读取不属于内容验收，不借此寻找缺陷或额外处理。
8. 内部回传真实链接不等于用户交付。实际交付方仍按宿主既定的视频负责执行方／图片 mainagent 分工执行，任何实际交付方都必须遵守上述卡片格式。已交付状态随交接保留，mainagent 不重复代发已经交付的视频。
9. 若既有流程委派 OrganizerAgent，hint 必须明确工具与全部已确认参数、适用的 RichMediaCard 格式，以及成功产物立即直交、禁止内容审查和自动修复重生的约束，不能只给规则链接。工具路由、视频确认、每批两项限制和异步委派保持宿主原合同，不在本 Skill 新建另一套编排流程。
10. 卡片展示不可用、入口不可消费或明确展示失败时，保留原结果和错误，仅恢复该项展示；不得降级链接／下载交付，也不得重新生成、重复处理或新建媒体对象。按原宿主规则由原交付方恢复，依赖该交付的后续步骤暂停，无依赖且已授权任务可继续；技术重试遵守已有上限，不新增数值、不循环重试。
11. 用户已取消或明确拒收的结果不发卡、不恢复后续制作，内部记录真实状态，不能将其记为 delivered。已有展示成功的同一产物不重复发送；原始结果直接采用为最终成片时复用交付记录并注明采用关系。
12. 没有展示成功反馈时，不把输出标签直接记为 delivery_status=delivered，也不据此重复发卡；片段交付不等于最终成片交付。状态与真实引用合并进已有制作记录，不额外建立多套清单。


卡片格式：`<RichMediaCard>{"refs":["本次 CLI 实际返回且可消费的媒体引用"]}</RichMediaCard>`。此处仅为规范结构示意；实际交付必须使用真实引用，并将卡片独立成行，不包裹代码或引号。

音频、字幕等其他媒体文件也必须使用 CLI 原始结果引用，展示格式按宿主原有规范执行，不推断额外卡片类型。没有媒体产物的文字、JSON、元信息等结果照常说明，不发空卡片。CLI 的 HTML、画布及其预览截图继续按原有 CLI 协议执行，不适用本媒体交付格式。

## 使用流程

调用本套 MediaKit 工具前，必须遵守顶部第一准则并核对 MediaKit 白名单。需求超出清单时停止本套 MediaKit 处理流程并说明该 Skill 的边界。禁止使用 mediakit-cli 的领域枚举、全量帮助或领域帮助发现组外 MediaKit 工具，只能核对白名单中已选 MediaKit 工具的 help/schema。

1. 按对象和目标选择领域 Skill；只说明媒体类型而未说明目标时，先向用户澄清。
2. 选定工具后，先读取该工具的完整 reference，再读取实时 `--help` 与 `--schema`。
3. 必填参数必须来自用户真实输入；可选参数只在用户明确提供，或可从意图准确确定时填写。不能准确确定时省略，确为完成任务所必需时先澄清；不得伪造 URL、文件、枚举或业务参数。
4. 对象或对象数组参数按下方「JSON 参数传参」构造；Windows PowerShell 不得套用 bash 单引号。

## 已选工具参数核对

先从上方完整白名单选定工具并读取对应完整 reference。仅可读取这个已选工具的 help/schema；以下 domain 和 tool 必须替换为白名单中同一行的领域与工具，不能用于枚举或搜索新工具。

```bash
mediakit-cli <domain> <tool> --help
mediakit-cli <domain> <tool> --schema
```

`--schema` 仅核对已选工具的当前 Cloud 机器合同，不发起业务调用；顶层包含 `name`、`description`、`input_schema` 和 `output_schema`。

## 媒体输入

当业务参数需要公网可访问媒体，而用户仅提供本机文件路径时，CLI
的 Cloud 输入适配器会处理上传。无需新增上传命令或上传参数。

## 音视频元数据前置探测

- 当目标工具的限制依赖音视频时长、分辨率、文件大小、封装、编码、码率、采样率或声道，而用户没有提供可信元信息时，先加载对应领域 Skill：音频使用 `probe-audio-metadata`，视频使用 `probe-video-metadata`；editing 按实际输入类型复用这两个工具。
- 探测后必须将结果与最终目标工具 reference 的限制逐项比较；确认超限或不兼容时停止并要求用户更换或调整输入，不得盲目调用。
- 元数据探测不能保证后端一定处理成功，也不替代目标工具的专属约束；图片格式、大小和尺寸由图片 CLI 的工具级前置检查执行。

## JSON 参数传参

对象或对象数组参数必须传合法 JSON 字符串，不能用逗号分隔或裸文本。
`array<string>` 仍用逗号分隔或重复 flag，不要套用本节。

支持四种载荷写法：

- 内联 JSON：直接把 JSON 作为 flag 值传入。
- `@文件`：从本机 JSON 文件读取，例如 `--subtitles @./subtitles.json`。
- `-` stdin：从标准输入读取；同一命令全局至多一个 `-`。
- `file://`：从文件 URL 读取，例如 `file://./subtitles.json` 或 `file:///abs/path/subtitles.json`。

POSIX / bash / zsh：内联 JSON 用单引号整体包裹，保留 JSON 内部双引号；大 JSON 优先使用 `@文件` 或 stdin。

```bash
mediakit-cli editing add-subtitle-to-video --video-url "<url>" --subtitles '[{"start_time":0,"end_time":3,"subtitle_text":"大家好"}]'
mediakit-cli editing add-subtitle-to-video --video-url "<url>" --subtitles @./subtitles.json
jq -nc '[{"start_time":0,"end_time":3,"subtitle_text":"大家好"}]' | mediakit-cli editing add-subtitle-to-video --video-url "<url>" --subtitles -
```

Windows PowerShell：单引号或 `$json` 变量都会把 JSON 里的 `"` 剥掉，CLI 会报
`invalid character 's'` / `'t'`。必须把 JSON flag 放在 `--%` 之后；整段 JSON
用双引号包裹，JSON 内部的 `"` 写成 `\"`。带空格的路径等普通参数放在 `--%`
之前。`--%` 之后不要使用 PowerShell 变量。文件载荷也放在 `--%` 之后，优先使用
`file:///C:/...` 或 `@C:\...`。

```powershell
mediakit-cli editing add-subtitle-to-video --video-url "C:\path\video.mp4" --% --subtitles "[{\"start_time\":0,\"end_time\":3,\"subtitle_text\":\"大家好\"}]"
mediakit-cli video erase-video-subtitle-pro --video-url "C:\path\video.mp4" --mode Text --% --erase-ratio-location "[{\"top_left_x\":0,\"top_left_y\":0,\"bottom_right_x\":1,\"bottom_right_y\":0.2}]"
mediakit-cli editing add-subtitle-to-video --video-url "C:\path\video.mp4" --% --subtitles file:///C:/path/subtitles.json
```

Windows 内联 JSON 禁止：

- `'[{...}]'` 单引号 JSON
- `--flag $json` 或 `--flag "$json"`
- `Get-Content` 读出 JSON 后再当 flag 传入
- `cmd /c` 多层转义

## 异步任务

异步工具返回 `task_id` 后，使用：

```bash
mediakit-cli shared query-task --task-id <task_id>
```

完整轮询与结果约定见 [reference/query_task.md](reference/query_task.md)。
