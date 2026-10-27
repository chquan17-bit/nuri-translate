[언어 선택](Home.md) · [한국어](Deployment.md) · [English](Deployment-en.md) · [简体中文](Deployment-zh-CN.md)

# 배포

**검증한 태그의 소스에서 한 번 빌드하고, 같은 immutable image digest를 ingress와 worker에 배포합니다.**

## 릴리스 추적 관계

```text
annotated tag
    └─ commit SHA
         └─ Cloud Build ID
              └─ image@sha256:…
                   ├─ ingress revision
                   └─ worker revision
```

이 문서는 기존 서비스의 이미지 업데이트 절차입니다. 최초 IAM 구성이나 결제 활성화 절차는 포함하지 않습니다. 실제 계정·프로젝트·서비스 이름은 운영자가 확인한 값으로 지정합니다.

## 1. 변경 검증과 태그

저장소 루트에서 테스트를 실행하고 staged 파일을 확인합니다. `.state`, `.venv`, 실제 `.env`, 자격 증명, 개인 화면, 런타임 상태 파일은 포함하지 않습니다.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
git diff --cached --check
git diff --cached --stat
git status --short
```

프로젝트 버전과 변경 기록을 맞춘 뒤 커밋하고 `main`을 push합니다. 태그가 이미 존재하는지 먼저 확인하고 새 annotated tag를 push합니다. 기존 태그를 옮기거나 강제 push하지 않습니다.

```powershell
$tag = 'v<version>'
git tag --list $tag
git ls-remote --tags origin $tag
# 위 확인에서 같은 태그가 없을 때만 실행
git tag -a $tag -m "Nuri $tag"
git push origin $tag
```

## 2. 깨끗한 태그 소스 준비

빈 경로에 detached worktree를 만듭니다. 로컬 `.state`와 자격 증명을 복사하지 않습니다.

```powershell
$releaseDir = '<absolute-path-to-new-release-checkout>'
git worktree add --detach $releaseDir $tag
git -C $releaseDir status --porcelain
git -C $releaseDir rev-parse HEAD
git rev-parse "$tag^{commit}"
```

`status --porcelain`이 비어 있고 두 commit SHA가 일치해야 합니다. `.gcloudignore`와 `.dockerignore`의 허용 목록을 확인해 필요한 빌드 파일만 전달합니다.

## 3. 기존 빌더로 빌드

```powershell
$account = '<personal-google-account>'
$project = '<runtime-project-id>'
$region = 'asia-northeast3'
$builder = '<existing-builder-service-account-email>'
$sourceBucket = 'gs://<existing-source-bucket>/source'
$image = "$region-docker.pkg.dev/$project/<repository>/<image>:$tag"

gcloud builds submit $releaseDir `
  --config "$releaseDir/cloudbuild.yaml" `
  --substitutions "_IMAGE=$image" `
  --service-account "projects/$project/serviceAccounts/$builder" `
  --gcs-source-staging-dir $sourceBucket `
  --region $region `
  --account $account --project $project
```

`cloudbuild.yaml`은 빌드와 이미지 push만 수행합니다. 빌드 성공 후 결과의 image digest를 기록합니다. 배포는 가변 image tag 대신 `image@sha256:…` 주소를 사용합니다.

## 4. 두 서비스의 이미지 업데이트

기존 설정을 먼저 보관하고, 아래 명령에서는 이미지만 변경합니다. worker 준비 완료를 확인한 뒤 ingress를 업데이트합니다.

```powershell
$worker = '<existing-worker-service>'
$ingress = '<existing-ingress-service>'
$digest = '<registry-path/image@sha256:digest>'

gcloud run services update $worker --image $digest --region $region `
  --account $account --project $project

gcloud run services describe $worker --region $region `
  --account $account --project $project --format=json

gcloud run services update $ingress --image $digest --region $region `
  --account $account --project $project

gcloud run services describe $ingress --region $region `
  --account $account --project $project --format=json
```

트래픽 준비에 시간이 걸리면 상태를 확인하며 완료를 기다립니다. 같은 변경을 중복 배포하지 않습니다. min 0 / max 1, 요청 기반, CPU·메모리, 서비스 계정, env·Secret Manager 참조, IAM이 유지되었는지 비교합니다.

## 5. 검증과 기록

[운영](Operations.md)의 HTTP 경계 검사와 실제 Discord 메뉴 검증을 수행합니다. 다음 항목을 릴리스 결과에 남깁니다.

| 기록 | 값 |
|---|---|
| 버전 / annotated tag | `<version>` / `v<version>` |
| commit SHA | `<full-sha>` |
| Cloud Build ID | `<build-id>` |
| image digest | `<image@sha256:…>` |
| ingress revision | `<revision>` |
| worker revision | `<revision>` |
| 검증 시각과 결과 | `<KST timestamp / result>` |
| 남은 제한 | min 0에 따른 유휴 뒤 첫 요청 지연 |

복구가 필요하면 이전에 검증한 digest와 revision 기록을 기준으로 두 서비스의 이미지를 되돌립니다. 태그나 Git 이력을 덮어써서 배포 기록을 수정하지 않습니다.

**다음:** [운영 검증 →](Operations.md) · [문제 해결](Troubleshooting.md)
