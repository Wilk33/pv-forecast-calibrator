from pathlib import Path
import tempfile
import unittest

from pv_forecast_calibrator.models import DailyRecord, ForecastSet
from pv_forecast_calibrator.storage import AppState, JsonStateStore, StateFileError


def make_record(date):
	forecasts=ForecastSet(10,20,10,30,15,20,25)
	return DailyRecord(date,date+"T04:20:00+02:00",forecasts,20,0,"learning",None)


class JsonStateStoreTests(unittest.TestCase):
	def test_missing_file_loads_empty_state(self):
		with tempfile.TemporaryDirectory() as directory:
			store=JsonStateStore(Path(directory)/"state.json")

			self.assertEqual(store.load(),AppState())

	def test_atomic_round_trip_preserves_state(self):
		with tempfile.TemporaryDirectory() as directory:
			path=Path(directory)/"state.json"
			store=JsonStateStore(path)
			state=AppState(records=[make_record("2026-10-08")],production_date="2026-10-08",production_max_kwh=12.3)

			store.save(state)

			self.assertEqual(store.load(),state)
			self.assertEqual(list(path.parent.glob("*.tmp")),[])

	def test_corrupt_file_is_reported(self):
		with tempfile.TemporaryDirectory() as directory:
			path=Path(directory)/"state.json"
			path.write_text("not json",encoding="utf-8")

			with self.assertRaises(StateFileError):
				JsonStateStore(path).load()

	def test_add_record_is_idempotent_and_trims_oldest_days(self):
		state=AppState()
		for day in range(1,6):
			state.add_record(make_record(f"2026-10-{day:02d}"),history_limit_days=3)
		state.add_record(make_record("2026-10-05"),history_limit_days=3)

		self.assertEqual([item.date for item in state.records],["2026-10-03","2026-10-04","2026-10-05"])


if __name__ == "__main__":
	unittest.main()
