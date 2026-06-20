#!/usr/bin/env python3
"""Transfer Feishu/Lark wiki/docx documents into the current user's space.

The script intentionally invokes lark-cli with argv arrays instead of shell
strings. That avoids PowerShell JSON quoting issues and preserves UTF-8 text.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


REQUIRED_SCOPES = (
    "wiki:node:retrieve",
    "wiki:node:copy",
    "wiki:space:retrieve",
    "drive:drive.metadata:readonly",
    "docs:document.content:read",
    "docx:document:create",
    "docs:document:copy",
)


@dataclass
class CmdResult:
    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    data: Any = None


@dataclass
class TransferItem:
    source_url: str
    ok: bool = False
    method: str | None = None
    title: str | None = None
    source_type: str | None = None
    source_token: str | None = None
    new_url: str | None = None
    new_token: str | None = None
    source_revision: int | None = None
    new_revision: int | None = None
    warnings: list[str] = field(default_factory=list)
    degradations: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation: dict[str, Any] = field(default_factory=dict)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    source_space_id: str | None = None
    source_node_token: str | None = None
    target_parent_node_token: str | None = None
    new_node_token: str | None = None
    depth: int | None = None


@dataclass
class WikiTreeNode:
    node_token: str
    space_id: str
    title: str
    obj_token: str | None
    obj_type: str | None
    parent_node_token: str | None
    has_child: bool
    depth: int


def run_lark(args: list[str], stdin: str | None = None) -> CmdResult:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    proc = subprocess.run(
        ["lark-cli", *args],
        input=stdin,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        env=env,
    )
    data = parse_json_maybe(proc.stdout) or parse_json_maybe(proc.stderr)
    return CmdResult(["lark-cli", *args], proc.returncode, proc.stdout, proc.stderr, data)


def parse_json_maybe(text: str) -> Any:
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch not in "{[":
            continue
        try:
            value, _ = decoder.raw_decode(text[i:])
            return value
        except json.JSONDecodeError:
            continue
    return None


def cmd_summary(result: CmdResult) -> dict[str, Any]:
    message = ""
    code = None
    if isinstance(result.data, dict):
        error = result.data.get("error") or {}
        message = error.get("message") or result.data.get("message") or ""
        code = error.get("code") or result.data.get("code")
    if not message:
        message = (result.stderr or result.stdout).strip()[:500]
    return {
        "args": redact_args(result.args),
        "returncode": result.returncode,
        "code": code,
        "message": message,
    }


def redact_args(args: list[str]) -> list[str]:
    redacted: list[str] = []
    for arg in args:
        if len(arg) > 240:
            redacted.append(arg[:120] + "...<truncated>")
        else:
            redacted.append(arg)
    return redacted


def require_ok(result: CmdResult, action: str) -> dict[str, Any]:
    if result.returncode != 0:
        raise RuntimeError(f"{action} failed: {cmd_summary(result)['message']}")
    if not isinstance(result.data, dict):
        raise RuntimeError(f"{action} did not return JSON")
    if result.data.get("ok") is False:
        error = result.data.get("error") or {}
        raise RuntimeError(f"{action} failed: {error.get('message') or result.data}")
    return result.data


def check_environment(as_identity: str) -> dict[str, Any]:
    if not shutil.which("lark-cli"):
        raise RuntimeError("lark-cli was not found on PATH")

    status = run_lark(["auth", "status", "--json", "--verify"])
    require_ok(status, "auth status")

    scope_check = run_lark(["auth", "check", "--scope", " ".join(REQUIRED_SCOPES), "--json"])
    data = require_ok(scope_check, "auth scope check")
    missing = data.get("missing")
    if missing:
        raise RuntimeError(
            "Missing lark-cli scopes: "
            + ", ".join(missing)
            + ". Run lark-cli auth login with the missing scopes."
        )

    return {
        "identity": as_identity,
        "auth_status": summarize_auth_status(status.data),
        "scope_check": {
            "ok": data.get("ok"),
            "granted": data.get("granted"),
            "missing": data.get("missing"),
            "_notice": data.get("_notice"),
        },
    }


def summarize_auth_status(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    identities = data.get("identities") or {}
    user = identities.get("user") or {}
    bot = identities.get("bot") or {}
    return {
        "appId": data.get("appId"),
        "brand": data.get("brand"),
        "identity": data.get("identity"),
        "verified": data.get("verified"),
        "user": {
            "status": user.get("status"),
            "available": user.get("available"),
            "verified": user.get("verified"),
            "userName": user.get("userName"),
            "openId": user.get("openId"),
            "tokenStatus": user.get("tokenStatus"),
            "expiresAt": user.get("expiresAt"),
            "refreshExpiresAt": user.get("refreshExpiresAt"),
        },
        "bot": {
            "status": bot.get("status"),
            "available": bot.get("available"),
            "verified": bot.get("verified"),
            "appName": bot.get("appName"),
        },
    }


def inspect_url(url: str, as_identity: str) -> dict[str, Any]:
    result = run_lark(["drive", "+inspect", "--url", url, "--format", "json", "--as", as_identity])
    data = require_ok(result, "inspect source")
    return data.get("data") or {}


def resolve_my_library_space(as_identity: str) -> str:
    params = json.dumps({"space_id": "my_library", "lang": "zh"}, ensure_ascii=False)
    result = run_lark(
        ["wiki", "spaces", "get", "--params", params, "--format", "json", "--as", as_identity]
    )
    data = require_ok(result, "resolve my_library")
    space = (data.get("data") or {}).get("space") or data.get("space") or {}
    space_id = space.get("space_id")
    if not space_id:
        raise RuntimeError("Could not resolve my_library space_id")
    return space_id


def get_wiki_node(node_token_or_url: str, as_identity: str) -> dict[str, Any]:
    result = run_lark(
        [
            "wiki",
            "+node-get",
            "--node-token",
            node_token_or_url,
            "--format",
            "json",
            "--as",
            as_identity,
        ]
    )
    data = require_ok(result, "get wiki node")
    node = data.get("data") or {}
    if not node.get("node_token"):
        raise RuntimeError(f"Could not resolve wiki node: {node_token_or_url}")
    return node


def list_child_nodes(space_id: str, parent_node_token: str, as_identity: str, depth: int) -> list[WikiTreeNode]:
    result = run_lark(
        [
            "wiki",
            "+node-list",
            "--space-id",
            space_id,
            "--parent-node-token",
            parent_node_token,
            "--page-all",
            "--page-limit",
            "0",
            "--format",
            "json",
            "--as",
            as_identity,
        ]
    )
    data = require_ok(result, "list child wiki nodes")
    nodes = (data.get("data") or {}).get("nodes") or []
    return [wiki_tree_node_from_raw(node, depth) for node in nodes]


def wiki_tree_node_from_raw(raw: dict[str, Any], depth: int) -> WikiTreeNode:
    node_token = raw.get("node_token")
    space_id = raw.get("space_id")
    if not node_token or not space_id:
        raise RuntimeError(f"Malformed wiki node data: {raw}")
    return WikiTreeNode(
        node_token=node_token,
        space_id=space_id,
        title=raw.get("title") or "",
        obj_token=raw.get("obj_token"),
        obj_type=raw.get("obj_type"),
        parent_node_token=raw.get("parent_node_token"),
        has_child=bool(raw.get("has_child")),
        depth=depth,
    )


def collect_wiki_tree(root_node_or_url: str, as_identity: str, max_depth: int = 0) -> list[WikiTreeNode]:
    root = wiki_tree_node_from_raw(get_wiki_node(root_node_or_url, as_identity), depth=0)
    nodes: list[WikiTreeNode] = []
    seen: set[tuple[str, str]] = set()

    def visit(node: WikiTreeNode) -> None:
        key = (node.space_id, node.node_token)
        if key in seen:
            return
        seen.add(key)
        nodes.append(node)
        if not node.has_child:
            return
        if max_depth and node.depth >= max_depth:
            return
        for child in list_child_nodes(node.space_id, node.node_token, as_identity, node.depth + 1):
            visit(child)

    visit(root)
    return nodes


def inspect_data_from_wiki_node(node: WikiTreeNode) -> dict[str, Any]:
    return {
        "title": node.title,
        "type": node.obj_type,
        "token": node.obj_token,
        "wiki_node": {
            "space_id": node.space_id,
            "node_token": node.node_token,
            "obj_type": node.obj_type,
            "obj_token": node.obj_token,
        },
    }


def wiki_url(node_token: str) -> str:
    return f"https://www.feishu.cn/wiki/{node_token}"


def try_native_wiki_copy(
    item: TransferItem,
    inspect_data: dict[str, Any],
    as_identity: str,
    dry_run: bool,
    target_space_id: str | None = None,
    target_parent_node_token: str | None = None,
) -> bool:
    wiki_node = inspect_data.get("wiki_node") or {}
    source_space_id = wiki_node.get("space_id")
    node_token = wiki_node.get("node_token")
    if not source_space_id or not node_token:
        item.attempts.append({"method": "native_wiki_copy", "skipped": "source is not a wiki node"})
        return False
    if not target_space_id and not target_parent_node_token:
        raise RuntimeError("native wiki copy needs target_space_id or target_parent_node_token")

    item.source_space_id = source_space_id
    item.source_node_token = node_token
    item.target_parent_node_token = target_parent_node_token

    args = [
        "wiki",
        "+node-copy",
        "--space-id",
        source_space_id,
        "--node-token",
        node_token,
        "--format",
        "json",
        "--as",
        as_identity,
    ]
    if target_parent_node_token:
        args.extend(["--target-parent-node-token", target_parent_node_token])
    else:
        args.extend(["--target-space-id", str(target_space_id)])
    if dry_run:
        args.append("--dry-run")
    else:
        args.append("--yes")

    result = run_lark(args)
    item.attempts.append({"method": "native_wiki_copy", **cmd_summary(result)})
    if result.returncode != 0 or not isinstance(result.data, dict) or result.data.get("ok") is False:
        return False
    if dry_run:
        item.ok = True
        item.method = "native_wiki_copy_dry_run"
        return True

    data = result.data.get("data") or result.data
    item.new_node_token = data.get("node_token")
    obj_type = data.get("obj_type")
    obj_token = data.get("obj_token")
    if obj_type and obj_token:
        item.new_url = canonical_doc_url(obj_type, obj_token)
        item.new_token = obj_token
    elif data.get("node_token"):
        item.new_url = "https://www.feishu.cn/wiki/" + data["node_token"]
    item.ok = True
    item.method = "native_wiki_copy"
    return True


def canonical_doc_url(obj_type: str, token: str) -> str:
    path = {
        "docx": "docx",
        "doc": "doc",
        "sheet": "sheets",
        "bitable": "base",
        "slides": "slides",
        "mindnote": "mindnotes",
        "file": "file",
    }.get(obj_type, obj_type)
    return f"https://www.feishu.cn/{path}/{token}"


def fetch_doc_xml(url: str, as_identity: str) -> tuple[str, int | None, str | None]:
    result = run_lark(
        [
            "docs",
            "+fetch",
            "--api-version",
            "v2",
            "--doc",
            url,
            "--detail",
            "full",
            "--format",
            "json",
            "--as",
            as_identity,
        ]
    )
    data = require_ok(result, "fetch source document")
    document = (data.get("data") or {}).get("document") or {}
    return document.get("content") or "", document.get("revision_id"), document.get("document_id")


def prepare_xml_for_rebuild(content: str) -> tuple[str, list[str]]:
    degradations: list[str] = []

    synced_count = len(re.findall(r"<synced-source\b", content))
    if synced_count:
        content = re.sub(r"<synced-source\b[^>]*>", "", content)
        content = re.sub(r"</synced-source>", "", content)
        degradations.append(
            f"Converted {synced_count} synced-source block(s) into ordinary child blocks."
        )

    readonly_count = len(re.findall(r"<readonly-block\b", content))
    if readonly_count:
        content = re.sub(r"<readonly-block\b[^>]*/>", "", content)
        content = re.sub(r"<readonly-block\b[^>]*>.*?</readonly-block>", "", content, flags=re.S)
        degradations.append(f"Removed {readonly_count} readonly-block placeholder(s).")

    crop_count = len(re.findall(r"\s+crop=\"[^\"]*\"", content))
    if crop_count:
        content = re.sub(r"\s+crop=\"[^\"]*\"", "", content)
        degradations.append(f"Removed {crop_count} unsupported image crop attribute(s).")

    id_count = len(re.findall(r"\s+id=\"[^\"]*\"", content))
    if id_count:
        content = re.sub(r"\s+id=\"[^\"]*\"", "", content)

    if re.search(r"\salt=", content):
        degradations.append("Image alt text may not be preserved by the Docx write API.")

    return content, degradations


def create_rebuilt_doc(
    content: str,
    target_position: str,
    as_identity: str,
    dry_run: bool,
    target_parent_node_token: str | None = None,
) -> dict[str, Any]:
    args = [
        "docs",
        "+create",
        "--api-version",
        "v2",
        "--content",
        "-",
        "--doc-format",
        "xml",
        "--format",
        "json",
        "--as",
        as_identity,
    ]
    if target_parent_node_token:
        args[4:4] = ["--parent-token", target_parent_node_token]
    else:
        args[4:4] = ["--parent-position", target_position]
    if dry_run:
        args.append("--dry-run")
    result = run_lark(args, stdin=content)
    data = require_ok(result, "create rebuilt document")
    return data


def validate_docs(
    source_content: str,
    new_url: str,
    as_identity: str,
) -> tuple[dict[str, Any], int | None]:
    new_content, new_revision, _ = fetch_doc_xml(new_url, as_identity)
    validation = {
        "headings_match": headings(source_content) == headings(new_content),
        "source_counts": quality_counts(source_content),
        "new_counts": quality_counts(new_content),
    }
    return validation, new_revision


def quality_counts(content: str) -> dict[str, int]:
    patterns = {
        "img": r"<img\b",
        "source": r"<source\b",
        "cite": r"<cite\b",
        "button": r"<button\b",
        "callout": r"<callout\b",
        "span": r"<span\b",
        "synced_source": r"<synced-source\b",
        "readonly_block": r"<readonly-block\b",
        "alt_attrs": r"\salt=",
        "background_attrs": r"background-color=",
        "text_color_attrs": r"text-color=",
        "crop_attrs": r"\scrop=",
    }
    return {name: len(re.findall(pattern, content)) for name, pattern in patterns.items()}


def headings(content: str) -> list[str]:
    values = []
    for match in re.finditer(r"<h[1-6][^>]*>(.*?)</h[1-6]>", content, flags=re.S):
        text = re.sub(r"<[^>]+>", "", match.group(1))
        values.append(re.sub(r"\s+", " ", text).strip())
    return values


def transfer_one(
    url: str,
    target_position: str,
    target_space_id: str | None,
    as_identity: str,
    skip_native_copy: bool,
    dry_run: bool,
    target_parent_node_token: str | None = None,
    source_node: WikiTreeNode | None = None,
) -> TransferItem:
    item = TransferItem(source_url=url, target_parent_node_token=target_parent_node_token)
    try:
        if source_node:
            inspect_data = inspect_data_from_wiki_node(source_node)
            item.depth = source_node.depth
            item.source_space_id = source_node.space_id
            item.source_node_token = source_node.node_token
        else:
            inspect_data = inspect_url(url, as_identity)
        item.title = inspect_data.get("title")
        item.source_type = inspect_data.get("type")
        item.source_token = inspect_data.get("token")

        if not skip_native_copy:
            copied = try_native_wiki_copy(
                item,
                inspect_data,
                as_identity,
                dry_run,
                target_space_id=target_space_id,
                target_parent_node_token=target_parent_node_token,
            )
            if copied:
                return item

        if item.source_type != "docx":
            raise RuntimeError(
                f"XML rebuild currently supports docx/wiki-docx only; got {item.source_type!r}"
            )

        source_content, source_revision, _ = fetch_doc_xml(url, as_identity)
        item.source_revision = source_revision
        prepared, degradations = prepare_xml_for_rebuild(source_content)
        item.degradations.extend(degradations)

        created = create_rebuilt_doc(
            prepared,
            target_position,
            as_identity,
            dry_run,
            target_parent_node_token=target_parent_node_token,
        )
        item.attempts.append({"method": "xml_rebuild", "returncode": 0})
        if dry_run:
            item.ok = True
            item.method = "xml_rebuild_dry_run"
            return item

        document = ((created.get("data") or {}).get("document") or {})
        item.new_url = document.get("url")
        item.new_token = document.get("document_id")
        item.new_revision = document.get("revision_id")
        for warning in (created.get("data") or {}).get("warnings") or []:
            item.warnings.append(str(warning))

        if item.new_url:
            try:
                new_node = get_wiki_node(item.new_url, as_identity)
                item.new_node_token = new_node.get("node_token")
            except Exception as exc:  # noqa: BLE001 - validation can still run on the doc URL.
                item.warnings.append(f"Could not resolve created wiki node: {exc}")
            validation, new_revision = validate_docs(source_content, item.new_url, as_identity)
            item.validation = validation
            item.new_revision = new_revision
            add_validation_degradations(item)

        item.ok = True
        item.method = "xml_rebuild"
        return item
    except Exception as exc:  # noqa: BLE001 - report batch failures without stopping.
        item.errors.append(str(exc))
        return item


def add_validation_degradations(item: TransferItem) -> None:
    counts = item.validation
    source = counts.get("source_counts") or {}
    new = counts.get("new_counts") or {}
    checks = ["img", "source", "cite", "button", "callout", "span"]
    for key in checks:
        if source.get(key) != new.get(key):
            item.degradations.append(f"{key} count changed: {source.get(key)} -> {new.get(key)}")
    if not counts.get("headings_match"):
        item.degradations.append("Heading outline changed.")
    if source.get("alt_attrs") and not new.get("alt_attrs"):
        item.degradations.append("Image alt attributes were dropped by the write API.")
    if source.get("crop_attrs") and not new.get("crop_attrs"):
        item.degradations.append("Image crop attributes were not preserved.")
    if source.get("readonly_block") and not new.get("readonly_block"):
        item.degradations.append("Readonly blocks were not preserved.")
    if source.get("synced_source") and not new.get("synced_source"):
        item.degradations.append("Synced-source wrappers were not preserved.")


def node_summary(node: WikiTreeNode | dict[str, Any]) -> dict[str, Any]:
    if isinstance(node, WikiTreeNode):
        return {
            "title": node.title,
            "node_token": node.node_token,
            "space_id": node.space_id,
            "obj_type": node.obj_type,
            "obj_token": node.obj_token,
            "parent_node_token": node.parent_node_token,
            "has_child": node.has_child,
            "depth": node.depth,
        }
    return {
        "title": node.get("title"),
        "node_token": node.get("node_token"),
        "space_id": node.get("space_id"),
        "obj_type": node.get("obj_type"),
        "obj_token": node.get("obj_token"),
        "parent_node_token": node.get("parent_node_token"),
        "has_child": node.get("has_child"),
    }


def dry_run_tree_items(tree: list[WikiTreeNode], target_parent_node_token: str) -> list[TransferItem]:
    target_by_source: dict[str, str] = {}
    items: list[TransferItem] = []
    for node in tree:
        parent_target = (
            target_parent_node_token
            if node.depth == 0
            else target_by_source.get(node.parent_node_token or "")
        )
        item = TransferItem(
            source_url=wiki_url(node.node_token),
            title=node.title,
            source_type=node.obj_type,
            source_token=node.obj_token,
            source_space_id=node.space_id,
            source_node_token=node.node_token,
            target_parent_node_token=parent_target,
            depth=node.depth,
        )
        if not parent_target:
            item.errors.append("Parent target node is unavailable in dry-run tree mapping.")
        elif node.obj_type == "docx":
            item.ok = True
            item.method = "xml_rebuild_tree_dry_run"
            target_by_source[node.node_token] = f"dry-run-child-of:{parent_target}"
        else:
            item.errors.append(f"XML fallback supports docx nodes only; got {node.obj_type!r}.")
        items.append(item)
    return items


def transfer_tree(
    source_tree_url: str,
    target_parent_url_or_token: str,
    target_position: str,
    as_identity: str,
    skip_native_copy: bool,
    dry_run: bool,
    max_depth: int,
) -> tuple[dict[str, Any], list[TransferItem]]:
    target_parent = get_wiki_node(target_parent_url_or_token, as_identity)
    target_parent_node_token = target_parent["node_token"]
    tree = collect_wiki_tree(source_tree_url, as_identity, max_depth=max_depth)
    if not tree:
        raise RuntimeError("Source tree is empty.")

    metadata: dict[str, Any] = {
        "source_tree_count": len(tree),
        "source_tree_preview": [node_summary(node) for node in tree],
        "target_parent": node_summary(target_parent),
    }

    root = tree[0]
    root_native_item = TransferItem(
        source_url=wiki_url(root.node_token),
        title=root.title,
        source_type=root.obj_type,
        source_token=root.obj_token,
        source_space_id=root.space_id,
        source_node_token=root.node_token,
        target_parent_node_token=target_parent_node_token,
        depth=root.depth,
    )

    if not skip_native_copy:
        try_native_wiki_copy(
            root_native_item,
            inspect_data_from_wiki_node(root),
            as_identity,
            dry_run,
            target_parent_node_token=target_parent_node_token,
        )
        metadata["native_tree_copy_attempt"] = root_native_item.attempts[-1:] or []
        if root_native_item.ok:
            if root_native_item.new_node_token and not dry_run:
                try:
                    copied_tree = collect_wiki_tree(root_native_item.new_node_token, as_identity)
                    metadata["created_tree_count"] = len(copied_tree)
                    metadata["created_tree_preview"] = [node_summary(node) for node in copied_tree]
                except Exception as exc:  # noqa: BLE001 - native copy itself already succeeded.
                    root_native_item.warnings.append(f"Could not list copied tree: {exc}")
            return metadata, [root_native_item]

    if dry_run:
        return metadata, dry_run_tree_items(tree, target_parent_node_token)

    created_parent_by_source: dict[str, str] = {}
    items: list[TransferItem] = []
    native_attempts = list(root_native_item.attempts)

    for node in tree:
        parent_target = (
            target_parent_node_token
            if node.depth == 0
            else created_parent_by_source.get(node.parent_node_token or "")
        )
        if not parent_target:
            item = TransferItem(
                source_url=wiki_url(node.node_token),
                ok=False,
                title=node.title,
                source_type=node.obj_type,
                source_token=node.obj_token,
                source_space_id=node.space_id,
                source_node_token=node.node_token,
                depth=node.depth,
            )
            item.errors.append("Parent transfer failed or did not yield a wiki node token; skipped.")
            items.append(item)
            continue

        leaf_native_allowed = not skip_native_copy and node.obj_type != "docx" and not node.has_child
        item = transfer_one(
            wiki_url(node.node_token),
            target_position,
            None,
            as_identity,
            not leaf_native_allowed,
            False,
            target_parent_node_token=parent_target,
            source_node=node,
        )
        if node.depth == 0 and native_attempts:
            item.attempts = native_attempts + item.attempts
        items.append(item)
        if item.ok and item.new_node_token:
            created_parent_by_source[node.node_token] = item.new_node_token

    return metadata, items


def load_urls(args: argparse.Namespace) -> list[str]:
    urls = list(args.urls)
    if args.input_file:
        text = Path(args.input_file).read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)
    seen: set[str] = set()
    unique = []
    for url in urls:
        if url not in seen:
            unique.append(url)
            seen.add(url)
    return unique


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "迁移飞书/Lark Wiki、Docx 链接或 Wiki 子树并验证质量。 / "
            "Transfer Feishu/Lark Wiki, Docx links, or Wiki subtrees with validation."
        )
    )
    parser.add_argument("urls", nargs="*", help="要迁移的飞书/Lark Wiki 或 Docx URL / URLs to transfer")
    parser.add_argument("--input-file", help="每行一个 URL 的 UTF-8 文件 / UTF-8 file with one URL per line")
    parser.add_argument("--source-tree-url", help="递归迁移的 Wiki 根节点 URL/Token / Root Wiki node URL/token")
    parser.add_argument("--target-parent-url", help="树迁移的目标 Wiki 父节点 / Target Wiki parent node")
    parser.add_argument("--target-position", default="my_library", help="文档创建位置 / Document parent position")
    parser.add_argument("--target-space-id", help="原生复制的目标 space_id / Target space_id for native copy")
    parser.add_argument("--as", dest="as_identity", default="user", choices=["user", "bot"])
    parser.add_argument("--skip-native-copy", action="store_true", help="直接使用 XML 重建 / Go straight to XML rebuild")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不创建文档 / Preview without creating documents")
    parser.add_argument("--max-depth", type=int, default=0, help="树深度限制，0 为无限 / Tree depth limit; 0 is unlimited")
    parser.add_argument("--report", help="JSON 报告输出路径 / JSON report output path")
    parser.add_argument("--no-auth-check", action="store_true", help="跳过认证和权限预检 / Skip auth and scope preflight")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    urls = load_urls(args)
    if args.source_tree_url and urls:
        parser.error("--source-tree-url 与位置参数/输入文件不能同时使用 / choose a tree URL or flat URLs, not both")
    if args.source_tree_url and not args.target_parent_url:
        parser.error("--source-tree-url 需要 --target-parent-url / --source-tree-url requires --target-parent-url")
    if not args.source_tree_url and not urls:
        parser.error("请至少提供一个 URL 或 --input-file / provide at least one URL or --input-file")

    report: dict[str, Any] = {
        "ok": False,
        "dry_run": args.dry_run,
        "mode": "tree" if args.source_tree_url else "flat",
        "target_position": args.target_position,
        "items": [],
    }

    try:
        if not args.no_auth_check:
            report["environment"] = check_environment(args.as_identity)

        if args.source_tree_url:
            metadata, items = transfer_tree(
                args.source_tree_url,
                args.target_parent_url,
                args.target_position,
                args.as_identity,
                args.skip_native_copy,
                args.dry_run,
                args.max_depth,
            )
            report.update(metadata)
        else:
            target_space_id = args.target_space_id or resolve_my_library_space(args.as_identity)
            report["target_space_id"] = target_space_id
            items = [
                transfer_one(
                    url,
                    args.target_position,
                    target_space_id,
                    args.as_identity,
                    args.skip_native_copy,
                    args.dry_run,
                )
                for url in urls
            ]
        report["items"] = [item.__dict__ for item in items]
        report["ok"] = all(item.ok for item in items)
    except Exception as exc:  # noqa: BLE001
        report["error"] = str(exc)

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        Path(args.report).write_text(text + "\n", encoding="utf-8")
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
