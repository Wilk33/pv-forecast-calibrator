from __future__ import annotations

from datetime import datetime,time,timedelta
import logging
from typing import Any

from .calibration import completed_mae,decide_forecast
from .config import AppConfig
from .ha import parse_numeric_state
from .models import DailyRecord,ForecastSet
from .storage import AppState,JsonStateStore


LOGGER=logging.getLogger(__name__)


class ForecastRuntime:
	def __init__(self,config: AppConfig,store: JsonStateStore,ha):
		self.config=config
		self.store=store
		self.ha=ha
		self.state=store.load()
		self.model_status="learning"

	async def tick(self,now: datetime) -> bool:
		local_now=now.astimezone(self.config.timezone)
		changed=False
		changed=await self._recover_previous_days(local_now) or changed
		changed=await self._track_production(local_now) or changed
		today=local_now.date().isoformat()
		clock=local_now.time().replace(tzinfo=None)
		record=self.state.record_for(today)
		if record is None and self.config.snapshot_time <= clock <= self.config.snapshot_deadline:
			changed=await self._capture(local_now) or changed
			record=self.state.record_for(today)
		elif record is None and clock > self.config.snapshot_deadline:
			self.model_status="missing_snapshot"
		elif record is not None:
			self.model_status=record.mode
		if record is not None and record.actual_kwh is None and clock >= self.config.settlement_time:
			changed=self._settle(today) or changed
		if changed:
			self.store.save(self.state)
		return changed

	async def _capture(self,now: datetime) -> bool:
		try:
			forecast_solar=await self.ha.get_state(self.config.forecast_solar_entity)
			solcast=await self.ha.get_state(self.config.solcast_entity)
			forecasts=ForecastSet.from_states(forecast_solar.get("state"),solcast)
			decision=decide_forecast(self.state.records,forecasts.spv,self.config.calibration)
			record=DailyRecord(
				date=now.date().isoformat(),
				captured_at=now.isoformat(),
				forecasts=forecasts,
				published_forecast_kwh=decision.forecast_kwh,
				correction_kwh=decision.correction_kwh,
				mode=decision.mode
			)
			added=self.state.add_record(record,self.config.history_limit_days)
			self.model_status=decision.mode
			return added
		except Exception:
			self.model_status="source_error"
			LOGGER.exception("Cannot capture morning forecast")
			return False

	async def _track_production(self,now: datetime) -> bool:
		date=now.date().isoformat()
		changed=False
		if self.state.production_date != date:
			self.state.production_date=date
			self.state.production_max_kwh=None
			changed=True
		try:
			payload=await self.ha.get_state(self.config.production_entity)
		except Exception:
			LOGGER.exception("Cannot read current PV production")
			return changed
		value=parse_numeric_state(payload)
		if value is not None and (self.state.production_max_kwh is None or value > self.state.production_max_kwh):
			self.state.production_max_kwh=value
			changed=True
		return changed

	async def _recover_previous_days(self,now: datetime) -> bool:
		changed=False
		for record in list(self.state.records):
			if record.actual_kwh is not None or record.date >= now.date().isoformat():
				continue
			start=datetime.fromisoformat(record.date).replace(tzinfo=self.config.timezone)
			end=start+timedelta(days=1)
			try:
				actual=await self.ha.history_max(self.config.production_entity,start,end)
			except Exception:
				LOGGER.exception("Cannot recover PV production for %s",record.date)
				continue
			if actual is not None:
				self.state.replace_record(record.with_actual(actual))
				changed=True
		return changed

	def _settle(self,date: str) -> bool:
		record=self.state.record_for(date)
		if record is None or record.actual_kwh is not None or self.state.production_max_kwh is None:
			return False
		return self.state.replace_record(record.with_actual(self.state.production_max_kwh))

	def state_payload(self,now: datetime) -> dict[str,Any]:
		local_now=now.astimezone(self.config.timezone)
		today=local_now.date().isoformat()
		current=self.state.record_for(today)
		completed=sorted((item for item in self.state.records if item.actual_kwh is not None),key=lambda item:item.date)
		previous=completed[-1] if completed else None
		return {
			"forecast_today_kwh":None if current is None else round(current.published_forecast_kwh,4),
			"correction_today_kwh":None if current is None else round(current.correction_kwh,4),
			"previous_production_kwh":None if previous is None else round(previous.actual_kwh,4),
			"previous_error_kwh":None if previous is None else round(previous.published_forecast_kwh-previous.actual_kwh,4),
			"mae_7d_kwh":_rounded(completed_mae(self.state.records,7)),
			"mae_30d_kwh":_rounded(completed_mae(self.state.records,30)),
			"valid_days":len(completed),
			"model_status":self.model_status,
			"last_update":local_now.isoformat()
		}


def _rounded(value: float | None) -> float | None:
	return None if value is None else round(value,4)
