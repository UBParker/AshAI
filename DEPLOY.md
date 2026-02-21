# Deploying AshAI

AshAI has two deployment targets:
1. **Backend (Gateway)** — Fly.io (Docker container)
2. **Frontend** — Cloudflare Pages (static SPA)

---

## Prerequisites

- [Fly.io CLI](https://fly.io/docs/getting-started/installing-flyctl/) installed
- A [Supabase](https://supabase.com) project
- A Cloudflare account (for Pages) or Vercel account
- An Anthropic/OpenAI API key

---

## Step 1: Supabase Setup

1. Create a new project at [supabase.com](https://supabase.com)
2. Go to **SQL Editor** and paste the contents of `supabase/migrations/20260220_friends_and_projects.sql`
3. Click **Run** to create all tables
4. Go to **Authentication > Settings** and enable Email auth
5. Note these values from **Settings > API**:
   - `Project URL` → `SUPABASE_URL`
   - `anon public key` → `SUPABASE_ANON_KEY` (for frontend)
   - `service_role secret key` → `SUPABASE_SERVICE_KEY` (for gateway only)

---

## Step 2: Deploy Backend to Fly.io

### First-time setup

```bash
# Login to Fly.io
fly auth login

# Launch the app (creates the app + volume, don't deploy yet)
fly launch --no-deploy

# Create persistent volume for user data
fly volumes create ashai_data --region iad --size 1

# Set secrets (these are encrypted, never in git)
fly secrets set \
  SUPABASE_URL="https://YOUR_PROJECT.supabase.co" \
  SUPABASE_SERVICE_KEY="eyJ..." \
  HELPERAI_ANTHROPIC_API_KEY="sk-ant-..." \
  HELPERAI_DEFAULT_PROVIDER="anthropic" \
  HELPERAI_DEFAULT_MODEL="claude-sonnet-4-20250514"

# Deploy
fly deploy
```

### Subsequent deploys

```bash
fly deploy
```

### Custom domain

```bash
# Add your domain
fly certs add gateway.ashai.net

# Then add a CNAME record in your DNS:
# gateway.ashai.net → ashai-gateway.fly.dev
```

### Useful commands

```bash
fly status              # Check app status
fly logs                # Stream logs
fly ssh console         # SSH into the container
fly scale count 1       # Ensure 1 instance running
fly scale vm shared-cpu-2x  # Resize VM
```

---

## Step 3: Deploy Frontend to Cloudflare Pages

### Option A: Cloudflare Pages (recommended)

1. Go to [Cloudflare Dashboard](https://dash.cloudflare.com) > Pages
2. Click **Create a project** > Connect to Git
3. Select your repository
4. Configure build settings:
   - **Framework preset**: None
   - **Build command**: `cd src/frontend && npm install && npm run build`
   - **Build output directory**: `src/frontend/build`
5. Add environment variables:
   - `VITE_SUPABASE_URL` = `https://YOUR_PROJECT.supabase.co`
   - `VITE_SUPABASE_ANON_KEY` = `eyJ...` (the anon/public key)
   - `VITE_GATEWAY_URL` = `https://gateway.ashai.net` (your Fly.io domain)
6. Deploy

Then add a custom domain: `app.ashai.net`

### Option B: Vercel

1. Import the repo on [vercel.com](https://vercel.com)
2. Set **Root Directory** to `src/frontend`
3. Framework: SvelteKit
4. Add the same `VITE_*` environment variables
5. Deploy

---

## Step 4: DNS Configuration

Add these DNS records:

| Type  | Name       | Value                          |
|-------|------------|--------------------------------|
| CNAME | gateway    | ashai-gateway.fly.dev          |
| CNAME | app        | your-project.pages.dev         |
| A/CNAME | @        | (your marketing site host)     |

---

## Environment Variables Reference

### Gateway (Fly.io secrets)

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Yes | Supabase service role key (admin) |
| `HELPERAI_ANTHROPIC_API_KEY` | Yes* | Anthropic API key |
| `HELPERAI_DEFAULT_PROVIDER` | Yes | `anthropic`, `openai`, etc. |
| `HELPERAI_DEFAULT_MODEL` | No | Model name (default: provider default) |
| `HELPERAI_OPENAI_API_KEY` | No | OpenAI API key (if using OpenAI) |
| `GATEWAY_PORT` | No | Default: 9000 |
| `GATEWAY_DATA_DIR` | No | Default: /data |

*At least one LLM API key is required.

### Frontend (build-time env vars)

| Variable | Required | Description |
|----------|----------|-------------|
| `VITE_SUPABASE_URL` | Yes | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Yes | Supabase anon/public key |
| `VITE_GATEWAY_URL` | Yes | Gateway URL (e.g., https://gateway.ashai.net) |

---

## Scaling Notes

- **VM size**: `shared-cpu-2x` with 1GB RAM supports ~4-5 concurrent users
- Each backend instance uses ~100-200MB RAM
- Scale up with `fly scale vm shared-cpu-4x` or `fly scale memory 2048`
- The gateway reaps idle personal instances after 30 min, project instances after 15 min with no users
- Persistent volume stores all SQLite DBs — back up with `fly ssh sftp`

---

## Troubleshooting

```bash
# Check if gateway is running
curl https://gateway.ashai.net/gateway/health

# View real-time logs
fly logs -a ashai-gateway

# SSH in and check data
fly ssh console
ls /data/users/
ls /data/projects/

# Restart
fly apps restart ashai-gateway
```
