"""Brush coverage image entity for the Oclean BLE integration.

Generates an SVG tooth diagram showing which zones were brushed and how
evenly the brushing time was distributed.  Individual tooth circles are
placed along an elliptical arch and split into inner/outer halves.

Adapted from upstream PR #88 (feat/brush-coverage-image) with one key
change: colours are SHARE-based instead of absolute "pressure" thresholds.
On the Y3 series the zone values are time (seconds on OCLEANY3MH, fixed
96-slot counts on OCLEANY3MD), so absolute thresholds never differentiate.
Rating comes from zone_utils.zone_ratings (target = sum/8):

    grey   -> not brushed (0)
    green  -> good  (>= 75 % of target)
    amber  -> ok    (>= 40 % of target)
    red    -> poor  (> 0, < 40 % of target)

No external assets or dependencies required - pure Python + math.
"""

from __future__ import annotations

import math

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DEVICE_NAME,
    CONF_MAC_ADDRESS,
    DATA_LAST_BRUSH_AREAS,
    DOMAIN,
    TOOTH_AREA_NAMES,
)
from .coordinator import OcleanCoordinator
from .entity import OcleanEntity
from .zone_utils import zone_ratings

# SVG canvas.
_W, _H = 300, 460
_MID_Y = 230  # horizontal divider between upper and lower jaw

# Arch geometry - ellipse parameters for tooth centre positions.
_UPPER = {"cx": _W / 2, "cy": _MID_Y - 8, "rx": 80, "ry": 160, "start": 185, "end": 355}
_LOWER = {"cx": _W / 2, "cy": _MID_Y + 8, "rx": 80, "ry": 160, "start": 5, "end": 175}
_TEETH_PER_JAW = 16
_TOOTH_R = 15

_BG = "#E0E0E0"
_BG_STROKE = "#D0D0D0"

# Same palette as the dashboard jaw model / calendar emojis.
_RATING_COLORS: dict[str, str | None] = {
    "good": "#4CAF50",
    "ok": "#FFC107",
    "poor": "#F44336",
    "missed": None,  # grey background tooth stays visible
}


def _zone_colors(areas: dict[str, int]) -> dict[str, str | None]:
    """Map each zone name to its share-based rating colour."""
    zones = [int(areas.get(n, 0)) for n in TOOTH_AREA_NAMES]
    ratings = zone_ratings(zones)
    if ratings is None:
        return dict.fromkeys(TOOTH_AREA_NAMES)
    return {name: _RATING_COLORS[ratings[i]] for i, name in enumerate(TOOTH_AREA_NAMES)}


# ------------------------------------------------------------------
# SVG helpers
# ------------------------------------------------------------------


def _tooth_positions(
    cx: float,
    cy: float,
    rx: float,
    ry: float,
    start_deg: float,
    end_deg: float,
    count: int,
) -> list[tuple[float, float]]:
    """Return (x, y) centres for *count* teeth along an elliptical arc."""
    start_rad = math.radians(start_deg)
    end_rad = math.radians(end_deg)
    return [
        (
            cx + rx * math.cos(start_rad + (end_rad - start_rad) * i / (count - 1)),
            cy + ry * math.sin(start_rad + (end_rad - start_rad) * i / (count - 1)),
        )
        for i in range(count)
    ]


def _tooth_zone_map(n_teeth: int, jaw_name: str) -> list[str]:
    """Return a list mapping each tooth index to its section (left/right).

    Upper jaw arc: first half = left, second half = right.
    Lower jaw arc: reversed (first half = right, second half = left).
    """
    mid = n_teeth // 2
    sections = ["left"] * mid + ["right"] * (n_teeth - mid)
    if jaw_name == "lower":
        sections = list(reversed(sections))
    return sections


def _semicircle_path(
    tx: float,
    ty: float,
    r: float,
    cx: float,
    cy: float,
    *,
    outer: bool,
) -> str:
    """SVG path for a semicircle split along the radial direction.

    Note the sweep flags are the OPPOSITE of upstream PR #88: in SVG screen
    coordinates (y down) sweep=1 runs clockwise, which for the p1->p2 chord
    chosen here bulges TOWARDS the arch centre (= inner/lingual half). The
    outer/buccal half therefore needs sweep=0. Verified against real zone
    data (outer-rated zones must colour the outward-facing semicircle).
    """
    angle = math.atan2(ty - cy, tx - cx)
    perp = angle + math.pi / 2
    p1x = tx + r * math.cos(perp)
    p1y = ty + r * math.sin(perp)
    p2x = tx - r * math.cos(perp)
    p2y = ty - r * math.sin(perp)
    sweep = 0 if outer else 1
    return f"M {p1x:.1f} {p1y:.1f} A {r} {r} 0 0 {sweep} {p2x:.1f} {p2y:.1f} Z"


def _generate_svg(areas: dict[str, int]) -> str:
    """Generate a complete SVG string for the given brush area values."""
    colors = _zone_colors(areas)
    elems: list[str] = []

    for jaw_name, jaw in [("upper", _UPPER), ("lower", _LOWER)]:
        cx, cy = jaw["cx"], jaw["cy"]
        rx, ry = jaw["rx"], jaw["ry"]
        start, end = jaw["start"], jaw["end"]

        positions = _tooth_positions(cx, cy, rx, ry, start, end, _TEETH_PER_JAW)
        zone_map = _tooth_zone_map(_TEETH_PER_JAW, jaw_name)

        for idx, (tx, ty) in enumerate(positions):
            section = zone_map[idx]
            color_out = colors.get(f"{jaw_name}_{section}_out")
            color_in = colors.get(f"{jaw_name}_{section}_in")

            # Grey background tooth.
            elems.append(
                f'<circle cx="{tx:.1f}" cy="{ty:.1f}" r="{_TOOTH_R}" '
                f'fill="{_BG}" stroke="{_BG_STROKE}" stroke-width="0.3"/>'
            )

            # Outer half (semicircle facing away from arch centre).
            if color_out:
                d = _semicircle_path(tx, ty, _TOOTH_R, cx, cy, outer=True)
                elems.append(f'<path d="{d}" fill="{color_out}" opacity="0.9"/>')

            # Inner half (semicircle facing toward arch centre).
            if color_in:
                d = _semicircle_path(tx, ty, _TOOTH_R, cx, cy, outer=False)
                elems.append(f'<path d="{d}" fill="{color_in}" opacity="0.9"/>')

    # Divider line and labels.
    elems.append(
        f'<line x1="20" y1="{_MID_Y}" x2="{_W - 20}" y2="{_MID_Y}" '
        f'stroke="{_BG_STROKE}" stroke-width="1" stroke-dasharray="4,4"/>'
    )
    elems.append(
        f'<text x="12" y="{_MID_Y + 5}" font-family="Arial,sans-serif" '
        f'font-size="13" fill="#BBB" text-anchor="middle">L</text>'
    )
    elems.append(
        f'<text x="{_W - 12}" y="{_MID_Y + 5}" font-family="Arial,sans-serif" '
        f'font-size="13" fill="#BBB" text-anchor="middle">R</text>'
    )

    elems_str = "\n  ".join(elems)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg"'
        f' viewBox="0 0 {_W} {_H}" width="{_W}" height="{_H}">\n'
        f'  <rect width="{_W}" height="{_H}" fill="white" rx="8"/>\n'
        f"  {elems_str}\n"
        f"</svg>\n"
    )


# ------------------------------------------------------------------
# Home Assistant entity
# ------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Oclean brush coverage image entity."""
    coordinator: OcleanCoordinator = hass.data[DOMAIN][entry.entry_id]
    mac = entry.data[CONF_MAC_ADDRESS]
    device_name = entry.data.get(CONF_DEVICE_NAME, "Oclean")
    async_add_entities([OcleanBrushCoverageImage(hass, coordinator, mac, device_name)])


class OcleanBrushCoverageImage(OcleanEntity, ImageEntity):
    """Image entity showing a colour-coded brush coverage diagram."""

    _attr_content_type = "image/svg+xml"
    _attr_translation_key = "brush_coverage"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: OcleanCoordinator,
        mac: str,
        device_name: str,
    ) -> None:
        OcleanEntity.__init__(self, coordinator, mac, device_name, "brush_coverage")
        # HA's real ImageEntity requires hass (upstream PR #88 omits it and
        # only passes its CI because the test conftest stubs ImageEntity).
        ImageEntity.__init__(self, hass)
        self._cached_image: bytes | None = None
        self._cached_areas: dict[str, int] | None = None

    def _get_areas(self) -> dict[str, int] | None:
        if self.coordinator.data is None:
            return None
        areas = self.coordinator.data.get(DATA_LAST_BRUSH_AREAS)
        return areas if isinstance(areas, dict) else None

    def _handle_coordinator_update(self) -> None:
        """Invalidate cache when area data changes."""
        areas = self._get_areas()
        if areas != self._cached_areas:
            self._cached_areas = areas
            self._cached_image = None
            self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    async def async_image(self) -> bytes | None:
        """Return the brush coverage SVG as bytes."""
        areas = self._get_areas()
        if areas is None:
            return None

        if self._cached_image is not None:
            return self._cached_image

        self._cached_image = _generate_svg(areas).encode("utf-8")
        return self._cached_image
