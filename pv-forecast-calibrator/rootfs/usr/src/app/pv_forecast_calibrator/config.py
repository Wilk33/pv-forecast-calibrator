from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError

from .calibration import CalibrationConfig


class ConfigurationError(ValueError):
	pass


def _entity(options: dict[str,Any],key: str) -> str:
	value=str(options.get(key,"")).strip()
	if not value.startswith("sensor.") or len(value) <= len("sensor."):
		raise ConfigurationError(f"Option {key} must contain a sensor entity id")
	return value


def _time(options: dict[str,Any],key: str,default: str) -> time:
	try:
		value=time.fromisoformat(str(options.get(key,default)))
	except ValueError as error:
		raise ConfigurationError(f"Option {key} must use HH:MM") from error
	if value.second or value.microsecond:
		raise ConfigurationError(f"Option {key} must use minute precision")
	return value


def _float(options: dict[str,Any],key: str,default: float) -> float:
	try:
		return float(options.get(key,default))
	except (TypeError,ValueError) as error:
		raise ConfigurationError(f"Option {key} must be a number") from error


def _int(options: dict[str,Any],key: str,default: int) -> int:
	try:
		return int(options.get(key,default))
	except (TypeError,ValueError) as error:
		raise ConfigurationError(f"Option {key} must be an integer") from error


@dataclass(frozen=True)
class AppConfig:
	forecast_solar_entity: str
	solcast_entity: str
	production_entity: str
	timezone: ZoneInfo
	snapshot_time: time
	snapshot_deadline: time
	settlement_time: time
	calibration: CalibrationConfig
	history_limit_days: int
	poll_interval_seconds: int
	mqtt_base_topic: str
	mqtt_discovery_prefix: str
	device_name: str
	log_level: str

	@classmethod
	def from_options(cls,options: dict[str,Any]) -> "AppConfig":
		try:
			timezone=ZoneInfo(str(options.get("timezone","Europe/Warsaw")))
		except ZoneInfoNotFoundError as error:
			raise ConfigurationError("Option timezone is not available") from error
		snapshot_time=_time(options,"snapshot_time","04:20")
		snapshot_deadline=_time(options,"snapshot_deadline","04:45")
		settlement_time=_time(options,"settlement_time","23:00")
		if snapshot_deadline < snapshot_time:
			raise ConfigurationError("snapshot_deadline must not be before snapshot_time")
		if settlement_time <= snapshot_deadline:
			raise ConfigurationError("settlement_time must be after snapshot_deadline")
		over_penalty=_float(options,"overprediction_penalty",2.0)
		max_correction=_float(options,"max_downward_correction_kwh",1.0)
		decay=_float(options,"decay",0.93)
		training=_int(options,"minimum_training_days",5)
		validation=_int(options,"minimum_validation_days",3)
		validation_window=_int(options,"validation_window_days",30)
		history_limit=_int(options,"history_limit_days",370)
		poll_interval=_int(options,"poll_interval_seconds",60)
		if over_penalty < 1:
			raise ConfigurationError("overprediction_penalty must be at least 1")
		if max_correction < 0:
			raise ConfigurationError("max_downward_correction_kwh must not be negative")
		if not 0 < decay <= 1:
			raise ConfigurationError("decay must be greater than 0 and at most 1")
		if training < 1:
			raise ConfigurationError("minimum_training_days must be positive")
		if validation < 1:
			raise ConfigurationError("minimum_validation_days must be positive")
		if validation_window < validation:
			raise ConfigurationError("validation_window_days must cover minimum_validation_days")
		if history_limit < training+validation:
			raise ConfigurationError("history_limit_days is too small for training and validation")
		if not 10 <= poll_interval <= 3600:
			raise ConfigurationError("poll_interval_seconds must be between 10 and 3600")
		return cls(
			forecast_solar_entity=_entity(options,"forecast_solar_entity"),
			solcast_entity=_entity(options,"solcast_entity"),
			production_entity=_entity(options,"production_entity"),
			timezone=timezone,
			snapshot_time=snapshot_time,
			snapshot_deadline=snapshot_deadline,
			settlement_time=settlement_time,
			calibration=CalibrationConfig(over_penalty,max_correction,decay,training,validation,validation_window),
			history_limit_days=history_limit,
			poll_interval_seconds=poll_interval,
			mqtt_base_topic=str(options.get("mqtt_base_topic","pv_forecast_calibrator")).strip(" /"),
			mqtt_discovery_prefix=str(options.get("mqtt_discovery_prefix","homeassistant")).strip(" /"),
			device_name=str(options.get("device_name","PV Forecast Calibrator")).strip() or "PV Forecast Calibrator",
			log_level=str(options.get("log_level","INFO")).upper()
		)
