from __future__ import annotations

from dataclasses import dataclass
import math

from .models import DailyRecord


@dataclass(frozen=True)
class CalibrationConfig:
	over_penalty: float=2.0
	max_downward_correction_kwh: float=1.0
	decay: float=0.93
	minimum_training_days: int=5
	minimum_validation_days: int=3
	validation_window_days: int=30


@dataclass(frozen=True)
class MetricSummary:
	samples: int
	mae: float
	asymmetric_loss: float


@dataclass(frozen=True)
class WalkForwardSample:
	date: str
	actual_kwh: float
	raw_forecast_kwh: float
	corrected_forecast_kwh: float
	correction_kwh: float


@dataclass(frozen=True)
class CalibrationDecision:
	forecast_kwh: float
	correction_kwh: float
	mode: str
	raw_metrics: MetricSummary | None
	corrected_metrics: MetricSummary | None


def asymmetric_loss(actual: float,prediction: float,over_penalty: float) -> float:
	error=prediction-actual
	return abs(error)*(over_penalty if error > 0 else 1.0)


def _weighted_quantile(values: list[float],quantile: float,weights: list[float]) -> float:
	pairs=sorted(zip(values,weights),key=lambda item:item[0])
	threshold=quantile*sum(weights)
	cumulative=0.0
	for value,weight in pairs:
		cumulative+=weight
		if cumulative >= threshold:
			return value
	return pairs[-1][0]


def _completed(history: list[DailyRecord]) -> list[DailyRecord]:
	return sorted((item for item in history if item.actual_kwh is not None),key=lambda item:item.date)


def _candidate_correction(history: list[DailyRecord],config: CalibrationConfig) -> float:
	completed=_completed(history)
	if not completed:
		return 0.0
	residuals=[item.actual_kwh-item.forecasts.spv for item in completed]
	ages=list(range(len(residuals)-1,-1,-1))
	weights=[config.decay**age for age in ages]
	quantile=1.0/(1.0+config.over_penalty)
	value=_weighted_quantile(residuals,quantile,weights)
	return max(-config.max_downward_correction_kwh,min(0.0,value))


def walk_forward(history: list[DailyRecord],config: CalibrationConfig) -> list[WalkForwardSample]:
	completed=_completed(history)
	result=[]
	for index in range(config.minimum_training_days,len(completed)):
		item=completed[index]
		correction=_candidate_correction(completed[:index],config)
		result.append(
			WalkForwardSample(
				date=item.date,
				actual_kwh=item.actual_kwh,
				raw_forecast_kwh=item.forecasts.spv,
				corrected_forecast_kwh=item.forecasts.spv+correction,
				correction_kwh=correction
			)
		)
	return result


def _metrics(samples: list[WalkForwardSample],corrected: bool,over_penalty: float) -> MetricSummary:
	if not samples:
		return MetricSummary(0,math.nan,math.nan)
	errors=[]
	losses=[]
	for item in samples:
		prediction=item.corrected_forecast_kwh if corrected else item.raw_forecast_kwh
		errors.append(abs(prediction-item.actual_kwh))
		losses.append(asymmetric_loss(item.actual_kwh,prediction,over_penalty))
	return MetricSummary(len(samples),sum(errors)/len(errors),sum(losses)/len(losses))


def passes_gate(raw: MetricSummary,corrected: MetricSummary) -> bool:
	return corrected.asymmetric_loss < raw.asymmetric_loss and corrected.mae <= raw.mae


def decide_forecast(history: list[DailyRecord],raw_spv: float,config: CalibrationConfig) -> CalibrationDecision:
	completed=_completed(history)
	validation=walk_forward(completed,config)
	if len(validation) < config.minimum_validation_days:
		return CalibrationDecision(raw_spv,0.0,"learning",None,None)
	validation=validation[-config.validation_window_days:]
	raw_metrics=_metrics(validation,False,config.over_penalty)
	corrected_metrics=_metrics(validation,True,config.over_penalty)
	if not passes_gate(raw_metrics,corrected_metrics):
		return CalibrationDecision(raw_spv,0.0,"fallback_spv",raw_metrics,corrected_metrics)
	correction=_candidate_correction(completed,config)
	return CalibrationDecision(raw_spv+correction,correction,"calibrated",raw_metrics,corrected_metrics)


def completed_mae(history: list[DailyRecord],days: int) -> float | None:
	completed=_completed(history)[-days:]
	if not completed:
		return None
	return sum(abs(item.published_forecast_kwh-item.actual_kwh) for item in completed)/len(completed)
