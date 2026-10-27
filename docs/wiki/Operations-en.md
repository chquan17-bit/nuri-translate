[Language selection](Home.md) · [한국어](Operations.md) · [English](Operations-en.md) · [简体中文](Operations-zh-CN.md)

# Operations

**Check readiness, matching images, cost settings, and access boundaries for both services.**

## Operating baseline

| Area | Baseline | Purpose |
|---|---|---|
| ingress / worker | Request-based billing, minimum 0 / maximum 1 instance | No continuously running idle instance |
| Resources | 1 CPU / 512 MiB | Preserve existing service sizing |
| Traffic | 100% to the ready revision | Distinguish a pending deployment from the active version |
| Image | Matching digest on both services | Keep request handling and processing on the same code version |
| Model | Configured Gemini model and existing free-tier status | Avoid an unintended paid-tier transition |
| Usage | 25 attempts per day, 10-second interval, one model request at a time | Enforce shared usage controls |
| Access | Public ingress; worker restricted through IAM | Separate the Discord entry point from task execution |

These values describe the current operating configuration. An image update must not silently change billing mode, service accounts, IAM, environment variables, or Secret Manager references.

## Verify a deployment

1. Confirm `Ready=True` and `latestReadyRevisionName` for both services.
2. Check that actual traffic points to the new revisions.
3. Compare each revision's image digest with the release record.
4. Confirm that unsigned ingress requests and anonymous worker requests are rejected.
5. Translate one real Discord card message and check both the content and response visibility.

Use `scripts/verify_cloud_boundaries.py` for HTTP checks. It does not call the model. Supply the deployed URLs and the intended Discord application ID:

```powershell
.\.venv\Scripts\python.exe scripts/verify_cloud_boundaries.py `
  --ingress-url 'https://<ingress-service>.run.app' `
  --worker-url 'https://<worker-service>.run.app' `
  --application-id '<discord-application-id>' `
  --output '.state/cloud-boundary-verification.json'
```

`--output` is optional; its default is `.state/cloud-boundary-verification.json`. Parent directories are created if needed. Instead of `--application-id`, set `NURI_APPLICATION_ID` in the process environment. Use the service base URLs without a route or query string.

| Check | Expected response |
|---|---|
| ingress `/health` | 200 |
| ingress `/tasks` | 404 |
| Unsigned `/interactions` | 401 |
| Forged-signature `/interactions` | 401 |
| Anonymous worker `/tasks` | 403 |

## Read application logs

Application logs contain short events describing processing stages and outcomes. Do not add source text, translations, keys, or tokens to logs.

| Event | Meaning |
|---|---|
| `command_accepted` | ingress submitted the task to the queue |
| `translation_completed` | Model results were delivered to Discord |
| `translation_rejected` | An expected rejection during input, quota, model, or response-delivery processing |
| `translation_failed` | An unexpected task-processing error |
| `quota_lease_release_failed` | Shared-lease cleanup failed after processing |
| `startup_configuration_invalid` | Required startup configuration failed validation |

`command_accepted` alone does not prove that translation succeeded. Check `translation_completed` and the result visible to the user.

## Usage and cost

A new daily count begins at midnight in Korea Standard Time (KST). An attempt reserved before model processing is not refunded if it fails, because the external service may already have processed it.

To inspect today's numeric usage with the maintenance script, explicitly identify the account and project:

```powershell
.\.venv\Scripts\python.exe scripts/cloud_usage.py inspect `
  --account '<personal-google-account>' --project '<runtime-project-id>'
```

`NURI_GCLOUD_ACCOUNT` and `NURI_CLOUD_PROJECT` are the corresponding environment alternatives. The script locates gcloud through PATH and passes both values explicitly; it does not change global gcloud configuration. The `seed` mode migrates local usage and changes shared state, so ordinary status checks should use `inspect`.

> [!IMPORTANT]
> A daily request limit is not a monetary spending cap. Even with minimum zero instances and request-based billing, build, image storage, networking, and other cloud usage can incur separate costs. Verify free-tier status in the relevant service's management interface.

## Cold-start limitation

After an idle period, ingress startup can cause the first request to exceed Discord's three-second deadline. Follow the cold-start procedure in [Troubleshooting](Troubleshooting-en.md). An always-running instance or periodic wake-up task is not part of the current operating configuration.

**Next:** [Deployment →](Deployment-en.md) · [Troubleshooting](Troubleshooting-en.md)
