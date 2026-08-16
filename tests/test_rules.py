import unittest

from app.rules import RULE_RE, normalize_metric, normalize_operator


class RuleParserTest(unittest.TestCase):
    def test_price_rule_with_spaces(self):
        match = RULE_RE.match("2330 價 >= 2000")

        self.assertIsNotNone(match)
        self.assertEqual(match.group("identifier"), "2330")
        self.assertEqual(normalize_metric(match.group("metric")), "price")
        self.assertEqual(normalize_operator(match.group("operator")), ">=")
        self.assertEqual(match.group("threshold"), "2000")

    def test_volume_rule_without_spaces(self):
        match = RULE_RE.match("2330量>=30000")

        self.assertIsNotNone(match)
        self.assertEqual(match.group("identifier"), "2330")
        self.assertEqual(normalize_metric(match.group("metric")), "volume")
        self.assertEqual(match.group("threshold"), "30000")

    def test_name_identifier_parses_for_future_resolution(self):
        match = RULE_RE.match("台積電 價 >= 2000")

        self.assertIsNotNone(match)
        self.assertEqual(match.group("identifier"), "台積電")
        self.assertEqual(normalize_metric(match.group("metric")), "price")

    def test_metric_is_required(self):
        self.assertIsNone(RULE_RE.match("2330 >= 600"))


if __name__ == "__main__":
    unittest.main()
