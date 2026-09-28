def pairwise_squared_distance(values):
    """Return sum((x[i] - x[j])**2 for all i < j), exactly for integers."""
    result = 0
    count = 0
    prefix_sum = 0
    prefix_squares = 0
    for value in values:
        square = value * value
        result += count * square - 2 * value * prefix_sum + prefix_squares
        count += 1
        prefix_sum += value
        prefix_squares += square
    return result
