"""PoW 求解器单元测试。"""
import hashlib

import pytest

from monkeycode.pow import fnv1a32, prng, solve


def test_fnv1a32_empty() -> None:
    """FNV-1a 偏移基础。"""
    assert fnv1a32("") == 0x811C9DC5


def test_prng_deterministic() -> None:
    """相同 seed/length 输出相同。"""
    assert prng("seed", 16) == prng("seed", 16)


def test_prng_differs_by_seed() -> None:
    """不同 seed 输出不同。"""
    assert prng("seed-a", 16) != prng("seed-b", 16)


def test_prng_respects_length() -> None:
    """输出长度等于请求长度。"""
    for length in (1, 8, 32, 64):
        assert len(prng("seed", length)) == length


def test_solve_returns_expected_count() -> None:
    """solutions 数量等于子质询数 c。"""
    solutions = solve("token-abc", c=3, s=8, d=4)
    assert len(solutions) == 3
    assert all(isinstance(n, int) and n >= 0 for n in solutions)


def test_solve_solutions_are_valid() -> None:
    """每个 solution 满足 sha256(salt+nonce) 以 target 开头。"""
    token = "deterministic-token"
    c, s, d = 3, 8, 4
    solutions = solve(token, c=c, s=s, d=d)
    for i, nonce in enumerate(solutions, start=1):
        base = f"{token}{i}"
        salt = prng(base, s)
        target = prng(f"{base}d", d)
        digest = hashlib.sha256(f"{salt}{nonce}".encode("utf-8")).hexdigest()
        assert digest.startswith(target)


def test_solve_raises_timeout() -> None:
    """超过最大尝试次数时抛出 TimeoutError。"""
    with pytest.raises(TimeoutError):
        solve("token", c=1, s=4, d=100, max_nonce=5)