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

문서 원본은 `docs/wiki/`입니다. 한국어 본문을 수정해 `main`에 반영하면 GitHub Actions가 영어·중국어를 번역하고 세 언어를 함께 게시합니다.

Sources live in `docs/wiki/`. Changes to Korean content on `main` are translated into English and Simplified Chinese, then all three languages are published together by GitHub Actions.

源文件位于 `docs/wiki/`。韩语正文的修改进入 `main` 后，GitHub Actions 会生成英语与简体中文译文，再统一发布三种语言。

번역·링크 검사가 실패하면 기존 Wiki를 유지합니다. 이 홈과 사이드바·푸터는 공통 다국어 메뉴이므로 세 언어를 함께 수정합니다. 설정과 작성 범위는 [Wiki 자동화 안내](../WIKI-AUTOMATION.md)를 확인하세요.

Translation or link validation failures leave the existing Wiki in place. This home, sidebar, and footer are shared multilingual templates; maintain their three languages together. See [Wiki automation](../WIKI-AUTOMATION.md#english) for setup and authoring scope.

翻译或链接检查失败时保留现有 Wiki。本首页、侧栏和页脚是共用多语言模板，请同时维护三种语言。配置与编辑范围见 [Wiki 自动化说明](../WIKI-AUTOMATION.md#简体中文)。

</details>
