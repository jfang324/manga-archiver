from argparse import ArgumentTypeError


def positive_int(value: str) -> int:
    """Validate that a string is a positive integer."""
    try:
        n = int(value)
    except ValueError as e:
        raise ArgumentTypeError(f"invalid integer value: {value}") from e

    if n < 1:
        raise ArgumentTypeError(f"must be at least 1, got {n}")

    return n
