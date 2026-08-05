"""Runtime fallback-resolution contract mirror (for conformance testing).

The frontend runtime resolver is the EXECUTION CONTRACT for fallback resolution:
`frontend/src/game/pixi/assets/AssetManager.ts` -> `resolveTiered` (lines ~252-267).
It builds a FIXED candidate sequence from the ORIGINAL request only:

    primary
      -> entry     : primary.fallbackAssetId          (if present)
      -> category  : categoryFallbacks[primary.category] (if present)
      -> universal : UNIVERSAL_FALLBACK_ASSET_ID (terminal, code-generated)

It is NOT per-entry recursive: it never follows a fallback target's OWN
fallbackAssetId, nor a category target's entry fallback. Duplicate candidate ids are
loaded at most once. Consequently the chain is CYCLE-FREE and bounded to at most
`MAX_FALLBACK_HOPS` fallback candidates BY CONSTRUCTION — there is no manifest that
makes the resolver exceed the bound, so the validator does not (and must not) model a
transitive combined fallback graph. This module reproduces that sequence so Python
conformance tests can pin it to the runtime's behavior.
"""

from __future__ import annotations

from typing import Any

# Runtime terminal fallback id (frontend generatedBuildingAsset.ts:
# `UNIVERSAL_FALLBACK_ASSET_ID = 'fallback.universal.generated'`).
UNIVERSAL_FALLBACK_ASSET_ID = "fallback.universal.generated"
# Runtime cap (frontend AssetManager.ts: `MAX_FALLBACK_DEPTH = 3`). The Primary is the
# original request and is NOT counted as a fallback hop.
MAX_FALLBACK_DEPTH = 3


def candidate_sequence(
    assets: dict[str, dict[str, Any]],
    category_fallbacks: dict[str, str],
    asset_id: str,
    *,
    universal_id: str = UNIVERSAL_FALLBACK_ASSET_ID,
) -> list[str]:
    """Reproduce `resolveTiered`'s candidate sequence for one request (deduped, in order).

    Index 0 is the Primary (original request); the remainder are the fallback
    candidates in Entry -> Category -> Universal order.
    """
    primary = assets.get(asset_id)
    raw: list[str] = [asset_id]
    if primary is not None:
        entry_fb = primary.get("fallbackAssetId")
        if isinstance(entry_fb, str) and entry_fb:
            raw.append(entry_fb)
        category = primary.get("category")
        cat_fb = category_fallbacks.get(category) if isinstance(category, str) else None
        if isinstance(cat_fb, str) and cat_fb:
            raw.append(cat_fb)
    raw.append(universal_id)

    out: list[str] = []
    seen: set[str] = set()
    for candidate in raw:  # dedupe: same id never loaded twice (resolveTiered `tried`)
        if candidate not in seen:
            seen.add(candidate)
            out.append(candidate)
    return out


def fallback_hops(sequence: list[str]) -> int:
    """Number of fallback hops (candidate count minus the Primary)."""
    return max(0, len(sequence) - 1)
