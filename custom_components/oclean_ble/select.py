"""Select entities for the Oclean Toothbrush integration."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CONF_DEVICE_NAME,
    CONF_MAC_ADDRESS,
    DOMAIN,
    OCLEANY3M_SCHEMES,
    SCHEMES_BY_MODEL,
    SIGNAL_PROGRAMS_UPDATED,
)
from .coordinator import OcleanCoordinator
from .entity import OcleanEntity
from .protocol import TYPE1, TYPE_Z1, is_known_model, protocol_for_model


def _schemes_for_model(
    model_id: str | None,
) -> dict[int, tuple[str, list[tuple[int, int]]]] | None:
    """Return the scheme dict for a device model, or None if unsupported.

    Scheme selection writes a device-specific scheme command, so it requires an
    explicitly recognised model (its pnum→scheme mapping). Unmapped models poll as
    TYPE1 via the fallback but get no scheme select — we won't guess their schemes.
    """
    if not model_id or not is_known_model(model_id):
        return None
    proto = protocol_for_model(model_id)
    if proto is TYPE1:
        return SCHEMES_BY_MODEL.get(model_id, OCLEANY3M_SCHEMES)
    if proto is TYPE_Z1:
        return SCHEMES_BY_MODEL.get(model_id)
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Oclean select entities."""
    coordinator: OcleanCoordinator = hass.data[DOMAIN][entry.entry_id]
    mac = entry.data[CONF_MAC_ADDRESS]
    device_name = entry.data.get(CONF_DEVICE_NAME, "Oclean")
    async_add_entities([OcleanSchemeSelect(coordinator, mac, device_name)])


class OcleanSchemeSelect(OcleanEntity, SelectEntity):
    """Select entity for choosing the active brush scheme.

    Supported on all TYPE1 devices (OCLEANY3M / X family, OCLEANY3P / X Pro Elite,
    OCLEANY3 / X Pro, OCLEANX20, …) and TYPE_Z1 (OCLEANY5 / Z1).
    The entity reports as unavailable for Legacy and unsupported models.
    State is assumed (write-only BLE command) and persisted so the selection
    survives HA restarts.
    """

    _attr_assumed_state = True
    _attr_icon = "mdi:toothbrush"
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "brush_scheme"

    def __init__(
        self,
        coordinator: OcleanCoordinator,
        mac: str,
        device_name: str,
    ) -> None:
        super().__init__(coordinator, mac, device_name, "brush_scheme")

    def _custom_programs(self) -> dict[int, dict]:
        """Return the global custom programmes {pnum: {"name","steps"}} (or {})."""
        store = self.hass.data.get(DOMAIN, {}).get("_programs")
        if store is None:
            return {}
        return store.list()

    async def async_added_to_hass(self) -> None:
        """Refresh options + attributes whenever the global programme store changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_PROGRAMS_UPDATED, self.async_write_ha_state
            )
        )

    @property
    def available(self) -> bool:
        """Available only for models that have a scheme dict."""
        if self.coordinator.data is None:
            return False
        return _schemes_for_model(self.coordinator.data.model_id) is not None

    @property
    def options(self) -> list[str]:
        """Preset names for this model + all global custom names, sorted A-Z."""
        if self.coordinator.data is None:
            return []
        schemes = _schemes_for_model(self.coordinator.data.model_id)
        if schemes is None:
            return []
        names = {name for _, (name, _) in schemes.items()}
        names |= {v["name"] for v in self._custom_programs().values()}
        return sorted(names)

    @property
    def current_option(self) -> str | None:
        """Name of the active pnum: custom store first, then model presets.

        Prefers the last explicitly-set pnum; falls back to the device-reported
        brush_mode from the 0302 device-settings response so the entity shows a
        meaningful value on first start before the user has selected anything.
        """
        if self.coordinator.data is None:
            return None
        schemes = _schemes_for_model(self.coordinator.data.model_id)
        if schemes is None:
            return None
        pnum = self.coordinator.active_scheme_pnum
        if pnum is None:
            pnum = self.coordinator.data.brush_mode
        if pnum is None:
            return None
        custom = self._custom_programs().get(pnum)
        if custom is not None:
            return custom["name"]
        entry = schemes.get(pnum)
        return entry[0] if entry else None

    async def async_select_option(self, option: str) -> None:
        """Send the SetBrushScheme command for the selected name.

        Custom programmes win on a name clash with a preset (the user's own name
        maps to their programme). Custom pnums (>=120) send their stored steps.
        """
        if self.coordinator.data is None:
            return
        schemes = _schemes_for_model(self.coordinator.data.model_id)
        if schemes is None:
            return
        # preset map first, custom overlaid so a custom name wins on collision
        name_to_pnum = {name: pnum for pnum, (name, _) in schemes.items()}
        custom_by_name = {v["name"]: (pnum, v["steps"]) for pnum, v in self._custom_programs().items()}
        if option in custom_by_name:
            pnum, steps = custom_by_name[option]
            await self.coordinator.async_set_custom_scheme(pnum, steps)
            self.async_write_ha_state()
            return
        pnum = name_to_pnum.get(option)
        if pnum is None:
            return
        await self.coordinator.async_set_brush_scheme(pnum)
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, dict]:
        """Expose all programmes so the editor dashboard can load/compare them.

        Shape: {pnum: {"name": str, "steps": [[gear, dur], ...], "kind": ...}}.
        Preset steps come from the model dict; custom steps from the global store.
        """
        if self.coordinator.data is None:
            return {}
        schemes = _schemes_for_model(self.coordinator.data.model_id)
        if schemes is None:
            return {}
        programs: dict[int, dict] = {}
        for pnum, (name, steps) in schemes.items():
            programs[pnum] = {
                "name": name,
                "steps": [[g, d] for g, d in steps],
                "kind": "preset",
            }
        for pnum, val in self._custom_programs().items():
            programs[pnum] = {
                "name": val["name"],
                "steps": [[g, d] for g, d in val["steps"]],
                "kind": "custom",
            }
        return {"programs": programs}
