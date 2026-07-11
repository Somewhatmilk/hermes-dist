# GCP Secret Manager setup (only when the user explicitly chooses cloud over local)

Default for this user is `~/.secrets/<name>.age` (local age). Use this guide only when the user has a concrete reason to need cross-machine access, e.g. running the agent on a VPS, sharing creds between desktop + laptop, or rotating many keys on a schedule.

## Free tier (why this won't cost anything at personal scale)

| Resource | Free | Overage |
|---|---|---|
| Active secret versions | 6 / month | $0.06 / version-month |
| Access operations | 10,000 / month | $0.03 / 10k requests |
| Rotation notifications | 10,000 / month | $0.05 / 100k |

This user's scale: 8 secrets, ~hundreds of access requests / month. Bills at $0.00.

The "billing account required" prompt is a project-creation prerequisite, not a charge. The user must link a payment method to create any GCP project; they will not be billed for staying under free tier.

**Recommended:** Set a budget alert at $1 immediately after project creation. Email fires if anything ever does charge. Setup: Billing → Budgets & alerts → Create budget → Amount $1 → Alert at 100%.

## Architecture

- **Service account, not user account.** `hermes-secret-reader` with only `roles/secretmanager.secretAccessor`.
- **JSON key on the local host, chmod 600.** Path: `~/.config/gcloud/hermes-sa.json`.
- **Environment variable** `GOOGLE_APPLICATION_CREDENTIALS` points the Secret Manager client libraries at the key. No browser login, no OAuth flow.
- **Values never enter agent context.** They flow `gcloud secrets versions access | <tool> --stdin`.

## One-time setup (user runs these)

```bash
# 1. Install + authenticate
#    https://cloud.google.com/sdk/docs/install
gcloud auth login
gcloud config set project YOUR_PROJECT_ID

# 2. Enable API + create service account + grant role + create key
gcloud services enable secretmanager.googleapis.com --project=$PROJECT_ID

gcloud iam service-accounts create hermes-secret-reader \
  --display-name="Hermes Secret Reader" \
  --project=$PROJECT_ID

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:hermes-secret-reader@$PROJECT_ID.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud iam service-accounts keys create ~/.config/gcloud/hermes-sa.json \
  --iam-account=hermes-secret-reader@$PROJECT_ID.iam.gserviceaccount.com

chmod 600 ~/.config/gcloud/hermes-sa.json

# 3. Create secret slots
for s in hf_token openrouter_key reddit_password x_password discord_password gmail_password; do
  gcloud secrets create "$s" --replication-policy=automatic --project=$PROJECT_ID
done

# 4. Add values (paste from password manager, never from chat with the agent)
gcloud secrets versions add hf_token --data-file=- --project=$PROJECT_ID
# (paste value, Enter, Ctrl-D)
```

Full script with all steps idempotent: `templates/gcp-secret-init.sh` in the umbrella skill `hermes-session-ritual`.

## Day-to-day pattern

```bash
# ~/.bashrc
export GCP_PROJECT_ID="your-project-id"
export GOOGLE_APPLICATION_CREDENTIALS="$HOM... gcloud key file"

hermes-secret() {
  local name="$1"
  gcloud secrets versions access latest --secret="$name" --project="$GCP_PROJECT_ID" 2>/dev/null
}

# Use:
hermes-secret hf_token | huggingface-cli login --token -
```

## When to switch from local age to this

- User explicitly says "I want this on multiple machines" or "I want phone access in an emergency."
- User has >20 secrets and rotation cadence is >monthly.
- User runs the agent on a VPS (the cloud vault is then local-from-the-VPS-perspective anyway).

Otherwise: stay with `~/.secrets/<name>.age`. Less attack surface, no Google in the threat model.