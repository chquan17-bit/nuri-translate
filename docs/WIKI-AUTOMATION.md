# Wiki 자동 번역과 게시

[한국어](#한국어) · [English](#english) · [简体中文](#简体中文)

[Wiki](https://github.com/chquan17-bit/nuri-translate/wiki) · [실행 기록 / Workflow runs / 运行记录](https://github.com/chquan17-bit/nuri-translate/actions/workflows/wiki-sync.yml)

## 한국어

한국어 Wiki 원본을 수정해 `main`에 반영하면, GitHub Actions가 변경된 내용을 영어와 중국어 간체로 번역하고 세 언어 문서를 GitHub Wiki에 함께 게시합니다. 이 기능은 저장소의 Actions secret `WIKI_GEMINI_API_KEY` 설정이 필요합니다.

### 수정할 파일

| 대상 | 작성자가 수정할 원본 | 자동 처리 |
|---|---|---|
| 언어별 홈 | `docs/wiki/Home-ko.md` | `Home-en.md`, `Home-zh-CN.md` 번역 |
| 문서 본문 | `docs/wiki/Architecture.md` 등 접미사가 없는 한국어 페이지 | 대응하는 `-en.md`, `-zh-CN.md` 번역 |
| 구조도 | `docs/assets/*-ko.svg` | 텍스트를 영어·중국어로 번역하고 Wiki용 이미지 생성 |
| 공통 메뉴 | `docs/wiki/Home.md`, `_Sidebar.md`, `_Footer.md` | 작성된 세 언어 내용을 그대로 게시 |
| README·배포 참고 문서 | 저장소의 해당 파일 | Wiki 본문으로 자동 복사하지 않음 |

기능이나 운영 방식이 바뀌면 해당 한국어 Wiki 원본도 함께 수정합니다. 영어·중국어 문서와 `docs/wiki-translations.json`은 워크플로가 갱신합니다. 공통 메뉴는 세 언어를 한 파일에서 관리하므로 문구를 바꿀 때 세 언어를 함께 수정하세요. 새 주제를 추가할 때는 한국어 페이지와 공통 메뉴의 연결도 추가합니다.

다른 언어로 번역되는 절을 `#fragment`로 연결할 때는 한국어 원본의 해당 제목 앞에 `<a id="stable-section"></a>`처럼 고정 ID를 두고 그 ID로 링크합니다. 제목을 번역해도 ID는 유지됩니다.

### 자동 처리 순서

1. `main`의 최신 문서를 확인하고 원본·번역 파일의 해시를 비교합니다. 변경이 없으면 모델을 호출하지 않습니다.
2. 필요한 한국어 페이지와 구조도 텍스트만 Gemini `gemini-3.5-flash-lite`로 번역합니다. 코드와 링크 대상 등 보호할 내용은 유지합니다.
3. 번역 결과의 형식과 문서 링크를 검사합니다. 실패하거나 결과가 잘리면 Wiki 게시를 중단하고 기존 Wiki를 유지합니다.
4. 생성된 번역과 해시 기록을 저장소에 커밋합니다. Wiki의 페이지·사이드바·푸터·이미지를 갱신하고 기존 Git 이력을 유지합니다.

PR 검증은 모델 호출이나 Wiki 게시 없이 수행합니다. 실제 번역과 쓰기 작업은 신뢰된 `main`에서 실행합니다. 실패 원인을 해결한 뒤 Actions의 `Wiki sync`에서 **Run workflow**로 다시 실행할 수 있습니다.

### 자격 증명과 사용량

저장소 **Settings → Secrets and variables → Actions**에 `WIKI_GEMINI_API_KEY`를 등록합니다. 키 값은 소스 파일이나 이 문서에 적지 않습니다. 워크플로는 이 값을 실행 중 `GEMINI_API_KEY`로 전달하고, Wiki 게시에는 GitHub가 작업별로 발급하는 `GITHUB_TOKEN`을 사용합니다. Wiki용 개인 PAT는 필요하지 않습니다.

번역 요청은 공개 문서 내용을 Google Gemini API로 보냅니다. 봇과 같은 Google 프로젝트의 키를 사용하면 문서 번역도 해당 프로젝트의 모델 할당량을 사용합니다. 이 워크플로는 유료 사용을 활성화하거나 봇의 배포·IAM·인스턴스 설정을 변경하지 않습니다. 할당량 초과 등으로 실패하면 실행 기록을 확인하고 재실행하세요.

### 검증과 수정 원칙

저장소 루트에서 실행할 수 있는 오프라인 검사는 다음과 같습니다.

```powershell
python -m unittest discover -s tests -p 'test_*wiki*.py' -v
python scripts/sync_wiki.py --root . --check
python scripts/translate_wiki.py --root . --check
```

마지막 명령은 번역 해시가 최신인지 확인합니다. 한국어 원본을 수정한 직후에는 번역 대기 상태를 보고할 수 있으며, 번역을 실행하지 않습니다. `--seed`는 검토를 마친 기존 번역을 최초 기준으로 등록할 때만 사용합니다.

문서의 기준은 저장소입니다. Wiki 화면에서 직접 수정한 내용은 다음 성공한 동기화 때 원본으로 대체될 수 있습니다. 자동 검증은 번역의 의미까지 보증하지 않으므로 중요한 사용법·운영·보안 문구는 생성된 번역을 검토하세요. 구조도 텍스트를 크게 늘렸다면 영어·중국어 이미지의 줄바꿈과 배치도 확인합니다.

## English

Edit the Korean Wiki source and merge or push it to `main`. GitHub Actions translates changed content into English and Simplified Chinese, then publishes all three languages to the native GitHub Wiki. The repository Actions secret `WIKI_GEMINI_API_KEY` must be configured first.

- Author content in `docs/wiki/Home-ko.md` and Korean topic files such as `Architecture.md`. The workflow updates the corresponding `-en.md` and `-zh-CN.md` files and `docs/wiki-translations.json`.
- For section links into translated pages, use an explicit stable anchor such as `<a id="stable-section"></a>` before the Korean heading and link to that ID. Translated headings retain the explicit ID.
- Edit diagram text in `docs/assets/*-ko.svg`. Automation translates text while preserving geometry, then renders Wiki images. Review longer translated labels for fit.
- `Home.md`, `_Sidebar.md`, and `_Footer.md` are shared multilingual templates. They are published as written, so maintain all three languages together. README and other repository reference documents are not automatically copied into Wiki articles; update the relevant Korean Wiki source when behavior changes.
- Unchanged hashes skip model calls. Translation, truncation, or link validation failures stop publication and leave the existing Wiki available. Pull requests run offline checks; translation and publishing run from trusted `main`. Use **Run workflow** on the `Wiki sync` Actions page to retry after resolving a failure.
- The model is Gemini `gemini-3.5-flash-lite`. `WIKI_GEMINI_API_KEY` is passed to the translation process as `GEMINI_API_KEY`; Wiki publishing uses the job's short-lived `GITHUB_TOKEN`, with no personal PAT. Reusing the bot's Google project also shares its model quota. The workflow does not enable paid usage or change bot deployment, IAM, or instance settings.
- Keep keys out of source and logs. The API receives the public documentation to translate. Structural checks do not guarantee translation accuracy; review important instructions and security wording.

The offline commands above check tests, Wiki links, and translation freshness. `translate_wiki.py --check` may report pending translations after a Korean edit; it does not call the model. Use `--seed` only to establish an explicitly reviewed baseline. Edit repository sources rather than Wiki pages: the next successful sync can replace direct Wiki edits while preserving Git history.

## 简体中文

修改韩语 Wiki 源文件并合并或推送到 `main` 后，GitHub Actions 会将变更内容翻译为英语和简体中文，再把三种语言一起发布到正式 GitHub Wiki。启用前需要配置仓库 Actions secret `WIKI_GEMINI_API_KEY`。

- 正文原稿为 `docs/wiki/Home-ko.md` 和 `Architecture.md` 等韩语主题文件。工作流会更新对应的 `-en.md`、`-zh-CN.md` 文件及 `docs/wiki-translations.json`。
- 链接到翻译页面的具体章节时，请在韩语标题前添加 `<a id="stable-section"></a>` 等固定锚点，并链接到该 ID。标题翻译后，显式 ID 保持不变。
- 架构图原稿为 `docs/assets/*-ko.svg`。自动化只翻译文字，保留图形布局，并生成 Wiki 图片。翻译后文字较长时，请检查显示效果。
- `Home.md`、`_Sidebar.md`、`_Footer.md` 是共用的多语言导航模板，会按原样发布，修改时需同时维护三种语言。README 等仓库参考文档不会自动复制为 Wiki 正文；功能变化时，请同步修改对应的韩语 Wiki 原稿。
- 文件哈希未变化时不调用模型。翻译失败、输出截断或链接检查失败时停止发布，现有 Wiki 保持可用。PR 仅执行离线检查；实际翻译与发布在可信的 `main` 上运行。排除故障后，可在 Actions 的 `Wiki sync` 页面选择 **Run workflow** 重试。
- 翻译模型为 Gemini `gemini-3.5-flash-lite`。`WIKI_GEMINI_API_KEY` 通过进程变量 `GEMINI_API_KEY` 提供；发布 Wiki 使用每次任务生成的短期 `GITHUB_TOKEN`，无需个人 PAT。复用机器人所在 Google 项目的密钥时，文档翻译也会使用该项目的模型配额。此工作流不会启用付费使用，也不会修改机器人部署、IAM 或实例配置。
- 不要将密钥写入源码或日志。API 接收待翻译的公开文档。格式检查不能保证翻译含义完全准确，重要的操作和安全说明仍需审阅。

上方命令可离线检查测试、Wiki 链接和翻译新鲜度。修改韩语后，`translate_wiki.py --check` 可能提示等待翻译，但不会调用模型。`--seed` 仅用于登记已明确审阅的初始翻译基准。请在仓库中编辑源文件：下一次成功同步可能覆盖直接在 Wiki 中的编辑，同时保留 Git 历史。
