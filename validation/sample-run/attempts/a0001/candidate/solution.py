def pairwise_squared_distance(values):
    """Return sum((x[i] - x[j])**2 for all i < j), exactly for integers."""
    result = 0
    for i in range(len(values)):
        for j in range(i + 1, len(values)):
            result += (values[i] - values[j]) ** 2
    return result
