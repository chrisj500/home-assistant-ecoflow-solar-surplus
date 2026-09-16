from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "ecoflow_solar_surplus"
NAME = "EcoFlow Solar Surplus Controller"
VERSION = "0.1.8"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

CONF_SITE_GRID_POWER = "site_grid_power"
CONF_SOLAR_POWER = "solar_power"
CONF_SHP_GRID_POWER = "shp_grid_power"
CONF_SHP_HOME_POWER = "shp_home_power"
CONF_CHARGING_POWER = "charging_power"
CONF_CHARGE_LIMIT = "charge_limit"
CONF_AC1_SOC = "ac1_soc"
CONF_AC2_SOC = "ac2_soc"
CONF_AC3_SOC = "ac3_soc"
CONF_AC1_CHANNEL = "ac1_channel"
CONF_AC2_CHANNEL = "ac2_channel"
CONF_AC3_CHANNEL = "ac3_channel"
CONF_AC1_FORCE = "ac1_force"
CONF_AC2_FORCE = "ac2_force"
CONF_AC3_FORCE = "ac3_force"

# Native Envoy realtime MQTT support. The upstream Envoy bridge publishes
# /ivp/meters/readings payloads to this topic. Realtime telemetry is optional;
# the configured Home Assistant site-grid and solar entities remain fallbacks.
DEFAULT_ENVOY_MQTT_TOPIC = "/envoy/json"
ENVOY_REALTIME_MAX_AGE_SECONDS = 5.0
GRID_COALESCE_SECONDS = 1.0

OPT_OPERATING_MODE = "operating_mode"
MODE_OBSERVE = "observe"
MODE_CONTROL = "control"

OPT_MINIMUM_RATE_W = "minimum_rate_w"
OPT_MAXIMUM_RATE_W = "maximum_rate_w"
OPT_RATE_STEP_W = "rate_step_w"
OPT_MAXIMUM_RATE_INCREASE_W = "maximum_rate_increase_w"
OPT_SLOW_IMPORT_DECREASE_W = "slow_import_decrease_w"
OPT_MODERATE_IMPORT_DECREASE_W = "moderate_import_decrease_w"
OPT_PREFERRED_IMPORT_W = "preferred_import_w"
OPT_IMPORT_HOLD_HIGH_W = "import_hold_high_w"
OPT_MODERATE_IMPORT_THRESHOLD_W = "moderate_import_threshold_w"
OPT_SEVERE_IMPORT_THRESHOLD_W = "severe_import_threshold_w"
OPT_START_EXPORT_W = "start_export_w"
OPT_EXPORT_GAIN = "export_gain"
OPT_IMPORT_GAIN = "import_gain"
OPT_MINIMUM_SOLAR_W = "minimum_solar_w"
OPT_METER_MAX_AGE_SECONDS = "meter_max_age_seconds"
OPT_PHYSICAL_METER_MAX_AGE_SECONDS = "physical_meter_max_age_seconds"
OPT_STOP_ALL_W = "stop_all_w"
OPT_START_2_W = "start_2_w"
OPT_STOP_2_W = "stop_2_w"
OPT_START_3_W = "start_3_w"
OPT_STOP_3_W = "stop_3_w"
OPT_PHYSICAL_RECOVERY_SECONDS = "physical_recovery_seconds"

DEFAULT_OPTIONS: dict[str, float | int | str] = {
    OPT_OPERATING_MODE: MODE_OBSERVE,
    OPT_MINIMUM_RATE_W: 500,
    OPT_MAXIMUM_RATE_W: 3900,
    OPT_RATE_STEP_W: 100,
    OPT_MAXIMUM_RATE_INCREASE_W: 800,
    OPT_SLOW_IMPORT_DECREASE_W: 200,
    OPT_MODERATE_IMPORT_DECREASE_W: 500,
    OPT_PREFERRED_IMPORT_W: 250,
    OPT_IMPORT_HOLD_HIGH_W: 350,
    OPT_MODERATE_IMPORT_THRESHOLD_W: 1000,
    OPT_SEVERE_IMPORT_THRESHOLD_W: 2000,
    OPT_START_EXPORT_W: 150,
    OPT_EXPORT_GAIN: 1.0,
    OPT_IMPORT_GAIN: 0.8,
    OPT_MINIMUM_SOLAR_W: 150,
    OPT_METER_MAX_AGE_SECONDS: 180,
    OPT_PHYSICAL_METER_MAX_AGE_SECONDS: 300,
    OPT_STOP_ALL_W: 250,
    OPT_START_2_W: 1800,
    OPT_STOP_2_W: 1100,
    OPT_START_3_W: 3300,
    OPT_STOP_3_W: 2400,
    OPT_PHYSICAL_RECOVERY_SECONDS: 120,
}

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}.command_state"
OBSERVABILITY_STORAGE_VERSION = 1
OBSERVABILITY_STORAGE_KEY_PREFIX = f"{DOMAIN}.observability"
SIGNAL_UPDATE = f"{DOMAIN}_update_{{}}"
