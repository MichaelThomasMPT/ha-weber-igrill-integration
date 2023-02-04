"""Parser for Weber iGrill BLE advertisements.

MIT License applies.
"""
from __future__ import annotations

import dataclasses
from collections import namedtuple
from logging import Logger

from bleak import BleakClient, BleakError, BLEDevice
from bleak_retry_connector import establish_connection
from bluetooth_sensor_state_data import BluetoothData
from sensor_state_data.enum import StrEnum

from .const import (APP_CHALLENGE_UUID, BATTERY_LEVEL_UUID,
                    DEVICE_CHALLENGE_UUID, DEVICE_RESPONSE_UUID)

Characteristic = namedtuple("Characteristic", ["uuid", "name", "format"])

sensors_characteristics_uuid = [
    BATTERY_LEVEL_UUID
]
sensors_characteristics_uuid_str = [
    str(x).upper() for x in sensors_characteristics_uuid]


class WeberIgrillSensor(StrEnum):
    BATTERY_PERCENT = "battery_percent"


@dataclasses.dataclass
class IGrillDevice:
    """Response data with information about the iGrill device"""

    hw_version: str = ""
    sw_version: str = ""
    name: str = ""
    identifier: str = ""
    address: str = ""
    sensors: dict[str, str | float | None] = dataclasses.field(
        default_factory=lambda: {}
    )


class IGRILLBluetoothDeviceData(BluetoothData):
    """Data for Weber iGrill sensors."""

    def __init__(
        self,
        logger: Logger
    ):
        super().__init__()
        self.logger = logger

    async def _get_device_characteristics(
        self, client: BleakClient, device: IGrillDevice
    ) -> IGrillDevice:
        device.address = client.address
        # TODO add more device characteristics in here
        return device

    async def _get_service_characteristics(
        self, client: BleakClient, device: IGrillDevice
    ) -> IGrillDevice:
        svcs = await client.get_services()
        for service in svcs:
            for characteristic in service.characteristics:
                if characteristic.uuid.upper() in sensors_characteristics_uuid_str:
                    # FIXME remove this
                    self.logger.warning(
                        "Checking characteristic: " + str(characteristic.uuid))
                    try:
                        data = await client.read_gatt_char(characteristic.uuid)
                    except BleakError as err:
                        self.logger.warning(
                            "Get service characteristics exception: %s", err
                        )  # FIXME remove this
                        self.logger.debug(
                            "Get service characteristics exception: %s", err
                        )
                        continue
                    data = await client.read_gatt_char(characteristic.uuid)
                    self.logger.warning(
                        "Read characteristic: " + str(data)
                    )  # FIXME remove this

                    if characteristic.uuid.upper() == BATTERY_LEVEL_UUID.upper():
                        self.logger.warning(
                            "Found battery characteristic!"
                        )  # FIXME remove this
                        device.sensors[WeberIgrillSensor.BATTERY_PERCENT] = float(
                            data)
        return device

    async def update_device(self, ble_device: BLEDevice) -> IGrillDevice:
        """Connects to the device through BLE and retrieves relevant data"""
        device = IGrillDevice()
        client = await establish_connection(BleakClient, ble_device, ble_device.address)
        client = await self._authenticate_igrill(client)

        try:
            device = await self._get_device_characteristics(client, device)
            device = await self._get_service_characteristics(client, device)
        finally:
            await client.disconnect()

        return device

    async def _authenticate_igrill(self, client: BleakClient) -> BleakClient:
        """
        Performs iDevices challenge/response handshake. Returns if handshake succeeded
        Works for all devices using this handshake, no key required
        (copied from https://github.com/kins-dev/igrill-smoker and 
        https://github.com/bendikwa/igrill/blob/master/igrill.py - thanks!)
        """
        self.logger.warning("Pairing...")  # FIXME make debug
        try:
            paired = await client.pair(protection_level=1)
            # FIXME make debug
            self.logger.warning(f"Successfully paired: {paired}.")
        except Exception as err:
            self.logger.error(f"Error when paring bluetooth device: {err}")

        self.logger.warning("Authenticating...")  # FIXME make debug

        # send app challenge (16 bytes) (must be wrapped in a bytearray)
        challenge = bytes(b'\0' * 16)
        self.logger.warning("Sending key of all 0's")  # FIXME make debug
        await client.write_gatt_char(APP_CHALLENGE_UUID, challenge, True)

        # Now send the device challenge ID back
        encrypted_device_challenge = await client.read_gatt_char(
            DEVICE_CHALLENGE_UUID)  # FIXME add try-catch block
        await client.write_gatt_char(DEVICE_RESPONSE_UUID,
                                     encrypted_device_challenge, True)

        self.logger.warning("Authenticated")  # FIXME make debug

        return client
