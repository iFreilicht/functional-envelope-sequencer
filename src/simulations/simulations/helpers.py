_FLOAT_TOLERANCE = 1e-9


def clamp_checked(value: float, min_value: float, max_value: float) -> float:
    """Clamp `value` to the range [`min_value`, `max_value`], inclusive.  Assert that
    `value` is within the range before clamping, allowing for a small amount of
    floating-point noise defined by `_FLOAT_TOLERANCE`.
    """
    assert min_value - _FLOAT_TOLERANCE <= value <= max_value + _FLOAT_TOLERANCE, (
        f"{value} is outside of limits [{min_value}, {max_value}]!"
    )
    return clamp(value, min_value, max_value)


def clamp(value: float, min_value: float, max_value: float) -> float:
    """Clamp `value` to the range [`min_value`, `max_value`], inclusive."""
    return max(min_value, min(value, max_value))
