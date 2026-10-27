<div align="center">

# Nuri · Knowledge Base

**번역 · 영어 학습 · 한 문장 연습**  
**Translate · Learn · Practice**  
**翻译 · 学习表达 · 练习一句话**

Discord · Python 3.13 · Cloud Run · Gemini

</div>

---

## 언어 선택 · Choose your language · 选择语言

| 한국어 | English | 简体中文 |
|---|---|---|
| [한국어 가이드](Home-ko.md) | [English guide](Home-en.md) | [简体中文指南](Home-zh-CN.md) |
| [시작하기](Getting-Started.md) | [Getting started](Getting-Started-en.md) | [开始使用](Getting-Started-zh-CN.md) |
| [아키텍처](Architecture.md) | [Architecture](Architecture-en.md) | [系统架构](Architecture-zh-CN.md) |
| [운영](Operations.md) | [Operations](Operations-en.md) | [运行维护](Operations-zh-CN.md) |
| [배포](Deployment.md) | [Deployment](Deployment-en.md) | [版本部署](Deployment-zh-CN.md) |
| [문제 해결](Troubleshooting.md) | [Troubleshooting](Troubleshooting-en.md) | [故障排查](Troubleshooting-zh-CN.md) |
| [보안과 데이터](Security.md) | [Security and data](Security-en.md) | [安全与数据](Security-zh-CN.md) |

> [!NOTE]
> **한국어** · 이 문서는 저장소 내 Wiki입니다. 현재 요금제에서는 비공개 GitHub Wiki 탭을 사용할 수 없습니다. 요금제나 공개 범위 변경 없이 이 문서 허브를 제공합니다.  
> **English** · This Wiki lives in the repository. The current plan does not enable the Wiki tab for this private repository. This documentation hub preserves the existing plan and repository visibility.  
> **简体中文** · 本 Wiki 位于代码仓库内。当前套餐不支持该私有仓库的 Wiki 标签页。本资料中心保留现有套餐和仓库可见性。

## 한눈에 보기 · At a glance · 项目概览

| | |
|---|---|
| **사용 / Use / 使用** | 선택한 메시지와 직접 입력한 글 · Selected or entered text · 所选消息或输入文本 |
| **결과 / Response / 结果** | 요청자에게만 표시 · Visible only to the requester · 仅请求者可见 |
| **실행 / Runtime / 运行** | Public ingress → Cloud Tasks → Private worker |
| **릴리스 / Release / 发布** | Annotated tag → Commit → Build → Image digest → Two revisions |
| **운영 / Operations / 运维** | Request-based · Min 0 / Max 1 · CPU 1 / 512 MiB |
| **알려진 제한 / Known limit / 已知限制** | 유휴 뒤 첫 요청 지연 · Cold-start delay after idle time · 空闲后的首次请求可能延迟 |

---

<details>
<summary>문서 관리 · Maintaining the docs · 文档维护</summary>

문서 원본은 `docs/wiki/`입니다. 기능·한도·명령을 바꾸면 세 언어의 대응 페이지를 함께 갱신합니다.  
The source is `docs/wiki/`. Update matching pages in all three languages when behavior, limits, or commands change.  
源文件位于 `docs/wiki/`。功能、限制或命令变更时，请同步更新三种语言的对应页面。

향후 비공개 Wiki를 사용할 수 있는 환경이 마련되면 별도 Wiki Git 저장소에 이 페이지들을 게시하고, `.md` 상대링크를 Wiki 페이지 slug로 변환합니다. `_Sidebar.md`와 `_Footer.md`를 함께 사용하며 기존 Wiki 내용이 있는지 먼저 확인합니다.  
If private Wikis become available later, publish these pages to the separate Wiki Git repository, convert relative `.md` links to Wiki page slugs, and include `_Sidebar.md` and `_Footer.md`. Inspect any existing Wiki content first.  
今后若具备私有 Wiki 功能，可将这些页面发布到独立的 Wiki Git 仓库，将相对 `.md` 链接转换为 Wiki 页面名称，并加入 `_Sidebar.md` 和 `_Footer.md`。请先检查已有 Wiki 内容。

</details>
