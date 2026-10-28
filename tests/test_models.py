import math
import unittest

from pv_forecast_calibrator.models import DailyRecord, ForecastDataError, ForecastSet


class ForecastSetTests(unittest.TestCase):
	def test_reads_solcast_attributes_and_calculates_three_averages(self):
		forecasts=ForecastSet.from_states(
			"15.987",
			{
				"state":"16.1263",
				"attributes":{
					"estimate":16.1263,
					"estimate10":6.674,
					"estimate90":29.2363
				}
			}
		)

		self.assertAlmostEqual(forecasts.fpv,15.987)
		self.assertAlmostEqual(forecasts.spv,16.1263)
		self.assertAlmostEqual(forecasts.spv_l,6.674)
		self.assertAlmostEqual(forecasts.spv_h,29.2363)
		self.assertAlmostEqual(forecasts.spv_div_l,11.40015)
		self.assertAlmostEqual(forecasts.spv_l_div_h,17.95515)
		self.assertAlmostEqual(forecasts.spv_div_h,22.6813)

	def test_invalid_fpv_is_optional(self):
		forecasts=ForecastSet.from_states(
			"unavailable",
			{"state":"20","attributes":{"estimate":20,"estimate10":10,"estimate90":30}}
		)

		self.assertIsNone(forecasts.fpv)
		self.assertEqual(forecasts.spv,20)

	def test_missing_solcast_bound_rejects_sample(self):
		with self.assertRaises(ForecastDataError):
			ForecastSet.from_states(
				"15",
				{"state":"20","attributes":{"estimate":20,"estimate90":30}}
			)

	def test_negative_or_non_finite_solcast_value_rejects_sample(self):
		for invalid in (-1,float("nan"),float("inf"),"unknown"):
			with self.subTest(invalid=invalid):
				with self.assertRaises(ForecastDataError):
					ForecastSet.from_states(
						"15",
						{"state":"20","attributes":{"estimate":invalid,"estimate10":10,"estimate90":30}}
					)

	def test_daily_record_round_trip_preserves_forecasts_and_actual(self):
		forecasts=ForecastSet.from_states(
			"15",
			{"state":"20","attributes":{"estimate":20,"estimate10":10,"estimate90":30}}
		)
		record=DailyRecord(
			date="2026-10-08",
			captured_at="2026-10-08T04:20:00+02:00",
			forecasts=forecasts,
			published_forecast_kwh=19,
			correction_kwh=-1,
			mode="calibrated_ensemble",
			actual_kwh=18.5,
			weighted_forecast_kwh=18.75,
			model_weights={"fpv":0.6,"spv":0.4}
		)

		loaded=DailyRecord.from_dict(record.to_dict())

		self.assertEqual(loaded,record)
		self.assertTrue(math.isfinite(loaded.actual_kwh))


if __name__ == "__main__":
	unittest.main()
