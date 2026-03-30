# Assignment Leaderboard Collector

This project builds a leaderboard of cross-repo contributions using GitHub pull request data.

It reads repositories from `assignments.txt`, then for each repo:
- Fetches pull requests
- Excludes PRs authored by the repository owner ("everyone else" rule)
- Counts only PRs authored by people listed in `assignments.txt`
- Counts total PRs and merged PRs
- Sums added/deleted lines from PR metadata

The aggregate leaderboard always includes every listed participant. If someone has no qualifying contributions, their row is still included with zeroes.

## Files

- `assignments.txt`: input list of participant + GitHub URL
- `github_leaderboard.py`: data collection script
- `leaderboard.csv`: generated aggregate leaderboard (created after running)
- `repo_breakdown.csv`: generated per-repository breakdown (created after running)

## Input Format

Each line in `assignments.txt` should look like this:

Name<two or more spaces>GitHub URL

Example:

Jane Doe    https://github.com/janedoe/my-repo

The URL can include extra path segments (like `/tree/main`); the script still extracts owner/repo correctly.

## GitHub Token

Use a Personal Access Token to avoid strict rate limits.

Install dependencies with `uv`:

```powershell
uv sync
```

PowerShell example:

```powershell
$env:GITHUB_TOKEN = "ghp_your_token_here"
```

Or place it in a `.env` file in this folder:

```dotenv
GITHUB_TOKEN=ghp_your_token_here
```

For GitHub Actions automation, add a repository secret named `GH_PAT` containing your personal access token.

## Run

From this folder:

```powershell
uv run python .\github_leaderboard.py --assignments .\assignments.txt --output .\leaderboard.csv --output-repo .\repo_breakdown.csv
```

Optional date filtering (ISO 8601):

```powershell
uv run python .\github_leaderboard.py --since 2026-03-01 --until 2026-03-30T23:59:59Z
```

## Automation

Workflow file: `.github/workflows/leaderboard.yml`

It runs at 07:00, 12:00, 17:00, and 22:00 UTC daily, regenerates the CSV files, and commits changes back to the repository.

GitHub Pages deployment workflow: `.github/workflows/deploy-pages.yml`

This workflow runs automatically after `leaderboard.yml` completes successfully (and can also be triggered manually). It publishes a static dashboard page that reads `leaderboard.csv` and `repo_breakdown.csv`.

## Output Columns

`leaderboard.csv` includes:
- `contributor`
- `prs_total`
- `prs_merged`
- `additions_all`
- `deletions_all`
- `changed_lines_all`
- `additions_merged`
- `deletions_merged`
- `changed_lines_merged`

This gives you flexibility to choose your final ranking metric in your dashboard.
