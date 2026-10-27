[Language selection](Home.md) · [한국어](Home-ko.md) · [English](Home-en.md) · [简体中文](Home-zh-CN.md)

<div align="center">

# Nuri · Operations Guide

**Translate selected text, learn alternative expressions, and practice with your own sentences.**

Discord · Python 3.13 · Cloud Run · Gemini

</div>

---

Nuri is a personal translation and English learning app used in Discord. It processes selected messages or manually entered text, and displays the results only to the requester. This Wiki is an operational manual covering everything from usage to deployment and incident response.

> [!NOTE]
> [Official GitHub Wiki](https://github.com/chquan17-bit/nuri-translate/wiki) provides guides in three languages. Making the source code and documentation public does not change bot usage permissions or cloud settings. The running bot can only be used by its owner, and results are displayed only to the requester.

## Start with the task you want

| Purpose | Guide | Key Content |
|---|---|---|
| Get Started | [Getting Started](Getting-Started-en.md) | Message menu, `/nuri`, Single sentence practice |
| Understand Processing | [Architecture](Architecture-en.md) | ingress → queue → worker, duplicate prevention |
| Check Status | [Operations](Operations-en.md) | Cost settings, limits, logs, validation |
| Deploy Version | [Deployment](Deployment-en.md) | Tag → commit → image → two services |
| Troubleshooting | [Troubleshooting](Troubleshooting-en.md) | Initial startup delay, limits, signatures, response errors |
| Check Data Boundaries | [Security and Data](Security-en.md) | Secrets, temporary processing, storage scope |

## Three Modes of Use

| Feature | Input | Result |
|---|---|---|
| **Nuri 번역** | Selected text or directly entered text | Translation → Original text |
| **Nuri와 영어 배우기** | Selected text or directly entered text | Translation → Up to 2 alternative expressions → Original text |
| **한 문장 써보기** | Input from learning result button | Corrected sentence → One key explanation → My sentence |

Reads the message body and card titles, descriptions, and item texts together. It does not automatically collect images, attachments, or external pages from links.

## Current Operational Principles

| Item | Standard |
|---|---|
| Execution | Separate public HTTP ingress and private worker |
| Access | Discord request signature verification, owner-only use |
| Service Size | Both services request-based, min 0 · max 1, CPU 1 · 512 MiB |
| Usage | 25times/day · 10s between requests · 1concurrent model processing |
| Duplicate Handling | Model call after Firestore reservation, preventing regeneration of the same interaction |
| Release | Build from clean source of annotated tag, deploy identical digest to both services |

> [!IMPORTANT]
> Minimum instances 0 are maintained, so the first request after a long idle period may exceed Discord's 3s response limit due to startup delay. This is a remaining limitation in current operations.

## Documentation and Release History

The original Wiki is managed in the `docs/wiki/` repository. Code defaults and current operational settings are separated, and actual deployment results are verified through release-specific commit SHA, build ID, image digest, and revision records. Document examples do not include actual keys, personal accounts, or cloud project identifiers.

Modifying the Korean original and reflecting it in `main` causes GitHub Actions to translate the changed text into English and Simplified Chinese and update all three language Wikis together. If translation or link validation fails, the existing Wiki is maintained. For writing locations and re-execution methods, refer to the [Documentation Automation Guide](../WIKI-AUTOMATION.md).

**Next:** [Getting Started →](Getting-Started-en.md)
