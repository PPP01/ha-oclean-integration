"""Oclean Smart Toothbrush Home Assistant integration."""

from __future__ import annotations

import json
import logging
import logging.handlers
import pathlib

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DEVICE_NAME,
    CONF_MAC_ADDRESS,
    CONF_MERGE_WINDOW,
    CONF_POLL_INTERVAL,
    CONF_POLL_WINDOWS,
    CONF_POST_BRUSH_COOLDOWN,
    CONF_ZONE_HISTORY,
    DEFAULT_MERGE_WINDOW,
    DEFAULT_POLL_INTERVAL,
    DEFAULT_POST_BRUSH_COOLDOWN,
    DEFAULT_ZONE_HISTORY,
    DOMAIN,
    SERVICE_GET_ZONE_HISTORY,
    SERVICE_POLL,
)
from .coordinator import OcleanCoordinator

_LOGGER = logging.getLogger(__name__)
_MANIFEST = json.loads((pathlib.Path(__file__).parent / "manifest.json").read_text())
_INTEGRATION_VERSION = _MANIFEST.get("version", "unknown")

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

# Key under hass.data[DOMAIN] where the shared file handler is stored
_FILE_HANDLER_KEY = "_file_handler"


def _build_file_handler(log_path: pathlib.Path) -> logging.handlers.RotatingFileHandler:
    """Create the RotatingFileHandler (blocking I/O – must run in executor)."""
    handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=1 * 1024 * 1024,  # 1 MB per file
        backupCount=2,  # keep oclean_ble.log + .1 + .2
        encoding="utf-8",
    )
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s  %(levelname)-8s  [%(name)s]  %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    return handler


async def _attach_file_handler(hass: HomeAssistant) -> None:
    """Attach a rotating file handler to the oclean_ble logger (once per HA session).

    Log file: <config_dir>/oclean_ble.log
    Max size:  1 MB, 2 rotated backups (≤ 3 MB total)
    Level:     DEBUG – all unknown-byte traces and raw hex dumps included.

    The handler is shared across multiple config entries (multiple devices).
    It is removed when the last entry is unloaded.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    if _FILE_HANDLER_KEY in domain_data:
        return  # already attached (or attachment in progress)

    # Set sentinel *before* the async gap so that a second config entry being
    # set up concurrently also sees the key and skips duplicate attachment.
    domain_data[_FILE_HANDLER_KEY] = None

    log_path = pathlib.Path(hass.config.config_dir) / "oclean_ble.log"
    # open() is blocking – run in the default executor to avoid loop warnings
    handler = await hass.async_add_executor_job(_build_file_handler, log_path)

    oclean_logger = logging.getLogger("custom_components.oclean_ble")
    oclean_logger.addHandler(handler)
    domain_data[_FILE_HANDLER_KEY] = handler
    _LOGGER.info("Oclean log file: %s", log_path)


async def _detach_file_handler(hass: HomeAssistant) -> None:
    """Remove the file handler when the last entry is unloaded."""
    domain_data = hass.data.get(DOMAIN, {})
    handler = domain_data.pop(_FILE_HANDLER_KEY, None)
    if handler is None:
        return
    oclean_logger = logging.getLogger("custom_components.oclean_ble")
    oclean_logger.removeHandler(handler)
    # handler.close() flushes and closes the underlying file – run in executor
    await hass.async_add_executor_job(handler.close)
    _LOGGER.debug("Oclean file log handler detached")


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Oclean from a config entry."""
    await _attach_file_handler(hass)

    mac = entry.data[CONF_MAC_ADDRESS]
    device_name = entry.data.get(CONF_DEVICE_NAME, "Oclean")
    poll_interval = entry.options.get(
        CONF_POLL_INTERVAL,
        entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )

    poll_windows = entry.options.get(CONF_POLL_WINDOWS, "")
    post_brush_cooldown_h = int(entry.options.get(CONF_POST_BRUSH_COOLDOWN, DEFAULT_POST_BRUSH_COOLDOWN))
    merge_window_min = int(entry.options.get(CONF_MERGE_WINDOW, DEFAULT_MERGE_WINDOW))
    zone_history_days = int(entry.options.get(CONF_ZONE_HISTORY, DEFAULT_ZONE_HISTORY))

    _LOGGER.info(
        "Oclean integration v%s starting: mac=%s name=%s (HA %s)",
        _INTEGRATION_VERSION,
        mac,
        device_name,
        HA_VERSION,
    )
    _LOGGER.debug(
        "Oclean config: poll_interval=%s poll_windows=%r post_brush_cooldown_h=%d",
        f"{poll_interval}s" if poll_interval > 0 else "manual (disabled)",
        poll_windows or "(none)",
        post_brush_cooldown_h,
    )

    coordinator = OcleanCoordinator(
        hass,
        mac,
        device_name,
        poll_interval,
        poll_windows=poll_windows,
        post_brush_cooldown_h=post_brush_cooldown_h,
        merge_window_min=merge_window_min,
        zone_history_days=zone_history_days,
    )

    # Register coordinator and set up platforms *before* the first poll so that
    # the poll service and all entities always exist, even when the device is
    # sleeping on HA startup.  Entities will show as unavailable until the first
    # successful poll.
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Listen for option updates (e.g. changed poll interval)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    # Register the poll service once per domain (shared across all config entries)
    if not hass.services.has_service(DOMAIN, SERVICE_POLL):

        async def _handle_poll(call: ServiceCall) -> None:
            """Trigger an immediate BLE poll for one or all Oclean devices."""
            entry_id: str | None = call.data.get("entry_id")
            domain_data = hass.data.get(DOMAIN, {})
            if entry_id:
                coordinator = domain_data.get(entry_id)
                if coordinator and isinstance(coordinator, OcleanCoordinator):
                    await coordinator.async_request_refresh()
            else:
                for key, value in domain_data.items():
                    if not key.startswith("_") and isinstance(value, OcleanCoordinator):
                        await value.async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            SERVICE_POLL,
            _handle_poll,
            schema=vol.Schema({vol.Optional("entry_id"): str}),
        )

        async def _handle_get_zone_history(call: ServiceCall) -> dict[str, object]:
            """Return the stored per-session zone history for one device."""
            entry_id: str = call.data["entry_id"]
            coordinator = hass.data.get(DOMAIN, {}).get(entry_id)
            if not isinstance(coordinator, OcleanCoordinator):
                raise ServiceValidationError(f"No Oclean device for entry_id {entry_id!r}")
            sessions = coordinator.zone_history
            if start := call.data.get("start"):
                start_dt = dt_util.parse_datetime(str(start))
                if start_dt is not None:
                    start_ts = int(dt_util.as_timestamp(start_dt))
                    sessions = [s for s in sessions if s["ts"] >= start_ts]
            if end := call.data.get("end"):
                end_dt = dt_util.parse_datetime(str(end))
                if end_dt is not None:
                    end_ts = int(dt_util.as_timestamp(end_dt))
                    sessions = [s for s in sessions if s["ts"] <= end_ts]
            return {"sessions": list(reversed(sessions))}

        hass.services.async_register(
            DOMAIN,
            SERVICE_GET_ZONE_HISTORY,
            _handle_get_zone_history,
            schema=vol.Schema(
                {
                    vol.Required("entry_id"): str,
                    vol.Optional("start"): str,
                    vol.Optional("end"): str,
                }
            ),
            supports_response=SupportsResponse.ONLY,
        )

    # Initial poll: best-effort.  If the device is sleeping, entities stay
    # unavailable and will update as soon as the next poll succeeds (either on
    # the configured interval or via a manual service call).
    await coordinator.async_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Remove file handler and poll service only when no more entries remain
        remaining = [k for k in hass.data.get(DOMAIN, {}) if not k.startswith("_")]
        if not remaining:
            await _detach_file_handler(hass)
            hass.services.async_remove(DOMAIN, SERVICE_POLL)
            hass.services.async_remove(DOMAIN, SERVICE_GET_ZONE_HISTORY)
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update (e.g. poll interval change)."""
    await hass.config_entries.async_reload(entry.entry_id)
