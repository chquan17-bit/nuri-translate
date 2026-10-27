[选择语言](Home.md) · [한국어](Getting-Started.md) · [English](Getting-Started-en.md) · [简体中文](Getting-Started-zh-CN.md)

# 开始使用

**在已安装 Nuri 的 Discord 中选择消息，或通过 `/nuri` 输入文字。**

## 1. 翻译所选文字

1. 右键点击要翻译的消息；移动端可长按消息。
2. 在 **Apps** 菜单中选择 **Nuri 번역**。
3. 查看仅对请求者可见的译文和原文。

应用会要求模型将英语翻译为韩语、韩语翻译为英语，其他语言翻译为韩语。

对于卡片消息，应用会合并 Discord 提供的 `content` 与 embed 的 `title`、`description`、`fields` 文本。完全相同的文本块只保留一次，并移除提及用户或角色的语法。如果只有提及信息或没有可读文本，会在调用模型前给出提示。

## 2. 学习表达

选择 **Nuri와 영어 배우기** 后，译文下方会显示最多 2 个可复用的英语表达。翻译与学习说明分别呈现，并附带原文，方便对照。

直接输入时，在 `/nuri` 的 `text` 中粘贴文本，再通过 `mode` 选择翻译或英语学习。

## 3. 用自己的句子练习

点击学习结果中的 **한 문장 써보기** 按钮并输入英语句子，即可查看更自然的表达和一项最有帮助的修改说明。按钮在 10 分钟后失效；失效后请重新运行 Nuri。

## 输入与输出标准

| 项目 | 标准 |
|---|---|
| 翻译、学习输入 | 合计最多 3,000 字符 |
| 练习句子 | 最多 1,000 字符 |
| 较长输出 | 按 UTF-16 单位控制在 Discord 消息上限内，最多分为 6 条 |
| 不读取的内容 | 图片内容、附件内容、链接指向的外部网页 |
| 结果可见范围 | 仅请求者可见，禁用自动提及 |

> [!NOTE]
> “仅对我显示”指 Discord 响应的可见范围。待翻译文本仍会发送给 Google API 进行处理。详情见[安全与数据](Security-zh-CN.md)。

## 在开发环境中检查

准备 Python 3.13 和 `uv`，然后在仓库根目录执行：

```powershell
uv --cache-dir .state/uv-cache sync --frozen
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m nuri doctor
```

`doctor` 仅检查凭据是否存在，不发送外部请求。`.env.example` 是环境变量名称示例，应用不会自动加载该文件。

Windows 的 `Configure-Nuri.cmd` 使用 DPAPI 加密本地恢复所需的凭据。Cloud Run 正常运行时，无需另外启动本地 Gateway。如果要迁移至新的 Discord 应用，除了环境变量，还必须检查代码中的应用 ID 校验值。

运行时仍专用于 Nuri 应用。更改管理脚本中的应用 ID 配置，并不会改变运行时固定的应用 ID 校验值。

**下一步：**[系统架构 →](Architecture-zh-CN.md) · [故障排查](Troubleshooting-zh-CN.md)
