"""Config flow for Weber iGrill integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_get_scanner,
)
from homeassistant.components.bluetooth.models import BluetoothScanningMode
from homeassistant.components.bluetooth.scanner import create_bleak_scanner
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import device_registry as dr

from .const import CONF_ENTRY_MANUAL, CONF_ENTRY_METHOD, CONF_ENTRY_SCAN, DOMAIN, WEBER_MAC_ID

from bleak import BleakClient, BleakError, BleakScanner
from bleak.backends.client import BaseBleakClient
from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection


_LOGGER = logging.getLogger(__name__)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Weber iGrill."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    @property
    def data_schema(self) -> vol.Schema:
        """Return the data schema for integration."""
        return vol.Schema({vol.Required(CONF_NAME): str, vol.Required(CONF_MAC): str})

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("Discovered bluetooth device: %s", discovery_info)
        await self.async_set_unique_id(dr.format_mac(discovery_info.address))
        self._abort_if_unique_id_configured()

        self.devices = [
            f"{discovery_info.address} ('Weber iGrill')"
        ]
        return await self.async_step_device()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""

        if user_input is None:
            schema = {
                vol.Required(CONF_ENTRY_METHOD): vol.In(
                    [CONF_ENTRY_SCAN, CONF_ENTRY_MANUAL]
                )
            }
            return self.async_show_form(step_id="user", data_schema=vol.Schema(schema))
        method = user_input[CONF_ENTRY_METHOD]
        _LOGGER.debug(f"Method selected: {method}")
        if method == CONF_ENTRY_SCAN:
            return await self.async_step_scan()
        else:
            self.devices = []
            return await self.async_step_device()

    async def async_step_scan(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the discovery by scanning."""
        errors = {}
        # if user_input is None:
        #     return self.async_show_form(step_id="scan")
        scanner = async_get_scanner(self.hass)
        _LOGGER.debug("Preparing for a scan")
        # first we check if scanner from HA bluetooth is enabled
        try:
            if len(scanner.discovered_devices) >= 1:
                # raises Attribute errors if bluetooth not configured
                _LOGGER.debug(f"Using HA scanner {scanner}")
        except AttributeError:
            scanner = create_bleak_scanner(BluetoothScanningMode.ACTIVE, None)
            _LOGGER.debug("Using bleak scanner through HA")
        try:
            _LOGGER.debug("Starting a scan for Weber iGrill devices")
            ble_devices = await discover_weber_igrills(scanner)
        except BleakError as err:
            _LOGGER.error(f"Bluetooth connection error while trying to scan: {err}")
            errors["base"] = "BleakError"
            return self.async_show_form(step_id="scan", errors=errors)

        if not ble_devices:
            return self.async_abort(reason="no_devices_found")
        self.devices = [
            f"{dev['ble_device'].address} ({dev['model']})" for dev in ble_devices
        ]

        return await self.async_step_device()

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle setting up a device."""
        if not user_input:
            schema_mac = str
            if self.devices:
                schema_mac = vol.In(self.devices)
            schema = vol.Schema(
                {vol.Required(CONF_NAME): str, vol.Required(CONF_MAC): schema_mac}
            )
            return self.async_show_form(step_id="device", data_schema=schema)

        user_input[CONF_MAC] = user_input[CONF_MAC][:17 ]
        unique_id = dr.format_mac(user_input[CONF_MAC])
        _LOGGER.debug(f"Weber iGrill UniqueID: {unique_id}")

        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

async def discover_weber_igrills(
    scanner: type[BleakScanner] | None = None,
) -> list[dict[str, Any]]:
    """Scanning feature
    Scan the BLE neighborhood for a Weber iGrill
    This method requires the script to be launched as root
    Returns the list of nearby iGrills
    """
    device_list = []
    scanner = scanner if scanner is not None else BleakScanner

    devices = await scanner.discover()
    for d in devices:
        model = "iGrill" #FIXME don't hardcode this here, extract it somehow instead
        if (d.address[0:8] == WEBER_MAC_ID): #This is the manufacturer MAC for Weber
          device_list.append({"ble_device": d, "model": model})
          _LOGGER.info(f"found {model} with mac: {d.address}, details:{d.details}")
    return device_list
