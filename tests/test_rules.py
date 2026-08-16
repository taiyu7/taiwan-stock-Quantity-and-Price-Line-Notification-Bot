import unittest
from unittest.mock import Mock

from app.rules import RULE_RE, create_rule_from_text, normalize_metric, normalize_operator
from app.stock_master import ResolveResult, Stock
from app.twse_client import Quote


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

    def test_create_rule_from_stock_name(self):
        db = Mock()
        stock_master = Mock()
        stock_master.resolve.return_value = ResolveResult.found(
            Stock(code="2330", name="台積電", market="tse", full_name="台灣積體電路製造股份有限公司")
        )
        twse = Mock()
        twse.fetch_quote.return_value = Quote(
            code="2330",
            name="台積電",
            market="tse",
            price=2000,
            volume=30000,
            raw_time="09:30:00",
        )

        message = create_rule_from_text(db, "user-1", "台積電 價 >= 2000", "price", twse, stock_master)

        self.assertIn("已建立提醒：台積電(2330)", message)
        twse.fetch_quote.assert_called_once_with("2330", "tse")

    def test_ambiguous_stock_name_requires_code(self):
        db = Mock()
        stock_master = Mock()
        stock_master.resolve.return_value = ResolveResult.ambiguous(
            [
                Stock(code="1111", name="中信", market="tse"),
                Stock(code="2222", name="中信金", market="tse"),
            ]
        )
        twse = Mock()

        message = create_rule_from_text(db, "user-1", "中信 價 >= 10", "price", twse, stock_master)

        self.assertIn("找到多個可能標的", message)
        self.assertIn("中信(1111)", message)
        twse.fetch_quote.assert_not_called()

    def test_code_fallback_tries_both_markets_when_master_misses(self):
        db = Mock()
        stock_master = Mock()
        stock_master.resolve.return_value = ResolveResult.not_found()
        twse = Mock()
        twse.fetch_quote.return_value = Quote(
            code="6488",
            name="環球晶",
            market="otc",
            price=500,
            volume=10000,
            raw_time="09:30:00",
        )

        message = create_rule_from_text(db, "user-1", "6488 價 >= 500", "price", twse, stock_master)

        self.assertIn("已建立提醒：環球晶(6488)", message)
        twse.fetch_quote.assert_called_once_with("6488", None)

    def test_unknown_code_returns_clear_message(self):
        db = Mock()
        stock_master = Mock()
        stock_master.resolve.return_value = ResolveResult.not_found()
        twse = Mock()
        twse.fetch_quote.return_value = None

        message = create_rule_from_text(db, "user-1", "9999 價 >= 10", "price", twse, stock_master)

        self.assertEqual(message, "找不到 9999 的即時資料，請確認標的是否仍可交易。")


if __name__ == "__main__":
    unittest.main()
