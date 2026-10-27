[Language selection](Home.md) · [한국어](Deployment.md) · [English](Deployment-en.md) · [简体中文](Deployment-zh-CN.md)

# Deployment

**Build once from a verified tag and deploy the same immutable image digest to ingress and worker.**

## Release traceability

```text
annotated tag
    └─ commit SHA
         └─ Cloud Build ID
              └─ image@sha256:…
                   ├─ ingress revision
                   └─ worker revision
```

This procedure updates images on existing services. It does not provision initial IAM access or enable billing. Use account, project, and service names verified by the operator.

## 1. Verify changes and create a tag

Run tests from the repository root and inspect staged files. Exclude `.state`, `.venv`, real `.env` files, credentials, private screenshots, and runtime state files.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
git diff --cached --check
git diff --cached --stat
git status --short
```

Align the project version and changelog, commit the changes, and push `main`. Check for an existing tag before creating and pushing a new annotated tag. Do not move an existing tag or force-push.

```powershell
$tag = 'v<version>'
git tag --list $tag
git ls-remote --tags origin $tag
# Run only if the checks above show that the tag does not exist.
git tag -a $tag -m "Nuri $tag"
git push origin $tag
```

## 2. Prepare clean tagged source

Create a detached worktree at an unused path. Do not copy local `.state` files or credentials into it.

```powershell
$releaseDir = '<absolute-path-to-new-release-checkout>'
git worktree add --detach $releaseDir $tag
git -C $releaseDir status --porcelain
git -C $releaseDir rev-parse HEAD
git rev-parse "$tag^{commit}"
```

`status --porcelain` must be empty, and both commit SHAs must match. Check the allowlists in `.gcloudignore` and `.dockerignore` so that only required build files are uploaded.

## 3. Build with the existing builder

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

`cloudbuild.yaml` builds and pushes the image only. After a successful build, record the resulting image digest. Deploy the `image@sha256:…` reference, rather than a mutable image tag.

## 4. Update both service images

Capture the existing configuration first. These commands change only the image. Verify that the worker is ready before updating ingress.

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

If traffic readiness takes time, check the deployment state and wait for completion. Do not deploy the same change again while it is pending. Compare the before-and-after configuration to verify minimum 0 / maximum 1 instance, request-based billing, CPU and memory, service accounts, environment and Secret Manager references, and IAM.

## 5. Verify and record the release

Perform the HTTP boundary checks and the real Discord menu test described in [Operations](Operations-en.md). Record these values with the release:

| Record | Value |
|---|---|
| Version / annotated tag | `<version>` / `v<version>` |
| Commit SHA | `<full-sha>` |
| Cloud Build ID | `<build-id>` |
| Image digest | `<image@sha256:…>` |
| ingress revision | `<revision>` |
| Worker revision | `<revision>` |
| Verification time and outcome | `<KST timestamp / result>` |
| Remaining limitation | First-request delay after idle periods with minimum zero instances |

If recovery is necessary, restore both service images using a previously verified digest and revision record. Do not rewrite tags or Git history to change the deployment record.

**Next:** [Operational verification →](Operations-en.md) · [Troubleshooting](Troubleshooting-en.md)
