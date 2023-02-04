"""Platform for sensor integration."""
from __future__ import annotations

import logging

from homeassistant import config_entries
from homeassistant.components.sensor import (SensorDeviceClass, SensorEntity,
                                             SensorEntityDescription,
                                             SensorStateClass)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import (CoordinatorEntity,
                                                      DataUpdateCoordinator)

from .const import DOMAIN
from .igrill_parser import IGrillDevice, WeberIgrillSensor

_LOGGER = logging.getLogger(__name__)

SENSORS_MAPPING_TEMPLATE: dict[str, SensorEntityDescription] = {
    WeberIgrillSensor.BATTERY_PERCENT: SensorEntityDescription(
        key=WeberIgrillSensor.BATTERY_PERCENT,
        name="Battery Percentage",
        device_class=SensorDeviceClass.BATTERY,
    )
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iGrill BLE sensors."""
    coordinator: DataUpdateCoordinator[IGrillDevice] = hass.data[DOMAIN][
        entry.entry_id
    ]

    sensors_mapping = SENSORS_MAPPING_TEMPLATE.copy()
    entities = []
    # FIXME remove this
    _LOGGER.warning("got sensors: %s", coordinator.data.sensors)
    _LOGGER.debug("got sensors: %s", coordinator.data.sensors)
    for sensor_type, sensor_value in coordinator.data.sensors.items():
        if sensor_type not in sensors_mapping:
            _LOGGER.warning(
                "Unknown sensor type detected: %s, %s",
                sensor_type,
                sensor_value,
            )  # FIXME should be debug, not warning
            continue
        entities.append(
            IGrillSensor(coordinator, coordinator.data,
                         sensors_mapping[sensor_type])
        )

    async_add_entities(entities)


class IGrillSensor(
    CoordinatorEntity[DataUpdateCoordinator[IGrillDevice]], SensorEntity
):
    """iGrill BLE sensors for the device."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator[IGrillDevice],
        igrill_device: IGrillDevice,
        entity_description: SensorEntityDescription,
    ) -> None:
        """Populate the iGrill entity with relevant data."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        # name = f"{igrill_device.name} {igrill_device.identifier}"
        name = "test name"

        # self._attr_unique_id = f"{name}_{entity_description.key}"
        self._attr_unique_id = "test_ID_123"

        self._id = igrill_device.address
        self._attr_device_info = DeviceInfo(
            connections={
                (
                    CONNECTION_BLUETOOTH,
                    igrill_device.address,
                )
            },
            name=name,
            manufacturer="Weber",
            hw_version=igrill_device.hw_version,
            sw_version=igrill_device.sw_version,
        )

    @property
    def native_value(self) -> StateType:
        """Return the value reported by the sensor."""
        return self.coordinator.data.sensors[self.entity_description.key]
