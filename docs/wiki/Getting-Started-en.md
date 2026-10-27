[Language selection](Home.md) · [한국어](Getting-Started.md) · [English](Getting-Started-en.md) · [简体中文](Getting-Started-zh-CN.md)

# Getting Started

**With Nuri installed in Discord, select a message or enter text with `/nuri`.**

## 1. Translate a selected message

1. Right-click a message, or press and hold it on mobile.
2. In the **Apps** menu, choose **Nuri 번역** (Translate).
3. Read the translation and source in the response visible only to you.

English text is translated into Korean, and Korean text into English. For other languages, the model is instructed to translate into Korean.

For card-style messages, Nuri combines the `content` and the text in embed `title`, `description`, and `fields` supplied by Discord. Exact duplicate text blocks are included once, and mention syntax is removed from the source. If the message contains only mentions or no readable text, Nuri explains the problem before calling the model.

## 2. Learn useful expressions

Choose **Nuri와 영어 배우기** (Learn English with Nuri) to see up to two reusable English expressions after the translation. Translation and learning notes are kept separate, and the source remains visible for comparison.

To enter text directly, paste it into the `text` option of `/nuri` and choose translation or English learning in `mode`.

## 3. Practice with your own sentence

Select **한 문장 써보기** (Try writing a sentence) beneath a learning result and enter an English sentence. Nuri returns a more natural version and one explanation of the most useful correction. The button expires after ten minutes; run Nuri again to start a new practice session.

## Input and output limits

| Item | Limit or behavior |
|---|---|
| Translation and learning input | Up to 3,000 characters in total |
| Practice sentence | Up to 1,000 characters |
| Long output | Split into at most six messages within Discord's UTF-16 message limits |
| Content not retrieved | Image contents, attachment contents, external linked pages |
| Response visibility | Visible only to the requester; automatic mentions disabled |

> [!NOTE]
> “Visible only to you” describes the Discord response's audience. The text to translate is sent to the Google API for processing. See [Security and data](Security-en.md) for details.

## Verify a development environment

Install Python 3.13 and `uv`, then run these commands from the repository root:

```powershell
uv --cache-dir .state/uv-cache sync --frozen
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -m nuri doctor
```

`doctor` checks whether credentials are present without making external requests. `.env.example` lists environment variable names; it is not loaded automatically.

On Windows, `Configure-Nuri.cmd` encrypts credentials for local recovery using DPAPI. There is no need to start a separate local Gateway while Cloud Run is operating normally. Moving to a different Discord app requires reviewing the application ID checks in the code as well as environment settings: the runtime remains specific to the Nuri app. The maintenance scripts' configurable application ID does not change that runtime check.

**Next:** [Architecture →](Architecture-en.md) · [Troubleshooting](Troubleshooting-en.md)
