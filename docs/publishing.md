# Publish Cloud Detective AI

Nothing has been pushed. Run these commands yourself only after reviewing the files. Never paste credentials into chat or put a token in a remote URL.

## Before your first commit

1. The license names D.M.G.Dissanayaka. Replace `YOUR_GITHUB_USERNAME` in README.
2. Fill the README screenshot placeholders with reviewed screenshots.
3. Review docs/publication-security.md and the known limitations in README.
4. Install Git if needed and sign in through Git Credential Manager's browser flow or GitHub Desktop when prompted.

## Exact PowerShell commands

```powershell
Set-Location 'C:\Users\HP\Desktop\codex\cloud-detective-ai'
git init -b main
# Only if Git has no author identity configured; use your preferred public/noreply email:
git config user.name "YOUR NAME"
git config user.email "YOUR_GITHUB_NOREPLY_EMAIL"

git status --short --untracked-files=all
git check-ignore .env .local-backups/ .venv/ frontend/node_modules/
git add .
git diff --cached --stat
git diff --cached --name-only
# This command should print no files:
git ls-files -- .env '.env.local' '.local-backups/*' '.venv/*' 'frontend/node_modules/*'
# Review the actual staged diff locally before committing:
git diff --cached
git commit -m "feat: add Cloud Detective AI incident investigation demo"
```

If a private file appears in the staged list, stop and unstage that specific file with `git rm --cached -- PATH` (or `git rm -r --cached -- DIRECTORY`), update .gitignore and review again. Do not use `git add -f` for ignored files.

## Create the GitHub repository yourself

In your browser, sign into GitHub and open https://github.com/new. Set the repository name to **cloud-detective-ai** and select **Public** for a CV portfolio. Leave README, .gitignore and license initialization disabled because these already exist locally. Click **Create repository**.

Return to PowerShell, replacing the username:

```powershell
git remote add origin https://github.com/gajendra54-design/Cloud-Detective-AI.git
git remote -v
git push -u origin main
```

Complete authentication through your own credential-manager/browser prompt. Do not send anyone your password or token. These steps follow [GitHub's existing-project guide](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github).

After pushing, open the **Actions** tab and inspect the checks. Do not claim CI passes until the run is green. Add the description/topics below and link the repository on your CV. The local preparation did not create a remote, push, or validate remote Actions.

## Optional logical commit messages

A single honest initial import is fine. If you prefer to stage related files separately *before* the first commit, these seven messages describe useful groups. They are not a fabricated development history or a claim that each group was independently released.

1. `chore: configure Compose stack and dependency locks`
2. `feat: add instrumented checkout and payment demo services`
3. `feat: persist incident detection and evidence in PostgreSQL`
4. `feat: add role-based approvals and verified recovery actions`
5. `feat: build incident investigation dashboard`
6. `test: cover recovery concurrency and database outages`
7. `docs: add setup guide, security limitations and MIT license`

## Repository metadata

- **Name:** `cloud-detective-ai`
- **Description:** Local incident investigation demo with evidence-backed diagnosis, human-approved recovery and independent verification.
- **Topics:** `fastapi`, `react`, `observability`, `incident-response`, `docker-compose`

## CV bullets

- Built a local incident investigation platform using FastAPI, React and PostgreSQL, connecting failure detection, evidence review and human-approved recovery in one workflow.
- Instrumented checkout and payment services with Prometheus, Grafana and OpenTelemetry to correlate metrics and traces during controlled failures.
- Implemented role-separated approvals and repeat-execution protection with SQLAlchemy, and validated recovery and database reconnection through automated Python tests.

These bullets describe implemented behavior without claiming production deployment, autonomous infrastructure control or unmeasured business impact.
