# Staging GitHub App — Setup Guide

This document records the one-time steps to register and configure the Kenjutsu **staging** GitHub App.
Keep it updated as credentials rotate or installations change.

> **Two apps, always.** Staging and production use separate GitHub Apps with different credentials and
> different webhook URLs. This isolates staging bugs from customer repos.

---

## Prerequisites

- GitHub account with admin access to the `smpnet74` organization (or personal account)
- Webhook receiver URL for staging (e.g. `https://staging.kenjutsu.dev/webhook`)
- Admin access to the `smpnet74/kenjutsu` repository (to write GitHub Environment secrets)

---

## Step 1 — Register the GitHub App

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**
   (or `https://github.com/settings/apps/new` for a personal account, or
   `https://github.com/organizations/smpnet74/settings/apps/new` for an org-owned app)

2. Fill in the form:

   | Field | Value |
   |-------|-------|
   | **GitHub App name** | `kenjutsu-staging` |
   | **Homepage URL** | `https://github.com/smpnet74/kenjutsu` |
   | **Webhook URL** | `https://staging.kenjutsu.dev/webhook` |
   | **Webhook secret** | Generate with `openssl rand -hex 32` — save this value |
   | **Expire user authorization tokens** | Enabled |
   | **Request user authorization (OAuth) during installation** | Disabled |
   | **Active** (webhooks) | Enabled |

3. **Repository permissions** (set each to the level shown):

   | Permission | Level |
   |-----------|-------|
   | Pull requests | Read & Write |
   | Checks | Read & Write |
   | Contents | Read-only |
   | Metadata | Read-only (mandatory) |

4. **Subscribe to events** (check all of these):
   - `Pull request`
   - `Issue comment`
   - `Installation` (under "GitHub App" events, not repository events)

5. **Where can this GitHub App be installed?** → Select **"Only on this account"**
   (prevents accidental installation on external repos during staging)

6. Click **Create GitHub App**.

---

## Step 2 — Note the App ID

After creation, you land on the app settings page.

- Copy the **App ID** (a number like `12345678`) — you'll need it in Step 4.

---

## Step 3 — Generate a Private Key

Still on the app settings page, scroll to **Private keys**:

1. Click **Generate a private key**
2. A `.pem` file downloads automatically — this is the `GITHUB_APP_PRIVATE_KEY`
3. The key is an RSA private key in PEM format; keep the full multi-line value including the
   `-----BEGIN RSA PRIVATE KEY-----` header and footer

---

## Step 4 — Store Secrets in GitHub Environment `staging`

The `staging` environment already exists in `smpnet74/kenjutsu`. Add these secrets via the
GitHub UI (**Settings → Environments → staging → Add secret**) or via CLI:

```bash
# Replace placeholder values with actual credentials

gh secret set GITHUB_APP_ID \
  --env staging \
  --repo smpnet74/kenjutsu \
  --body "YOUR_APP_ID"

gh secret set GITHUB_APP_PRIVATE_KEY \
  --env staging \
  --repo smpnet74/kenjutsu \
  --body "$(cat path/to/downloaded-private-key.pem)"

gh secret set GITHUB_WEBHOOK_SECRET \
  --env staging \
  --repo smpnet74/kenjutsu \
  --body "YOUR_WEBHOOK_SECRET"
```

Required secrets summary:

| Secret name | Description |
|------------|-------------|
| `GITHUB_APP_ID` | Numeric App ID from Step 2 |
| `GITHUB_APP_PRIVATE_KEY` | Full PEM content from Step 3 |
| `GITHUB_WEBHOOK_SECRET` | Value generated in Step 1 |

---

## Step 5 — Install the App on Test Repositories

1. Go to the app settings page → **Install App** tab
2. Click **Install** next to `smpnet74`
3. Choose **Only select repositories** and add:
   - `smpnet74/kenjutsu`
   - `smpnet74/scratch`
   - `smpnet74/claude-devteam`
4. Click **Install**

The app will now receive webhook events from pull request activity on those three repos.

---

## Step 6 — Verify Webhook Delivery

Once the staging service is deployed (see DEM-166):

1. Open a pull request on one of the test repos
2. Go to the GitHub App settings → **Advanced** tab → **Recent Deliveries**
3. Confirm a `pull_request` event was delivered with HTTP 200 from the staging webhook endpoint

---

## App Details (fill in after registration)

| Field | Value |
|-------|-------|
| App name | `kenjutsu-staging` |
| App ID | _(fill in after Step 2)_ |
| Installation ID (smpnet74) | _(fill in after Step 5)_ |
| Webhook URL | `https://staging.kenjutsu.dev/webhook` |
| Registered by | _(fill in)_ |
| Registration date | _(fill in)_ |

---

## Notes

- The **production** GitHub App (`kenjutsu-production`) will be registered separately in Phase 5.
  It uses a different App ID, private key, and webhook URL (`https://kenjutsu.dev/webhook`).
- Private keys do not expire but should be rotated if compromised. Generate a new one, update the
  secret, redeploy, then delete the old key from the app settings page.
- If the webhook secret needs rotation: update `GITHUB_WEBHOOK_SECRET` in the environment secrets,
  update the webhook secret in the app settings, and redeploy staging.
- Architecture reference: `research/kenjutsu-architecture-v3.md` §7.1 and §13.1
