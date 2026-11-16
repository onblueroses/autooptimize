# arm: data structure
# why: Keep the composites in a set. The set costs more than the bytearray, so this is slower.
"""Demo target: count the primes below each limit."""


def count_primes(limit):
    composites = set()
    count = 0
    for n in range(2, limit):
        if n not in composites:
            count += 1
            composites.update(range(n * n, limit, n))
    return count


def solve(limits):
    return [count_primes(limit) for limit in limits]
