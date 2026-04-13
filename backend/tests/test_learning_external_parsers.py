import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.learning.external_parsers import parse_external_payload_with_parser


class LearningExternalParsersTests(unittest.TestCase):
    def test_cwe_parser_extracts_weakness(self):
        payload = '{"Weaknesses":{"Weakness":[{"ID":"79","Name":"XSS","Description":"desc"}]}}'
        parsed = parse_external_payload_with_parser(payload, source_name="cwe")
        self.assertEqual(parsed.parser_name, "cwe_parser")
        self.assertEqual(parsed.items[0]["weakness_id"], "CWE-79")

    def test_owasp_parser_extracts_category(self):
        payload = '{"A01:2021":{"title":"Broken Access Control","description":"desc","cwe":"CWE-284"}}'
        parsed = parse_external_payload_with_parser(payload, source_name="owasp")
        self.assertEqual(parsed.parser_name, "owasp_parser")
        self.assertEqual(parsed.items[0]["weakness_id"], "CWE-284")

    def test_semgrep_parser_extracts_rules(self):
        payload = (
            '{"rules":[{"id":"python.lang.security.sql-injection","message":"SQL injection",'
            '"languages":["python"],"pattern":"execute(query)",'
            '"metadata":{"cwe":"CWE-89","owasp":"a03_injection"}}]}'
        )
        parsed = parse_external_payload_with_parser(payload, source_name="semgrep")
        self.assertEqual(parsed.parser_name, "semgrep_parser")
        self.assertEqual(parsed.items[0]["item_type"], "framework_rule")
        self.assertEqual(parsed.items[0]["weakness_id"], "CWE-89")

    def test_codeql_parser_extracts_queries(self):
        payload = (
            '{"queries":[{"id":"py/sql-injection","name":"SQL injection","description":"desc",'
            '"language":"python","tags":["security","external/cwe/cwe-89"]}]}'
        )
        parsed = parse_external_payload_with_parser(payload, source_name="codeql")
        self.assertEqual(parsed.parser_name, "codeql_parser")
        self.assertEqual(parsed.items[0]["weakness_id"], "CWE-89")

    def test_juliet_parser_extracts_cases(self):
        payload = '{"cases":[{"cwe":"CWE-22","title":"Path traversal","language":"java","description":"desc"}]}'
        parsed = parse_external_payload_with_parser(payload, source_name="juliet")
        self.assertEqual(parsed.parser_name, "juliet_parser")
        self.assertEqual(parsed.items[0]["weakness_id"], "CWE-22")

    def test_unknown_source_uses_generic_parser(self):
        payload = '{"items":[{"title":"Generic item","summary":"desc"}]}'
        parsed = parse_external_payload_with_parser(payload, source_name="unknown")
        self.assertEqual(parsed.parser_name, "generic_parser")
        self.assertEqual(len(parsed.items), 1)


if __name__ == "__main__":
    unittest.main()
