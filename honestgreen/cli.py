"""Command line interface: `honestgreen check`, `honestgreen policy init`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from honestgreen import __version__, engine, gitio, policy, report

EXIT_OK, EXIT_FINDINGS, EXIT_ERROR = 0, 1, 2


def cmd_check(args: argparse.Namespace) -> int:
    repo = Path(args.repo).resolve()
    head = None if args.head in (None, "WORKTREE") else args.head
    if args.policy:
        pol = policy.load(Path(args.policy))
    else:
        # Read the policy from the base, never from the change under review:
        # otherwise a change could relax its own policy (e.g. fail_on = "never").
        base_commit = gitio.merge_base(repo, args.base, head or "HEAD")
        pol = policy.from_text(gitio.read_at(repo, base_commit, policy.POLICY_FILE),
                               f"{args.base}:{policy.POLICY_FILE}")
    if args.fail_on:
        pol.fail_on = args.fail_on
    claims_text = None
    if args.claims:
        claims_text = sys.stdin.read() if args.claims == "-" else Path(args.claims).read_text()
    result = engine.run(repo, args.base, head, pol, claims_text)
    text = report.FORMATS[args.format](result)
    if args.output:
        Path(args.output).write_text(text + "\n")
    else:
        print(text)
    return EXIT_FINDINGS if result.failed else EXIT_OK


def cmd_policy_init(args: argparse.Namespace) -> int:
    target = Path(args.repo) / policy.POLICY_FILE
    if target.exists() and not args.force:
        print(f"{target} already exists (use --force to overwrite)", file=sys.stderr)
        return EXIT_ERROR
    target.write_text(policy.DEFAULT_POLICY)
    print(f"Created {target}")
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="honestgreen", description="Detect changes that weaken a test suite.")
    p.add_argument("--version", action="version", version=f"honestgreen {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    c = sub.add_parser("check", help="analyse test changes between a base ref and HEAD / working tree")
    c.add_argument("--base", default="main", help="base branch or commit (default: main)")
    c.add_argument("--head", default=None,
                   help="head commit (default: the working tree, including uncommitted changes)")
    c.add_argument("--format", choices=report.FORMATS, default="text")
    c.add_argument("--output", help="write the report to a file instead of stdout")
    c.add_argument("--policy", help=f"policy file (default: <repo>/{policy.POLICY_FILE})")
    c.add_argument("--fail-on", choices=["high", "medium", "low", "never"],
                   help="override the policy's fail_on")
    c.add_argument("--claims", metavar="FILE",
                   help="the author's summary (agent final message or PR description; '-' for stdin). "
                        "Reports changes it does not mention (HG030)")
    c.add_argument("--repo", default=".", help="repository path (default: current directory)")
    c.set_defaults(func=cmd_check)

    pol = sub.add_parser("policy", help="manage the policy file")
    pol_sub = pol.add_subparsers(dest="policy_command", required=True)
    init = pol_sub.add_parser("init", help=f"create {policy.POLICY_FILE}")
    init.add_argument("--repo", default=".")
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_policy_init)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (gitio.GitError, policy.PolicyError) as e:
        print(f"honestgreen: error: {e}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
