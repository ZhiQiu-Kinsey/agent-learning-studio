"""Plain-text order summary built from the pricing helpers."""
from shop.pricing import apply_discount, grand_total, shipping, subtotal, tax


def order_summary(items):
    """One line per charge, ending with the total the customer pays."""
    base = subtotal(items)
    discounted = apply_discount(base)
    lines = [
        f"Subtotal: {base:.2f}",
        f"Discount: -{base - discounted:.2f}",
        f"Shipping: {shipping(discounted):.2f}",
        f"Tax: {tax(discounted):.2f}",
        f"Total: {grand_total(items):.2f}",
    ]
    return "\n".join(lines)
