# arm: caching
# why: Cache results between calls. This version has a typo and crashes.
"""Demo target: count the primes below each limit."""

import functools


@functools.lru_cache(maxsize=None)
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
    return [count_prime(limit) for limit in limits]
