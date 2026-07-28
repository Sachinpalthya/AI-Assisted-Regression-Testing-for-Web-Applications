"""
sample_project/calculator.py

A simple calculator module demonstrating common arithmetic operations.
Intentionally includes a subtle bug for the AI to detect.
"""


class Calculator:
    """A stateful calculator with history tracking."""

    def __init__(self):
        self.history = []

    def add(self, a: float, b: float) -> float:
        """Return the sum of a and b."""
        result = a + b
        self.history.append(("add", a, b, result))
        return result

    def subtract(self, a: float, b: float) -> float:
        """Return a minus b."""
        result = a - b
        self.history.append(("subtract", a, b, result))
        return result

    def multiply(self, a: float, b: float) -> float:
        """Return the product of a and b."""
        result = a * b
        self.history.append(("multiply", a, b, result))
        return result

    def divide(self, a: float, b: float) -> float:
        """
        Return a divided by b.
        Raises ValueError if b is zero.
        """
        if b == 0:
            raise ValueError("Cannot divide by zero")
        result = a / b
        self.history.append(("divide", a, b, result))
        return result

    def power(self, base: float, exponent: float) -> float:
        """Return base raised to the power of exponent."""
        result = base ** exponent
        self.history.append(("power", base, exponent, result))
        return result

    def get_history(self) -> list:
        """Return all past calculations."""
        return self.history.copy()

    def clear_history(self) -> None:
        """Clear the calculation history."""
        self.history = []


def percentage(value: float, total: float) -> float:
    """
    Calculate what percentage `value` is of `total`.

    Args:
        value: The part value
        total: The whole value

    Returns:
        Percentage as a float (e.g. 25.0 for 25%)

    Raises:
        ValueError: If total is zero
        TypeError:  If inputs are not numeric
    """
    if not isinstance(value, (int, float)) or not isinstance(total, (int, float)):
        raise TypeError("Both value and total must be numeric")
    if total == 0:
        raise ValueError("Total cannot be zero")
    return (value / total) * 100


def is_prime(n: int) -> bool:
    """
    Determine if an integer n is a prime number.

    Args:
        n: Integer to check

    Returns:
        True if n is prime, False otherwise
    """
    if not isinstance(n, int):
        raise TypeError("Input must be an integer")
    if n < 2:
        return False
    for i in range(2, int(n ** 0.5) + 1):
        if n % i == 0:
            return False
    return True
