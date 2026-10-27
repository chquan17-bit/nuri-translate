"""Validate Wiki sources and export them into an existing Wiki Git checkout.

Only paths recorded by this exporter are removed on subsequent runs. The caller
owns Git authentication, commits and pushes; this module never uses credentials.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import tempfile
from urllib.parse import quote, unquote, urlsplit


REPOSITORY = "chquan17-bit/nuri-translate"
MANIFEST = ".nuri-wiki-manifest.json"
SHARED = {"Home.md", "_Sidebar.md", "_Footer.md"}
INLINE_LINK = re.compile(r'(!?\[[^\]\n]*\]\()(<[^>\n]+>|[^\s()]+)(\s+"[^"\n]*")?(\))')
REFERENCE = re.compile(r'^(\s{0,3}\[[^\]\n]+\]:\s*)(<[^>\n]+>|\S+)(.*)$')
INLINE_CODE = re.compile(r'(`+)(.*?)(?<!`)\1(?!`)', re.DOTALL)
FENCE = re.compile(r'^\s{0,3}(`{3,}|~{3,})')
PAGE_NAME = re.compile(r'(?:[A-Za-z0-9][A-Za-z0-9-]*|_Sidebar|_Footer)\.md$')
ASSET_NAME = re.compile(r'[A-Za-z0-9][A-Za-z0-9-]*\.(?:svg|png|jpg|jpeg|gif)$')


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def contained(path: Path, parent: Path) -> Path:
    # Check before resolve(), which would erase symlink evidence.
    if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != parent.parent):
        raise ValueError(f"Symlinks are not allowed in Wiki paths: {path.name}")
    resolved = path.resolve()
    if not resolved.is_relative_to(parent.resolve()):
        raise ValueError(f"Path escapes documentation root: {path.name}")
    return resolved


def markdown_files(root: Path) -> list[Path]:
    directory = root / "docs/wiki"
    files = sorted(directory.glob("*.md"))
    names = {p.name for p in files}
    if not SHARED.issubset(names) or "Home-ko.md" not in names:
        raise ValueError("Wiki requires Home-ko.md, Home.md, _Sidebar.md and _Footer.md")
    for path in files:
        contained(path, directory)
        if path.is_symlink() or not PAGE_NAME.fullmatch(path.name):
            raise ValueError(f"Unsupported Wiki filename: {path.name}")
        if not read_text(path).strip():
            raise ValueError(f"Empty Wiki page: {path.name}")
    return files


def check_languages(files: list[Path]) -> None:
    names = {p.name for p in files}
    for path in files:
        if path.name in SHARED:
            continue
        stem = path.stem
        if stem.endswith("-zh-CN"):
            base = stem[:-6]
        elif stem.endswith("-en"):
            base = stem[:-3]
        elif stem == "Home-ko":
            base = "Home"
        else:
            base = stem
        trio = {"Home-ko.md" if base == "Home" else f"{base}.md",
                f"{base}-en.md", f"{base}-zh-CN.md"}
        if missing := trio - names:
            raise ValueError(f"Missing language pages: {', '.join(sorted(missing))}")


def rewrite_url(destination: str, page: Path, root: Path, repository: str,
                assets: set[Path]) -> str:
    angled = destination.startswith("<") and destination.endswith(">")
    raw = destination[1:-1] if angled else destination
    parts = urlsplit(raw)
    if parts.scheme or parts.netloc:
        if parts.scheme not in {"https", "http", "mailto"}:
            raise ValueError(f"Unsupported link scheme in {page.name}")
        return destination
    if not parts.path:
        return destination
    if parts.query:
        raise ValueError(f"Relative links with query strings are unsupported: {page.name}")
    target = contained(page.parent / unquote(parts.path), root)
    relative = target.relative_to(root.resolve())
    if any(part.startswith(".") for part in relative.parts) or not target.is_file():
        raise ValueError(f"Missing or private link target in {page.name}: {parts.path}")
    suffix = f"#{parts.fragment}" if parts.fragment else ""
    if target.parent == (root / "docs/wiki").resolve() and target.suffix == ".md":
        url = f"https://github.com/{repository}/wiki/{quote(target.stem)}{suffix}"
    elif target.parent == (root / "docs/assets").resolve():
        if not ASSET_NAME.fullmatch(target.name) or target.is_symlink():
            raise ValueError(f"Unsupported Wiki image: {target.name}")
        assets.add(target)
        name = target.with_suffix(".png").name if target.suffix == ".svg" else target.name
        url = f"https://raw.githubusercontent.com/wiki/{repository}/assets/{quote(name)}{suffix}"
    else:
        url = f"https://github.com/{repository}/blob/main/{quote(relative.as_posix())}{suffix}"
    return f"<{url}>" if angled else url


def rewrite_markdown(text: str, page: Path, root: Path, repository: str,
                     assets: set[Path]) -> str:
    output = []
    fence = None
    for line in text.splitlines(keepends=True):
        marker = FENCE.match(line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            output.append(line)
            continue
        if fence:
            output.append(line)
            continue
        if line.startswith(("    ", "\t")):
            output.append(line)
            continue
        # A whole link inside code is an example; code within its label is valid.
        code_spans = [match.span() for match in INLINE_CODE.finditer(line)]
        def replace_link(match):
            if any(start <= match.start() and match.end() <= end for start, end in code_spans):
                return match.group()
            return (match.group(1) + rewrite_url(match.group(2), page, root, repository, assets)
                    + (match.group(3) or "") + match.group(4))
        line = INLINE_LINK.sub(replace_link, line)
        if reference := REFERENCE.match(line.rstrip("\n")):
            line = (reference.group(1)
                    + rewrite_url(reference.group(2), page, root, repository, assets)
                    + reference.group(3) + ("\n" if line.endswith("\n") else ""))
        output.append(line)
    if fence is not None:
        raise ValueError(f"Unclosed code fence in {page.name}")
    return "".join(output)


def prepare(root: Path, repository: str = REPOSITORY, require_languages: bool = True):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError("Invalid repository identity")
    root = root.resolve()
    pages = markdown_files(root)
    if require_languages:
        check_languages(pages)
    assets: set[Path] = set()
    rendered = {p.name: rewrite_markdown(read_text(p), p, root, repository, assets) for p in pages}
    outputs = [p.with_suffix(".png").name if p.suffix == ".svg" else p.name for p in assets]
    if len(outputs) != len(set(outputs)):
        raise ValueError("Wiki image output names collide")
    return rendered, assets


def render_svg(source: Path, destination: Path) -> None:
    executable = shutil.which("rsvg-convert")
    if not executable:
        raise ValueError("Install librsvg2-bin and fonts-noto-cjk to export Wiki images")
    # Fontconfig on the runner supplies Noto CJK when Windows font families are absent.
    subprocess.run([executable, "--format=png", "--output", str(destination), str(source)],
                   check=True, timeout=60, capture_output=True)
    if destination.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"Invalid rendered PNG: {source.name}")


def managed_path(directory: Path, value: str) -> Path:
    posix = PurePosixPath(value)
    valid = (len(posix.parts) == 1 and PAGE_NAME.fullmatch(value)) or (
        len(posix.parts) == 2 and posix.parts[0] == "assets"
        and ASSET_NAME.fullmatch(posix.name) and posix.suffix != ".svg")
    if not valid or posix.is_absolute() or ".." in posix.parts:
        raise ValueError("Invalid managed Wiki path")
    result = directory.joinpath(*posix.parts)
    contained(result, directory)
    if result.is_symlink():
        raise ValueError("Managed Wiki symlinks are not allowed")
    return result


def publish_files(root: Path, destination: Path, repository: str = REPOSITORY,
                  renderer=render_svg) -> dict:
    root, destination = root.resolve(), destination.resolve()
    if destination == root or destination.is_relative_to(root / "docs"):
        raise ValueError("Wiki destination must be separate from documentation sources")
    if not (destination / ".git").exists():
        raise ValueError("Destination must be an existing Wiki Git checkout")
    rendered, assets = prepare(root, repository)
    manifest_path = destination / MANIFEST
    contained(manifest_path, destination)
    previous = json.loads(read_text(manifest_path)) if manifest_path.exists() else {"files": []}
    old_files = previous["files"]
    if not isinstance(old_files, list) or not all(isinstance(p, str) for p in old_files):
        raise ValueError("Invalid Wiki manifest")
    for old in old_files:
        managed_path(destination, old)
    # Stage every page and image before changing the checkout.
    with tempfile.TemporaryDirectory(prefix="nuri-wiki-") as temporary:
        stage = Path(temporary)
        for name, text in rendered.items():
            (stage / name).write_text(text, encoding="utf-8", newline="\n")
        (stage / "assets").mkdir()
        for source in sorted(assets):
            target = stage / "assets" / (source.with_suffix(".png").name if source.suffix == ".svg" else source.name)
            if source.suffix == ".svg":
                renderer(source, target)
            else:
                shutil.copyfile(source, target)
        files = sorted(p.relative_to(stage).as_posix() for p in stage.rglob("*") if p.is_file())
        for name in files:
            managed_path(destination, name)
        for name in set(old_files) - set(files):
            managed_path(destination, name).unlink(missing_ok=True)
        for name in files:
            target = managed_path(destination, name)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(stage / name, target)
        manifest = {"version": 1, "source": f"https://github.com/{repository}/tree/main/docs/wiki", "files": files}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return {"pages": len(rendered), "images": len(assets)}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--repository", default=REPOSITORY)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.check:
            pages, assets = prepare(args.root, args.repository)
            print(f"Wiki sources valid: {len(pages)} Markdown files, {len(assets)} images")
        elif args.destination:
            result = publish_files(args.root, args.destination, args.repository)
            print(f"Wiki prepared: {result['pages']} Markdown files, {result['images']} images")
        else:
            parser.error("Provide --check or --destination")
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"Wiki export failed: {type(exc).__name__}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
