from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any

from . import __version__


LOGGER=logging.getLogger(__name__)


@dataclass(frozen=True)
class SensorDefinition:
	name: str
	unit: str | None=None
	device_class: str | None=None
	state_class: str | None=None
	options: list[str] | None=None


@dataclass(frozen=True)
class DiscoveryMessage:
	key: str
	topic: str
	payload: dict[str,Any]


SENSORS={
	"forecast_today_kwh":SensorDefinition("Skorygowana prognoza PV na dzisiaj","kWh","energy","measurement"),
	"weighted_forecast_today_kwh":SensorDefinition("Prognoza ważona PV przed korektą","kWh","energy","measurement"),
	"correction_today_kwh":SensorDefinition("Zastosowana korekta prognozy PV","kWh","energy","measurement"),
	"weight_fpv_percent":SensorDefinition("Waga FPV","%",None,"measurement"),
	"weight_spv_percent":SensorDefinition("Waga SPV","%",None,"measurement"),
	"weight_spv_l_percent":SensorDefinition("Waga SPV L","%",None,"measurement"),
	"weight_spv_h_percent":SensorDefinition("Waga SPV H","%",None,"measurement"),
	"weight_spv_div_l_percent":SensorDefinition("Waga SPV/L","%",None,"measurement"),
	"weight_spv_l_div_h_percent":SensorDefinition("Waga SPV L/H","%",None,"measurement"),
	"weight_spv_div_h_percent":SensorDefinition("Waga SPV/H","%",None,"measurement"),
	"previous_production_kwh":SensorDefinition("Produkcja PV poprzedniego dnia","kWh","energy","measurement"),
	"previous_error_kwh":SensorDefinition("Błąd prognozy PV poprzedniego dnia","kWh","energy","measurement"),
	"mae_7d_kwh":SensorDefinition("MAE prognozy PV 7 dni","kWh","energy","measurement"),
	"mae_30d_kwh":SensorDefinition("MAE prognozy PV 30 dni","kWh","energy","measurement"),
	"valid_days":SensorDefinition("Kompletne dni modelu",None,None,"measurement"),
	"model_status":SensorDefinition(
		"Stan modelu prognozy PV",
		device_class="enum",
		options=["learning","calibrated_spv","calibrated_ensemble","fallback_spv","missing_snapshot","source_error"]
	),
	"last_update":SensorDefinition("Ostatnia aktualizacja prognozy PV",device_class="timestamp")
}


def discovery_messages(prefix: str,base_topic: str,device_name: str) -> list[DiscoveryMessage]:
	device={
		"identifiers":["pv_forecast_calibrator"],
		"name":device_name,
		"manufacturer":"PV Forecast Calibrator",
		"model":"Local PV forecast calibration",
		"sw_version":__version__
	}
	messages=[]
	for key,definition in SENSORS.items():
		payload={
			"name":definition.name,
			"unique_id":f"pv_forecast_calibrator_{key}",
			"object_id":f"pv_forecast_calibrator_{key}",
			"state_topic":f"{base_topic}/state",
			"value_template":"{{ value_json."+key+" }}",
			"availability_topic":f"{base_topic}/availability",
			"payload_available":"online",
			"payload_not_available":"offline",
			"device":device
		}
		if definition.unit:
			payload["unit_of_measurement"]=definition.unit
		if definition.device_class:
			payload["device_class"]=definition.device_class
		if definition.state_class:
			payload["state_class"]=definition.state_class
		if definition.options:
			payload["options"]=definition.options
		messages.append(
			DiscoveryMessage(
				key=key,
				topic=f"{prefix}/sensor/pv_forecast_calibrator/{key}/config",
				payload=payload
			)
		)
	return messages


class MqttPublisher:
	def __init__(self,service: dict[str,Any],base_topic: str,discovery_prefix: str,device_name: str):
		self.service=service
		self.base_topic=base_topic
		self.discovery_prefix=discovery_prefix
		self.device_name=device_name
		self.client=None

	def connect(self):
		import paho.mqtt.client as mqtt
		self.client=mqtt.Client(
			mqtt.CallbackAPIVersion.VERSION2,
			client_id="pv-forecast-calibrator",
			protocol=mqtt.MQTTv311
		)
		username=self.service.get("username")
		if username:
			self.client.username_pw_set(username,self.service.get("password"))
		if self.service.get("ssl"):
			self.client.tls_set()
		self.client.will_set(f"{self.base_topic}/availability","offline",qos=1,retain=True)
		self.client.connect_async(
			str(self.service.get("host","core-mosquitto")),
			int(self.service.get("port",1883)),
			60
		)
		self.client.loop_start()
		LOGGER.info(
			"Rozpoczęto połączenie MQTT: host=%s, port=%s, TLS=%s",
			self.service.get("host","core-mosquitto"),
			self.service.get("port",1883),
			bool(self.service.get("ssl"))
		)

	def publish_discovery(self):
		self._require_client()
		messages=discovery_messages(self.discovery_prefix,self.base_topic,self.device_name)
		for message in messages:
			self.client.publish(message.topic,json.dumps(message.payload,ensure_ascii=False),qos=1,retain=True)
		LOGGER.info("Wysłano %d komunikatów MQTT Discovery",len(messages))

	def publish_state(self,payload: dict[str,Any]):
		self._require_client()
		self.client.publish(f"{self.base_topic}/availability","online",qos=1,retain=True)
		self.client.publish(
			f"{self.base_topic}/state",
			json.dumps(payload,ensure_ascii=False,allow_nan=False),
			qos=1,
			retain=True
		)
		LOGGER.debug("Wysłano stan MQTT na %s/state",self.base_topic)

	def close(self):
		if self.client is None:
			return
		self.client.publish(f"{self.base_topic}/availability","offline",qos=1,retain=True)
		self.client.disconnect()
		self.client.loop_stop()
		LOGGER.info("Zamknięto połączenie MQTT")

	def _require_client(self):
		if self.client is None:
			raise RuntimeError("MQTT publisher is not connected")
