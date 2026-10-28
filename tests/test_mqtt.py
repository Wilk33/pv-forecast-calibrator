import unittest

from pv_forecast_calibrator.mqtt import MqttPublisher,SENSORS,discovery_messages


class FakeClient:
	def __init__(self):
		self.messages=[]

	def publish(self,topic,payload,qos,retain):
		self.messages.append((topic,payload,qos,retain))


class MqttDiscoveryTests(unittest.TestCase):
	def test_exposes_final_weighted_forecast_and_seven_model_weights(self):
		self.assertEqual(
			set(SENSORS),
			{
				"forecast_today_kwh",
				"weighted_forecast_today_kwh",
				"correction_today_kwh",
				"weight_fpv_percent",
				"weight_spv_percent",
				"weight_spv_l_percent",
				"weight_spv_h_percent",
				"weight_spv_div_l_percent",
				"weight_spv_l_div_h_percent",
				"weight_spv_div_h_percent",
				"previous_production_kwh",
				"previous_error_kwh",
				"mae_7d_kwh",
				"mae_30d_kwh",
				"valid_days",
				"model_status",
				"last_update"
			}
		)

	def test_discovery_has_units_availability_and_stable_ids(self):
		messages=discovery_messages("homeassistant","pv_forecast_calibrator","PV Forecast Calibrator")

		self.assertEqual(len(messages),17)
		by_key={message.key:message for message in messages}
		forecast=by_key["forecast_today_kwh"].payload
		self.assertEqual(forecast["unit_of_measurement"],"kWh")
		self.assertEqual(forecast["device_class"],"energy")
		self.assertEqual(forecast["state_class"],"measurement")
		self.assertEqual(forecast["unique_id"],"pv_forecast_calibrator_forecast_today_kwh")
		self.assertEqual(forecast["availability_topic"],"pv_forecast_calibrator/availability")

	def test_model_status_is_enum_with_all_runtime_states(self):
		messages=discovery_messages("homeassistant","pv_forecast_calibrator","PV Forecast Calibrator")
		status=next(message.payload for message in messages if message.key == "model_status")

		self.assertEqual(
			status["options"],
			["learning","calibrated_spv","calibrated_ensemble","fallback_spv","missing_snapshot","source_error"]
		)

	def test_source_forecast_values_are_not_duplicated(self):
		self.assertNotIn("raw_fpv_kwh",SENSORS)
		self.assertNotIn("raw_spv_kwh",SENSORS)
		self.assertNotIn("raw_spv_l_kwh",SENSORS)
		self.assertNotIn("raw_spv_h_kwh",SENSORS)

	def test_publishes_discovery_and_state_as_retained_messages(self):
		publisher=MqttPublisher({},"pv_forecast_calibrator","homeassistant","PV Forecast Calibrator")
		publisher.client=FakeClient()

		publisher.publish_discovery()
		publisher.publish_state({"forecast_today_kwh":20})

		self.assertTrue(all(message[3] for message in publisher.client.messages))
		self.assertIn(("pv_forecast_calibrator/availability","online",1,True),publisher.client.messages)


if __name__ == "__main__":
	unittest.main()
