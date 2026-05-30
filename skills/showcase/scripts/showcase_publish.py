#!/usr/bin/env python3
"""Publish verified Showcase artifacts to a GitHub Pages repository."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CONFIG_ENV = "SHOWCASE_PUBLISH_CONFIG"
DEFAULT_BRANCH = "main"
DEFAULT_SOURCE_DIR = "docs"
MANIFEST_NAME = "showcases.json"


def default_config_path() -> Path:
    config_root = os.environ.get("XDG_CONFIG_HOME")
    if config_root:
        return Path(config_root) / "showcase-skill" / "publish.json"
    return Path.home() / ".config" / "showcase-skill" / "publish.json"


def config_path(args: argparse.Namespace) -> Path:
    explicit = getattr(args, "config", None) or os.environ.get(CONFIG_ENV)
    return Path(explicit).expanduser() if explicit else default_config_path()


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80].strip("-") or "showcase"


def run(
    command: list[str],
    cwd: Path | None = None,
    *,
    check: bool = True,
    capture: bool = False,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        check=check,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(
            f"No publish config found at {path}. Run `configure` first."
        )
    config = read_json(path, {})
    for key in ("repo_path", "base_url", "branch", "source_dir"):
        if not config.get(key):
            raise SystemExit(f"Publish config is missing `{key}`: {path}")
    return config


def parse_github_repo(value: str | None) -> str | None:
    if not value:
        return None
    value = value.removesuffix(".git")
    match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+)$", value)
    if match:
        return f"{match.group('owner')}/{match.group('repo')}"
    if re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", value):
        return value
    raise SystemExit(f"Could not parse GitHub repo from `{value}`")


def default_base_url(github_repo: str) -> str:
    owner, repo = github_repo.split("/", 1)
    if repo == f"{owner}.github.io":
        return f"https://{owner}.github.io/"
    return f"https://{owner}.github.io/{repo}/"


def join_url(base_url: str, relative_path: str) -> str:
    return f"{base_url.rstrip('/')}/{relative_path.strip('/')}/"


def git_output(repo: Path, *args: str) -> str:
    result = run(["git", *args], cwd=repo, capture=True)
    return result.stdout.strip()


def current_branch(repo: Path) -> str:
    return git_output(repo, "branch", "--show-current") or DEFAULT_BRANCH


def has_origin(repo: Path) -> bool:
    result = run(["git", "remote", "get-url", "origin"], cwd=repo, capture=True, check=False)
    return result.returncode == 0 and bool(result.stdout.strip())


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def git_ref_exists(repo: Path, ref: str) -> bool:
    result = run(["git", "show-ref", "--verify", "--quiet", ref], cwd=repo, check=False)
    return result.returncode == 0


def ensure_clean(repo: Path) -> None:
    if git_output(repo, "status", "--porcelain"):
        raise SystemExit(f"Publishing repo has uncommitted changes: {repo}")


def source_root(config: dict[str, Any]) -> Path:
    return Path(config["repo_path"]).expanduser().resolve() / config["source_dir"]


def manifest_path(config: dict[str, Any]) -> Path:
    return source_root(config) / MANIFEST_NAME


def safe_child(root: Path, relative_path: str) -> Path:
    root = root.resolve()
    target = (root / relative_path).resolve()
    if target != root and root not in target.parents:
        raise SystemExit(f"Refusing to operate outside {root}: {target}")
    return target


def load_manifest(config: dict[str, Any]) -> dict[str, Any]:
    return read_json(manifest_path(config), {"items": []})


def save_manifest(config: dict[str, Any], manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = iso(utc_now())
    write_json(manifest_path(config), manifest)


def render_index(config: dict[str, Any], manifest: dict[str, Any]) -> str:
    now = utc_now()
    items = sorted(
        manifest.get("items", []),
        key=lambda item: item.get("created_at", ""),
        reverse=True,
    )
    cards: list[str] = []
    for item in items:
        title = html.escape(item.get("title") or item.get("slug") or "Showcase")
        kind = html.escape(item.get("kind", "persistent"))
        url = html.escape(item.get("url", "#"))
        created = html.escape(item.get("created_at", ""))
        expires_at = item.get("expires_at")
        expires_dt = parse_iso(expires_at)
        state = "Expired" if expires_dt and expires_dt <= now else "Live"
        expiry = "Persistent" if not expires_at else f"Expires {html.escape(expires_at)}"
        cards.append(
            f"""
      <article>
        <div class="meta">{kind} - {state}</div>
        <h2><a href="{url}">{title}</a></h2>
        <p>{expiry}</p>
        <p class="small">Created {created}</p>
      </article>"""
        )
    body = "\n".join(cards) or "<p>No showcases published yet.</p>"
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Showcases</title>
  <style>
    :root {{
      color-scheme: light dark;
      --bg: #f7f7f4;
      --text: #171717;
      --muted: #66645e;
      --line: rgba(23, 23, 23, 0.14);
      --surface: #ffffff;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --bg: #111111;
        --text: #f4f4f1;
        --muted: #aaa79f;
        --line: rgba(244, 244, 241, 0.18);
        --surface: #1a1a1a;
      }}
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font: 16px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    main {{
      width: min(960px, calc(100vw - 32px));
      margin: 64px auto;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      margin-bottom: 24px;
      padding-bottom: 24px;
    }}
    h1 {{
      font-size: 40px;
      line-height: 1.1;
      margin: 0 0 8px;
    }}
    h2 {{
      font-size: 20px;
      line-height: 1.2;
      margin: 8px 0;
    }}
    a {{ color: inherit; }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
    }}
    article {{
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 20px;
    }}
    p {{ color: var(--muted); margin: 8px 0 0; }}
    .meta, .small {{
      color: var(--muted);
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>Showcases</h1>
      <p>Published previews generated by the Showcase skill.</p>
    </header>
    <section class="grid">
{body}
    </section>
  </main>
</body>
</html>
"""


def write_index(config: dict[str, Any], manifest: dict[str, Any]) -> None:
    root = source_root(config)
    root.mkdir(parents=True, exist_ok=True)
    (root / ".nojekyll").write_text("", encoding="utf-8")
    (root / "temp").mkdir(exist_ok=True)
    (root / "persistent").mkdir(exist_ok=True)
    (root / "index.html").write_text(render_index(config, manifest), encoding="utf-8")


def ensure_pages_worktree(repo_path: Path, source_repo: Path, branch: str) -> None:
    if not is_git_repo(source_repo):
        raise SystemExit(f"Source repo for publishing worktree is not a git repo: {source_repo}")
    if repo_path.exists():
        if is_git_repo(repo_path):
            return
        if any(repo_path.iterdir()):
            raise SystemExit(f"Refusing to use non-empty non-git directory: {repo_path}")
        raise SystemExit(f"Remove the empty directory before adding a git worktree: {repo_path}")

    repo_path.parent.mkdir(parents=True, exist_ok=True)
    if has_origin(source_repo):
        run(["git", "fetch", "origin", branch], cwd=source_repo, check=False)

    if git_ref_exists(source_repo, f"refs/heads/{branch}"):
        run(["git", "worktree", "add", str(repo_path), branch], cwd=source_repo)
    elif git_ref_exists(source_repo, f"refs/remotes/origin/{branch}"):
        run(["git", "worktree", "add", "-B", branch, str(repo_path), f"origin/{branch}"], cwd=source_repo)
    else:
        run(["git", "worktree", "add", "--orphan", "-b", branch, str(repo_path)], cwd=source_repo)


def install_cleanup_workflow(repo: Path, config: dict[str, Any]) -> None:
    helper_dir = repo / ".showcase"
    helper_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__).resolve(), helper_dir / "showcase_publish.py")
    workflow_config = dict(config)
    workflow_config["repo_path"] = "."
    write_json(helper_dir / "publish.json", workflow_config)

    workflow = repo / ".github" / "workflows" / "cleanup-temp-showcases.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        """name: Cleanup temporary showcases

on:
  schedule:
    - cron: "17 9 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Configure git
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
      - name: Clean expired showcases
        run: python3 .showcase/showcase_publish.py --config .showcase/publish.json cleanup --yes --no-push
      - name: Push cleanup commit
        run: git push
""",
        encoding="utf-8",
    )


def install_branch_cleanup_workflow(source_repo: Path, config: dict[str, Any], no_push: bool) -> None:
    ensure_clean(source_repo)
    workflow_config = dict(config)
    workflow_config["repo_path"] = "pages"
    workflow_json = json.dumps(workflow_config, indent=2)
    branch = config["branch"]

    workflow = source_repo / ".github" / "workflows" / "cleanup-temp-showcases.yml"
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(
        f"""name: Cleanup temporary showcases

on:
  schedule:
    - cron: "17 9 * * *"
  workflow_dispatch:

permissions:
  contents: write

jobs:
  cleanup:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          path: source
      - uses: actions/checkout@v4
        with:
          ref: {branch}
          path: pages
      - name: Configure git
        working-directory: pages
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
      - name: Write publish config
        run: |
          cat > "$RUNNER_TEMP/showcase-publish.json" <<'JSON'
{workflow_json}
JSON
      - name: Clean expired showcases
        run: python3 source/skills/showcase/scripts/showcase_publish.py --config "$RUNNER_TEMP/showcase-publish.json" cleanup --yes
""",
        encoding="utf-8",
    )
    commit_and_push(
        source_repo,
        current_branch(source_repo),
        "Install showcase cleanup workflow",
        no_push,
    )


def sync_repo(repo: Path, branch: str, no_push: bool) -> None:
    if not no_push and has_origin(repo):
        run(["git", "pull", "--ff-only", "origin", branch], cwd=repo)


def commit_and_push(repo: Path, branch: str, message: str, no_push: bool) -> None:
    run(["git", "add", "."], cwd=repo)
    staged = run(["git", "diff", "--cached", "--quiet"], cwd=repo, check=False)
    if staged.returncode == 0:
        print("No publishing repo changes to commit.")
        return
    run(["git", "commit", "-m", message], cwd=repo)
    if not no_push and has_origin(repo):
        run(["git", "push", "-u", "origin", branch], cwd=repo)


def ensure_publish_repo(config: dict[str, Any], no_push: bool) -> Path:
    repo = Path(config["repo_path"]).expanduser().resolve()
    if not is_git_repo(repo):
        raise SystemExit(f"Configured publishing path is not a git repo: {repo}")
    ensure_clean(repo)
    sync_repo(repo, config["branch"], no_push)
    return repo


def configure(args: argparse.Namespace) -> None:
    repo_path = Path(args.repo_path).expanduser().resolve()
    source_repo = Path(args.worktree_from).expanduser().resolve() if args.worktree_from else None
    github_repo = parse_github_repo(args.github_repo or args.remote)
    base_url = args.base_url or (default_base_url(github_repo) if github_repo else None)
    if not base_url:
        raise SystemExit("Provide --base-url, or provide --github-repo so it can be inferred.")
    if args.source_dir not in (".", "docs"):
        raise SystemExit("GitHub Pages branch publishing supports --source-dir docs or .")

    remote = args.remote
    if github_repo and not remote:
        remote = f"https://github.com/{github_repo}.git"

    if args.create_github_repo:
        if not github_repo:
            raise SystemExit("--create-github-repo requires --github-repo owner/name")
        exists = run(["gh", "repo", "view", github_repo], check=False, capture=True)
        if exists.returncode != 0:
            run(
                [
                    "gh",
                    "repo",
                    "create",
                    github_repo,
                    "--public",
                    "--description",
                    "Published Showcase artifacts",
                ]
            )

    if source_repo:
        ensure_pages_worktree(repo_path, source_repo, args.branch)
    elif repo_path.exists() and not is_git_repo(repo_path):
        if any(repo_path.iterdir()):
            raise SystemExit(f"Refusing to initialize non-empty non-git directory: {repo_path}")
        run(["git", "init", "-b", args.branch], cwd=repo_path)
    elif not repo_path.exists():
        if github_repo:
            run(["gh", "repo", "clone", github_repo, str(repo_path)])
        else:
            repo_path.mkdir(parents=True)
            run(["git", "init", "-b", args.branch], cwd=repo_path)

    if not is_git_repo(repo_path):
        raise SystemExit(f"Failed to create git repo at {repo_path}")

    current_branch = git_output(repo_path, "branch", "--show-current")
    branch = args.branch or current_branch or DEFAULT_BRANCH
    if current_branch != branch:
        run(["git", "checkout", "-B", branch], cwd=repo_path)

    if remote and not has_origin(repo_path):
        run(["git", "remote", "add", "origin", remote], cwd=repo_path)

    config = {
        "base_url": base_url.rstrip("/") + "/",
        "branch": branch,
        "github_repo": github_repo,
        "repo_path": str(repo_path),
        "source_dir": args.source_dir,
    }
    write_json(config_path(args), config)

    manifest = load_manifest(config)
    write_index(config, manifest)
    if args.install_cleanup_workflow:
        if source_repo and args.source_dir == ".":
            install_branch_cleanup_workflow(source_repo, config, args.no_push)
        else:
            install_cleanup_workflow(repo_path, config)
    commit_and_push(repo_path, branch, "Initialize showcase publishing", args.no_push)

    if args.enable_pages and github_repo and not args.no_push:
        enable_pages(github_repo, branch, args.source_dir)

    print(f"Publish config: {config_path(args)}")
    print(f"Publishing repo: {repo_path}")
    print(f"Base URL: {config['base_url']}")


def enable_pages(github_repo: str, branch: str, source_dir: str) -> None:
    source_path = "/" if source_dir == "." else f"/{source_dir}"
    payload = json.dumps({"source": {"branch": branch, "path": source_path}})
    page = run(["gh", "api", f"repos/{github_repo}/pages"], check=False, capture=True)
    method = "PUT" if page.returncode == 0 else "POST"
    result = run(
        ["gh", "api", "--method", method, f"repos/{github_repo}/pages", "--input", "-"],
        input_text=payload,
        check=False,
        capture=True,
    )
    if result.returncode == 0:
        return

    # GitHub can start branch publishing as the gh-pages branch is pushed, then
    # return 409 to the explicit create call. Treat that as success if the site
    # now resolves to the requested source.
    refreshed = run(["gh", "api", f"repos/{github_repo}/pages"], check=False, capture=True)
    if result.returncode == 1 and "already enabled" in result.stderr.lower() and refreshed.returncode == 0:
        page_config = json.loads(refreshed.stdout)
        source = page_config.get("source", {})
        if source.get("branch") == branch and source.get("path") == source_path:
            return
    raise SystemExit(result.stderr.strip() or result.stdout.strip())


def publish(args: argparse.Namespace) -> None:
    config = load_config(config_path(args))
    repo = ensure_publish_repo(config, args.no_push)
    root = source_root(config)
    source = Path(args.source).expanduser().resolve()
    if not source.exists() or not source.is_dir():
        raise SystemExit(f"Showcase source directory does not exist: {source}")
    if not (source / "index.html").exists():
        raise SystemExit(f"Showcase source must contain index.html: {source}")

    kind = args.kind
    now = utc_now()
    if kind == "temp" and args.days < 1:
        raise SystemExit("--days must be at least 1 for temporary showcases")

    base_slug = slugify(args.slug or source.name)
    slug = base_slug
    relative = f"{kind}/{slug}"
    destination = safe_child(root, relative)
    if destination.exists() and not args.overwrite:
        slug = f"{base_slug}-{now.strftime('%Y%m%d-%H%M%S')}"
        relative = f"{kind}/{slug}"
        destination = safe_child(root, relative)
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)

    manifest = load_manifest(config)
    items = [
        item for item in manifest.get("items", []) if item.get("path") != f"{relative}/"
    ]
    url = join_url(config["base_url"], relative)
    expires_at = iso(now + timedelta(days=args.days)) if kind == "temp" else None
    items.append(
        {
            "created_at": iso(now),
            "expires_at": expires_at,
            "kind": kind,
            "path": f"{relative}/",
            "slug": slug,
            "source": str(source),
            "title": args.title or slug.replace("-", " ").title(),
            "url": url,
        }
    )
    manifest["items"] = items
    save_manifest(config, manifest)
    write_index(config, manifest)
    commit_and_push(repo, config["branch"], f"Publish showcase {slug}", args.no_push)
    print(url)


def cleanup(args: argparse.Namespace) -> None:
    config = load_config(config_path(args))
    repo = ensure_publish_repo(config, args.no_push)
    root = source_root(config)
    manifest = load_manifest(config)
    now = utc_now()

    keep: list[dict[str, Any]] = []
    remove: list[dict[str, Any]] = []
    for item in manifest.get("items", []):
        expires_at = parse_iso(item.get("expires_at"))
        should_remove = item.get("kind") == "temp" and (
            args.all_temp or (expires_at is not None and expires_at <= now)
        )
        (remove if should_remove else keep).append(item)

    if not remove:
        print("No temporary showcases matched cleanup criteria.")
        return

    if not args.yes:
        if not sys.stdin.isatty():
            raise SystemExit("Refusing non-interactive cleanup without --yes.")
        answer = input(f"Remove {len(remove)} temporary showcase(s)? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("Cleanup cancelled.")
            return

    for item in remove:
        relative_path = item.get("path", "")
        target = safe_child(root, relative_path)
        if target.exists():
            shutil.rmtree(target)
        print(f"Removed {relative_path}")

    manifest["items"] = keep
    save_manifest(config, manifest)
    write_index(config, manifest)
    commit_and_push(repo, config["branch"], "Clean up temporary showcases", args.no_push)


def list_showcases(args: argparse.Namespace) -> None:
    config = load_config(config_path(args))
    manifest = load_manifest(config)
    now = utc_now()
    for item in sorted(manifest.get("items", []), key=lambda row: row.get("created_at", "")):
        expires_at = parse_iso(item.get("expires_at"))
        state = "expired" if expires_at and expires_at <= now else "live"
        expiry = item.get("expires_at") or "persistent"
        print(f"{item.get('kind')} {state} {expiry} {item.get('url')}")


def doctor(args: argparse.Namespace) -> None:
    path = config_path(args)
    config = load_config(path)
    repo = Path(config["repo_path"]).expanduser().resolve()
    print(f"Config: {path}")
    print(f"Publishing repo: {repo}")
    print(f"Base URL: {config['base_url']}")
    print(f"Branch: {config['branch']}")
    print(f"Source dir: {config['source_dir']}")
    if not is_git_repo(repo):
        raise SystemExit("Publishing repo is missing .git")
    print(f"Git status: {'clean' if not git_output(repo, 'status', '--porcelain') else 'dirty'}")
    print(f"Origin: {git_output(repo, 'remote', 'get-url', 'origin') if has_origin(repo) else 'none'}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", help=f"Config path. Defaults to ${CONFIG_ENV} or {default_config_path()}")
    subparsers = parser.add_subparsers(dest="command", required=True)

    configure_parser = subparsers.add_parser("configure", help="Create or record a publishing repo.")
    configure_parser.add_argument("--repo-path", required=True, help="Local path for the Pages publishing repo.")
    configure_parser.add_argument("--github-repo", help="GitHub repo as owner/name.")
    configure_parser.add_argument("--remote", help="Git remote URL for the publishing repo.")
    configure_parser.add_argument("--worktree-from", help="Existing local repo to attach repo-path as a Pages branch worktree.")
    configure_parser.add_argument("--base-url", help="Published Pages base URL.")
    configure_parser.add_argument("--branch", default=DEFAULT_BRANCH)
    configure_parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR, choices=["docs", "."])
    configure_parser.add_argument("--create-github-repo", action="store_true")
    configure_parser.add_argument("--enable-pages", action="store_true")
    configure_parser.add_argument("--install-cleanup-workflow", action="store_true")
    configure_parser.add_argument("--no-push", action="store_true")
    configure_parser.set_defaults(func=configure)

    publish_parser = subparsers.add_parser("publish", help="Publish a verified showcase directory.")
    publish_parser.add_argument("--source", required=True, help="Verified showcase output directory.")
    publish_parser.add_argument("--kind", choices=["temp", "persistent"], default="temp")
    publish_parser.add_argument("--days", type=int, default=7)
    publish_parser.add_argument("--slug")
    publish_parser.add_argument("--title")
    publish_parser.add_argument("--overwrite", action="store_true")
    publish_parser.add_argument("--no-push", action="store_true")
    publish_parser.set_defaults(func=publish)

    cleanup_parser = subparsers.add_parser("cleanup", help="Remove expired or all temporary showcases.")
    cleanup_parser.add_argument("--all-temp", action="store_true", help="Remove all temporary showcases.")
    cleanup_parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    cleanup_parser.add_argument("--no-push", action="store_true")
    cleanup_parser.set_defaults(func=cleanup)

    list_parser = subparsers.add_parser("list", help="List published showcases.")
    list_parser.set_defaults(func=list_showcases)

    doctor_parser = subparsers.add_parser("doctor", help="Validate publish configuration.")
    doctor_parser.set_defaults(func=doctor)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
