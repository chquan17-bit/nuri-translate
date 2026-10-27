[언어 선택](Home.md) · [한국어](Security.md) · [English](Security-en.md) · [简体中文](Security-zh-CN.md)

# 보안과 데이터

**선택한 텍스트를 필요한 경로로만 전달하고, 저장·로그·접근의 범위를 구분합니다.**

## 접근 경계

| 경계 | 적용 방식 |
|---|---|
| Discord → ingress | Ed25519 서명과 timestamp 확인, 앱 ID 검증 |
| 사용자 → 기능 | 구성된 소유자 ID 확인 |
| 연습 버튼 → modal | 소유자와 만료 시간을 포함한 HMAC 서명 |
| Cloud Tasks → worker | OIDC service identity와 Cloud Run IAM |
| worker → Gemini | Secret Manager에서 제공된 API 키 |
| 결과 → Discord | interaction의 개인 응답, 멘션 차단 |

worker의 인증은 Cloud Run IAM에서 수행합니다. 요청 헤더에 특정 문자열이 있다는 이유만으로 인증된 호출로 간주하지 않습니다. ingress에는 worker의 `/tasks` 라우트를 등록하지 않습니다.

## 데이터가 지나가는 곳

| 위치 | 포함되는 정보 | 운영 원칙 |
|---|---|---|
| Discord interaction | 사용자가 선택·입력한 텍스트, 응답용 토큰 | 검증 후 필요한 작업 데이터만 전달 |
| Cloud Tasks | 처리할 원문과 짧게 유효한 응답 토큰 | 작업 전달을 위한 임시 보관 |
| Gemini API | 번역·교정할 텍스트 | 생성 요청, 외부 도구·검색 없음 |
| 애플리케이션 메모리 | 원문, 모델 결과, 호출 자격 정보 | 처리 중 사용 |
| Firestore | KST 날짜, 횟수, 해시 기반 요청 마커, lease 시각 | 원문·번역·사용자 ID·자격 증명 미저장 |
| 애플리케이션 로그 | 결과와 처리 단계의 고정 이벤트 | 원문·번역·키·토큰 미기록 |
| 로컬 `.state` | 복구 설정, 로컬 사용량 및 진단 상태 | Git·빌드 업로드 제외 |

Discord와 Google 서비스 자체의 데이터 보존은 이 애플리케이션이 통제하는 범위와 다릅니다. 비공개 Discord 응답을 외부 서비스에 전송되지 않는 처리로 해석하지 않습니다.

## 모델 입력과 출력

원문은 JSON envelope의 `source` 데이터로 전달합니다. 원문에 포함된 지시, 역할 변경, URL, 명령을 번역 대상 텍스트로 취급하도록 모델을 안내합니다. 검색·도구 실행·링크 수집 기능은 제공하지 않습니다.

모델 출력은 JSON 구조와 문자열 길이를 확인합니다. 응답 형식이 맞지 않거나 완전한 종료를 확인할 수 없으면 오류로 처리합니다. Discord 표시 시 원문과 결과의 Markdown을 이스케이프하고 자동 멘션을 비활성화합니다.

## 자격 증명 관리

- Cloud Run은 기존 서비스 계정과 Secret Manager 참조를 사용합니다. 장기 서비스 계정 키를 저장소나 GitHub에 추가하지 않습니다.
- 클라우드 HTTP 처리는 Discord interaction 응답을 사용하므로 로컬 Gateway용 Bot Token을 배포할 필요가 없습니다.
- Windows 복구 설정은 DPAPI로 암호화하며 같은 Windows 사용자 환경에서 사용합니다. 암호화된 파일도 Git에 커밋하지 않습니다.
- 키 교체 뒤에는 값 자체가 아닌 secret 참조·버전·동작 결과만 기록합니다.

## 저장소에 포함하지 않는 것

실제 `.env`, `.state`, `.venv`, API 키, 토큰, DPAPI 파일, 개인 화면, 로컬 상태 JSON과 운영 증거는 제외합니다. `.gitignore`만 신뢰하지 않고 커밋할 파일 목록과 staged diff를 확인합니다. 빌드는 깨끗한 태그 소스와 제한된 업로드 목록을 사용합니다.

보안 경계를 확인하려면 [운영의 HTTP 검사](Operations.md)를, 문제가 생겼을 때의 기록 방법은 [문제 해결](Troubleshooting.md)을 참고하세요.
