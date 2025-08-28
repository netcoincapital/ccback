#!/usr/bin/env python3

def dynamic_decimal_format(price_value: float) -> str:
    """
    Format decimal values based on their magnitude
    """
    if price_value == 0:
        return "0.00000000"
    elif price_value >= 1:
        return f"{price_value:,.2f}"
    elif price_value >= 0.01:
        return f"{price_value:,.4f}"
    elif price_value >= 0.0001:
        return f"{price_value:,.6f}"
    elif price_value >= 0.00000001:
        return f"{price_value:,.8f}"
    else:
        # برای اعداد خیلی کوچک، از نمایش علمی جلوگیری کنیم
        return f"{price_value:.12f}".rstrip('0').rstrip('.')

# تست فرمت کردن قیمت‌های مختلف
test_prices = [
    0.0,
    0.00002345,  # SHIB price example
    0.000000012,  # Very small price
    0.0001,
    0.01,
    1.5,
    1234.56
]

print("Testing price formatting:")
for price in test_prices:
    formatted = dynamic_decimal_format(price)
    print(f"Price: {price:e} -> Formatted: {formatted}")

print("\nSpecific SHIB test cases:")
shib_prices = [0.00002345, 0.00001234, 0.000000567]
for price in shib_prices:
    formatted = dynamic_decimal_format(price)
    print(f"SHIB Price: {price} -> Formatted: {formatted}")
