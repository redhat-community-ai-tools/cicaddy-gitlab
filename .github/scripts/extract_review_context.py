#!/usr/bin/env python3
"""Extract code knowledge graph review context for CI pre-review step."""

import argparse
import json
import os
import subprocess
import sys


def get_changed_files(base_ref: str) -> list[str]:
    """Get changed files from git diff against base ref."""
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        capture_output=True,
        text=True,
    )
    return [f for f in result.stdout.strip().split("\n") if f]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract code graph review context"
    )
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Base git ref for diff (default: origin/main)",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="BFS traversal depth (default: 2)",
    )
    parser.add_argument(
        "--max-lines",
        type=int,
        default=200,
        help="Max source lines per file (default: 200)",
    )
    args = parser.parse_args()

    changed_files = get_changed_files(args.base_ref)
    if not changed_files:
        json.dump({"status": "no_changes", "changed_files": []}, sys.stdout, indent=2)
        return

    try:
        from code_review_graph.graph import GraphStore

        store = GraphStore(".")
        context = store.get_review_context(
            changed_files,
            max_depth=args.max_depth,
            include_source=True,
            max_lines_per_file=args.max_lines,
        )
        json.dump(context, sys.stdout, indent=2)
    except ImportError:
        print(
            "code-review-graph not installed, outputting changed files only",
            file=sys.stderr,
        )
        json.dump(
            {"status": "no_graph", "changed_files": changed_files}, sys.stdout, indent=2
        )
    except Exception as e:
        print(f"Graph analysis failed: {e}", file=sys.stderr)
        json.dump(
            {"status": "error", "error": str(e), "changed_files": changed_files},
            sys.stdout,
            indent=2,
        )


if __name__ == "__main__":
    main()
