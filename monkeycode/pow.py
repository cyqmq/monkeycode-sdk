"""MonkeyCode PoW 验证码求解器。

协议：SHA-256 前缀碰撞（工作量证明），无需识别图片。
流程：
  1. POST /api/v1/public/captcha/challenge 获取 {challenge: {c,s,d}, token}
  2. 对每个 i(1..c)：用确定性 PRNG 生成 salt 和 target，
     爆破 nonce 使 sha256(salt + nonce) 以 target 开头
  3. POST /api/v1/public/captcha/redeem 提交 solutions，得到 captcha_token

参考实现：chaitin/MonkeyCode desktop/src/baizhi/pow.rs
"""
from __future__ import annotations

import hashlib


def fnv1a32(s: str) -> int:
    """FNV-1a 32 位哈希，用于播种 PRNG。"""
    h = 0x811C9DC5
    for byte in s.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def prng(seed: str, length: int) -> str:
    """xorshift32 确定性 PRNG，生成指定长度的十六进制串。"""
    state = fnv1a32(seed)
    result: list[str] = []
    total = 0
    while total < length:
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        state &= 0xFFFFFFFF
        result.append(f"{state:08x}")
        total += 8
    return "".join(result)[:length]


def solve(
    token: str,
    c: int,
    s: int,
    d: int,
    max_nonce: int = 5_000_000,
) -> list[int]:
    """求解 PoW 验证码，返回 solutions（每个子质询的 nonce）。"""
    solutions: list[int] = []
    for i in range(1, c + 1):
        base = f"{token}{i}"
        salt = prng(base, s)
        target = prng(f"{base}d", d)
        nonce = 0
        while True:
            digest = hashlib.sha256(f"{salt}{nonce}".encode("utf-8")).hexdigest()
            if digest.startswith(target):
                solutions.append(nonce)
                break
            nonce += 1
            if nonce > max_nonce:
                raise TimeoutError(
                    f"子质询 {i} 超过最大尝试次数 {max_nonce}（salt={salt}, target={target}）"
                )
    return solutions