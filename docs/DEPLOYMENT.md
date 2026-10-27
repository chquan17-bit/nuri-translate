# Cloud Run 배포 안내 · Deployment · 部署说明

이미 구성된 Nuri 환경에 새 버전을 배포하는 절차입니다. 공개 ingress와 비공개 worker의 IAM, 서비스 계정, 환경변수, Secret Manager 참조, Cloud Tasks, Firestore 및 Gemini 무료 등급을 유지합니다. 새 권한이나 결제 연결을 만드는 절차는 포함하지 않습니다.

*English: Build a clean annotated tag, deploy one immutable digest to both existing services, and preserve existing access and cost settings.*  
*中文：从干净的附注标签构建，将同一不可变镜像摘要部署到两个现有服务，并保留访问权限与成本设置。*

## 릴리스 전 확인

1. 개인 GitHub 계정과 대상 저장소를 확인하고 기존 원격 브랜치·태그를 조회합니다. 공개 저장소에 비밀 값이나 개인 운영 기록이 포함되지 않았는지 확인하며, 기존 이력을 강제로 덮어쓰지 않습니다.
2. 저장소 로컬 Git 작성자를 확인합니다. 전역 Git 설정은 변경하지 않습니다.
3. staged 파일 목록과 내용에서 자격 증명, `.state/`, `.venv/`, 운영 상태 및 개인 화면이 없는지 검사합니다.
4. [오프라인 테스트](../VALIDATION.md)를 실행하고 `pyproject.toml` 버전과 `CHANGELOG.md`를 확인합니다.
5. 검증한 커밋을 `main`에 push한 뒤 해당 커밋의 annotated tag를 생성하고 push합니다. 기존 태그를 이동하거나 덮어쓰지 않습니다.

## 대상 변수

다음 PowerShell 값을 확인한 기존 환경으로 채웁니다. 계정과 프로젝트는 모든 `gcloud` 호출에 명시하며 기본 설정을 바꾸지 않습니다. 아래는 자리표시자입니다.

```powershell
$Account = 'YOUR_PERSONAL_GOOGLE_ACCOUNT'
$Project = 'YOUR_EXISTING_RUNTIME_PROJECT'
$Region = 'YOUR_CLOUD_RUN_REGION'
$Ingress = 'YOUR_EXISTING_INGRESS_SERVICE'
$Worker = 'YOUR_EXISTING_WORKER_SERVICE'
$Builder = 'projects/YOUR_EXISTING_RUNTIME_PROJECT/serviceAccounts/YOUR_EXISTING_BUILDER_SERVICE_ACCOUNT'
$SourceBucket = 'gs://YOUR_EXISTING_BUILD_SOURCE_BUCKET/source'
$ImageRepository = 'YOUR_REGION-docker.pkg.dev/YOUR_EXISTING_RUNTIME_PROJECT/YOUR_REPOSITORY/YOUR_IMAGE'
$ApplicationId = 'YOUR_DISCORD_APPLICATION_ID'
$IngressUrl = 'https://YOUR_EXISTING_INGRESS_HOST.run.app'
$WorkerUrl = 'https://YOUR_EXISTING_WORKER_HOST.run.app'
$Version = 'v0.1.0'
```

배포 전 현재 이미지·revision·트래픽과 운영 설정을 로컬 기록에 남깁니다. 비밀 값은 읽거나 출력하지 않습니다. 기존 환경변수와 Secret Manager 참조를 비교할 때에도 실제 비밀 값이 아닌 참조를 확인합니다.

```powershell
gcloud run services describe $Ingress --region=$Region --account=$Account --project=$Project --format=json
gcloud run services describe $Worker --region=$Region --account=$Account --project=$Project --format=json
gcloud run services get-iam-policy $Ingress --region=$Region --account=$Account --project=$Project --format=json
gcloud run services get-iam-policy $Worker --region=$Region --account=$Account --project=$Project --format=json
```

보존할 기준은 다음과 같습니다.

| 구분 | 기준 |
| --- | --- |
| 두 서비스 | 요청 기반 과금, 최소 인스턴스 0·최대 1, CPU 1·메모리 512 MiB |
| ingress | 공개 호출 허용, Discord 서명·시간·앱·사용자 검사 |
| worker | 비공개, 기존 Cloud Tasks OIDC 호출자만 접근 |
| 자격 증명 | 기존 서비스 계정과 Secret Manager 참조 |
| 모델·사용량 | 기존 무료 등급과 일일 제한, 생성 자동 재시도 없음 |
| Cloud Tasks | 기존 대기열·전달 재시도·동시 처리 설정 |

## 깨끗한 태그 checkout에서 빌드

`$RepoRoot`는 로컬 저장소 루트, `$BuildDirectory`는 아직 존재하지 않는 별도 checkout 경로입니다. Git 객체로부터 clone하며 인증 정보와 실행 상태를 복사하지 않습니다.

```powershell
$RepoRoot = (Get-Location).Path
$BuildDirectory = Join-Path $RepoRoot ('.state/releases/' + $Version + '/checkout')
git -C $RepoRoot cat-file -t $Version
git -C $RepoRoot rev-parse ($Version + '^{commit}')
git clone --no-hardlinks --branch $Version --single-branch $RepoRoot $BuildDirectory
git -C $BuildDirectory status --porcelain
$Commit = git -C $BuildDirectory rev-parse HEAD
$ImageTag = $ImageRepository + ':' + $Version
```

`cat-file` 결과가 `tag`인지, HEAD가 태그의 commit과 일치하는지, `status --porcelain` 출력이 비어 있는지 확인합니다. 명령이 실패하면 진행하지 않습니다. `.gcloudignore`는 런타임 소스와 빌드 파일만 업로드합니다.

```powershell
gcloud builds submit $BuildDirectory --config=(Join-Path $BuildDirectory 'cloudbuild.yaml') --substitutions=('_IMAGE=' + $ImageTag) --service-account=$Builder --gcs-source-staging-dir=$SourceBucket --region=$Region --account=$Account --project=$Project --async --format='value(id)'
```

반환된 ID를 `$BuildId`로 기록하고 성공 상태가 될 때까지 확인합니다. 재시도 전에 기존 빌드 상태를 먼저 확인합니다.

```powershell
gcloud builds describe $BuildId --region=$Region --account=$Account --project=$Project --format='json(id,status,results.images)'
```

`SUCCESS`인 빌드의 `results.images`에서 digest를 확인합니다. `$ImageDigest`는 `$ImageRepository + '@sha256:...'` 형태의 완전한 참조입니다. 빌드 실패나 digest 불일치가 있으면 배포하지 않습니다.

## 같은 digest를 두 서비스에 배포

이미지만 변경해 기존 설정을 보존합니다. worker가 준비된 뒤 ingress를 변경하고 각 명령의 성공과 새 revision의 준비 상태를 확인합니다.

```powershell
gcloud run services update $Worker --image=$ImageDigest --region=$Region --account=$Account --project=$Project
gcloud run services update $Ingress --image=$ImageDigest --region=$Region --account=$Account --project=$Project
gcloud run services describe $Worker --region=$Region --account=$Account --project=$Project --format=json
gcloud run services describe $Ingress --region=$Region --account=$Account --project=$Project --format=json
```

두 최신 준비 revision이 같은 digest를 실행하고 트래픽을 받는지 확인합니다. IAM, 서비스 계정, Secret Manager 참조, 환경변수, 요청 기반 과금과 min 0/max 1이 유지됐는지도 비교합니다. 준비에 몇 분이 걸릴 수 있으므로 같은 서비스를 중복 배포하지 않습니다.

## 배포 후 검증과 기록

준비 완료 후 기존 개발 환경에서 실행합니다. 경계 검사는 자격 증명과 모델 호출을 사용하지 않습니다.

```powershell
.\.venv\Scripts\python.exe scripts/verify_cloud_boundaries.py --ingress-url $IngressUrl --worker-url $WorkerUrl --application-id $ApplicationId --output .state/cloud-boundary-verification.json
```

health, 서명 거절, worker 익명 접근 거절이 모두 통과했는지 확인합니다. 마지막으로 승인된 Discord 원문에서 메뉴 번역을 한 번 실행하고 [검증 안내](../VALIDATION.md)에 따라 embed 본문과 비공개 결과를 확인합니다. 최소 인스턴스 0의 첫 기동 제한은 함께 기록합니다.

| 기록 항목 | 값 |
| --- | --- |
| 저장소 | 대상 저장소 URL |
| 버전·annotated tag | 버전과 태그 객체 SHA |
| 소스 | commit SHA |
| 빌드 | Cloud Build ID와 성공 상태 |
| 이미지 | 완전한 image digest |
| worker | revision·준비 상태·트래픽 |
| ingress | revision·준비 상태·트래픽 |
| 검증 | 테스트 수, 경계 검사, 실제 메뉴 결과, 확인 시각 |

운영별 기록은 `.state/` 등 Git 제외 경로에 보관하거나 승인된 릴리스 설명에 첨부합니다. 인증 정보·원문·응답 토큰·개인 화면을 넣지 않습니다. 이미 배포한 태그를 기록 추가 목적으로 다시 만들지 않습니다.

## 관리 스크립트

계정별 값은 명령 인수나 프로세스 환경에 명시합니다. 비밀 값은 명령 인수로 넘기지 않습니다.

| 스크립트 | 대상 지정 |
| --- | --- |
| `cloud_connection.py` | `--application-id`, `--project`; upload 작업에는 `--account`도 필수 |
| `cloud_usage.py` | inspect/seed 작업에 `--project`, `--account` 필수 |
| `verify_cloud_boundaries.py` | `--ingress-url`, `--worker-url`, `--application-id`; 선택적으로 `--output` |
| `Cloud-Nuri-Connection.ps1` | `-ApplicationId`, `-Project`, `-Account` |
| `Verify-NuriRotation.ps1` | `-ApplicationId` |

연결 스크립트의 환경변수 대안은 `NURI_APPLICATION_ID`, `NURI_CLOUD_PROJECT`, `NURI_GCLOUD_ACCOUNT`입니다. 상세 모드는 각 스크립트의 도움말을 확인합니다. upload, seed, endpoint 변경은 운영 상태를 바꾸므로 해당 작업이 필요한 경우에만 사용합니다. 이 관리 도구의 대상 인수와 애플리케이션 런타임의 앱 ID 검증은 별개입니다.

## 로컬 Gateway 복구

Cloud Run에서 Gateway로 전환하려면 Discord 앱의 Interaction Endpoint와 로컬 실행 상태를 일관되게 변경해야 합니다. 기존 HTTP endpoint를 확인하고 Gateway 전환 시 이를 비운 뒤, `.state/cloud-active.json`의 활성 표시를 실제 운영 상태와 맞춥니다. 클라우드와 로컬이 같은 요청을 동시에 처리하지 않는지 확인합니다.

로컬 자격 증명은 `Configure-Nuri.cmd`로 입력하고 `Check-Nuri.cmd`로 확인합니다. 코드의 대상 앱 ID와 실제 Discord 앱이 일치하는지 검토한 뒤 필요한 경우에만 명령을 등록합니다. 클라우드 복귀 시 기존 `/interactions` URL을 다시 설정하고 로컬 Gateway를 종료합니다. 토큰을 문서나 명령 인수에 붙여 넣지 않습니다.
