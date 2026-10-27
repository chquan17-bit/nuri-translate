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
> **한국어** · [정식 GitHub Wiki](https://github.com/chquan17-bit/nuri-translate/wiki)와 공개 저장소에서 문서를 제공합니다. 소스 공개는 봇 권한과 클라우드 설정을 바꾸지 않으며, 운영 중인 봇과 응답은 소유자 전용으로 유지합니다.  
> **English** · Documentation is available in the [official GitHub Wiki](https://github.com/chquan17-bit/nuri-translate/wiki) and public repository. Public source does not change bot access or cloud settings; the running bot remains owner-only and its replies remain private.  
> **简体中文** · 文档已发布到[正式 GitHub Wiki](https://github.com/chquan17-bit/nuri-translate/wiki)及公开仓库。公开源码不会改变机器人访问权限或云配置；运行中的机器人仍仅供所有者使用，回复保持私有。

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

변경한 원본을 별도 Wiki Git 저장소에 동기화할 때 `.md` 상대링크를 Wiki 페이지 주소로 변환하고 이미지 경로를 확인합니다. `_Sidebar.md`와 `_Footer.md`를 함께 게시하며 기존 Wiki 이력을 보존합니다.  
When syncing sources to the separate Wiki Git repository, convert relative `.md` links to Wiki page URLs and verify image paths. Publish `_Sidebar.md` and `_Footer.md` alongside the pages, preserving existing Wiki history.  
将更新后的源文件同步到独立的 Wiki Git 仓库时，请将相对 `.md` 链接转换为 Wiki 页面地址，并检查图片路径。同步发布 `_Sidebar.md` 和 `_Footer.md`，保留已有 Wiki 历史。

</details>
