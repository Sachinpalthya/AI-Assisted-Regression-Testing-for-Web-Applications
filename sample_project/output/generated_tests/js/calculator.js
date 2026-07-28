/**
 * calculator.js — Simple arithmetic utilities for regression testing demo.
 */

/**
 * Adds two numbers.
 * @param {number} a
 * @param {number} b
 * @returns {number}
 */
function add(a, b) {
    return a + b;
}

/**
 * Subtracts b from a.
 * @param {number} a
 * @param {number} b
 * @returns {number}
 */
function subtract(a, b) {
    return a - b;
}

/**
 * Multiplies two numbers.
 * @param {number} a
 * @param {number} b
 * @returns {number}
 */
function multiply(a, b) {
    return a * b;
}

/**
 * Divides a by b.
 * @param {number} a
 * @param {number} b
 * @returns {number}
 * @throws {Error} if b is zero
 */
function divide(a, b) {
    if (b === 0) {
        throw new Error("Division by zero is not allowed");
    }
    return a / b;
}

/**
 * Returns the factorial of n (n >= 0).
 * @param {number} n
 * @returns {number}
 */
function factorial(n) {
    if (n < 0) throw new Error("Factorial is not defined for negative numbers");
    if (n === 0 || n === 1) return 1;
    return n * factorial(n - 1);
}

/**
 * Clamps a value between min and max.
 * @param {number} value
 * @param {number} min
 * @param {number} max
 * @returns {number}
 */
function clamp(value, min, max) {
    if (min > max) throw new Error("min must not be greater than max");
    return Math.min(Math.max(value, min), max);
}

module.exports = { add, subtract, multiply, divide, factorial, clamp };
