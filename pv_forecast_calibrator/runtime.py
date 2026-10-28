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
		self._history_attempted_dates=set()
		self._missing_snapshot_logged_dates=set()
		verified=sum(1 for item in self.state.records if item.actual_kwh is not None and item.actual_verified)
		unverified=sum(1 for item in self.state.records if item.actual_kwh is not None and not item.actual_verified)
		LOGGER.info(
			"Wczytano historię: rekordy=%d, kompletne_zweryfikowane=%d, wymagające_uzgodnienia=%d",
			len(self.state.records),
			verified,
			unverified
		)

	async def tick(self,now: datetime) -> bool:
		local_now=now.astimezone(self.config.timezone)
		LOGGER.debug("Cykl %s",local_now.isoformat())
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
			if today not in self._missing_snapshot_logged_dates:
				LOGGER.warning(
					"Brak porannej próbki %s - minęła granica %s, prognoza śróddzienna nie zostanie użyta",
					today,
					self.config.snapshot_deadline.isoformat(timespec="minutes")
				)
				self._missing_snapshot_logged_dates.add(today)
		elif record is not None:
			self.model_status=record.mode
		if record is not None and record.actual_kwh is None and clock >= self.config.settlement_time:
			changed=self._settle(today) or changed
		if changed:
			self.store.save(self.state)
		LOGGER.debug(
			"Koniec cyklu %s: zmiana=%s, stan=%s, maksimum_produkcji=%s",
			local_now.isoformat(),
			changed,
			self.model_status,
			self.state.production_max_kwh
		)
		return changed

	async def _capture(self,now: datetime) -> bool:
		try:
			forecast_solar=await self.ha.get_state(self.config.forecast_solar_entity)
			solcast=await self.ha.get_state(self.config.solcast_entity)
			forecasts=ForecastSet.from_states(forecast_solar.get("state"),solcast)
			decision=decide_forecast(self.state.records,forecasts,self.config.calibration)
			LOGGER.info(
				"Poranna próbka %s: FPV=%s kWh, SPV=%.4f kWh, SPV_L=%.4f kWh, SPV_H=%.4f kWh, SPV/L=%.4f kWh, SPV_L/H=%.4f kWh, SPV/H=%.4f kWh",
				now.date().isoformat(),
				"brak" if forecasts.fpv is None else f"{forecasts.fpv:.4f}",
				forecasts.spv,
				forecasts.spv_l,
				forecasts.spv_h,
				forecasts.spv_div_l,
				forecasts.spv_l_div_h,
				forecasts.spv_div_h
			)
			self._log_decision(decision)
			record=DailyRecord(
				date=now.date().isoformat(),
				captured_at=now.isoformat(),
				forecasts=forecasts,
				published_forecast_kwh=decision.forecast_kwh,
				correction_kwh=decision.correction_kwh,
				mode=decision.mode,
				weighted_forecast_kwh=decision.weighted_forecast_kwh,
				model_weights=decision.model_weights
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
		clock=now.time().replace(tzinfo=None)
		changed=False
		if self.state.production_date != date:
			previous_date=self.state.production_date
			previous_max=self.state.production_max_kwh
			self.state.production_date=date
			self.state.production_max_kwh=None
			changed=True
			LOGGER.info(
				"Nowy dzień produkcji %s: wyzerowano akumulator lokalny, poprzednia_data=%s, poprzednie_maksimum=%s; odczyty rozpoczną się o %s",
				date,
				previous_date,
				previous_max,
				self.config.snapshot_time.isoformat(timespec="minutes")
			)
		if clock < self.config.snapshot_time:
			LOGGER.debug(
				"Odczyt produkcji pominięty przed %s, aby nie przejąć wartości sprzed resetu licznika",
				self.config.snapshot_time.isoformat(timespec="minutes")
			)
			return changed
		try:
			payload=await self.ha.get_state(self.config.production_entity)
		except Exception:
			LOGGER.exception("Nie można odczytać bieżącej produkcji PV")
			return changed
		value=parse_numeric_state(payload)
		LOGGER.debug(
			"Odczyt produkcji %s: surowy=%r, liczba=%s, maksimum_przed=%s",
			date,
			payload.get("state"),
			value,
			self.state.production_max_kwh
		)
		if value is not None and (self.state.production_max_kwh is None or value > self.state.production_max_kwh):
			self.state.production_max_kwh=value
			changed=True
			LOGGER.debug("Nowe maksimum produkcji %s: %.4f kWh",date,value)
		return changed

	async def _recover_previous_days(self,now: datetime) -> bool:
		changed=False
		for record in list(self.state.records):
			if record.actual_verified or record.date >= now.date().isoformat():
				continue
			if record.date in self._history_attempted_dates:
				continue
			self._history_attempted_dates.add(record.date)
			start,end=self._history_window(record.date)
			try:
				actual=await self.ha.history_max(self.config.production_entity,start,end)
			except Exception:
				LOGGER.exception("Nie można odzyskać produkcji PV dla %s",record.date)
				continue
			if actual is not None:
				old=record.actual_kwh
				self.state.replace_record(record.with_actual(actual,verified=True))
				changed=True
				if old is None:
					LOGGER.info(
						"Odzyskano produkcję %s z historii: %.4f kWh, zakres=%s - %s",
						record.date,
						actual,
						start.isoformat(),
						end.isoformat()
					)
				elif abs(old-actual) > 0.00005:
					LOGGER.info(
						"Uzgodnienie historii %s: produkcja %.4f -> %.4f kWh, zakres=%s - %s",
						record.date,
						old,
						actual,
						start.isoformat(),
						end.isoformat()
					)
				else:
					LOGGER.info("Potwierdzono produkcję %s: %.4f kWh",record.date,actual)
			else:
				LOGGER.warning(
					"Brak danych historii dla %s w zakresie %s - %s; dzień pozostaje wyłączony z uczenia",
					record.date,
					start.isoformat(),
					end.isoformat()
				)
		return changed

	def _settle(self,date: str) -> bool:
		record=self.state.record_for(date)
		if record is None or record.actual_kwh is not None or self.state.production_max_kwh is None:
			return False
		actual=self.state.production_max_kwh
		changed=self.state.replace_record(record.with_actual(actual,verified=True))
		if changed:
			error=record.published_forecast_kwh-actual
			LOGGER.info(
				"Zamknięcie dnia %s: prognoza=%.4f kWh, produkcja=%.4f kWh, błąd_podpisany=%+.4f kWh, błąd_bezwzględny=%.4f kWh, tryb=%s",
				date,
				record.published_forecast_kwh,
				actual,
				error,
				abs(error),
				record.mode
			)
		return changed

	def _history_window(self,date: str) -> tuple[datetime,datetime]:
		day=datetime.fromisoformat(date).date()
		start=datetime.combine(day,self.config.snapshot_time,tzinfo=self.config.timezone)
		end=datetime.combine(day+timedelta(days=1),time(0,0),tzinfo=self.config.timezone)
		return start,end

	def _log_decision(self,decision) -> None:
		LOGGER.info(
			"Decyzja modelu: %s, historia=%d dni, walidacja=%d/%d, prognoza_ważona=%.4f kWh, kandydat_korekty=%+.4f kWh, zastosowana_korekta=%+.4f kWh, wynik=%.4f kWh, powód=%s",
			decision.mode,
			decision.completed_days,
			decision.validation_samples,
			decision.required_validation_samples,
			decision.weighted_forecast_kwh,
			decision.candidate_correction_kwh,
			decision.correction_kwh,
			decision.forecast_kwh,
			decision.reason
		)
		LOGGER.info(
			"Wagi modeli: %s",
			", ".join(f"{key}={value*100:.2f}%" for key,value in decision.model_weights.items())
		)
		if decision.raw_metrics is not None and decision.corrected_metrics is not None:
			LOGGER.info(
				"Bramka jakości: próbki=%d, wariant_bazowy_MAE=%.4f kWh, kandydat_MAE=%.4f kWh, wariant_bazowy_koszt=%.4f, kandydat_koszt=%.4f",
				decision.raw_metrics.samples,
				decision.raw_metrics.mae,
				decision.corrected_metrics.mae,
				decision.raw_metrics.asymmetric_loss,
				decision.corrected_metrics.asymmetric_loss
			)

	def state_payload(self,now: datetime) -> dict[str,Any]:
		local_now=now.astimezone(self.config.timezone)
		today=local_now.date().isoformat()
		current=self.state.record_for(today)
		completed=sorted(
			(item for item in self.state.records if item.actual_kwh is not None and item.actual_verified),
			key=lambda item:item.date
		)
		previous=completed[-1] if completed else None
		return {
			"forecast_today_kwh":None if current is None else round(current.published_forecast_kwh,4),
			"weighted_forecast_today_kwh":None if current is None or current.weighted_forecast_kwh is None else round(current.weighted_forecast_kwh,4),
			"correction_today_kwh":None if current is None else round(current.correction_kwh,4),
			"weight_fpv_percent":_weight_percent(current,"fpv"),
			"weight_spv_percent":_weight_percent(current,"spv"),
			"weight_spv_l_percent":_weight_percent(current,"spv_l"),
			"weight_spv_h_percent":_weight_percent(current,"spv_h"),
			"weight_spv_div_l_percent":_weight_percent(current,"spv_div_l"),
			"weight_spv_l_div_h_percent":_weight_percent(current,"spv_l_div_h"),
			"weight_spv_div_h_percent":_weight_percent(current,"spv_div_h"),
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


def _weight_percent(record: DailyRecord | None,key: str) -> float | None:
	if record is None or key not in record.model_weights:
		return None
	return round(record.model_weights[key]*100,6)
