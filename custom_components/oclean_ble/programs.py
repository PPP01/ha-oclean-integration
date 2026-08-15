"""Global custom brushing-programme store for the Oclean integration.

One instance per Home Assistant, shared by every config entry (device), so a
programme created for one brush is usable on all of them. Persisted to
.storage/oclean_ble_custom_programs as:

    {"programs": {"<pnum>": {"name": "...", "steps": [[gear, dur], ...]}}}

pnum (int) is the identity; JSON forces string keys, coerced on load.
"""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import (
    PROGRAMS_STORAGE_KEY,
    PROGRAMS_STORAGE_VERSION,
    SIGNAL_PROGRAMS_UPDATED,
)
from .program_utils import MIN_CUSTOM_PNUM, next_free_pnum, validate_program_steps


class CustomProgramStore:
    """Loads, lists, saves and deletes cross-device custom programmes."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store: Store = Store(hass, PROGRAMS_STORAGE_VERSION, PROGRAMS_STORAGE_KEY)
        self._programs: dict[int, dict[str, Any]] = {}
        self._loaded = False

    async def async_load(self) -> None:
        """Load programmes from disk (idempotent)."""
        data = await self._store.async_load()
        programs: dict[int, dict[str, Any]] = {}
        if data and isinstance(data.get("programs"), dict):
            for key, val in data["programs"].items():
                try:
                    pnum = int(key)
                    steps = [(int(g), int(d)) for g, d in val["steps"]]
                    programs[pnum] = {"name": str(val["name"]), "steps": steps}
                except (KeyError, ValueError, TypeError):
                    continue  # skip malformed entry rather than fail the whole load
        self._programs = programs
        self._loaded = True

    def list(self) -> dict[int, dict[str, Any]]:
        """Return a shallow copy of {pnum: {"name", "steps"}}."""
        return {p: {"name": v["name"], "steps": list(v["steps"])} for p, v in self._programs.items()}

    def get(self, pnum: int) -> dict[str, Any] | None:
        """Return {"name", "steps"} for *pnum*, or None if unknown."""
        entry = self._programs.get(int(pnum))
        if entry is None:
            return None
        return {"name": entry["name"], "steps": list(entry["steps"])}

    async def async_save(
        self,
        name: str,
        steps: list[tuple[int, int]],
        pnum: int | None = None,
    ) -> int:
        """Create or overwrite a programme; return its pnum.

        pnum None or 0 -> allocate the next free pnum >= 120. An explicit pnum
        must be >= 120 (presets are immutable). Validates steps and name, then
        persists and fires SIGNAL_PROGRAMS_UPDATED.
        """
        validate_program_steps(steps)
        if not name or not name.strip():
            raise ValueError("programme name must not be empty")
        if pnum in (None, 0):
            pnum = next_free_pnum(self._programs)
        else:
            pnum = int(pnum)
            if pnum < MIN_CUSTOM_PNUM:
                raise ValueError(
                    f"custom pnum must be >= {MIN_CUSTOM_PNUM} (presets are immutable)"
                )
        self._programs[pnum] = {
            "name": name.strip(),
            "steps": [(int(g), int(d)) for g, d in steps],
        }
        await self._async_persist()
        return pnum

    async def async_delete(self, pnum: int) -> None:
        """Remove a programme (no-op if unknown); persist + fire the signal."""
        self._programs.pop(int(pnum), None)
        await self._async_persist()

    async def _async_persist(self) -> None:
        await self._store.async_save(
            {
                "programs": {
                    str(p): {"name": v["name"], "steps": [[g, d] for g, d in v["steps"]]}
                    for p, v in self._programs.items()
                }
            }
        )
        async_dispatcher_send(self._hass, SIGNAL_PROGRAMS_UPDATED)
