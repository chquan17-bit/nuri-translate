[Language selection](Home.md) · [한국어](Home-ko.md) · [English](Home-en.md) · [简体中文](Home-zh-CN.md)

<div align="center">

# Nuri · Operations Guide

**Translate selected text, learn useful expressions, and practice with your own sentences.**

Discord · Python 3.13 · Cloud Run · Gemini

</div>

---

Nuri is a personal translation and English learning app for Discord. It processes messages you select or text you enter, and displays results only to the person who requested them. This guide covers everyday use, deployment, and troubleshooting.

> [!NOTE]
> This Wiki is provided inside the repository. The private GitHub Wiki tab is restricted on the current plan. Publishing these documents did not require a plan upgrade or a change to repository visibility.

## Start with your task

| Goal | Guide | What it covers |
|---|---|---|
| Use Nuri for the first time | [Getting started](Getting-Started-en.md) | Message menus, `/nuri`, sentence practice |
| Understand request processing | [Architecture](Architecture-en.md) | ingress → queue → worker, duplicate prevention |
| Check the running system | [Operations](Operations-en.md) | Cost settings, limits, logs, verification |
| Deploy a version | [Deployment](Deployment-en.md) | Tag → commit → image → both services |
| Investigate a problem | [Troubleshooting](Troubleshooting-en.md) | Cold starts, limits, signatures, response errors |
| Understand data handling | [Security and data](Security-en.md) | Credentials, temporary processing, stored data |

## Three ways to use Nuri

The Discord interface uses the Korean command and button labels shown below.

| Feature | Input | Result |
|---|---|---|
| **Nuri 번역** — Translate | Selected or manually entered text | Translation → source |
| **Nuri와 영어 배우기** — Learn English with Nuri | Selected or manually entered text | Translation → up to two reusable expressions → source |
| **한 문장 써보기** — Try writing a sentence | Text entered through the learning result's button | Corrected sentence → one key explanation → your sentence |

Nuri reads the message body together with the text in card titles, descriptions, and fields. It does not automatically retrieve images, attachment contents, or external pages linked in the message.

## Current operating policy

| Area | Policy |
|---|---|
| Runtime | Separate public HTTP ingress and private worker |
| Access | Verify Discord request signatures; allow only the owner |
| Service sizing | Both services: request-based billing, minimum 0 / maximum 1 instance, 1 CPU / 512 MiB |
| Usage | 25 attempts per day, 10 seconds between requests, one model request at a time |
| Duplicate prevention | Reserve in Firestore before calling the model; never regenerate the same interaction |
| Releases | Build from a clean annotated-tag checkout; deploy the same image digest to both services |

> [!IMPORTANT]
> With a minimum of zero instances, the first request after a long idle period can exceed Discord's three-second response deadline while ingress starts. This remains a limitation of the current operating configuration.

## Documentation and release records

The documentation source is maintained in `docs/wiki/` in the repository. Code defaults and deployed settings are separate: use each release's commit SHA, build ID, image digest, and revision records to identify what was deployed. Examples omit real keys, personal accounts, and cloud project identifiers.

**Next:** [Getting started →](Getting-Started-en.md)
