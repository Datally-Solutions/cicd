from pathlib import Path
import re
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "reusable-terraform.yml"


class ReusableTerraformContractTest(unittest.TestCase):
    def setUp(self):
        self.workflow = WORKFLOW.read_text(encoding="utf-8")

    def test_tfvars_compatibility_input_and_secret_are_declared(self):
        self.assertRegex(
            self.workflow,
            re.compile(
                r"has_tfvars:\n"
                r"\s+description: .+\n"
                r"\s+required: false\n"
                r"\s+type: string\n"
                r'\s+default: "true"',
                re.MULTILINE,
            ),
        )
        self.assertIn("secrets:", self.workflow)
        self.assertIn("TF_VARS:", self.workflow)
        self.assertIn("required: false", self.workflow)

    def test_tfvars_secret_is_written_and_cleaned_up(self):
        self.assertIn("- name: Write tfvars", self.workflow)
        self.assertIn("if: inputs.has_tfvars == 'true'", self.workflow)
        self.assertIn("TF_VARS_CONTENT: ${{ secrets.TF_VARS }}", self.workflow)
        self.assertIn(
            'run: printf \'%s\\n\' "$TF_VARS_CONTENT" > "$WORKING_DIR/terraform.tfvars"',
            self.workflow,
        )
        self.assertIn("- name: Cleanup tfvars", self.workflow)
        self.assertIn("if: always() && inputs.has_tfvars == 'true'", self.workflow)
        self.assertIn('run: rm -f "$WORKING_DIR/terraform.tfvars"', self.workflow)


if __name__ == "__main__":
    unittest.main()
