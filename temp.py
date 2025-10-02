import math


def find_power_curve_parameters(point1, point2):
    """
    Calculates the parameters for a power function of the form:
    y = multiplier * x^power
    that passes exactly through two given points.

    Args:
        point1 (tuple): The first point as (x1, y1).
        point2 (tuple): The second point as (x2, y2).

    Returns:
        tuple: A tuple containing the calculated (multiplier, power).

    Raises:
        ValueError: If x or y values are not positive or if a unique
                    curve cannot be determined.
    """
    x1, y1 = point1
    x2, y2 = point2

    # --- Input Validation ---
    if x1 <= 0 or x2 <= 0 or y1 <= 0 or y2 <= 0:
        raise ValueError("All x and y values must be positive for this power function.")
    if x1 == x2 or y1 == y2:
        raise ValueError("Points must be unique and not form a horizontal or vertical line.")

    # --- Solve for 'power' (p) ---
    # y2 / y1 = (x2 / x1)^p
    # Take the log of both sides to solve for p:
    # ln(y2 / y1) = p * ln(x2 / x1)
    power = math.log(y2 / y1) / math.log(x2 / x1)

    # --- Solve for 'multiplier' (m) ---
    # m = y1 / (x1^p)
    multiplier = y1 / (x1 ** power)

    return multiplier, power


# --- Example Usage ---
if __name__ == "__main__":
    # Let's use the points that caused the error before:
    p1 = (1, 25)
    p2 = (3, 40)

    try:
        # Calculate the parameters
        m, p = find_power_curve_parameters(p1, p2)

        print(f"To fit a power curve through {p1} and {p2}:")
        print(f"\nThe function is: y = {m:.4f} * x^{p:.4f}\n")
        print("-" * 30)

        # --- Verification Step ---
        print("Verification:")
        # Test point 1
        x1, y1 = p1
        y_calc1 = m * (x1 ** p)
        print(f"For x={x1}, the calculated y is {y_calc1:.4f} (Expected: {y1})")

        # Test point 2
        x2, y2 = p2
        y_calc2 = m * (x2 ** p)
        print(f"For x={x2}, the calculated y is {y_calc2:.4f} (Expected: {y2})")

        if 0 < p < 1:
            print("\nSince 0 < power < 1, this function has diminishing returns. ✅")

    except ValueError as e:
        print(f"Error: {e}")