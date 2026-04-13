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
| `has_tfvars` | boolean | no | Write `TF_VARS` secret to `terraform.tfvars` (default: `true`) |
| `extra_vars` | string | no | Space-separated `-var key=value` flags for `terraform plan` |
| `terraform_version` | string | no | Terraform version to install (default: `1.10.3`) |

**Required secrets** (passed via `secrets: inherit` from the calling workflow):

| Secret | Description |
|--------|-------------|
| `WIF_PROVIDER` | Workload Identity Provider resource name |
| `CICD_SA_EMAIL` | CI/CD service account email |
| `TFSTATE_BUCKET` | GCS bucket for Terraform state |
| `GCP_PROJECT_ID` | GCP project ID (exposed as `TF_VAR_GCP_PROJECT_ID`) |
| `GCP_REGION` | GCP region (exposed as `TF_VAR_GCP_REGION`) |
| `TF_VARS` | Contents written to `terraform.tfvars` (only when `has_tfvars: true`) |

**What the workflow does:**

1. Authenticates to GCP via Workload Identity Federation (no long-lived keys)
2. Runs `terraform fmt -check`, `terraform validate`, `terraform plan`
3. Posts a plan summary as a PR comment (fmt / validate / plan status + output)
4. Fails the job if any step fails
5. Uploads the plan artifact on `main` (only when plan succeeds)
6. Runs `terraform apply` on push to `main`
7. Cleans up `terraform.tfvars` in a final `if: always()` step

## Security

- GCP auth uses Workload Identity Federation — no service account JSON keys in GitHub secrets
- WIF access is restricted to `Datally-Solutions` org repositories (`repository_owner == 'Datally-Solutions'`), preventing fork PRs from obtaining credentials
- `extra_vars` is passed via an env var and expanded as a bash array to prevent shell injection
- `working_directory` is passed via env var in shell steps to prevent path injection
- `terraform.tfvars` uses a single-quoted heredoc (`<<'EOF'`) to prevent secret expansion in the YAML context

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
    secrets: inherit
```
