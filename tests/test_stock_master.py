import unittest
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import StockMasterEntry, SyncState
from app.stock_master import Stock, StockMasterClient


class StockMasterClientTest(unittest.TestCase):
    def setUp(self):
        self.client = StockMasterClient()
        self.client._stocks = [
            Stock(code="2330", name="台積電", market="tse", full_name="台灣積體電路製造股份有限公司"),
            Stock(code="2317", name="鴻海", market="tse", full_name="鴻海精密工業股份有限公司"),
            Stock(code="1234", name="中信", market="otc", full_name="中信股份有限公司"),
            Stock(code="2891", name="中信金", market="tse", full_name="中國信託金融控股股份有限公司"),
        ]
        self.client._loaded_at = 9_999_999_999

    def test_resolve_by_code(self):
        result = self.client.resolve("2330")

        self.assertEqual(result.status, "found")
        self.assertEqual(result.stock.name, "台積電")
        self.assertEqual(result.stock.market, "tse")

    def test_resolve_by_short_name(self):
        result = self.client.resolve("台積電")

        self.assertEqual(result.status, "found")
        self.assertEqual(result.stock.code, "2330")

    def test_resolve_by_full_name(self):
        result = self.client.resolve("台灣積體電路製造股份有限公司")

        self.assertEqual(result.status, "found")
        self.assertEqual(result.stock.code, "2330")

    def test_ambiguous_contains_match(self):
        result = self.client.resolve("中")

        self.assertEqual(result.status, "ambiguous")
        self.assertGreaterEqual(len(result.candidates), 2)

    def test_not_found(self):
        result = self.client.resolve("不存在公司")

        self.assertEqual(result.status, "not_found")

    def test_saves_stock_master_to_db_and_reuses_it(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine)

        with session_factory() as db:
            client = StockMasterClient()
            client._fetch_market = Mock(
                side_effect=[
                    [Stock(code="2330", name="台積電", market="tse", full_name="台灣積體電路製造股份有限公司")],
                    [],
                ]
            )

            result = client.resolve("台積電", db)

            self.assertEqual(result.status, "found")
            self.assertEqual(db.query(StockMasterEntry).count(), 1)
            self.assertIsNotNone(db.get(SyncState, "stock_master"))

        with session_factory() as db:
            client = StockMasterClient()
            client._fetch_market = Mock(return_value=[])

            result = client.resolve("台積電", db)

            self.assertEqual(result.status, "found")
            self.assertEqual(result.stock.code, "2330")
            client._fetch_market.assert_not_called()


if __name__ == "__main__":
    unittest.main()
