[选择语言](Home.md) · [한국어](Deployment.md) · [English](Deployment-en.md) · [简体中文](Deployment-zh-CN.md)

# 版本部署

**从已验证标签对应的源码构建一次，再将相同、不可变的 image digest 部署至 ingress 和 worker。**

## 发布追踪关系

```text
附注标签（annotated tag）
    └─ commit SHA
         └─ Cloud Build ID
              └─ image@sha256:…
                   ├─ ingress revision
                   └─ worker revision
```

本文说明现有服务的镜像更新流程，不包含首次 IAM 配置或开启结算的操作。账号、项目和服务名称必须使用运维人员已确认的值。

## 1. 验证变更并创建标签

在仓库根目录运行测试并检查暂存文件。不要包含 `.state`、`.venv`、真实 `.env`、凭据、个人截图或运行状态文件。

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
git diff --cached --check
git diff --cached --stat
git status --short
```

核对项目版本与变更记录，提交后推送 `main`。先检查目标标签是否已存在，再创建并推送新的附注标签。不要移动已有标签或强制推送。

```powershell
$tag = 'v<version>'
git tag --list $tag
git ls-remote --tags origin $tag
# 仅在上述检查确认同名标签不存在时执行
git tag -a $tag -m "Nuri $tag"
git push origin $tag
```

## 2. 准备干净的标签源码

在新路径创建 detached worktree。不要复制本地 `.state` 或凭据。

```powershell
$releaseDir = '<absolute-path-to-new-release-checkout>'
git worktree add --detach $releaseDir $tag
git -C $releaseDir status --porcelain
git -C $releaseDir rev-parse HEAD
git rev-parse "$tag^{commit}"
```

`status --porcelain` 应无输出，两个 commit SHA 应一致。检查 `.gcloudignore` 与 `.dockerignore` 的允许列表，仅传递构建所需的文件。

## 3. 使用现有构建身份

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

`cloudbuild.yaml` 仅负责构建与推送镜像。构建成功后记录结果中的 image digest。部署时使用 `image@sha256:…` 地址，不使用可变的镜像标签。

## 4. 更新两个服务的镜像

先保存现有配置，以下命令只更新镜像。确认 worker 就绪后，再更新 ingress。

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

如果流量准备较慢，应检查状态并等待完成，不要重复部署相同变更。对比确认 min 0 / max 1、按请求计费、CPU 和内存、服务账号、环境变量、Secret Manager 引用与 IAM 均得到保留。

## 5. 验证与记录

执行[运行维护](Operations-zh-CN.md)中的 HTTP 边界检查，并在真实 Discord 消息菜单中验证一次。发布结果应记录以下信息：

| 记录项 | 值 |
|---|---|
| 版本 / 附注标签 | `<version>` / `v<version>` |
| commit SHA | `<full-sha>` |
| Cloud Build ID | `<build-id>` |
| image digest | `<image@sha256:…>` |
| ingress revision | `<revision>` |
| worker revision | `<revision>` |
| 验证时间与结果 | `<KST timestamp / result>` |
| 剩余限制 | min 0 导致空闲后的首次请求延迟 |

需要回退时，以先前已验证的 digest 和 revision 记录为依据，恢复两个服务的镜像。不要通过覆盖标签或 Git 历史来修改部署记录。

**下一步：**[运行验证 →](Operations-zh-CN.md) · [故障排查](Troubleshooting-zh-CN.md)
