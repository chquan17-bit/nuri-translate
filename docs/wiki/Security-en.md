[Language selection](Home.md) · [한국어](Security.md) · [English](Security-en.md) · [简体中文](Security-zh-CN.md)

# Security and Data

**Send selected text only through the required processing path, and distinguish access, storage, and logging boundaries.**

## Access boundaries

| Boundary | Control |
|---|---|
| Discord → ingress | Verify Ed25519 signature, timestamp, and application ID |
| User → feature | Check the configured owner ID |
| Practice button → modal | HMAC signature containing the owner and expiry time |
| Cloud Tasks → worker | OIDC service identity and Cloud Run IAM |
| Worker → Gemini | API key supplied through Secret Manager |
| Result → Discord | Private interaction response with mentions disabled |

Cloud Run IAM authenticates access to the worker. The application does not treat a caller as authenticated merely because a request header contains a particular value. The worker's `/tasks` route is not registered on ingress.

## Where data is processed or stored

| Location | Data involved | Operating policy |
|---|---|---|
| Discord interaction | User-selected or entered text and a response token | Validate, then forward only required task data |
| Cloud Tasks | Source text to process and a short-lived response token | Temporary storage for task delivery |
| Gemini API | Text to translate or correct | Generation request only; no external tools or search |
| Application memory | Source text, model results, credentials used for calls | Used during processing |
| Firestore | KST date, counts, hashed request markers, lease timestamps | No source text, translations, user IDs, or credentials |
| Application logs | Fixed events describing outcomes and processing stages | No source text, translations, keys, or tokens |
| Local `.state` | Recovery configuration, local usage, diagnostic state | Excluded from Git and build uploads |

Data retention by Discord and Google services is separate from the storage controlled by this application. A private Discord response does not mean that processing avoids external services.

## Model input and output

Source text is sent as the `source` data field of a JSON envelope. The model is instructed to treat instructions, role changes, URLs, and commands within that field as text to translate. No search, tool execution, or link-retrieval capability is provided.

Model output is checked for JSON structure and string lengths. An invalid format or an incomplete generation is treated as an error. Before display in Discord, Markdown in the source and result is escaped and automatic mentions are disabled.

## Credential management

- Cloud Run uses existing service accounts and Secret Manager references. Do not add long-lived service account keys to the repository or GitHub.
- Cloud HTTP processing uses Discord interaction responses, so the Bot Token used by the local Gateway does not need to be deployed.
- Windows recovery configuration is encrypted with DPAPI for the same Windows user context. Encrypted credential files must still stay out of Git.
- After key rotation, record secret references, versions, and verification outcomes rather than secret values.

## Files excluded from the repository

Exclude real `.env` files, `.state`, `.venv`, API keys, tokens, DPAPI files, private screenshots, local status JSON, and operational evidence. Inspect the staged file list and diff instead of relying solely on `.gitignore`. Build from clean tagged source using a restricted upload allowlist.

See the [HTTP checks in Operations](Operations-en.md) to verify the access boundaries, and [Troubleshooting](Troubleshooting-en.md) for guidance on recording a problem.
