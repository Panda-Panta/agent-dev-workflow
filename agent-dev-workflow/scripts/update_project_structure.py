#!/usr/bin/env python3
"""Maintain a project directory tree inside a Markdown document. Python 3 only."""

import argparse
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from functools import lru_cache
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile


BEGIN = "<!-- BEGIN AUTO STRUCTURE -->"
END = "<!-- END AUTO STRUCTURE -->"
FIXED_EXCLUDES = (".git", "node_modules", "dist", "build", "target", "venv", ".venv",
                  "__pycache__", "cache", ".cache", "coverage", ".next")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="Project root directory")
    parser.add_argument("--output", default="PROJECT_STRUCTURE.md", type=Path,
                        help="UTF-8 .md/.markdown path inside root (default: PROJECT_STRUCTURE.md)")
    parser.add_argument("--depth", default=4, type=int, help="Maximum displayed path depth, root is 0 (default: 4)")
    parser.add_argument("--exclude", action="append", default=[], metavar="GLOB",
                        help="Repeatable glob: basename anywhere, or root-relative / path; ** matches directories")
    parser.add_argument("--check", action="store_true", help="Read-only check: 0 current, 1 stale, 2 error")
    return parser.parse_args()


def visible(value):
    """Keep unusual path characters from adding Markdown lines or marker tokens."""
    return "".join(
        "\\x%02x" % ord(char) if char in "`<>\\" or ord(char) < 32 or ord(char) == 127
        else "\\u%04x" % ord(char) if 0xD800 <= ord(char) <= 0xDFFF else char
        for char in value
    )


def path_glob(parts, pattern):
    @lru_cache(maxsize=None)
    def matches(index, step):
        if step == len(pattern):
            return index == len(parts)
        if pattern[step] == "**":
            return matches(index, step + 1) or (index < len(parts) and matches(index + 1, step))
        return index < len(parts) and fnmatchcase(parts[index], pattern[step]) and matches(index + 1, step + 1)
    return matches(0, 0)


def excluded(relative, kind, patterns):
    parts = relative.split("/")
    name = parts[-1].casefold()
    if name in FIXED_EXCLUDES:
        return True
    if (name == ".env" or name.startswith(".env.")) and name not in (".env.example", ".env.sample"):
        return True
    for raw in patterns:
        directory_only = raw.endswith("/")
        pattern = raw.rstrip("/")
        if directory_only and kind != "dir":
            continue
        if "/" not in pattern:
            if fnmatchcase(parts[-1], pattern):
                return True
        elif path_glob(tuple(parts), tuple(pattern.lstrip("/").split("/"))):
            return True
    return False


def path_kind(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        return "link"
    return "dir" if stat.S_ISDIR(info.st_mode) else "file"


def reject_link_components(path):
    """Inspect the lexical path before resolve() could hide a link or junction."""
    absolute = path if path.is_absolute() else Path.cwd() / path
    current = Path(absolute.anchor)
    for piece in absolute.parts[1:]:
        current = current / piece
        try:
            if path_kind(current) == "link":
                raise ValueError("Output/root path must not pass through a symbolic link, junction, or reparse point")
        except FileNotFoundError:
            continue


def validate_output(root, output):
    if output.suffix.casefold() not in (".md", ".markdown"):
        raise ValueError("--output must have a .md or .markdown extension")
    if os.name == "nt" and any(":" in part for part in output.parts[1:]):
        raise ValueError("--output must not name a Windows alternate data stream")
    reject_link_components(output)
    resolved = output.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        raise ValueError("--output must be inside the resolved --root directory") from None
    if resolved == root:
        raise ValueError("--output must name a file, not the project root")
    try:
        info = resolved.lstat()
    except FileNotFoundError:
        return resolved
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("--output must be a regular file")
    if info.st_nlink > 1:
        raise ValueError("--output has multiple hard links; refusing to modify an aliased file")
    return resolved


def write_document(root, output, original, rendered):
    """Stage a complete replacement only after validation; never rewrite equal bytes."""
    validate_output(root, output)
    output.parent.mkdir(parents=True, exist_ok=True)
    validate_output(root, output)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(prefix=".structure-", suffix=".tmp", dir=output.parent, delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(rendered)
            handle.flush()
            os.fsync(handle.fileno())
        validate_output(root, output)
        current = output.read_bytes() if output.exists() else None
        if current != original:
            raise ValueError("--output changed during indexing; rerun to preserve concurrent edits")
        if original is not None:
            os.chmod(temp_path, stat.S_IMODE(output.stat().st_mode))
        os.replace(temp_path, output)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def contains_links(root):
    """Git for Windows follows junctions; preflight metadata without following links.

    Inspect even ignored/excluded source directories, since Git has not applied
    our display exclusions. Git's own .git metadata directories are never walked.
    """
    pending = [root]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                try:
                    kind = path_kind(Path(entry.path))
                except FileNotFoundError:
                    continue
                if kind == "link":
                    return True
                if kind == "dir" and entry.name.casefold() != ".git":
                    pending.append(entry.path)
    return False


def git_paths(root):
    """Use NUL-separated names, retaining tracked files even if now ignored."""
    try:
        probe = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
                               capture_output=True, timeout=30)
        if probe.returncode != 0 or probe.stdout.strip() != b"true":
            return None, "filesystem (Git worktree unavailable; gitignore is not applied)"
        if contains_links(root):
            return None, "filesystem (link protection: Git enumeration can follow junctions; gitignore is not applied)"
        result = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others",
                                 "--exclude-standard", "-z", "--", "."], capture_output=True, timeout=60)
        if result.returncode != 0:
            return None, "filesystem (git ls-files failed; gitignore is not applied)"
        names = {os.fsdecode(name) for name in result.stdout.split(b"\0") if name}
        return sorted(names), "git (git ls-files --cached --others --exclude-standard; deduplicated)"
    except (OSError, subprocess.TimeoutExpired):
        return None, "filesystem (Git unavailable or timed out; gitignore is not applied)"


def collect(root, output, patterns):
    paths = {}
    candidates, mode = git_paths(root)
    if candidates is not None:
        for relative in candidates:
            parts = relative.split("/")
            if relative.startswith("/") or any(part in ("", ".", "..") for part in parts):
                raise ValueError("Git returned an invalid relative path")
            for index in range(len(parts)):
                name = "/".join(parts[:index + 1])
                try:
                    kind = path_kind(root.joinpath(*parts[:index + 1]))
                except FileNotFoundError:
                    break
                if excluded(name, kind, patterns):
                    break
                paths[name] = kind
                if kind != "dir":
                    break
    else:
        def walk(directory, prefix=""):
            with os.scandir(directory) as entries:
                for entry in entries:
                    relative = prefix + entry.name
                    try:
                        kind = path_kind(Path(entry.path))
                    except FileNotFoundError:
                        continue
                    if excluded(relative, kind, patterns):
                        continue
                    paths[relative] = kind
                    if kind == "dir":
                        walk(entry.path, relative + "/")
        walk(root)
    # Always include the output itself, even before creation or when ignored.
    pieces = output.relative_to(root).parts
    for index in range(len(pieces)):
        paths["/".join(pieces[:index + 1])] = "file" if index == len(pieces) - 1 else "dir"
    return paths, mode


@dataclass
class Node:
    kind: str = "dir"
    children: dict = field(default_factory=dict)
    output_path: bool = False


def tree_lines(paths, depth, output_relative):
    tree = Node()
    pieces = output_relative.split("/")
    output_ancestors = {"/".join(pieces[:index + 1]) for index in range(len(pieces))}
    for path, kind in sorted(paths.items()):
        node = tree
        pieces = path.split("/")
        for piece in pieces[:-1]:
            node = node.children.setdefault(piece, Node())
        node.children.setdefault(pieces[-1], Node(kind)).kind = kind
        node.children[pieces[-1]].output_path = path in output_ancestors

    def visit(node, prefix="", level=1):
        names = sorted((name for name in node.children if level <= depth or node.children[name].output_path),
                       key=lambda name: (node.children[name].kind != "dir", name.casefold(), name))
        for index, name in enumerate(names):
            last = index == len(names) - 1
            child = node.children[name]
            suffix = "/" if child.kind == "dir" else " [link; not traversed]" if child.kind == "link" else ""
            if child.children and level >= depth:
                suffix += " [depth limit: only output path shown]" if child.output_path else " [depth limit: children omitted]"
            yield prefix + ("└── " if last else "├── ") + visible(name) + suffix
            if child.children and (level < depth or child.output_path):
                yield from visit(child, prefix + ("    " if last else "│   "), level + 1)

    return ["./", *visit(tree)]


def merge_document(old, lines):
    """Leave all manually authored bytes outside the marker pair intact."""
    has_bom = old is not None and old.startswith(b"\xef\xbb\xbf")
    text = old.decode("utf-8-sig") if old is not None else "# Project structure\n\n"
    newline_match = re.search(r"\r\n|\n|\r", text)
    newline = newline_match.group() if newline_match else "\n"
    mentions = re.findall(r"<!--\s*(?:BEGIN|END)\s+AUTO\s+STRUCTURE\b", text)
    positions = {}
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\r\n").strip(" \t")
        if stripped in (BEGIN, END):
            positions.setdefault(stripped, []).append((offset, offset + line.index(stripped)))
        offset += len(line)
    body = newline.join(lines)
    if mentions or BEGIN in text or END in text:
        if (len(mentions) != 2 or text.count(BEGIN) != 1 or text.count(END) != 1
                or len(positions.get(BEGIN, [])) != 1 or len(positions.get(END, [])) != 1):
            raise ValueError("Malformed or duplicate AUTO STRUCTURE markers; use one complete pair on separate lines")
        begin = positions[BEGIN][0][1] + len(BEGIN)
        end = positions[END][0][0]
        if end < begin:
            raise ValueError("AUTO STRUCTURE end marker precedes begin marker")
        result = text[:begin] + newline + body + newline + text[end:]
    else:
        gap = "" if not text or text.endswith(newline * 2) else newline if text.endswith(newline) else newline * 2
        result = text + gap + BEGIN + newline + body + newline + END + newline
    return (b"\xef\xbb\xbf" if has_bom else b"") + result.encode("utf-8")


def main():
    args = arguments()
    try:
        reject_link_components(args.root)
        root = args.root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("--root must be a directory")
        if args.depth < 1:
            raise ValueError("--depth must be at least 1")
        output = args.output if args.output.is_absolute() else root / args.output
        output = validate_output(root, output)
        paths, mode = collect(root, output, args.exclude)
        lines = ["Index mode: " + mode + ".", "Depth: %d (root is 0; deeper children are omitted)." % args.depth,
                 "Fixed exclusions (any path component, case-insensitive): " + ", ".join(FIXED_EXCLUDES) + ".",
                 "Environment exclusions: .env, .env.*; exceptions: .env.example, .env.sample.",
                 "Custom exclusions (case-sensitive glob): " + (", ".join(visible(p) for p in args.exclude) or "none") + ".",
                 "The output path is always included, even when ignored, excluded, or beyond the depth limit.",
                 "", "```text", *tree_lines(paths, args.depth, output.relative_to(root).as_posix()), "```"]
        old = output.read_bytes() if output.exists() else None
        rendered = merge_document(old, lines)
        if old == rendered:
            print("Project structure is current.")
            return 0
        if args.check:
            print("Project structure is stale.")
            return 1
        write_document(root, output, old, rendered)
        print("Project structure updated.")
        return 0
    except (OSError, ValueError) as error:
        print("error: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
