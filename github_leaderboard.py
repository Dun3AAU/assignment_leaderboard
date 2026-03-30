#!/usr/bin/env python3
"""Build a cross-repo contribution leaderboard from GitHub pull requests.

The script expects an input file where each line contains a participant name and a
GitHub URL separated by at least two spaces.

Example line:
    Jane Doe    https://github.com/example-user/example-repo

For each repo, it collects PRs and excludes PRs authored by that repo owner.
It then aggregates contributor stats across all listed repositories.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from dotenv import load_dotenv
from typing import Dict, Iterable, List, Optional, Tuple


@dataclass
class RepoEntry:
    participant_name: str
    source_url: str
    owner: str
    repo: str


@dataclass
class ContributorStats:
    prs_total: int = 0
    prs_merged: int = 0
    additions_all: int = 0
    deletions_all: int = 0
    additions_merged: int = 0
    deletions_merged: int = 0


@dataclass
class RepoContributorStats:
    owner: str
    repo: str
    contributor: str
    prs_total: int = 0
    prs_merged: int = 0
    additions_all: int = 0
    deletions_all: int = 0
    additions_merged: int = 0
    deletions_merged: int = 0


def parse_iso8601(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Invalid timestamp '{value}'. Use ISO 8601, e.g. 2026-03-01 or 2026-03-01T00:00:00Z"
        ) from exc


def parse_repo_from_url(url: str) -> Optional[Tuple[str, str]]:
    parsed = urllib.parse.urlparse(url.strip())
    if not parsed.netloc or "github.com" not in parsed.netloc.lower():
        return None

    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) < 2:
        return None

    owner = path_parts[0]
    repo = path_parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    return owner, repo


def parse_assignments_file(path: str) -> List[RepoEntry]:
    entries: List[RepoEntry] = []
    with open(path, "r", encoding="utf-8") as infile:
        for line_number, raw_line in enumerate(infile, start=1):
            line = raw_line.strip()
            if not line:
                continue

            url_match = re.search(r"https?://github\.com/\S+", line, re.IGNORECASE)
            if url_match:
                url = url_match.group(0).strip()
                name = line[: url_match.start()].strip()
                if not name:
                    print(f"Skipping malformed line {line_number}: {raw_line.rstrip()}", file=sys.stderr)
                    continue
            else:
                parts = re.split(r"\s{2,}", line, maxsplit=1)
                if len(parts) == 2:
                    name, url = parts[0].strip(), parts[1].strip()
                else:
                    tokens = line.split()
                    if len(tokens) < 2:
                        print(f"Skipping malformed line {line_number}: {raw_line.rstrip()}", file=sys.stderr)
                        continue
                    name = " ".join(tokens[:-1])
                    url = tokens[-1]

            repo_parts = parse_repo_from_url(url)
            if not repo_parts:
                print(f"Skipping non-GitHub or malformed URL on line {line_number}: {url}", file=sys.stderr)
                continue

            owner, repo = repo_parts
            entries.append(
                RepoEntry(
                    participant_name=name,
                    source_url=url,
                    owner=owner,
                    repo=repo,
                )
            )

    return entries


def github_get_json(url: str, token: Optional[str]) -> dict | list:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "assignment-leaderboard-script",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API error {exc.code} for {url}: {details}") from exc


def fetch_pull_requests(owner: str, repo: str, token: Optional[str]) -> List[dict]:
    prs: List[dict] = []
    page = 1

    while True:
        url = (
            f"https://api.github.com/repos/{owner}/{repo}/pulls"
            f"?state=all&per_page=100&page={page}"
        )
        data = github_get_json(url, token)
        if not isinstance(data, list):
            raise RuntimeError(f"Unexpected response when listing PRs for {owner}/{repo}")

        if not data:
            break

        prs.extend(data)
        page += 1

    return prs


def fetch_pr_details(owner: str, repo: str, pr_number: int, token: Optional[str]) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    data = github_get_json(url, token)
    if not isinstance(data, dict):
        raise RuntimeError(f"Unexpected response for PR {owner}/{repo}#{pr_number}")
    return data


def in_time_window(created_at: str, since: Optional[datetime], until: Optional[datetime]) -> bool:
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)

    if since and created < since:
        return False
    if until and created > until:
        return False
    return True


def update_stats(stats: ContributorStats, is_merged: bool, additions: int, deletions: int) -> None:
    stats.prs_total += 1
    stats.additions_all += additions
    stats.deletions_all += deletions
    if is_merged:
        stats.prs_merged += 1
        stats.additions_merged += additions
        stats.deletions_merged += deletions


def update_repo_stats(
    stats: RepoContributorStats,
    is_merged: bool,
    additions: int,
    deletions: int,
) -> None:
    stats.prs_total += 1
    stats.additions_all += additions
    stats.deletions_all += deletions
    if is_merged:
        stats.prs_merged += 1
        stats.additions_merged += additions
        stats.deletions_merged += deletions


def write_leaderboard_csv(path: str, aggregated: Dict[str, ContributorStats]) -> None:
    rows = []
    for contributor, stats in aggregated.items():
        rows.append(
            {
                "contributor": contributor,
                "prs_total": stats.prs_total,
                "prs_merged": stats.prs_merged,
                "additions_all": stats.additions_all,
                "deletions_all": stats.deletions_all,
                "changed_lines_all": stats.additions_all + stats.deletions_all,
                "additions_merged": stats.additions_merged,
                "deletions_merged": stats.deletions_merged,
                "changed_lines_merged": stats.additions_merged + stats.deletions_merged,
            }
        )

    rows.sort(
        key=lambda r: (
            r["changed_lines_merged"],
            r["prs_merged"],
            r["changed_lines_all"],
            r["prs_total"],
        ),
        reverse=True,
    )

    with open(path, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(
            outfile,
            fieldnames=[
                "contributor",
                "prs_total",
                "prs_merged",
                "additions_all",
                "deletions_all",
                "changed_lines_all",
                "additions_merged",
                "deletions_merged",
                "changed_lines_merged",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def ensure_all_participants_present(
    entries: Iterable[RepoEntry],
    aggregated: Dict[str, ContributorStats],
) -> Dict[str, ContributorStats]:
    ordered_usernames: List[str] = []
    seen: set[str] = set()

    for entry in entries:
        username = entry.owner.lower()
        if username in seen:
            continue
        seen.add(username)
        ordered_usernames.append(username)

    completed: Dict[str, ContributorStats] = {}
    for username in ordered_usernames:
        completed[username] = aggregated.get(username, ContributorStats())

    return completed


def write_repo_breakdown_csv(path: str, per_repo_stats: Dict[Tuple[str, str, str], RepoContributorStats]) -> None:
    rows = []
    for (owner, repo, contributor), stats in per_repo_stats.items():
        rows.append(
            {
                "repo_owner": owner,
                "repo_name": repo,
                "contributor": contributor,
                "prs_total": stats.prs_total,
                "prs_merged": stats.prs_merged,
                "additions_all": stats.additions_all,
                "deletions_all": stats.deletions_all,
                "changed_lines_all": stats.additions_all + stats.deletions_all,
                "additions_merged": stats.additions_merged,
                "deletions_merged": stats.deletions_merged,
                "changed_lines_merged": stats.additions_merged + stats.deletions_merged,
            }
        )

    rows.sort(
        key=lambda r: (
            r["repo_owner"].lower(),
            r["repo_name"].lower(),
            -r["changed_lines_merged"],
            -r["prs_merged"],
        )
    )

    with open(path, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(
            outfile,
            fieldnames=[
                "repo_owner",
                "repo_name",
                "contributor",
                "prs_total",
                "prs_merged",
                "additions_all",
                "deletions_all",
                "changed_lines_all",
                "additions_merged",
                "deletions_merged",
                "changed_lines_merged",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def build_leaderboard(
    entries: Iterable[RepoEntry],
    token: Optional[str],
    since: Optional[datetime],
    until: Optional[datetime],
) -> Tuple[Dict[str, ContributorStats], Dict[Tuple[str, str, str], RepoContributorStats]]:
    aggregated: Dict[str, ContributorStats] = {}
    per_repo_stats: Dict[Tuple[str, str, str], RepoContributorStats] = {}
    participant_usernames = {entry.owner.lower() for entry in entries}

    for entry in entries:
        print(f"Processing {entry.owner}/{entry.repo} ...")
        try:
            prs = fetch_pull_requests(entry.owner, entry.repo, token)
        except RuntimeError as exc:
            print(f"  Warning: {exc}", file=sys.stderr)
            continue

        for pr in prs:
            pr_number = pr.get("number")
            pr_created_at = pr.get("created_at")
            if not isinstance(pr_number, int) or not isinstance(pr_created_at, str):
                continue

            if not in_time_window(pr_created_at, since, until):
                continue

            try:
                details = fetch_pr_details(entry.owner, entry.repo, pr_number, token)
            except RuntimeError as exc:
                print(f"  Warning: {exc}", file=sys.stderr)
                continue

            author = ((details.get("user") or {}).get("login") or "").strip()
            if not author:
                continue

            # Competition asks for contributions from everyone else, not repo owner.
            if author.lower() == entry.owner.lower():
                continue

            # Count only contributions from listed participants.
            if author.lower() not in participant_usernames:
                continue

            additions = int(details.get("additions") or 0)
            deletions = int(details.get("deletions") or 0)
            is_merged = bool(details.get("merged_at"))

            contributor_key = author.lower()
            stats = aggregated.setdefault(contributor_key, ContributorStats())
            update_stats(stats, is_merged, additions, deletions)

            repo_key = (entry.owner.lower(), entry.repo.lower(), contributor_key)
            repo_stats = per_repo_stats.setdefault(
                repo_key,
                RepoContributorStats(owner=entry.owner, repo=entry.repo, contributor=author),
            )
            update_repo_stats(repo_stats, is_merged, additions, deletions)

    return aggregated, per_repo_stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a cross-repo contribution leaderboard from GitHub PR data.")
    parser.add_argument(
        "--assignments",
        default="assignments.txt",
        help="Input file with participant names and GitHub repo URLs (default: assignments.txt).",
    )
    parser.add_argument(
        "--output",
        default="leaderboard.csv",
        help="Path to output aggregated leaderboard CSV (default: leaderboard.csv).",
    )
    parser.add_argument(
        "--output-repo",
        default="repo_breakdown.csv",
        help="Path to output repo-level breakdown CSV (default: repo_breakdown.csv).",
    )
    parser.add_argument(
        "--token",
        default=os.getenv("GITHUB_TOKEN"),
        help="GitHub token (defaults to GITHUB_TOKEN env var).",
    )
    parser.add_argument(
        "--since",
        type=parse_iso8601,
        default=None,
        help="Only include PRs created on/after this ISO 8601 timestamp.",
    )
    parser.add_argument(
        "--until",
        type=parse_iso8601,
        default=None,
        help="Only include PRs created on/before this ISO 8601 timestamp.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv(override=False)

    args = parse_args()

    entries = parse_assignments_file(args.assignments)
    if not entries:
        print("No valid repositories found in assignments file.", file=sys.stderr)
        return 1

    if not args.token:
        print(
            "Warning: No GitHub token provided. Unauthenticated API requests are heavily rate-limited.",
            file=sys.stderr,
        )

    aggregated, per_repo_stats = build_leaderboard(
        entries=entries,
        token=args.token,
        since=args.since,
        until=args.until,
    )
    aggregated = ensure_all_participants_present(entries, aggregated)

    write_leaderboard_csv(args.output, aggregated)
    write_repo_breakdown_csv(args.output_repo, per_repo_stats)

    print(f"Wrote aggregated leaderboard to: {args.output}")
    print(f"Wrote repo-level breakdown to: {args.output_repo}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
