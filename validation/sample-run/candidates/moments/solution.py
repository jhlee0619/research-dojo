def pairwise_squared_distance(values):
    """Return sum((x[i] - x[j])**2 for all i < j), exactly for integers."""
    total = sum(values)
    return len(values) * sum(value * value for value in values) - total * total
