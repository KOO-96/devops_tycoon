"""First Production Image Readiness — deterministic budget EVIDENCE (synthetic).

Pins the GPU-memory estimates to the validator's OWN formula (`core.gpu_bytes`,
RGBA8 = w*h*4, mip *4/3) against the canonical PROPOSED targets. These are ESTIMATES,
not hardware VRAM (see docs/operations/first-production-image-budget-evidence.md). No
production assets; no target number is invented or changed here.
"""

from __future__ import annotations

from tools.asset_ops.core import (
    CRITICAL_GPU_BYTES,
    RESIDENT_GPU_BYTES,
    TEXTURE_HARD_MAX,
    TEXTURE_RECOMMENDED,
    gpu_bytes,
)

MiB = 1024 * 1024


def test_gpu_formula_matches_rgba8_and_mip() -> None:
    # The estimate is exactly the validator's contract: RGBA8 bytes, mip ~*1.333.
    assert gpu_bytes(2048, 2048, mipmap=False) == 2048 * 2048 * 4 == 16 * MiB
    assert gpu_bytes(1000, 500, mipmap=False) == 1000 * 500 * 4
    assert gpu_bytes(2048, 2048, mipmap=True) == (2048 * 2048 * 4 * 4) // 3  # ~21.33 MiB


def test_recommended_texture_within_budgets() -> None:
    # 2048^2 (recommended max) fits both the 32 MiB critical and 64 MiB resident targets.
    dec = gpu_bytes(TEXTURE_RECOMMENDED, TEXTURE_RECOMMENDED, mipmap=False)
    assert dec == 16 * MiB
    assert dec <= CRITICAL_GPU_BYTES  # 16 <= 32
    assert dec <= RESIDENT_GPU_BYTES  # 16 <= 64
    assert gpu_bytes(TEXTURE_RECOMMENDED, TEXTURE_RECOMMENDED, mipmap=True) <= RESIDENT_GPU_BYTES


def test_4096_exception_consumes_whole_resident_budget() -> None:
    # A single 4096^2 decoded texture == the entire 64 MiB resident cap; mipmapped it
    # EXCEEDS it — so 4096^2 is exception-only and cannot share resident with anything.
    dec = gpu_bytes(TEXTURE_HARD_MAX, TEXTURE_HARD_MAX, mipmap=False)
    assert dec == 64 * MiB == RESIDENT_GPU_BYTES
    assert dec > CRITICAL_GPU_BYTES  # 64 > 32 critical
    assert gpu_bytes(TEXTURE_HARD_MAX, TEXTURE_HARD_MAX, mipmap=True) > RESIDENT_GPU_BYTES


def test_evidence_table_is_deterministic() -> None:
    # The representative sizes used in the budget-evidence doc, pinned.
    table = {
        n: (gpu_bytes(n, n, mipmap=False), gpu_bytes(n, n, mipmap=True))
        for n in (64, 512, 2048, 4096)
    }
    assert table[64] == (16384, 21845)
    assert table[512] == (1048576, 1398101)
    assert table[2048] == (16777216, 22369621)
    assert table[4096] == (67108864, 89478485)
