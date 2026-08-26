# cicd

Shared GitHub Actions reusable workflows for the Cat Litter Monitor monorepo.

## Workflows

### `reusable-terraform.yml`

A parameterised Terraform plan + apply workflow called by both `backend` and `infra` repos.

**Inputs:**

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `working_directory` | string | yes | Path to Terraform root (e.g. `.`) |
| `state_prefix` | string | yes | GCS state prefix (e.g. `infra`, `backend`) |
| `environment` | string | no | GitHub environment (default: `production`) |
| `has_tfvars` | string | no | Write `TF_VARS` secret to `terraform.tfvars` when set to `"true"` (default: `"true"`) |
| `firmware_check_token_sm_secret` | string | no | Secret Manager secret name; when set, value is exported as `TF_VAR_firmware_check_token` |
| `provisioning_token_sm_secret` | string | no | Secret Manager secret name; when set, value is exported as `TF_VAR_provisioning_token` |
| `extra_vars` | string | no | Space-separated `-var key=value` flags for `terraform plan` (non-sensitive only) |
| `terraform_version` | string | no | Terraform version to install (default: `1.10.3`) |

**Secrets** (passed via `secrets: inherit` from the calling workflow):

| Secret | Description |
|--------|-------------|
| `TF_VARS` | Contents written to `terraform.tfvars` (only when `has_tfvars: true`) |

Project ID, region, state bucket, and alert email are hardcoded in the workflow. Auth is entirely Workload Identity Federation + IAM (see below) — those strings are not credentials.

#### Dual GCP identity (PR vs main)

The workflow picks the GCP identity from `github.event_name`:

| Event | WIF pool / provider | Service account | Purpose |
|-------|---------------------|-----------------|---------|
| `pull_request` | `github-pool-readonly` / `github-provider-readonly` | `terraform-plan-sa` | Read-only `terraform plan` |
| `push` (and other non-PR) | `github-pool` / `github-provider` | `terraform-cicd-sa` | Plan + apply |

This split is intentional and lives in [`infra/iam.tf`](https://github.com/Datally-Solutions/infra/blob/main/iam.tf):

- The privileged pool only allows `refs/heads/main` and `refs/tags/v*` — PR refs cannot impersonate `terraform-cicd-sa`.
- The read-only pool allows PR refs for `backend` and `infra` only, and grants exclusively `terraform-plan-sa` (get/list-style permissions; no create/update/delete).
- PR plans run with `-lock=false` because the plan SA cannot create the GCS state lock object and does not need one (no state writes).

**Trade-off to know:** the plan role includes `secretmanager.versions.access` so Terraform can refresh `google_secret_manager_secret_version` resources during plan. A compromised same-org PR branch could read secret payloads via plan; forks still cannot reach this identity (`repository_owner == 'Datally-Solutions'`).

**What the workflow does:**

1. Authenticates to GCP via the identity above (composite action `.github/actions/gcp-auth`)
2. Optionally writes `terraform.tfvars` and fetches SM-backed TF vars
3. Runs `terraform fmt -check`, `terraform validate`, `terraform plan`
4. Posts a plan summary as a PR comment (fmt / validate / plan status + output)
5. Fails the job if any of those steps failed
6. Uploads the plan artifact on `main` (only when plan succeeds)
7. Runs `terraform apply` on push to `main` only when `success()` and `steps.plan.outcome == 'success'` (a custom `if` drops GHA’s implicit success check — without both gates a failed plan can still apply a stale checked-in `tfplan`)
8. Cleans up `terraform.tfvars` in a final `if: always()` step

### Other reusable workflows

| Workflow | Purpose |
|----------|---------|
| `reusable-cloud-build.yml` | Submit a Cloud Build with `SHORT_SHA` substitution (privileged WIF) |
| `reusable-firebase-deploy.yml` | `firebase deploy --only <targets>` (privileged WIF) |
| `reusable-firmware-upload.yml` | Upload `firmware.bin` + `latest.json` to the firmware GCS bucket |

These use the privileged `gcp-auth` defaults (`terraform-cicd-sa`). Callers that need a different SA (e.g. Play deploy) can override `workload_identity_provider` / `service_account` on the action.

## Security

- GCP auth uses Workload Identity Federation — no service account JSON keys in GitHub secrets
- Privileged WIF is restricted to trusted refs in the `Datally-Solutions` org; fork PRs cannot obtain credentials
- PR Terraform plans use a separate read-only pool + SA (cannot apply)
- Apply on `main` is gated on `success()` and a successful plan outcome (same contract as the plan-artifact upload)
- `extra_vars` is passed via an env var and expanded as a bash array to prevent shell injection
- `working_directory` is passed via env var in shell steps to prevent path injection
- `terraform.tfvars` uses `printf` of a secret env var; SM-fetched tokens are masked with `::add-mask::`

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
      # Optional — only for roots that need these TF vars:
      # firmware_check_token_sm_secret: "litter-firmware-check-token"
      # provisioning_token_sm_secret: "litter-provisioning-token"
    secrets: inherit
```
