// Calculator.java — Simple arithmetic utilities for regression testing demo.

/**
 * Provides basic arithmetic operations for testing purposes.
 */
public class Calculator {

    /**
     * Adds two numbers.
     */
    public double add(double a, double b) {
        return a + b;
    }

    /**
     * Subtracts b from a.
     */
    public double subtract(double a, double b) {
        return a - b;
    }

    /**
     * Multiplies two numbers.
     */
    public double multiply(double a, double b) {
        return a * b;
    }

    /**
     * Divides a by b.
     *
     * @throws ArithmeticException if b is zero
     */
    public double divide(double a, double b) {
        if (b == 0) {
            throw new ArithmeticException("Division by zero is not allowed");
        }
        return a / b;
    }

    /**
     * Returns the factorial of n (n >= 0).
     *
     * @throws IllegalArgumentException for negative input
     */
    public long factorial(int n) {
        if (n < 0) {
            throw new IllegalArgumentException("Factorial is not defined for negative numbers");
        }
        long result = 1;
        for (int i = 2; i <= n; i++) {
            result *= i;
        }
        return result;
    }

    /**
     * Clamps value to the inclusive range [min, max].
     *
     * @throws IllegalArgumentException if min > max
     */
    public double clamp(double value, double min, double max) {
        if (min > max) {
            throw new IllegalArgumentException("min must not be greater than max");
        }
        return Math.min(Math.max(value, min), max);
    }
}
