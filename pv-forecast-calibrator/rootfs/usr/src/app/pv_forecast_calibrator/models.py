from __future__ import annotations

from dataclasses import dataclass,field
import math
from typing import Any


class ForecastDataError(ValueError):
	pass


def _number(value: Any,name: str,required: bool=True) -> float | None:
	try:
		if isinstance(value,bool):
			raise ValueError
		number=float(str(value).replace(",","."))
	except (TypeError,ValueError):
		if not required:
			return None
		raise ForecastDataError(f"{name} is not a number") from None
	if not math.isfinite(number) or number < 0:
		if not required:
			return None
		raise ForecastDataError(f"{name} must be a finite non-negative number")
	return number


def _finite_number(value: Any,name: str) -> float:
	try:
		number=float(value)
	except (TypeError,ValueError):
		raise ForecastDataError(f"{name} is not a number") from None
	if not math.isfinite(number):
		raise ForecastDataError(f"{name} must be finite")
	return number


@dataclass(frozen=True)
class ForecastSet:
	fpv: float | None
	spv: float
	spv_l: float
	spv_h: float
	spv_div_l: float
	spv_l_div_h: float
	spv_div_h: float

	@classmethod
	def from_states(cls,forecast_solar_state: Any,solcast_state: dict[str,Any]) -> "ForecastSet":
		attributes=solcast_state.get("attributes",{})
		if not isinstance(attributes,dict):
			raise ForecastDataError("Solcast attributes must be an object")
		spv=_number(attributes.get("estimate"),"Solcast estimate")
		spv_l=_number(attributes.get("estimate10"),"Solcast estimate10")
		spv_h=_number(attributes.get("estimate90"),"Solcast estimate90")
		return cls(
			fpv=_number(forecast_solar_state,"Forecast.Solar state",required=False),
			spv=spv,
			spv_l=spv_l,
			spv_h=spv_h,
			spv_div_l=(spv+spv_l)/2,
			spv_l_div_h=(spv_l+spv_h)/2,
			spv_div_h=(spv+spv_h)/2
		)

	def to_dict(self) -> dict[str,float | None]:
		return {
			"fpv":self.fpv,
			"spv":self.spv,
			"spv_l":self.spv_l,
			"spv_h":self.spv_h,
			"spv_div_l":self.spv_div_l,
			"spv_l_div_h":self.spv_l_div_h,
			"spv_div_h":self.spv_div_h
		}

	@classmethod
	def from_dict(cls,value: dict[str,Any]) -> "ForecastSet":
		return cls(
			fpv=_number(value.get("fpv"),"fpv",required=False),
			spv=_number(value.get("spv"),"spv"),
			spv_l=_number(value.get("spv_l"),"spv_l"),
			spv_h=_number(value.get("spv_h"),"spv_h"),
			spv_div_l=_number(value.get("spv_div_l"),"spv_div_l"),
			spv_l_div_h=_number(value.get("spv_l_div_h"),"spv_l_div_h"),
			spv_div_h=_number(value.get("spv_div_h"),"spv_div_h")
		)


@dataclass(frozen=True)
class DailyRecord:
	date: str
	captured_at: str
	forecasts: ForecastSet
	published_forecast_kwh: float
	correction_kwh: float
	mode: str
	actual_kwh: float | None=None
	actual_verified: bool=False
	weighted_forecast_kwh: float | None=None
	model_weights: dict[str,float]=field(default_factory=dict)

	def to_dict(self) -> dict[str,Any]:
		return {
			"date":self.date,
			"captured_at":self.captured_at,
			"forecasts":self.forecasts.to_dict(),
			"published_forecast_kwh":self.published_forecast_kwh,
			"correction_kwh":self.correction_kwh,
			"mode":self.mode,
			"actual_kwh":self.actual_kwh,
			"actual_verified":self.actual_verified,
			"weighted_forecast_kwh":self.weighted_forecast_kwh,
			"model_weights":self.model_weights
		}

	@classmethod
	def from_dict(cls,value: dict[str,Any]) -> "DailyRecord":
		actual=value.get("actual_kwh")
		weighted=value.get("weighted_forecast_kwh")
		weights=value.get("model_weights",{})
		if not isinstance(weights,dict):
			raise ForecastDataError("model_weights must be an object")
		return cls(
			date=str(value["date"]),
			captured_at=str(value["captured_at"]),
			forecasts=ForecastSet.from_dict(value["forecasts"]),
			published_forecast_kwh=_number(value["published_forecast_kwh"],"published_forecast_kwh"),
			correction_kwh=_finite_number(value["correction_kwh"],"correction_kwh"),
			mode=str(value["mode"]),
			actual_kwh=None if actual is None else _number(actual,"actual_kwh"),
			actual_verified=bool(value.get("actual_verified",False)),
			weighted_forecast_kwh=None if weighted is None else _number(weighted,"weighted_forecast_kwh"),
			model_weights={str(key):_number(item,"model_weight") for key,item in weights.items()}
		)

	def with_actual(self,actual_kwh: float,verified: bool=True) -> "DailyRecord":
		actual=_number(actual_kwh,"actual_kwh")
		return DailyRecord(
			date=self.date,
			captured_at=self.captured_at,
			forecasts=self.forecasts,
			published_forecast_kwh=self.published_forecast_kwh,
			correction_kwh=self.correction_kwh,
			mode=self.mode,
			actual_kwh=actual,
			actual_verified=verified,
			weighted_forecast_kwh=self.weighted_forecast_kwh,
			model_weights=self.model_weights
		)
