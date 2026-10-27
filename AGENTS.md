# Nuri contributor guidance

## Documentation and Wiki

- Keep user-facing documentation accurate when behavior, commands, limits, deployment, or data handling changes. Update the relevant **Korean Wiki source** in `docs/wiki/` in the same change. A README edit alone does not update the Wiki article.
- Korean content sources are `Home-ko.md` and topic files such as `Architecture.md` and `Operations.md`. Files ending in `-en.md` or `-zh-CN.md` are generated translations. The `Wiki sync` workflow translates changed Korean sources on `main`, commits translations and their hash record, validates the result, and publishes all three languages to the native GitHub Wiki.
- Diagram sources are `docs/assets/*-ko.svg`. Automation translates their text into `*-en.svg` and `*-zh-CN.svg`, preserving diagram geometry, then renders Wiki images. Keep Korean changes within the existing diagram layout and review translated labels for fit.
- `docs/wiki/Home.md`, `_Sidebar.md`, and `_Footer.md` are shared multilingual navigation templates. They are published as written and are **not** machine-translated. Maintain their Korean, English, and Simplified Chinese text together.
- Maintain content in this repository. Direct Wiki edits may be replaced by the next successful sync. Normal Git commits preserve Wiki history; never force-push the Wiki or rewrite release tags.
- Do not use `--seed` to hide stale translations. It is for explicitly accepting an already-reviewed translation baseline, not the normal authoring or CI path.
- Read `docs/WIKI-AUTOMATION.md` before changing the workflow, translation cache, or publishing scripts. Use focused offline tests for automation changes. Do not invoke a live model for routine local tests.
- Translation validation checks structure and protected content, not semantic accuracy. Review generated English and Chinese wording when a change affects important instructions or security claims.

## Credentials and runtime

- Keep API keys, tokens, local operational evidence, `.state/`, and credentials out of tracked files, prompts, test fixtures, and logs.
- Wiki translation reads the repository Actions secret `WIKI_GEMINI_API_KEY` through the process variable `GEMINI_API_KEY`. Publishing uses the job's short-lived `GITHUB_TOKEN`; do not add a personal access token for Wiki access.
- Documentation automation does not authorize bot deployment, billing changes, credential rotation, or changes to Cloud Run IAM, limits, or settings.
- For authorized GitHub administration, explicitly select the repository owner's account for the process; do not change a global account default. For authorized Google Cloud work, confirm the dedicated personal project and account, then pass both explicitly to every command.
