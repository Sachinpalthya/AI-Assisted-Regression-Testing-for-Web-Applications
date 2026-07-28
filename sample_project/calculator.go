// calculator.go — Simple arithmetic utilities for regression testing demo.
package calculator

import "errors"

// Add returns the sum of a and b.
func Add(a, b float64) float64 {
	return a + b
}

// Subtract returns a minus b.
func Subtract(a, b float64) float64 {
	return a - b
}

// Multiply returns the product of a and b.
func Multiply(a, b float64) float64 {
	return a * b
}

// Divide returns a divided by b.
// Returns an error if b is zero.
func Divide(a, b float64) (float64, error) {
	if b == 0 {
		return 0, errors.New("division by zero is not allowed")
	}
	return a / b, nil
}

// Factorial returns the factorial of n (n >= 0).
// Returns an error for negative input.
func Factorial(n int) (int, error) {
	if n < 0 {
		return 0, errors.New("factorial is not defined for negative numbers")
	}
	if n == 0 || n == 1 {
		return 1, nil
	}
	result, err := Factorial(n - 1)
	if err != nil {
		return 0, err
	}
	return n * result, nil
}

// Clamp restricts value to the range [min, max].
func Clamp(value, min, max float64) (float64, error) {
	if min > max {
		return 0, errors.New("min must not be greater than max")
	}
	if value < min {
		return min, nil
	}
	if value > max {
		return max, nil
	}
	return value, nil
}
