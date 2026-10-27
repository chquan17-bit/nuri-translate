[Language selection](Home.md) · [한국어](Troubleshooting.md) · [English](Troubleshooting-en.md) · [简体中文](Troubleshooting-zh-CN.md)

# Troubleshooting

**Start with the symptom the user saw, then narrow the cause across ingress, the queue, the worker, and the model.**

## Symptom guide

| Symptom | Check first | Action |
|---|---|---|
| “The application did not respond” after a long idle period | ingress readiness and cold-start delay | Send one new request after the instance is ready |
| The response remains in the processing state | Worker readiness, queue delivery, completion events | Establish whether the model was called before repeatedly retrying |
| Only a mention appears, or Nuri says no text was found | Actual text in the selected message | Select the original message containing text, or use `/nuri` |
| Input is too long | Combined length of body and card text | Split the text into sections of at most 3,000 characters |
| Daily limit reached | KST date and number of reserved attempts | Wait until the next KST day |
| Another request is being processed | Active processing or an outstanding global lease | Wait for completion; after an abnormal exit, check the lease of up to 300 seconds |
| Google 429 | Model API quota | Wait, then retry manually if appropriate |
| Google 401 / 403 | Secret Manager reference and API project permissions | Check references, active secret versions, and access without exposing values |
| Google 5xx or timeout | Provider or connectivity failure | Check status, then retry a short sentence manually |
| Practice button expired | Ten-minute validity period | Run Nuri again to obtain a new button |
| Startup fails after deployment | Required environment and secret references | Compare `startup_configuration_invalid` with the previous working configuration |

## Investigate a cold-start failure

1. Verify that the latest revision has `Ready=True`.
2. Check whether ingress `/health` is reachable.
3. Look for a `command_accepted` event for the previous request.
4. Check whether the worker completed processing, then submit one new Discord request.

A successful request immediately after a health check uses an instance that is already running. It does not demonstrate that the first-request-after-idle limitation has been resolved.

## When 401, 403, and 404 are expected

| Request | Expected result | Reason |
|---|---|---|
| Unsigned ingress `/interactions` | 401 | Discord signature verification |
| Anonymous worker `/tasks` | 403 | Cloud Run IAM boundary |
| ingress `/tasks` | 404 | ingress has no task-processing route |

Do not disable authentication or make the worker public to address these expected responses.

## Attempt counts after a processing error

A request reserved before model processing counts toward the daily limit even if it fails. Redelivering the same interaction does not call the model again if the interaction was already reserved. Do not erase usage records or cancel reservations just because a response was not received.

## Record diagnostic evidence

Record the version, commit, revision, event time, HTTP status, and fixed event name. Do not include source text, translations, response tokens, API keys, or HTTP request bodies. Keep private screenshots out of Git and the documentation.

**Next:** [Back to operations →](Operations-en.md) · [Security and data](Security-en.md)
