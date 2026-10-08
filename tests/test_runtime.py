from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

from pv_forecast_calibrator.config import AppConfig
from pv_forecast_calibrator.models import DailyRecord,ForecastSet
from pv_forecast_calibrator.runtime import ForecastRuntime
from pv_forecast_calibrator.storage import AppState,JsonStateStore

from tests.test_config import valid_options


WARSAW=ZoneInfo("Europe/Warsaw")


class FakeHomeAssistant:
	def __init__(self):
		self.states={
			"sensor.energy_production_today":{"state":"15.987","attributes":{}},
			"sensor.solcast_pv_forecast_prognoza_na_dzisiaj":{
				"state":"16.1263",
				"attributes":{"estimate":16.1263,"estimate10":6.674,"estimate90":29.2363}
			},
			"sensor.deye_deye_10kw_pv_production_today":{"state":"0","attributes":{}}
		}
		self.state_calls=[]
		self.history_values={}

	async def get_state(self,entity_id):
		self.state_calls.append(entity_id)
		return self.states[entity_id]

	async def history_max(self,entity_id,start,end):
		return self.history_values.get(start.date().isoformat())


class ForecastRuntimeTests(unittest.IsolatedAsyncioTestCase):
	def setUp(self):
		self.directory=tempfile.TemporaryDirectory()
		self.addCleanup(self.directory.cleanup)
		self.store=JsonStateStore(Path(self.directory.name)/"state.json")
		self.config=AppConfig.from_options(valid_options())
		self.ha=FakeHomeAssistant()
		self.runtime=ForecastRuntime(self.config,self.store,self.ha)

	async def test_captures_once_inside_morning_window(self):
		now=datetime(2026,10,8,4,20,tzinfo=WARSAW)

		await self.runtime.tick(now)
		await self.runtime.tick(datetime(2026,10,8,4,21,tzinfo=WARSAW))

		state=self.store.load()
		self.assertEqual(len(state.records),1)
		self.assertEqual(state.records[0].date,"2026-10-08")
		self.assertEqual(state.records[0].published_forecast_kwh,16.1263)
		self.assertEqual(state.records[0].mode,"learning")
		self.assertEqual(self.ha.state_calls.count(self.config.solcast_entity),1)

	async def test_does_not_capture_intraday_forecast_after_deadline(self):
		await self.runtime.tick(datetime(2026,10,8,12,0,tzinfo=WARSAW))

		self.assertIsNone(self.store.load().record_for("2026-10-08"))
		self.assertEqual(self.runtime.model_status,"missing_snapshot")
		self.assertNotIn(self.config.solcast_entity,self.ha.state_calls)

	async def test_tracks_maximum_and_settles_day_once(self):
		await self.runtime.tick(datetime(2026,10,8,4,20,tzinfo=WARSAW))
		self.ha.states[self.config.production_entity]["state"]="12.5"
		await self.runtime.tick(datetime(2026,10,8,12,0,tzinfo=WARSAW))
		self.ha.states[self.config.production_entity]["state"]="11.0"
		await self.runtime.tick(datetime(2026,10,8,23,0,tzinfo=WARSAW))
		await self.runtime.tick(datetime(2026,10,8,23,1,tzinfo=WARSAW))

		record=self.store.load().record_for("2026-10-08")
		self.assertEqual(record.actual_kwh,12.5)

	async def test_recovers_unsettled_previous_day_from_history(self):
		forecasts=ForecastSet(15,20,10,30,15,20,25)
		record=DailyRecord("2026-10-07","2026-10-07T04:20:00+02:00",forecasts,20,0,"learning",None)
		state=AppState(records=[record])
		self.store.save(state)
		self.ha.history_values["2026-10-07"]=18.4
		self.runtime=ForecastRuntime(self.config,self.store,self.ha)

		await self.runtime.tick(datetime(2026,10,8,4,0,tzinfo=WARSAW))

		self.assertEqual(self.store.load().record_for("2026-10-07").actual_kwh,18.4)

	async def test_state_payload_contains_only_outputs_not_source_forecasts(self):
		await self.runtime.tick(datetime(2026,10,8,4,20,tzinfo=WARSAW))

		payload=self.runtime.state_payload(datetime(2026,10,8,4,20,tzinfo=WARSAW))

		self.assertEqual(payload["forecast_today_kwh"],16.1263)
		self.assertEqual(payload["correction_today_kwh"],0)
		self.assertNotIn("spv",payload)
		self.assertNotIn("fpv",payload)


if __name__ == "__main__":
	unittest.main()
