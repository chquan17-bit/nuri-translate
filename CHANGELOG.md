# 변경 기록 · Changelog · 更新日志

## 0.1.0 — 2026-10-27

Nuri 개인 Discord 번역·영어 연습 앱의 첫 버전 릴리스입니다.

- 선택 메시지 또는 붙여 넣은 글 번역, 다시 쓸 표현 학습, 한 문장 영어 연습.
- 일반 본문과 embed 제목·설명·필드를 함께 읽고 멘션만 있는 입력은 모델 호출 전에 안내.
- 번역·교정을 먼저 표시하며 짧은 결과는 한 메시지로, 긴 결과도 비공개·멘션 차단 유지.
- 공개 HTTP ingress의 Discord 서명 검사와 Cloud Tasks를 통한 비공개 worker 호출.
- Firestore의 일일 한도·쿨다운·중복 생성 방지와 Windows Gateway 복구 경로.
- 의존성 고정 및 자격 증명·로컬 상태·개인 운영 증거의 Git/빌드 제외.

**알려진 제한:** 유휴 시 0으로 축소된 ingress의 첫 기동이 Discord의 3초 초기 응답 제한을 넘을 수 있습니다.

**English:** First versioned release with selected-message and embed translation, private learning/practice replies, authenticated Cloud Tasks delivery, durable limits, and Windows recovery. Scale-to-zero ingress cold starts can still exceed Discord's initial response deadline.

**中文：** 首个版本提供所选消息与卡片正文翻译、仅请求者可见的学习和练习结果、经过身份验证的 Cloud Tasks 投递、持久化额度限制及 Windows 恢复方式。缩容至零后的首次启动仍可能超出 Discord 的初始响应时限。
