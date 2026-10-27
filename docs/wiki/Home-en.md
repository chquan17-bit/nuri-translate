[Language selection](Home.md) · [한국어](Home-ko.md) · [English](Home-en.md) · [简体中文](Home-zh-CN.md)

<div align="center">

# Nuri · Operations Guide

**Translate selected text, learn reusable expressions, and practice with your own sentences.**

Discord · Python 3.13 · Cloud Run · Gemini

</div>

---

Nuri is a personal translation and English learning app used in Discord. It processes selected messages or directly entered text, displaying the results only to the requester. This Wiki is an operational manual covering everything from usage to deployment and incident response.

> [!NOTE]
> [Official GitHub Wiki](https://github.com/chquan17-bit/nuri-translate/wiki) provides guides in three languages. Making the source code and documentation public does not change bot permissions or cloud settings. The running bot can only be used by its owner, and results are shown only to the requester.

## Start with your desired task

| Purpose | Guide | Key Content |
|---|---|---|
| Getting Started | [Getting Started](Getting-Started-en.md) | Message Menu, `/nuri`, One-Sentence Practice |
| Understanding the Process | [Architecture](Architecture-en.md) | ingress → queue → worker, deduplication |
| Checking Regular Status | [Operations](Operations-en.md) | Cost settings, limits, logs, verification |
| Deploying Versions | [Deployment](Deployment-en.md) | Tag → commit → image → two services |
| When Issues Occur | [Troubleshooting](Troubleshooting-en.md) | Initial startup delay, limits, signature, response errors |
| Checking Data Boundaries | [Security and Data](Security-en.md) | Secrets, temporary processing, storage scope |

## Three Ways to Use

| Feature | Input | Result |
|---|---|---|
| **Nuri 번역** | Selected text or directly entered text | Translation → Original text |
| **Nuri와 영어 배우기** | Selected text or directly entered text | Translation → Up to 2 reusable expressions → Original text |
| **한 문장 써보기** | Input from the button on the learning result | Corrected sentence → One key explanation → Your sentence |

Read the message body and the card's title, description, and item text together. Images, attachments, and external link pages are not automatically collected.

## Current Operating Principles

| Item | Standard |
|---|---|
| Execution | Separate public HTTP ingress and private worker |
| Access | Verify Discord request signatures, owner-only use |
| Service Size | Both services are request-based, min 0 · max 1, CPU 1 · 512 MiB |
| Usage | Daily requests: 25 · Request interval: 10 seconds · Concurrent model requests: 1 |
| Deduplication | Model call after Firestore reservation, preventing recreation of the same interaction |
| Release | Build from clean source of annotated tag, deploy same digest to both services |

> [!IMPORTANT]
> Minimum instances 0 are maintained, so the first request after a long idle period may exceed Discord's 3-second response limit due to startup delay. This is a remaining limitation in current operations.

## Documentation and Release History

Wiki document sources are managed in the `docs/wiki/` folder within this repository. Code defaults and current operational settings are distinguished, and actual deployment results are tracked via release-specific commit SHA, build ID, image digest, and revision records. Document examples do not include actual keys, personal accounts, or cloud project identifiers.

When changes to the Korean source are merged or pushed to the `main` branch, GitHub Actions translates the changed body into English and Simplified Chinese and updates the three-language Wikis together. If translation or link verification fails, the existing Wiki is kept. For writing locations and re-execution methods, refer to the [Documentation Automation Guide](../WIKI-AUTOMATION.md).

**Next:** [Getting Started →](Getting-Started-en.md)
