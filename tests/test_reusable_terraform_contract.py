import unittest
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "reusable-terraform.yml"


class ReusableTerraformContractTest(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_legacy_tfvars_contract_is_supported(self):
        """Known callers still pass has_tfvars: "true" with secrets: inherit."""
        self.assertIn("has_tfvars:", self.workflow)
        self.assertIn('type: string', self.workflow)
        self.assertIn('default: "true"', self.workflow)
        self.assertIn("TF_VARS:", self.workflow)
        self.assertIn("required: false", self.workflow)
        self.assertIn("- name: Write tfvars", self.workflow)
        self.assertIn("if: inputs.has_tfvars == 'true'", self.workflow)
        self.assertIn("TF_VARS_CONTENT: ${{ secrets.TF_VARS }}", self.workflow)
        self.assertIn('printf \'%s\\n\' "$TF_VARS_CONTENT" > "$WORKING_DIR/terraform.tfvars"', self.workflow)

    def test_tfvars_file_is_cleaned_up(self):
        self.assertIn("- name: Cleanup tfvars", self.workflow)
        self.assertIn("if: always() && inputs.has_tfvars == 'true'", self.workflow)
        self.assertIn('rm -f "$WORKING_DIR/terraform.tfvars"', self.workflow)


if __name__ == "__main__":
    unittest.main()
