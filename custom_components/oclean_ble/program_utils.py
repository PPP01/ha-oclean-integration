"""Pure helpers for Oclean custom brushing programmes (no Home Assistant imports).

Isolated from programs.py so the pnum-allocation and step-validation logic can be
unit-tested with plain pytest — the dev shell here ships no `homeassistant`
package. programs.py (the Store-backed manager) and coordinator.py both import
from this module, keeping validation and range constants in one place (DRY).
"""

from __future__ import annotations

from collections.abc import Iterable

# Custom programmes live at pnum >= 120 so they never collide with a model preset
# (OCLEANY3M 0/72-90, OCLEANY3 +90, OCLEANY5 91-104).
MIN_CUSTOM_PNUM = 120
MAX_CUSTOM_PNUM = 255  # protocol pnum is a single byte

# The BLE write accepts up to 9 steps (10 -> 22-byte 2nd packet > ATT-MTU-23
# usable 20 -> GATT error 133). But the brush firmware only *runs* the first 8
# steps of a 9-step scheme (verified live 2026-07-01), so the useful maximum is 8.
MAX_CUSTOM_STEPS = 8

MIN_GEAR = 1
MAX_GEAR = 41  # 1-32 Clean, 33-36 Whitening, 37-40 Massage, 41 extended
MIN_DURATION = 1
MAX_DURATION = 255


def next_free_pnum(existing: Iterable[int]) -> int:
    """Return the lowest free custom pnum >= MIN_CUSTOM_PNUM.

    *existing* may contain ints or numeric strings (JSON store keys). Raises
    ValueError when the whole custom range (120-255) is occupied.
    """
    used = {int(p) for p in existing}
    for pnum in range(MIN_CUSTOM_PNUM, MAX_CUSTOM_PNUM + 1):
        if pnum not in used:
            return pnum
    raise ValueError("no free custom programme slot (120-255 all in use)")


def validate_program_steps(steps: list[tuple[int, int]]) -> None:
    """Validate a custom programme step list; raise ValueError on any violation.

    Rules: 1..MAX_CUSTOM_STEPS steps, each a (gear, duration) with gear in
    MIN_GEAR..MAX_GEAR and duration in MIN_DURATION..MAX_DURATION seconds.
    """
    if not steps:
        raise ValueError("steps must contain at least one (gear, duration) pair")
    if len(steps) > MAX_CUSTOM_STEPS:
        raise ValueError(f"too many steps ({len(steps)}); max {MAX_CUSTOM_STEPS}")
    for gear, dur in steps:
        if not MIN_GEAR <= gear <= MAX_GEAR:
            raise ValueError(f"gear {gear} out of range ({MIN_GEAR}-{MAX_GEAR})")
        if not MIN_DURATION <= dur <= MAX_DURATION:
            raise ValueError(f"duration {dur} out of range ({MIN_DURATION}-{MAX_DURATION} s)")
