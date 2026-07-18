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


if __name__ == "__main__":
    unittest.main()
