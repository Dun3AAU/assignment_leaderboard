# Assignment Leaderboard

A small data pipeline that aggregates cross-repository GitHub contribution activity into CSV outputs and publishes a GitHub Pages dashboard.

## What It Tracks

For each repository listed in `assignments.txt`, the collector:
- Reads all pull requests
- Excludes PRs authored by the repository owner
- Includes only PRs authored by participants listed in `assignments.txt`
- Aggregates PR counts and changed lines (additions/deletions)

The aggregate leaderboard always includes all listed participants. Participants with no qualifying contributions are included with zero values.

## Repository Layout

- `assignments.txt`: participant names and repository URLs
- `github_leaderboard.py`: data collection and aggregation script
- `docs/leaderboard.csv`: dashboard leaderboard data source
- `docs/repo_breakdown.csv`: dashboard repo breakdown data source
- `leaderboard.csv`: mirrored aggregate output at repository root
- `repo_breakdown.csv`: mirrored repo breakdown output at repository root
- `docs/`: static dashboard source files for GitHub Pages
- `.github/workflows/leaderboard.yml`: scheduled data refresh workflow
- `.github/workflows/deploy-pages.yml`: Pages deployment workflow

## Input Format

Each line in `assignments.txt` should contain a display name and a GitHub URL.

Example:

```text
Jane Doe    https://github.com/janedoe/project-repo
```

URLs with additional path segments (for example `/tree/main`) are supported.

## Setup

Install dependencies with uv:

```powershell
uv sync
```

Create a `.env` file in the project root:

```dotenv
GITHUB_TOKEN=ghp_example_token
```

## Run the Collector

```powershell
uv run python .\github_leaderboard.py --assignments .\assignments.txt --output .\leaderboard.csv --output-repo .\repo_breakdown.csv
```

Optional date filtering:

```powershell
uv run python .\github_leaderboard.py --since 2026-03-01 --until 2026-03-30T23:59:59Z
```

## Dashboard Preview (Local)

Do not open `docs/index.html` directly with `file://`.

Serve the repository from a local HTTP server:

```powershell
uv run python -m http.server 8000
```

Then open:

`http://localhost:8000/docs/index.html`

## Automation

### Leaderboard Refresh

Workflow: `.github/workflows/leaderboard.yml`

Schedule: 07:00, 12:00, 17:00, and 22:00 UTC daily.

This workflow:
- Syncs dependencies with uv
- Regenerates `docs/leaderboard.csv` and `docs/repo_breakdown.csv`
- Mirrors CSV outputs to repository root for non-dashboard consumers
- Commits and pushes updated CSV files when data changes

### GitHub Pages Deployment

Workflow: `.github/workflows/deploy-pages.yml`

Trigger:
- Runs automatically after a successful run of `Update Leaderboard`
- Can also be triggered manually

This workflow packages dashboard assets and CSV outputs and deploys them to GitHub Pages.

## Required Repository Secret

Add this Actions secret for scheduled API access:

- `GH_PAT`: Personal Access Token with permissions needed to read repository PR metadata

## Output Columns

### leaderboard.csv

- `contributor`
- `prs_total`
- `prs_merged`
- `additions_all`
- `deletions_all`
- `changed_lines_all`
- `additions_merged`
- `deletions_merged`
- `changed_lines_merged`

### repo_breakdown.csv

- `repo_owner`
- `repo_name`
- `contributor`
- `prs_total`
- `prs_merged`
- `additions_all`
- `deletions_all`
- `changed_lines_all`
- `additions_merged`
- `deletions_merged`
- `changed_lines_merged`

## Security Notes

- Never commit real tokens to version control.
- Store local credentials in `.env` and CI credentials in GitHub Actions secrets.
