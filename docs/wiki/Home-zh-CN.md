[选择语言](Home.md) · [한국어](Home-ko.md) · [English](Home-en.md) · [简体中文](Home-zh-CN.md)

<div align="center">

# Nuri · 运营指南

**翻译所选内容，学习可复用的表达，并通过自己的句子进行练习。**

Discord · Python 3.13 · Cloud Run · Gemini

</div>

---

Nuri 是一个用于 Discord 的个人翻译与英语学习应用。它处理所选的消息或直接输入的文本，并将结果仅显示给请求者。本 Wiki 是涵盖从使用方法到部署和故障排除的运营手册。

> [!NOTE]
> [正式 GitHub Wiki](https://github.com/chquan17-bit/nuri-translate/wiki) 提供三种语言的指南。即使公开源码和文档，机器人使用权限和云配置也不会改变。运行中的机器人仅限所有者使用，结果仅显示给请求者。

## 从您想要的操作开始

| 目的 | 指南 | 核心内容 |
|---|---|---|
| 初次使用 | [开始使用](Getting-Started-zh-CN.md) | 消息菜单，`/nuri`, 单句练习 |
| 理解处理流程 | [架构](Architecture-zh-CN.md) | ingress → 队列 → worker，防重复 |
| 确认日常状态 | [运营](Operations-zh-CN.md) | 费用设置、限制、日志、验证 |
| 部署版本 | [部署](Deployment-zh-CN.md) | 标签 → 提交 → 镜像 → 两个服务 |
| 遇到问题时 | [故障排除](Troubleshooting-zh-CN.md) | 首次启动延迟、限制、签名、响应错误 |
| 确认数据边界 | [安全与数据](Security-zh-CN.md) | 密钥、临时处理、存储范围 |

## 三种使用方式

| 功能 | 输入 | 结果 |
|---|---|---|
| **Nuri 번역** | 所选文本或直接输入的文本 | 翻译 → 原文 |
| **Nuri와 영어 배우기** | 所选文本或直接输入的文本 | 翻译 → 最多 2个可复用表达 → 原文 |
| **한 문장 써보기** | 从学习结果的按钮中输入 | 纠正后的句子 → 一个核心解释 → 我的句子 |

同时读取正文以及卡片的标题、说明和条目文本。不会自动收集图像、附件或链接的外部页面。

## 当前运营原则

| 项目 | 标准 |
|---|---|
| 运行 | 分离公开的 HTTP ingress 与私有的 worker |
| 访问 | 验证 Discord 请求签名，仅限所有者使用 |
| 服务规模 | 两个服务均基于请求，最小 0 · 最大 1, CPU 1 · 512 MiB |
| 使用量 | 每天 25次 · 请求间隔 10秒 · 模型并行处理 1个 |
| 重复处理 | 在 Firestore 预定后调用模型，防止重复生成相同的 interaction |
| 发布 | 从 annotated tag 的干净源码构建，向两个服务部署相同的 digest |

> [!IMPORTANT]
> 由于保持了最小实例 0，因此在长时间闲置后的首次请求可能会因启动延迟而超过 Discord 的 3秒响应限制。这是当前运营中残存的限制。

## 文档与发布记录

Wiki 的源文件在仓库 `docs/wiki/`中进行管理。区分代码的默认值与当前运营设置，实际部署结果通过各发布的 commit SHA、build ID、image digest 和 revision 记录进行确认。文档示例中不包含实际的密钥、个人账号或云项目标识符。

修改韩国语原文并反映到 `main`后，GitHub Actions 会将更改后的正文翻译成英语和简体中文，并同时更新三种语言的 Wiki。如果翻译或链接验证失败，则保留原有的 Wiki。有关编写位置和重新运行方法，请参考 [文档自动化指南](../WIKI-AUTOMATION.md)。

**下一步：** [开始使用 →](Getting-Started-zh-CN.md)
