# scripts/_complexity_label.py
"""Local Big-O label from a fitted log-log exponent (repo-B has no cross-repo import to repo-P)."""


def label(k: float) -> str:
    if k < 0.15:
        return "O(1)"
    if k < 0.85:
        return "O(log n)"
    if k < 1.2:
        return "O(n)"
    if k < 1.6:
        return "O(n log n)"
    if k < 2.5:
        return "O(n^2)"
    return "O(n^3+)"
