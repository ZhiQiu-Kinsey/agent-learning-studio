import unittest

from shop.report import order_summary


class ReportTests(unittest.TestCase):
    def test_summary_lists_every_charge(self):
        text = order_summary([{"unit_price": 100.0, "quantity": 1}])
        self.assertEqual(text.splitlines(), [
            "Subtotal: 100.00",
            "Discount: -10.00",
            "Shipping: 0.00",
            "Tax: 7.20",
            "Total: 97.20",
        ])


if __name__ == "__main__":
    unittest.main()
