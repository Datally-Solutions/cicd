import re
from pathlib import Path
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "reusable-terraform.yml"


class ReusableTerraformContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_has_tfvars_input_accepts_existing_string_callers(self):
        self.assertRegex(
            self.workflow,
            re.compile(
                r"^\s{6}has_tfvars:\n"
                r"\s{8}description: .+\n"
                r"\s{8}required: false\n"
                r"\s{8}type: string\n"
                r"\s{8}default: \"true\"$",
                re.MULTILINE,
            ),
        )

    def test_tf_vars_secret_is_part_of_workflow_call_contract(self):
        self.assertRegex(
            self.workflow,
            re.compile(
                r"^\s{4}secrets:\n"
                r"\s{6}TF_VARS:\n"
                r"\s{8}required: false$",
                re.MULTILINE,
            ),
        )

    def test_tfvars_file_is_written_and_cleaned_up_when_enabled(self):
        self.assertIn("if: inputs.has_tfvars == 'true'", self.workflow)
        self.assertIn("TF_VARS_CONTENT: ${{ secrets.TF_VARS }}", self.workflow)
        self.assertIn('printf \'%s\\n\' "$TF_VARS_CONTENT" > terraform.tfvars', self.workflow)
        self.assertIn("if: always() && inputs.has_tfvars == 'true'", self.workflow)
        self.assertIn("rm -f terraform.tfvars", self.workflow)

    def test_pull_request_runs_use_the_readonly_plan_identity(self):
        # Both branches must be explicit — a step's `with:` can't conditionally omit a key,
        # and an empty string would override gcp-auth's own default instead of falling back
        # to it (see gcp-auth/action.yml).
        self.assertIn(
            "workload_identity_provider: ${{ github.event_name == 'pull_request' && "
            "'projects/853335570767/locations/global/workloadIdentityPools/"
            "github-pool-readonly/providers/github-provider-readonly' || "
            "'projects/853335570767/locations/global/workloadIdentityPools/"
            "github-pool/providers/github-provider' }}",
            self.workflow,
        )
        self.assertIn(
            "service_account: ${{ github.event_name == 'pull_request' && "
            "'terraform-plan-sa@cat-litter-monitor.iam.gserviceaccount.com' || "
            "'terraform-cicd-sa@cat-litter-monitor.iam.gserviceaccount.com' }}",
            self.workflow,
        )

    def test_pull_request_plan_does_not_take_a_state_lock(self):
        # The read-only plan SA can't write the GCS lock object (storage.objects.create) —
        # and a PR plan makes no state changes, so it doesn't need to hold the lock anyway.
        self.assertIn('lock_arg="-lock=true"', self.workflow)
        self.assertIn(
            'if [[ "${{ github.event_name }}" == "pull_request" ]]; then', self.workflow
        )
        self.assertIn('lock_arg="-lock=false"', self.workflow)

    def test_apply_still_requires_push_to_main(self):
        # Apply must never run off a failed/skipped plan or a red job (custom `if`
        # drops GHA's implicit success(); a stale checked-in tfplan must not apply).
        self.assertIn(
            "if: success() && github.ref == 'refs/heads/main' && "
            "github.event_name == 'push' && steps.plan.outcome == 'success'",
            self.workflow,
        )
        self.assertIn("terraform apply -auto-approve tfplan", self.workflow)


if __name__ == "__main__":
    unittest.main()
