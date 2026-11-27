# `design-cli design-workspace +workspace-create`

HTML 的制作必须已有用户明确的自由编辑意愿；预览与交付统一按 [HTML 交付规范](../references/canvas-delivery.md)，仅使用 `creative_design_preview` 返回的设计预览／编辑入口真实短链 + RichMediaCard；禁止交付 HTML 文件、源码附件、打包源文件或下载链接。以下 CLI 仅用于用户另行要求的画布对象读写，不替代该预览交付链路。

建一张新画布。调用 Alice IDL 的 `CreateCanvasWorkspaceForCLI`。

## 用途

用于实际需要保存或修改画布对象的任务，不因产物类型或宿主自动初始化画布。所有产物按 [主入口](../SKILL.md#交付规范)及 [交付协议](../references/canvas-delivery.md)使用 RichMediaCard + 真实短链交付。

返回 `canvas_workspace_id`，供七个 Item／Frame 读写命令的 `--canvas-workspace-id` 使用。适用流程中没有当前任务的 Workspace ID 时，制作前调用；已有唯一有效 ID 时直接复用，不重复创建。

它与 `+get-workspace` 都不带 `--canvas-workspace-id`。本命令创建 Workspace，`+create` 创建 Item／Frame，两者不要混用。

## 命令

```bash
design-cli design-workspace +workspace-create --title <title>
```

## 参数与请求

| CLI 参数 | 必填 | JSON 字段 |
|---|---:|---|
| `--title` | 是 | `title`；空值或纯空白按缺失处理，退出码 `2`、不发请求 |

`conversation_id` 也进请求体，但**不是 CLI 参数** —— 它由 CLI 从环境变量读取（沙箱注入）：优先 `MCP_VM_CONVERSATION_ID`，未设或纯空白时回退 `SESSION_ID`，两者都没有才整格省略。不要试图用命令行指定会话。

```text
POST /creativity/canvas_workspace/cli/create_workspace
Content-Type: application/json
```

```json
{"title":"雨夜便利店短剧","conversation_id":"7788"}
```

## 输出

`xml_data` 内为 `<canvas_workspace>`：

```xml
<canvas_workspace>
  <canvas_workspace_id>cws_10001</canvas_workspace_id>
  <version>1</version>
</canvas_workspace>
```

只回 ID 与版本，不回画布内容——新画布本来就是空的。**记下 `canvas_workspace_id`**，后续所有命令都要用它。

## Workspace ID 与产物交付

读取并保留响应中的原始 `canvas_workspace_id`，用于后续 CLI 读写，不需要展示初始化卡片。HTML 交付仅用 `creative_design_preview` 返回的真实短链 + RichMediaCard；其他产物按主入口取得真实短链交付。Workspace 创建成功不代表产物已交付，Workspace ID 也不作为短链使用。

`version` 是画布的全局版本号，新建时为 `1`。

## 注意

- **没有幂等**：同样的 `--title` 调两次会建出两张画布。调用超时且未取得 ID 时，仅通过已验证的当前会话查询能力（如 [+get-workspace](get-workspace.md)）找回；无法确认就停止重建并报告，不按通用重试次数再次创建。
- 会话由环境变量决定，命令行改不了。

退出码与错误处理见 [`README.md`](README.md)。
