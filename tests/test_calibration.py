import json
from pathlib import Path
import unittest

from pv_forecast_calibrator.calibration import (
	CalibrationConfig,
	MetricSummary,
	asymmetric_loss,
	calculate_model_weights,
	decide_forecast,
	passes_gate,
	walk_forward
)
from pv_forecast_calibrator.models import DailyRecord, ForecastSet


FIXTURE=Path(__file__).parent/"fixtures"/"local_history.json"


def record(item):
	forecasts=ForecastSet(
		fpv=item["fpv"],
		spv=item["spv"],
		spv_l=item["spv_l"],
		spv_h=item["spv_h"],
		spv_div_l=(item["spv"]+item["spv_l"])/2,
		spv_l_div_h=(item["spv_l"]+item["spv_h"])/2,
		spv_div_h=(item["spv"]+item["spv_h"])/2
	)
	return DailyRecord(
		date=item["date"],
		captured_at=item["date"]+"T04:20:00+02:00",
		forecasts=forecasts,
		published_forecast_kwh=item["spv"],
		correction_kwh=0,
		mode="learning",
		actual_kwh=item["actual"],
		actual_verified=True
	)


def forecasts(fpv,spv,spv_l,spv_h):
	return ForecastSet(
		fpv=fpv,
		spv=spv,
		spv_l=spv_l,
		spv_h=spv_h,
		spv_div_l=(spv+spv_l)/2,
		spv_l_div_h=(spv_l+spv_h)/2,
		spv_div_h=(spv+spv_h)/2
	)


class CalibrationTests(unittest.TestCase):
	def setUp(self):
		items=json.loads(FIXTURE.read_text(encoding="utf-8"))
		self.history=[record(item) for item in items]
		self.config=CalibrationConfig(
			over_penalty=2,
			max_downward_correction_kwh=1,
			max_upward_correction_kwh=1,
			decay=0.93,
			minimum_training_days=5,
			minimum_validation_days=3,
			validation_window_days=30
		)

	def test_overprediction_costs_twice_the_same_underprediction(self):
		self.assertEqual(asymmetric_loss(actual=10,prediction=12,over_penalty=2),4)
		self.assertEqual(asymmetric_loss(actual=10,prediction=8,over_penalty=2),2)

	def test_local_history_activates_correction_clamped_to_minus_one(self):
		decision=decide_forecast(self.history,forecasts(28,30,18,38),self.config)

		self.assertEqual(decision.mode,"calibrated_spv")
		self.assertAlmostEqual(decision.correction_kwh,-1)
		self.assertAlmostEqual(decision.forecast_kwh,29)
		self.assertLess(decision.corrected_metrics.asymmetric_loss,decision.raw_metrics.asymmetric_loss)
		self.assertLessEqual(decision.corrected_metrics.mae,decision.raw_metrics.mae)
		self.assertIn("MAE",decision.reason)
		self.assertIn("koszt",decision.reason)

	def test_too_little_validation_uses_raw_spv(self):
		decision=decide_forecast(self.history[:7],forecasts(28,30,18,38),self.config)

		self.assertEqual(decision.mode,"learning")
		self.assertEqual(decision.correction_kwh,0)
		self.assertEqual(decision.forecast_kwh,30)
		self.assertEqual(decision.completed_days,7)
		self.assertEqual(decision.validation_samples,2)
		self.assertEqual(decision.required_validation_samples,3)
		self.assertIn("brakuje 1",decision.reason)

	def test_unverified_actual_is_excluded_from_learning(self):
		item=self.history[0]
		unverified=DailyRecord(
			date=item.date,
			captured_at=item.captured_at,
			forecasts=item.forecasts,
			published_forecast_kwh=item.published_forecast_kwh,
			correction_kwh=item.correction_kwh,
			mode=item.mode,
			actual_kwh=item.actual_kwh,
			actual_verified=False
		)

		decision=decide_forecast([unverified]+self.history[1:8],forecasts(28,30,18,38),self.config)

		self.assertEqual(decision.mode,"learning")
		self.assertEqual(decision.completed_days,7)

	def test_gate_rejects_lower_asymmetric_loss_when_mae_is_higher(self):
		raw=MetricSummary(samples=5,mae=2,asymmetric_loss=4)
		corrected=MetricSummary(samples=5,mae=2.1,asymmetric_loss=3)

		self.assertFalse(passes_gate(raw,corrected))

	def test_walk_forward_never_uses_the_day_being_predicted(self):
		first=walk_forward(self.history[:10],self.config)
		second=walk_forward(self.history[:11],self.config)

		self.assertEqual(first,second[:len(first)])

	def test_perfect_raw_spv_falls_back(self):
		history=[]
		for day in range(1,12):
			item={"date":f"2026-01-{day:02d}","actual":20,"fpv":18,"spv":20,"spv_l":10,"spv_h":30}
			history.append(record(item))

		decision=decide_forecast(history,forecasts(18,22,12,32),self.config)

		self.assertEqual(decision.mode,"fallback_spv")
		self.assertEqual(decision.correction_kwh,0)
		self.assertEqual(decision.forecast_kwh,22)

	def test_consistent_underprediction_can_activate_upward_correction(self):
		history=[]
		for day in range(1,13):
			item={"date":f"2026-01-{day:02d}","actual":24,"fpv":20,"spv":20,"spv_l":20,"spv_h":20}
			history.append(record(item))

		decision=decide_forecast(history,forecasts(30,30,30,30),self.config)

		self.assertEqual(decision.mode,"calibrated_spv")
		self.assertAlmostEqual(decision.candidate_correction_kwh,1)
		self.assertAlmostEqual(decision.correction_kwh,1)
		self.assertAlmostEqual(decision.forecast_kwh,31)

	def test_model_weights_reward_small_asymmetric_error_in_kwh(self):
		history=[]
		for day in range(1,9):
			item={"date":f"2026-02-{day:02d}","actual":20,"fpv":20,"spv":35,"spv_l":25,"spv_h":45}
			history.append(record(item))

		weights=calculate_model_weights(history,self.config)

		self.assertEqual(set(weights),{"fpv","spv","spv_l","spv_h","spv_div_l","spv_l_div_h","spv_div_h"})
		self.assertAlmostEqual(sum(weights.values()),1)
		self.assertGreater(weights["fpv"],weights["spv_l"])
		self.assertGreater(weights["spv_l"],weights["spv"])

	def test_ensemble_replaces_spv_when_walk_forward_results_are_better(self):
		history=[]
		for day in range(1,13):
			item={"date":f"2026-02-{day:02d}","actual":20,"fpv":20,"spv":35,"spv_l":25,"spv_h":45}
			history.append(record(item))
		current=forecasts(21,36,26,46)

		decision=decide_forecast(history,current,self.config)

		self.assertEqual(decision.mode,"calibrated_ensemble")
		self.assertLess(decision.forecast_kwh,25)
		self.assertLess(decision.weighted_forecast_kwh,25)
		self.assertGreater(decision.model_weights["fpv"],decision.model_weights["spv"])


if __name__ == "__main__":
	unittest.main()
