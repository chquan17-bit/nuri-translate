# 검증 안내 · Validation · 验证说明

## 릴리스 준비 검증

2026-10-27 관리 스크립트 검증을 추가한 뒤 오프라인 테스트 **121개가 통과**했습니다(6.941초). 잠금 파일과 컨테이너 requirements의 일관성을 확인했으며, 비밀 값이 없는 환경의 `doctor`는 예상한 비연결 상태를 보고했습니다. 실제 빌드·배포·Discord 검증은 해당 릴리스 기록과 함께 확인합니다.

*English: Release preparation passed 121 offline tests. Build and deployment checks are recorded separately.*  
*中文：发布准备阶段的 121 项离线测试通过；构建与部署检查另行记录。*

## 인계 당시의 이력

2026-10-27 릴리스 인계 시점에 오프라인 테스트 **116개가 통과**했습니다. 같은 날 실제 Discord 카드형 메시지에서 메뉴로 영어 학습을 실행해 전체 번역·학습 표현·원문 표시를 확인했습니다. 이는 태그 릴리스 이전 검증입니다. 새 릴리스의 빌드와 배포 결과는 별도 릴리스 기록에서 확인합니다. 개인 화면과 계정별 운영 기록은 저장소에 포함하지 않습니다.

*English: 116 tests passed at handoff; this is historical evidence, not a claim about a later deployment.*  
*中文：交接时 116 项测试通过；这属于历史验证，不代表后续部署已经验证。*

## 오프라인 테스트

저장소 루트에서 잠금 파일로 환경을 설치하고 실행합니다.

```powershell
uv --cache-dir .state/uv-cache sync --frozen
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

테스트는 모델과 클라우드 저장소를 모의 처리하며 실제 Gemini 요청을 발생시키지 않습니다.

| 영역 | 확인 내용 |
| --- | --- |
| 선택 메시지 | 본문·embed 제목/설명/필드 수집, 멘션 제거, 중복 텍스트 정리, 빈 본문 거절, 합산 길이 제한 |
| 출력 | 번역 우선, 짧은 결과 한 메시지, Markdown 처리, Unicode 보존, UTF-16 길이와 최대 메시지 수 |
| Discord | User Install, 소유자 제한, 다른 앱 등록 거절, 비공개 응답·후속 메시지, 연습의 사용자·만료 검사 |
| HTTP ingress | Ed25519 서명, 변조·누락·시간 오류 거절, 앱·사용자 검사, worker 경로 분리, 등록 시간 제한 |
| Cloud Tasks·worker | OIDC 대상, 결정적 작업 ID, 중복 전달, 입력 재검사, 예외 비노출, 중복 생성 방지 |
| 사용량 | 재시작 후 한도·쿨다운, 한국 시간 날짜 변경, 동시 요청, 실패 시 차감, 저장 실패 시 차단 |
| 모델 | 구조화 응답 검사, 잘못되거나 중단된 응답, 인증 오류·429·시간 초과, 자동 재시도 방지 |

## 배포 후 경계 검사

`scripts/verify_cloud_boundaries.py`로 배포된 URL에 대해 다음을 확인합니다. 인수는 [배포 안내](docs/DEPLOYMENT.md)를 참고하세요.

- ingress `/health`: HTTP 200.
- ingress `/tasks`: HTTP 404.
- 서명이 없거나 위조된 `/interactions`: HTTP 401.
- 익명 worker `/tasks`: HTTP 403.

이 검사는 자격 증명과 모델 호출을 사용하지 않습니다. 배포된 revision이 준비 상태가 될 때까지 기다린 뒤 검사합니다. 실패하면 상태와 설정을 확인하고 같은 배포를 중복 실행하지 않습니다.

## 실제 Discord 확인

승인된 테스트 메시지에서 메뉴를 한 번 실행합니다. embed가 있다면 카드 제목·설명·필드 내용이 번역에 포함되는지, 번역·학습 표현·원문이 읽기 좋게 표시되는지, 결과가 요청자에게만 표시되는지 확인합니다. 실제 요청은 일일 한도를 사용하므로 불필요하게 반복하지 않습니다.

최소 인스턴스 0에서는 유휴 후 첫 요청이 Discord의 초기 응답 시간 제한을 넘을 수 있습니다. 준비된 상태에서 성공한 검증을 첫 기동 문제 해결로 해석하지 않습니다.

## 릴리스 기록

태그, 태그가 가리키는 commit SHA, Cloud Build ID, 이미지 digest, ingress/worker revision, 검사 결과를 함께 기록합니다. 인증 정보·요청 원문·응답 토큰·개인 화면은 기록하지 않습니다. 배포 후 기록을 덧붙이기 위해 태그 커밋을 이동하거나 덮어쓰지 않습니다.
