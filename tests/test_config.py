import unittest

from pv_forecast_calibrator.config import AppConfig, ConfigurationError


def valid_options():
	return {
		"forecast_solar_entity":"sensor.energy_production_today",
		"solcast_entity":"sensor.solcast_pv_forecast_prognoza_na_dzisiaj",
		"production_entity":"sensor.deye_deye_10kw_pv_production_today"
	}


class AppConfigTests(unittest.TestCase):
	def test_defaults_match_approved_model(self):
		config=AppConfig.from_options(valid_options())

		self.assertEqual(config.timezone.key,"Europe/Warsaw")
		self.assertEqual(config.snapshot_time.isoformat(timespec="minutes"),"04:20")
		self.assertEqual(config.snapshot_deadline.isoformat(timespec="minutes"),"04:45")
		self.assertEqual(config.settlement_time.isoformat(timespec="minutes"),"23:00")
		self.assertEqual(config.calibration.over_penalty,2)
		self.assertEqual(config.calibration.max_downward_correction_kwh,1)
		self.assertEqual(config.calibration.max_upward_correction_kwh,1)
		self.assertFalse(config.reset_history_on_start)

	def test_rejects_non_sensor_entity(self):
		options=valid_options()
		options["solcast_entity"]="weather.home"

		with self.assertRaises(ConfigurationError):
			AppConfig.from_options(options)

	def test_rejects_deadline_before_snapshot(self):
		options=valid_options()
		options["snapshot_time"]="05:00"
		options["snapshot_deadline"]="04:45"

		with self.assertRaises(ConfigurationError):
			AppConfig.from_options(options)

	def test_rejects_invalid_numeric_ranges(self):
		for key,value in (
			("overprediction_penalty",0.9),
			("overprediction_penalty","nan"),
			("max_downward_correction_kwh",-1),
			("max_upward_correction_kwh",-1),
			("reset_history_on_start","true"),
			("decay",1.1),
			("minimum_training_days",0),
			("minimum_validation_days",0),
			("history_limit_days",4)
		):
			with self.subTest(key=key):
				options=valid_options()
				options[key]=value
				with self.assertRaises(ConfigurationError):
					AppConfig.from_options(options)


if __name__ == "__main__":
	unittest.main()
