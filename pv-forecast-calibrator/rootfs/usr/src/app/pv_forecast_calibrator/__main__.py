from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
import os
from pathlib import Path

import aiohttp

from .config import AppConfig
from .ha import HomeAssistantClient
from .mqtt import MqttPublisher
from .runtime import ForecastRuntime
from .storage import JsonStateStore
from .supervisor import SupervisorClient


OPTIONS_PATH=Path("/data/options.json")
STATE_PATH=Path("/data/state.json")


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
	token=os.environ.get("SUPERVISOR_TOKEN","")
	if not token:
		raise RuntimeError("SUPERVISOR_TOKEN is missing")
	timeout=aiohttp.ClientTimeout(total=30)
	async with aiohttp.ClientSession(timeout=timeout) as session:
		ha=HomeAssistantClient(session,token)
		supervisor=SupervisorClient(session,token)
		service=await supervisor.mqtt_service()
		publisher=MqttPublisher(service,config.mqtt_base_topic,config.mqtt_discovery_prefix,config.device_name)
		runtime=ForecastRuntime(config,JsonStateStore(STATE_PATH),ha)
		publisher.connect()
		try:
			publisher.publish_discovery()
			while True:
				now=datetime.now(config.timezone)
				await runtime.tick(now)
				publisher.publish_state(runtime.state_payload(now))
				await asyncio.sleep(config.poll_interval_seconds)
		finally:
			publisher.close()


def main():
	asyncio.run(run())


if __name__ == "__main__":
	main()
