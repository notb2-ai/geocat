import unittest

from scripts.build_sing_box import SRS_VERSION, verify_compiled_rule


class CompiledRuleTests(unittest.TestCase):
    def test_accepts_exact_domain_covered_by_same_suffix(self):
        expected = {"domain": ["example.org", "exact.org"], "domain_suffix": ["example.org"]}
        decoded = {"version": SRS_VERSION, "rules": [
            {"domain_suffix": ["example.org"], "domain": ["exact.org"]},
        ]}
        verify_compiled_rule(decoded, expected)

    def test_rejects_changed_rules(self):
        expected = {"domain": ["exact.org"], "domain_suffix": ["example.org"]}
        suffix = {"domain_suffix": ["example.org"]}
        for rules, error in (
            ([suffix], "missing"),
            ([{**suffix, "domain": ["exact.org", "extra.org"]}], "unexpected"),
            ([{**suffix, "domain": ["exact.org", "exact.org"]}], "duplicate"),
            ([{**suffix, "domain": ["exact.org"], "invert": True}], "rule fields"),
            ([suffix, {"domain": ["exact.org"]}], "exactly one"),
        ):
            with self.subTest(rules=rules), self.assertRaisesRegex(ValueError, error):
                verify_compiled_rule({"version": SRS_VERSION, "rules": rules}, expected)
