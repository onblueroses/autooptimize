# arm: algorithm
# why: Use a sieve of Eratosthenes instead of trial division.
"""Demo target: count the primes below each limit."""


def count_primes(limit):
    if limit < 3:
        return 0
    sieve = bytearray([1]) * limit
    sieve[0] = sieve[1] = 0
    for n in range(2, int(limit ** 0.5) + 1):
        if sieve[n]:
            sieve[n * n::n] = bytes(len(range(n * n, limit, n)))
    return sum(sieve)


def solve(limits):
    return [count_primes(limit) for limit in limits]
