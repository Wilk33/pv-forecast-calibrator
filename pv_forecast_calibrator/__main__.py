from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
import os
from pathlib import Path

import aiohttp

from . import __version__
from .config import AppConfig
from .ha import HomeAssistantClient
from .mqtt import MqttPublisher
from .runtime import ForecastRuntime
from .storage import JsonStateStore
from .supervisor import SupervisorClient


OPTIONS_PATH=Path("/data/options.json")
STATE_PATH=Path("/data/state.json")
LOGGER=logging.getLogger(__name__)


def load_options(path: Path=OPTIONS_PATH) -> dict:
	value=json.loads(path.read_text(encoding="utf-8"))
	if not isinstance(value,dict):
		raise ValueError("Options file root must be an object")
	return value


async def run():
	options=load_options()
	config=AppConfig.from_options(options)
	logging.basicConfig(
		level=getattr(logging,config.log_level,logging.INFO),
		format="%(asctime)s %(levelname)s %(name)s: %(message)s"
	)
	LOGGER.info("Uruchomienie PV Forecast Calibrator %s",__version__)
	LOGGER.info(
		"Konfiguracja: Forecast.Solar=%s, Solcast=%s, produkcja=%s, strefa=%s, próbka=%s-%s, zamknięcie=%s, kara_przeszacowania=%.3f, maks_korekta_w_dół=%.3f kWh, trening=%d, walidacja=%d, okno=%d",
		config.forecast_solar_entity,
		config.solcast_entity,
		config.production_entity,
		config.timezone.key,
		config.snapshot_time.isoformat(timespec="minutes"),
		config.snapshot_deadline.isoformat(timespec="minutes"),
		config.settlement_time.isoformat(timespec="minutes"),
		config.calibration.over_penalty,
		config.calibration.max_downward_correction_kwh,
		config.calibration.minimum_training_days,
		config.calibration.minimum_validation_days,
		config.calibration.validation_window_days
	)
	token=os.environ.get("SUPERVISOR_TOKEN","")
	if not token:
		raise RuntimeError("SUPERVISOR_TOKEN is missing")
	timeout=aiohttp.ClientTimeout(total=30)
	async with aiohttp.ClientSession(timeout=timeout) as session:
		ha=HomeAssistantClient(session,token)
		supervisor=SupervisorClient(session,token)
		service=await supervisor.mqtt_service()
		LOGGER.info(
			"Konfiguracja MQTT odebrana: host=%s, port=%s, TLS=%s, temat=%s, Discovery=%s",
			service.get("host","core-mosquitto"),
			service.get("port",1883),
			bool(service.get("ssl")),
			config.mqtt_base_topic,
			config.mqtt_discovery_prefix
		)
		publisher=MqttPublisher(service,config.mqtt_base_topic,config.mqtt_discovery_prefix,config.device_name)
		runtime=ForecastRuntime(config,JsonStateStore(STATE_PATH),ha)
		publisher.connect()
		try:
			publisher.publish_discovery()
			LOGGER.info("Opublikowano konfigurację MQTT Discovery")
			while True:
				now=datetime.now(config.timezone)
				await runtime.tick(now)
				payload=runtime.state_payload(now)
				LOGGER.debug("Pakiet MQTT: %s",payload)
				publisher.publish_state(payload)
				await asyncio.sleep(config.poll_interval_seconds)
		finally:
			LOGGER.info("Zamykanie aplikacji i połączenia MQTT")
			publisher.close()


def main():
	asyncio.run(run())


if __name__ == "__main__":
	main()
