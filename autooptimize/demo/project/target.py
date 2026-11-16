"""Demo target: count the primes below each limit."""


def count_primes(limit):
    count = 0
    for n in range(2, limit):
        is_prime = True
        for d in range(2, n):
            if d * d > n:
                break
            if n % d == 0:
                is_prime = False
                break
        if is_prime:
            count += 1
    return count


def solve(limits):
    return [count_primes(limit) for limit in limits]
