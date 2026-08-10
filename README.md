# cicd

Shared GitHub Actions reusable workflows for the Cat Litter Monitor monorepo.

## Workflows

### `reusable-terraform.yml`

A parameterised Terraform plan + apply workflow called by both `backend` and `infra` repos.

**Dual WIF identities** (hardcoded in the workflow — not GitHub secrets):

| Event | Workload Identity Provider | Service account |
|-------|----------------------------|-----------------|
| `pull_request` | `…/workloadIdentityPools/github-pool-readonly/providers/github-provider-readonly` | `terraform-plan-sa@cat-litter-monitor.iam.gserviceaccount.com` |
| anything else (e.g. push to `main`) | `…/workloadIdentityPools/github-pool/providers/github-provider` | `terraform-cicd-sa@cat-litter-monitor.iam.gserviceaccount.com` |

PR runs plan with the read-only SA (`-lock=false`; that SA cannot write the GCS state lock). Apply runs only on `push` to `main` with the privileged SA. See `infra/iam.tf` for why the read-only path is a separate WIF pool.

**Inputs:**

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `working_directory` | string | yes | Path to Terraform root (e.g. `.`) |
| `state_prefix` | string | yes | GCS state prefix (e.g. `infra`, `backend`) |
| `environment` | string | no | GitHub environment (default: `production`) |
| `has_tfvars` | string | no | Write `TF_VARS` secret to `terraform.tfvars` when set to `"true"` (default: `"true"`) |
| `firmware_check_token_sm_secret` | string | no | Secret Manager secret id; when non-empty, value is fetched and exported as `TF_VAR_firmware_check_token` (default: `""`) |
| `provisioning_token_sm_secret` | string | no | Secret Manager secret id; when non-empty, value is fetched and exported as `TF_VAR_provisioning_token` (default: `""`) |
| `extra_vars` | string | no | Space-separated `-var key=value` flags for `terraform plan` |
| `terraform_version` | string | no | Terraform version to install (default: `1.10.3`) |

**Hardcoded env** (non-secret; set in the workflow job):

| Name | Value |
|------|-------|
| `GCP_REGION` | `europe-west9` (also `TF_VAR_GCP_REGION`) |
| `TFSTATE_BUCKET` | `cat-litter-monitor-tfstate` |
| `ALERT_EMAIL` | used as `TF_VAR_alert_email` |
| project id | from `gcp-auth` output (`cat-litter-monitor` → `TF_VAR_GCP_PROJECT_ID`) |

**Optional secret** (passed via `secrets:` / `secrets: inherit`):

| Secret | Description |
|--------|-------------|
| `TF_VARS` | Contents written to `terraform.tfvars` (only when `has_tfvars: true`) |

`WIF_PROVIDER` / `CICD_SA_EMAIL` are **not** read from GitHub secrets — provider + SA are selected above.

**What the workflow does:**

1. Authenticates to GCP via Workload Identity Federation (PR → plan SA; otherwise → cicd SA)
2. Optionally writes `terraform.tfvars` and/or fetches SM tokens into `TF_VAR_*`
3. Runs `terraform fmt -check`, `terraform validate`, `terraform plan`
4. Posts a plan summary as a PR comment (fmt / validate / plan status + output)
5. Fails the job if any step fails
6. Uploads the plan artifact on `main` (only when plan succeeds)
7. Runs `terraform apply` on push to `main`
8. Cleans up `terraform.tfvars` in a final `if: always()` step

### Other reusable workflows

| Workflow | Purpose |
|----------|---------|
| `reusable-cloud-build.yml` | Authenticate via WIF, then `gcloud builds submit` with a config path + `SHORT_SHA` substitution |
| `reusable-firebase-deploy.yml` | Authenticate via WIF, install Firebase CLI, `firebase deploy --only <targets>` |
| `reusable-firmware-upload.yml` | Download `firmware` artifact, upload versioned + `latest/firmware.bin` to GCS, write `latest.json` (version / url / sha256) |

Shared auth lives in `.github/actions/gcp-auth` (defaults to the privileged provider + `terraform-cicd-sa`).

## Security

- GCP auth uses Workload Identity Federation — no service account JSON keys in GitHub secrets
- Privileged pool (`github-pool`) is restricted to trusted `main` / `refs/tags/v*` refs in `Datally-Solutions` org repos; PR refs use the separate read-only pool + plan SA only
- Fork PRs cannot obtain either identity (`repository_owner == 'Datally-Solutions'` on both providers)
- `extra_vars` is passed via an env var and expanded as a bash array to prevent shell injection
- `working_directory` is passed via env var in shell steps to prevent path injection
- `terraform.tfvars` uses a printf of an env-held secret; SM token values are masked before export to `GITHUB_ENV`
- Apply never runs on pull-request events

## Usage example

```yaml
jobs:
  terraform:
    permissions:
      contents: read
      id-token: write
      pull-requests: write
    uses: Datally-Solutions/cicd/.github/workflows/reusable-terraform.yml@main
    with:
      working_directory: "."
      state_prefix: "infra"
      has_tfvars: true
      firmware_check_token_sm_secret: "litter-firmware-check-token"
    secrets: inherit
```
