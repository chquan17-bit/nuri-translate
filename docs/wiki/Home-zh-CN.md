[选择语言](Home.md) · [한국어](Home-ko.md) · [English](Home-en.md) · [简体中文](Home-zh-CN.md)

<div align="center">

# Nuri · 运营指南

**翻译所选文章，学习可复用的表达，并用自己的句子进行练习。**

Discord · Python 3.13 · Cloud Run · Gemini

</div>

---

Nuri 是一款在 Discord 上使用的个人翻译与英语学习应用。它会处理所选消息或直接输入的文本，并将结果仅显示给请求者。本 Wiki 是从使用方法到部署及故障排除的操作手册。

> [!NOTE]
> [正式 GitHub Wiki](https://github.com/chquan17-bit/nuri-translate/wiki) 提供三种语言的指南。公开源码和文档不会改变机器人使用权限和云端配置。运行中的机器人仅限所有者使用，结果仅显示给请求者。

## 从想要的操作开始

| 目的 | 指南 | 核心内容 |
|---|---|---|
| 初次使用 | [开始](Getting-Started-zh-CN.md) | 消息菜单，`/nuri`, 单句练习 |
| 理解处理过程 | [架构](Architecture-zh-CN.md) | ingress → 队列 → worker，防重复制 |
| 检查常规状态 | [运营](Operations-zh-CN.md) | 费用设置、限制、日志、验证 |
| 部署版本 | [部署](Deployment-zh-CN.md) | 标签 → 提交 → 镜像 → 两个服务 |
| 遇到问题时 | [问题排查](Troubleshooting-zh-CN.md) | 首次启动延迟、限制、签名、响应错误 |
| 确认数据边界 | [安全与数据](Security-zh-CN.md) | 密钥、临时处理、存储范围 |

## 三种使用方式

| 功能 | 输入 | 结果 |
|---|---|---|
| **Nuri 번역** | 所选文章或直接输入的文章 | 翻译 → 原文 |
| **Nuri와 영어 배우기** | 所选文章或直接输入的文章 | 翻译 → 可复用的表达最多 2个 → 原文 |
| **한 문장 써보기** | 从学习结果的按钮中输入 | 纠正后的句子 → 一项核心解释 → 我的句子 |

同时读取消息正文以及卡片的标题、说明和条目文本。不会自动收集图像、附件和链接的外部页面。

## 当前运营原则

| 项目 | 标准 |
|---|---|
| 执行 | 分离公开 HTTP ingress 与私有 worker |
| 访问 | 验证 Discord 请求签名，仅限所有者使用 |
| 服务规格 | 两个服务均为请求驱动，最小 0 · 最大 1, CPU 1 · 512 MiB |
| 用量 | 每日请求 25次 · 请求间隔 10秒 · 并发处理的模型请求 1个 |
| 重复处理 | 在 Firestore 预定后调用模型，防止重复生成相同的 interaction |
| 发布 | 从 annotated tag 的干净源码构建，向两个服务部署相同的 digest |

> [!IMPORTANT]
> 由于维持了最小实例数0，在长期空闲后，首次请求可能会因启动延迟而超过 Discord 的 3秒响应限制。这是当前运营中残存的限制。

## 文档与发布记录

Wiki 文档原件在此仓库的 `docs/wiki/` 文件夹中管理。区分代码的默认值与当前运营配置，实际部署结果通过各发布的 commit SHA、build ID、image digest、revision 记录进行确认。文档示例中不包含实际密钥、个人账号及云端项目标识符。

当把韩国语原件的更改合并或 push 到 `main` 分支时，GitHub Actions 会将更改后的正文翻译成英语和简体中文，并同时更新三种语言的 Wiki。如果翻译或链接验证失败，则保留现有的 Wiki。编写位置与重新执行方法请参考 [文档自动化指南](../WIKI-AUTOMATION.md)。

**下一篇：** [开始 →](Getting-Started-zh-CN.md)
