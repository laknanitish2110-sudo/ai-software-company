# GitHub Integration

#integration #level-4 #deploy

> Auto-deploy every project the Engineer builds. Judges click a link, see a working app.

## Status: `Planned` — starts when GitHub Student Developer Pack arrives

## Why This Matters

The Engineer currently generates code as a ZIP file. Nobody runs ZIP files at a hackathon. Judges want to **click a link and see it work.**

With GitHub integration, every pipeline run produces:
- A **public GitHub repo** with clean code
- A **live deployed URL** judges can visit
- A **CI/CD pipeline** that validates the code actually builds

## Architecture

```
Engineer generates code
    |
    v
[github.py] Create repo + push files
    |
    v
[GitHub Actions] Install deps -> Build -> Test
    |
    +---> Build fails? --> Feed errors to Engineer --> Fix --> Push again
    |
    +---> Build passes? --> Deploy
                              |
                              v
                    [Vercel / GitHub Pages]
                              |
                              v
                    Live URL returned to user
```

## Repo Strategy

One GitHub org (e.g. `sih-builds`), one repo per project.

```
sih-builds/smart-waste-management
sih-builds/grievance-redressal-ai
sih-builds/rural-health-monitor
```

Each repo is public, browsable, and shareable with judges.

## Deployment Targets

| Project Type | Deploy To | Cost |
|-------------|-----------|------|
| Static / React / Next.js | Vercel | Free (Student Pack) |
| Full-stack (Node + DB) | Vercel + Vercel Postgres | Free tier |
| Python backend | Railway | Free credits (Student Pack) |
| Static HTML/CSS/JS | GitHub Pages | Free |

**Primary:** Vercel (auto-deploy on push, instant `.vercel.app` URL)
**Fallback:** GitHub Pages (static sites only)

## GitHub Actions Workflow

Pushed into every repo as `.github/workflows/build.yml`:

```yaml
name: Build & Deploy
on: push
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Detect project type
        id: detect
        run: |
          if [ -f "package.json" ]; then echo "type=node" >> $GITHUB_OUTPUT
          elif [ -f "requirements.txt" ]; then echo "type=python" >> $GITHUB_OUTPUT
          else echo "type=static" >> $GITHUB_OUTPUT; fi
      - name: Setup Node
        if: steps.detect.outputs.type == 'node'
        uses: actions/setup-node@v4
        with: { node-version: '20' }
      - name: Install & Build (Node)
        if: steps.detect.outputs.type == 'node'
        run: npm install && npm run build
      - name: Setup Python
        if: steps.detect.outputs.type == 'python'
        uses: actions/setup-python@v5
        with: { python-version: '3.12' }
      - name: Install & Test (Python)
        if: steps.detect.outputs.type == 'python'
        run: pip install -r requirements.txt
      - name: Report status
        if: always()
        run: |
          curl -X POST "${{ secrets.WEBHOOK_URL }}" \
            -H "Content-Type: application/json" \
            -d '{"event":"build_status","repo":"${{ github.repository }}","status":"${{ job.status }}"}'
```

## New Backend Services

| File | Purpose |
|------|---------|
| `app/services/github.py` | GitHub API — create repo, push files, read Actions status |
| `app/services/deployer.py` | Vercel API — trigger deploy, get URL |
| `app/services/build_monitor.py` | Watch build status, feed errors back |

## Config Needed (.env)

```env
GITHUB_TOKEN=ghp_...          # Fine-grained PAT (repo, workflow, actions)
GITHUB_ORG=sih-builds         # Or personal account
VERCEL_TOKEN=...              # From Vercel dashboard
VERCEL_TEAM_ID=...            # Optional
```

## Orchestrator Changes

```python
# After Engineer approval:
files = generate_project_files(project_id, content)
repo_url = await github.create_and_push(project_id, files)
deploy_url = await deployer.deploy(repo_url, project_type)
build_ok = await build_monitor.wait_for_build(repo_url)

if not build_ok:
    errors = await build_monitor.get_errors(repo_url)
    # Auto-fix loop: feed errors back to Engineer
    
save_urls(project_id, repo_url, deploy_url)
start_next_agent(PPT)  # PPT now knows the live URL
```

## Phase 2: Interactive Engineer

After GitHub integration works, the Engineer stage becomes interactive:

1. Engineer shows build plan
2. User approves/modifies
3. Engineer generates v1 -> push -> deploy
4. User sees live preview
5. User requests changes -> Engineer iterates -> redeploy
6. Repeat until "ship it"
7. PPT creates slides with screenshots of the REAL app

## What GitHub Student Pack Provides

- GitHub repos (unlimited public)
- GitHub Actions (2,000 min/month free)
- GitHub Pages (free static hosting)
- Vercel Pro (free with Student Pack)
- Railway credits ($5/month)
- Azure credits ($100)
- Namecheap free domain (.me)

## Dependencies

- [[Tech Stack]]
- [[Orchestrator]]
- [[Engineer Agent]]
- [[Model Strategy]]
