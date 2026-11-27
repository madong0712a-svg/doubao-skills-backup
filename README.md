# 豆包 / 智能体技能备份（doubao-skills-backup）

本机所用全部技能的离线备份，用于重装系统或换机后恢复。

## 目录与原始路径对应

| 仓库目录 | 本机原始路径 | 说明 |
|---|---|---|
| `user_skills/` | `C:\Users\madong\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.user_skills\` | 自建及自装的用户技能 |
| `builtin_skills/` | `C:\Users\madong\AppData\Local\Doubao\User Data\Default\.doubao\agent_mode\workspace\.skills\` | 豆包客户端内置 / 官方技能 |
| `agents_skills/` | `C:\Users\madong\.agents\skills\` | 另一智能体框架下自装的第三方技能（钉钉、微信、抖音等） |

## 恢复方法

1. 确认豆包 / 智能体客户端已安装并至少启动过一次，使上述目录生成。
2. 按上表把对应目录下的技能文件夹整体拷回本机原始路径：
   - 自建技能放回 `user_skills/` 对应的 `.user_skills\`；
   - 内置技能放回 `builtin_skills/` 对应的 `.skills\`；
   - 第三方技能放回 `agents_skills/` 对应的 `.agents\skills\`。
3. 重启客户端，技能即被识别。

## 说明

- 备份时已排除 `.git`、`__pycache__`、`*.pyc` 等缓存与版本目录。
- `builtin_skills/` 为客户端官方分发，重装豆包后通常会自动恢复；本仓库一并留存以便离线对照。
- 当天运行产生的临时清单、待审核表、个人数据不在备份范围内。

## 备份信息

- 备份日期：2026-11-27
- 技能数量：user_skills 20、builtin_skills 49、agents_skills 23，合计 92 个
