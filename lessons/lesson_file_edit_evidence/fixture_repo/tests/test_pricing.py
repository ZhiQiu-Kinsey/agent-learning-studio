import unittest

from shop.pricing import apply_discount, discount_rate, grand_total, shipping, subtotal, tax


class PricingTests(unittest.TestCase):
    def test_subtotal(self):
        items = [{"unit_price": 12.5, "quantity": 2}, {"unit_price": 3.0, "quantity": 1}]
        self.assertEqual(subtotal(items), 28.0)

    def test_discount_tiers_up_to_200(self):
        self.assertEqual(discount_rate(99.99), 0.0)
        self.assertEqual(discount_rate(100.0), 0.10)
        self.assertEqual(discount_rate(200.0), 0.15)

    def test_new_tier_from_300(self):
        self.assertEqual(discount_rate(299.99), 0.15)
        self.assertEqual(discount_rate(300.0), 0.20)
        self.assertEqual(apply_discount(300.0), 240.0)

    def test_free_shipping_from_exactly_50(self):
        self.assertEqual(shipping(49.99), 4.5)
        self.assertEqual(shipping(50.0), 0.0)

    def test_tax(self):
        self.assertEqual(tax(100.0), 8.0)

    def test_grand_total(self):
        items = [{"unit_price": 100.0, "quantity": 1}]
        self.assertEqual(grand_total(items), 97.2)


if __name__ == "__main__":
    unittest.main()
