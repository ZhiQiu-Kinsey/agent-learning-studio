"""Order pricing for a small shop: subtotal, discount, shipping, tax and the grand total."""

TAX_RATE = 0.08
FREE_SHIPPING_FROM = 50.0
SHIPPING_FEE = 4.5


def subtotal(items):
    """Sum of unit_price * quantity over all items, rounded to cents."""
    total = 0.0
    for item in items:
        total += item["unit_price"] * item["quantity"]
    return round(total, 2)


def discount_rate(amount):
    """Share taken off an order: 15% from 200, 10% from 100, otherwise nothing."""
    if amount >= 200:
        return 0.15
    if amount >= 100:
        return 0.10
    return 0.0


def apply_discount(amount):
    """Amount left to pay after the discount, rounded to cents."""
    return round(amount * (1 - discount_rate(amount)), 2)


def shipping(amount):
    """Shipping fee for the discounted amount; orders from FREE_SHIPPING_FROM ship free."""
    if amount > FREE_SHIPPING_FROM:
        return 0.0
    return SHIPPING_FEE


def tax(amount):
    """Tax on the discounted amount, rounded to cents."""
    return round(amount * TAX_RATE, 2)


def grand_total(items):
    """What the customer pays: discounted subtotal + shipping + tax."""
    discounted = apply_discount(subtotal(items))
    return round(discounted + shipping(discounted) + tax(discounted), 2)
