[选择语言](Home.md) · [한국어](Security.md) · [English](Security-en.md) · [简体中文](Security-zh-CN.md)

# 安全与数据

**仅沿必要的路径传递所选文本，并明确区分存储、日志与访问范围。**

## 访问边界

| 边界 | 控制方式 |
|---|---|
| Discord → ingress | Ed25519 签名、timestamp 与应用 ID 校验 |
| 用户 → 功能 | 校验配置中的所有者 ID |
| 练习按钮 → modal | 包含所有者与到期时间的 HMAC 签名 |
| Cloud Tasks → worker | OIDC 服务身份与 Cloud Run IAM |
| worker → Gemini | Secret Manager 提供的 API 密钥 |
| 结果 → Discord | interaction 的个人响应，禁用提及 |

worker 的身份验证由 Cloud Run IAM 执行。请求头中包含某个字符串并不代表调用已通过身份验证。ingress 不注册 worker 的 `/tasks` 路由。

## 数据流经的位置

| 位置 | 包含的信息 | 运行原则 |
|---|---|---|
| Discord interaction | 用户选择或输入的文本、响应令牌 | 验证后仅传递所需任务数据 |
| Cloud Tasks | 待处理原文和短期有效的响应令牌 | 为任务投递而临时保存 |
| Gemini API | 待翻译或修改的文本 | 发出生成请求，不使用外部工具或搜索 |
| 应用内存 | 原文、模型结果、调用凭据 | 处理过程中使用 |
| Firestore | KST 日期、次数、基于哈希的请求标记、租约时间 | 不保存原文、译文、用户 ID 或凭据 |
| 应用日志 | 表示结果和处理阶段的固定事件 | 不记录原文、译文、密钥或令牌 |
| 本地 `.state` | 恢复配置、本地用量与诊断状态 | 排除在 Git 与构建上传之外 |

Discord 和 Google 服务自身的数据保留规则，不属于本应用可控制的范围。不能将 Discord 私有响应理解为文本不会发送到外部服务。

## 模型输入与输出

原文以 JSON envelope 中的 `source` 数据传入。模型会收到指示，将原文中的指令、角色变更、URL 和命令视为待翻译文本。应用不提供搜索、工具执行或链接抓取功能。

模型输出会经过 JSON 结构和字符串长度校验。如果格式不正确或无法确认完整结束，则按错误处理。在 Discord 中显示原文和结果前，会转义 Markdown 并禁用自动提及。

## 凭据管理

- Cloud Run 使用现有服务账号与 Secret Manager 引用，不向仓库或 GitHub 添加长期服务账号密钥。
- 云端 HTTP 处理使用 Discord interaction 响应，不需要部署本地 Gateway 所用的 Bot Token。
- Windows 恢复配置由 DPAPI 加密，在同一 Windows 用户环境中使用。加密文件同样不得提交至 Git。
- 轮换密钥后，只记录 secret 引用、版本与验证结果，不记录密钥值。

## 不应提交到仓库的内容

真实 `.env`、`.state`、`.venv`、API 密钥、令牌、DPAPI 文件、个人截图、本地状态 JSON 和运行证据均应排除。除了 `.gitignore`，还要检查待提交文件列表和 staged diff。构建应使用干净的标签源码与受限的上传列表。

访问边界检查见[运行维护](Operations-zh-CN.md)；异常诊断记录方式见[故障排查](Troubleshooting-zh-CN.md)。
