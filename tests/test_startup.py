from pathlib import Path
import tempfile
import unittest

from pv_forecast_calibrator.startup import reset_history_if_requested
from pv_forecast_calibrator.storage import AppState, JsonStateStore


class FakeSupervisor:
	def __init__(self):
		self.saved_options=None

	async def update_options(self,options):
		self.saved_options=options


class StartupTests(unittest.IsolatedAsyncioTestCase):
	async def test_requested_reset_clears_state_and_turns_option_off(self):
		with tempfile.TemporaryDirectory() as directory:
			store=JsonStateStore(Path(directory)/"state.json")
			store.save(AppState(production_date="2026-10-28",production_max_kwh=12.5))
			supervisor=FakeSupervisor()
			options={"reset_history_on_start":True,"device_name":"PV Forecast Calibrator"}

			was_reset=await reset_history_if_requested(options,store,supervisor)

			self.assertTrue(was_reset)
			self.assertEqual(store.load(),AppState())
			self.assertEqual(
				supervisor.saved_options,
				{"reset_history_on_start":False,"device_name":"PV Forecast Calibrator"}
			)
			self.assertTrue(options["reset_history_on_start"])

	async def test_disabled_reset_keeps_state_and_does_not_update_options(self):
		with tempfile.TemporaryDirectory() as directory:
			store=JsonStateStore(Path(directory)/"state.json")
			store.save(AppState(production_date="2026-10-28",production_max_kwh=12.5))
			supervisor=FakeSupervisor()

			was_reset=await reset_history_if_requested(
				{"reset_history_on_start":False},
				store,
				supervisor
			)

			self.assertFalse(was_reset)
			self.assertEqual(store.load().production_max_kwh,12.5)
			self.assertIsNone(supervisor.saved_options)
