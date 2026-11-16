# arm: tidy
# why: Rename variables for clarity. The algorithm is unchanged, so no speed change is expected.
"""Demo target: count the primes below each limit."""


def count_primes(limit):
    total = 0
    for candidate in range(2, limit):
        prime = True
        for divisor in range(2, candidate):
            if divisor * divisor > candidate:
                break
            if candidate % divisor == 0:
                prime = False
                break
        if prime:
            total += 1
    return total


def solve(limits):
    return [count_primes(limit) for limit in limits]
