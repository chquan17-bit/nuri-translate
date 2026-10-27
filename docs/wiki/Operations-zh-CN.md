[选择语言](Home.md) · [한국어](Operations.md) · [English](Operations-en.md) · [简体中文](Operations-zh-CN.md)

# 运行维护

**同时检查两个服务的就绪状态、镜像一致性、成本配置与访问边界。**

## 运行标准

| 类别 | 标准 | 检查目的 |
|---|---|---|
| ingress / worker | 按请求计费，最少 0 / 最多 1 个实例 | 空闲时不保持常驻实例 |
| 资源 | 1 CPU / 512 MiB | 保留现有服务规格 |
| 流量 | 100% 指向已就绪的 revision | 区分未完成部署与实际流量 |
| 镜像 | 两个服务使用相同 digest | 保持接收与处理代码版本一致 |
| 模型 | 配置中的 Gemini 模型，保留现有免费层级 | 不擅自转为付费使用 |
| 用量 | 每天 25 次，间隔 10 秒，同时处理 1 个模型请求 | 通过共享状态控制使用 |
| 访问 | 公开 ingress / IAM 限制的 worker | 分离 Discord 入口与任务执行 |

这些值是当前运行标准。发布过程中，不应将计费模式、服务账号、IAM、环境变量或 Secret Manager 引用的变更混入镜像更新。

## 部署后检查

1. 确认两个服务的 `Ready=True` 与 `latestReadyRevisionName`。
2. 确认实际流量指向新 revision。
3. 对比 revision 的 image digest 与发布记录。
4. 确认无签名的 ingress 请求和匿名 worker 请求被拒绝。
5. 在 Discord 中对一条真实卡片消息执行一次翻译，检查内容与可见范围。

HTTP 边界检查使用 `scripts/verify_cloud_boundaries.py`，不会调用模型。选项详情见脚本的 `--help` 和仓库部署指南。

```powershell
.\.venv\Scripts\python.exe scripts/verify_cloud_boundaries.py `
  --ingress-url '<ingress-url>' --worker-url '<worker-url>' `
  --application-id '<discord-application-id>' `
  --output '.state/cloud-boundary-verification.json'
```

`--output` 为可选参数，默认值是 `.state/cloud-boundary-verification.json`；必要时会自动创建上级目录。也可以通过进程环境变量 `NURI_APPLICATION_ID` 代替 `--application-id`。URL 应为不带路径或查询字符串的服务基础地址。

管理脚本通过明确的参数，或 `NURI_APPLICATION_ID`、`NURI_CLOUD_PROJECT`、`NURI_GCLOUD_ACCOUNT` 环境变量接收配置，不依赖 gcloud 的默认账号或项目。这些是管理脚本的设置，不会修改现有 Cloud Run 运行配置。

| 检查项 | 预期结果 |
|---|---|
| ingress `/health` | 200 |
| ingress `/tasks` | 404 |
| 无签名的 `/interactions` | 401 |
| 伪造签名的 `/interactions` | 401 |
| 匿名 worker `/tasks` | 403 |

## 阅读日志

应用日志只记录表示阶段与结果的简短事件，不应添加原文、译文、密钥或令牌。

| 事件 | 含义 |
|---|---|
| `command_accepted` | ingress 已将任务送入队列 |
| `translation_completed` | 模型结果已成功发送给 Discord |
| `translation_rejected` | 输入、限额、模型或结果发送阶段发生可处理的拒绝 |
| `translation_failed` | 未预期的任务错误 |
| `quota_lease_release_failed` | 处理结束后的共享租约清理失败 |
| `startup_configuration_invalid` | 必需的启动配置校验失败 |

不能仅凭 `command_accepted` 就判断翻译成功。应结合 `translation_completed` 与用户实际看到的结果确认。

## 用量与费用

每日计数从 KST 午夜开始计算。模型处理前已预约的请求即使失败，也不返还次数，因为外部服务可能已经处理了请求。

查询当天用量时，明确指定账号和项目：

```powershell
.\.venv\Scripts\python.exe scripts/cloud_usage.py inspect `
  --account '<personal-google-account>' --project '<runtime-project-id>'
```

对应的环境变量为 `NURI_GCLOUD_ACCOUNT` 和 `NURI_CLOUD_PROJECT`。脚本通过 PATH 查找 gcloud，明确传入这两个值，不会更改全局配置。`seed` 模式会迁移本地用量并修改共享状态，日常状态检查应使用 `inspect`。

> [!IMPORTANT]
> 每日次数限制不是金额上限。即使保持最少 0 个实例和按请求计费，构建、镜像存储、网络及其他云资源的费用仍需单独检查。免费层级状态应在管理界面中确认。

## 冷启动限制

空闲后的首次请求可能因 ingress 启动而超过 Discord 的 3 秒期限。遇到这种情况，请按[故障排查](Troubleshooting-zh-CN.md)中的冷启动步骤确认。当前运行方式不包含常驻待机实例或周期性唤醒任务。

**下一步：**[版本部署 →](Deployment-zh-CN.md) · [故障排查](Troubleshooting-zh-CN.md)
