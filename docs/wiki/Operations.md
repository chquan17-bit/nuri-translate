[언어 선택](Home.md) · [한국어](Operations.md) · [English](Operations-en.md) · [简体中文](Operations-zh-CN.md)

# 운영

**두 서비스의 준비 상태, 이미지 일치, 비용 설정, 접근 경계를 함께 확인합니다.**

## 운영 기준

| 구분 | 기준 | 확인 이유 |
|---|---|---|
| ingress / worker | 요청 기반, min 0 / max 1 | 유휴 상시 실행을 두지 않는 운영 방식 |
| 자원 | CPU 1 / 512 MiB | 기존 서비스 크기 유지 |
| 트래픽 | 준비된 revision에 100% | 미완료 배포와 실제 운영 구분 |
| 이미지 | 두 서비스의 digest 일치 | 수신·처리 코드 버전 일치 |
| 모델 | 구성된 Gemini 모델, 기존 무료 등급 유지 | 임의 유료 전환 방지 |
| 사용량 | 25회/일, 10초 간격, 모델 처리 동시 1개 | 공유 상태에 의한 사용 제어 |
| 접근 | 공개 ingress / IAM으로 제한한 worker | Discord 진입점과 작업 실행 분리 |

이 값은 현재 운영 기준입니다. 릴리스 중 비용 방식, 서비스 계정, IAM, 환경 변수, Secret Manager 참조를 이미지 업데이트와 함께 임의로 변경하지 않습니다.

## 배포 후 확인

1. 두 서비스의 `Ready=True`와 `latestReadyRevisionName`을 확인합니다.
2. 실제 트래픽이 새 revision을 가리키는지 확인합니다.
3. revision의 image digest가 릴리스 기록과 같은지 비교합니다.
4. 서명 없는 ingress 요청과 익명 worker 요청이 거부되는지 확인합니다.
5. 실제 Discord 카드 메시지에서 한 번 번역하여 결과의 내용과 공개 범위를 확인합니다.

HTTP 경계 검증은 `scripts/verify_cloud_boundaries.py`를 사용합니다. 이 검사는 모델을 호출하지 않습니다. 실행 옵션은 해당 스크립트의 `--help`와 저장소 배포 가이드를 확인하세요.

```powershell
.\.venv\Scripts\python.exe scripts/verify_cloud_boundaries.py `
  --ingress-url '<ingress-url>' --worker-url '<worker-url>' `
  --application-id '<discord-application-id>' `
  --output '.state/cloud-boundary-verification.json'
```

`--output`은 선택 사항이며 기본값은 `.state/cloud-boundary-verification.json`입니다. 저장할 상위 폴더는 필요하면 생성됩니다. `--application-id` 대신 프로세스 환경 변수 `NURI_APPLICATION_ID`를 사용할 수 있습니다. URL에는 경로나 쿼리를 붙이지 않은 서비스 기본 주소를 전달합니다.

관리 스크립트의 연결 정보는 명시적인 인수나 `NURI_APPLICATION_ID`, `NURI_CLOUD_PROJECT`, `NURI_GCLOUD_ACCOUNT` 환경 변수로 전달합니다. 기본 gcloud 계정·프로젝트에 의존하지 않습니다. 이 값들은 관리 스크립트용이며 기존 Cloud Run 런타임 구성을 바꾸지 않습니다.

| 검사 | 기대 결과 |
|---|---|
| ingress `/health` | 200 |
| ingress `/tasks` | 404 |
| 서명 없는 `/interactions` | 401 |
| 위조 서명의 `/interactions` | 401 |
| 익명 worker `/tasks` | 403 |

## 로그 읽기

애플리케이션 로그는 단계와 결과를 나타내는 짧은 이벤트를 기록합니다. 원문·번역·키·토큰을 로그에 추가하지 않습니다.

| 이벤트 | 의미 |
|---|---|
| `command_accepted` | ingress가 작업을 대기열에 전달 |
| `translation_completed` | 모델 결과를 Discord에 전달 완료 |
| `translation_rejected` | 입력, 한도, 모델 또는 응답 전달 단계의 처리 가능한 거부 |
| `translation_failed` | 예상하지 못한 작업 오류 |
| `quota_lease_release_failed` | 완료 뒤 공유 lease 정리 실패 |
| `startup_configuration_invalid` | 필수 시작 구성 검증 실패 |

`command_accepted`만으로 번역 성공을 판단하지 않습니다. `translation_completed` 및 사용자 화면의 결과를 함께 확인합니다.

## 사용량과 비용

KST 자정부터 새 날짜의 횟수를 계산합니다. 모델 처리 전에 예약된 요청은 실패해도 횟수를 돌려주지 않습니다. 외부 서비스가 이미 요청을 처리했을 수 있기 때문입니다.

오늘 사용량은 계정과 프로젝트를 명시해 조회합니다.

```powershell
.\.venv\Scripts\python.exe scripts/cloud_usage.py inspect `
  --account '<personal-google-account>' --project '<runtime-project-id>'
```

환경 변수 대안은 `NURI_GCLOUD_ACCOUNT`와 `NURI_CLOUD_PROJECT`입니다. 스크립트는 PATH에서 gcloud를 찾고 두 값을 명시하며 전역 구성을 바꾸지 않습니다. `seed`는 로컬 사용량을 옮겨 공유 상태를 변경하는 모드이므로 일반 상태 확인에는 `inspect`를 사용합니다.

> [!IMPORTANT]
> 하루 횟수 제한은 금액 상한이 아닙니다. min 0과 요청 기반 설정을 유지해도 빌드, 이미지 저장, 네트워크, 기타 클라우드 사용에 따른 비용은 별도 확인이 필요합니다. 무료 등급의 상태는 관리 화면에서 확인합니다.

## 첫 기동 제한

유휴 상태 뒤 첫 요청은 ingress 시작 때문에 Discord의 3초 제한을 넘길 수 있습니다. 이 경우 [문제 해결](Troubleshooting.md)의 첫 기동 절차를 따릅니다. 상시 대기 인스턴스나 주기적인 깨우기 작업은 현재 운영 방식에 포함하지 않습니다.

**다음:** [배포 →](Deployment.md) · [문제 해결](Troubleshooting.md)
