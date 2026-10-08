import unittest

from pv_forecast_calibrator.supervisor import normalize_supervisor_data


class SupervisorTests(unittest.TestCase):
	def test_unwraps_supervisor_data(self):
		payload={"result":"ok","data":{"host":"core-mosquitto","port":1883,"username":"user"}}

		self.assertEqual(
			normalize_supervisor_data(payload),
			{"host":"core-mosquitto","port":1883,"username":"user"}
		)

	def test_accepts_direct_service_payload(self):
		payload={"host":"mqtt","port":1883}

		self.assertEqual(normalize_supervisor_data(payload),payload)

	def test_rejects_non_object_data(self):
		with self.assertRaises(ValueError):
			normalize_supervisor_data({"data":[]})


if __name__ == "__main__":
	unittest.main()
