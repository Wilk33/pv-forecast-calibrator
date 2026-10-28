from __future__ import annotations

from dataclasses import dataclass
import math

from .models import DailyRecord,ForecastSet


MODEL_KEYS=("fpv","spv","spv_l","spv_h","spv_div_l","spv_l_div_h","spv_div_h")


@dataclass(frozen=True)
class CalibrationConfig:
	over_penalty: float=2.0
	max_downward_correction_kwh: float=1.0
	max_upward_correction_kwh: float=1.0
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
	weighted_forecast_kwh: float
	corrected_forecast_kwh: float
	correction_kwh: float


@dataclass(frozen=True)
class CalibrationDecision:
	forecast_kwh: float
	correction_kwh: float
	weighted_forecast_kwh: float
	model_weights: dict[str,float]
	mode: str
	raw_metrics: MetricSummary | None
	corrected_metrics: MetricSummary | None
	completed_days: int
	validation_samples: int
	required_validation_samples: int
	candidate_correction_kwh: float
	reason: str


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
	return sorted(
		(item for item in history if item.actual_kwh is not None and item.actual_verified),
		key=lambda item:item.date
	)


def _model_value(item: DailyRecord,key: str) -> float | None:
	return getattr(item.forecasts,key)


def calculate_model_weights(history: list[DailyRecord],config: CalibrationConfig) -> dict[str,float]:
	completed=_completed(history)
	if not completed:
		return {key:1.0/len(MODEL_KEYS) for key in MODEL_KEYS}
	scores={}
	for key in MODEL_KEYS:
		losses=[]
		weights=[]
		for age,item in enumerate(reversed(completed)):
			forecast=_model_value(item,key)
			if forecast is None:
				continue
			losses.append(asymmetric_loss(item.actual_kwh,forecast,config.over_penalty))
			weights.append(config.decay**age)
		if len(losses) < min(config.minimum_training_days,len(completed)):
			continue
		scores[key]=sum(loss*weight for loss,weight in zip(losses,weights))/sum(weights)
	if not scores:
		return {key:1.0/len(MODEL_KEYS) for key in MODEL_KEYS}
	best=min(scores.values())
	temperature=max(0.25,best*0.25)
	raw={key:math.exp(-(score-best)/temperature) for key,score in scores.items()}
	total=sum(raw.values())
	return {key:raw.get(key,0.0)/total for key in MODEL_KEYS}


def weighted_forecast(forecasts,weights: dict[str,float]) -> float:
	available=[]
	for key in MODEL_KEYS:
		value=getattr(forecasts,key)
		weight=weights.get(key,0.0)
		if value is not None and weight > 0:
			available.append((value,weight))
	if not available:
		return forecasts.spv
	total=sum(weight for _,weight in available)
	return sum(value*weight for value,weight in available)/total


def _candidate_correction_from_residuals(residuals: list[float],config: CalibrationConfig) -> float:
	if not residuals:
		return 0.0
	ages=list(range(len(residuals)-1,-1,-1))
	weights=[config.decay**age for age in ages]
	quantile=1.0/(1.0+config.over_penalty)
	value=_weighted_quantile(residuals,quantile,weights)
	return max(-config.max_downward_correction_kwh,min(config.max_upward_correction_kwh,value))


def _candidate_correction(history: list[DailyRecord],config: CalibrationConfig) -> float:
	completed=_completed(history)
	residuals=[item.actual_kwh-item.forecasts.spv for item in completed]
	return _candidate_correction_from_residuals(residuals,config)


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
				weighted_forecast_kwh=item.forecasts.spv,
				corrected_forecast_kwh=item.forecasts.spv+correction,
				correction_kwh=correction
			)
		)
	return result


def ensemble_walk_forward(history: list[DailyRecord],config: CalibrationConfig) -> list[WalkForwardSample]:
	completed=_completed(history)
	result=[]
	for index in range(config.minimum_training_days,len(completed)):
		item=completed[index]
		previous=completed[:index]
		weights=calculate_model_weights(previous,config)
		base=weighted_forecast(item.forecasts,weights)
		residuals=[sample.actual_kwh-sample.weighted_forecast_kwh for sample in result]
		correction=_candidate_correction_from_residuals(residuals,config)
		result.append(
			WalkForwardSample(
				date=item.date,
				actual_kwh=item.actual_kwh,
				raw_forecast_kwh=item.forecasts.spv,
				weighted_forecast_kwh=base,
				corrected_forecast_kwh=base+correction,
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


def _decide_spv(
	history: list[DailyRecord],
	forecasts: ForecastSet,
	config: CalibrationConfig,
	weighted_base: float,
	model_weights: dict[str,float],
	reason_prefix: str=""
) -> CalibrationDecision:
	completed=_completed(history)
	validation=walk_forward(completed,config)
	candidate=_candidate_correction(completed,config)
	if len(validation) < config.minimum_validation_days:
		missing=config.minimum_validation_days-len(validation)
		return CalibrationDecision(
			forecast_kwh=forecasts.spv,
			correction_kwh=0.0,
			weighted_forecast_kwh=weighted_base,
			model_weights=model_weights,
			mode="learning",
			raw_metrics=None,
			corrected_metrics=None,
			completed_days=len(completed),
			validation_samples=len(validation),
			required_validation_samples=config.minimum_validation_days,
			candidate_correction_kwh=candidate,
			reason=f"za mało próbek walidacyjnych - brakuje {missing}"
		)
	validation=validation[-config.validation_window_days:]
	raw_metrics=_metrics(validation,False,config.over_penalty)
	corrected_metrics=_metrics(validation,True,config.over_penalty)
	metric_reason=(
		f"SPV: MAE {raw_metrics.mae:.4f} -> {corrected_metrics.mae:.4f} kWh, "
		f"koszt {raw_metrics.asymmetric_loss:.4f} -> {corrected_metrics.asymmetric_loss:.4f}; "
	)
	if not passes_gate(raw_metrics,corrected_metrics):
		return CalibrationDecision(
			forecast_kwh=forecasts.spv,
			correction_kwh=0.0,
			weighted_forecast_kwh=weighted_base,
			model_weights=model_weights,
			mode="fallback_spv",
			raw_metrics=raw_metrics,
			corrected_metrics=corrected_metrics,
			completed_days=len(completed),
			validation_samples=len(validation),
			required_validation_samples=config.minimum_validation_days,
			candidate_correction_kwh=candidate,
			reason=reason_prefix+metric_reason+"korekta SPV nie poprawiła jednocześnie kosztu asymetrycznego i MAE"
		)
	return CalibrationDecision(
		forecast_kwh=forecasts.spv+candidate,
		correction_kwh=candidate,
		weighted_forecast_kwh=weighted_base,
		model_weights=model_weights,
		mode="calibrated_spv",
		raw_metrics=raw_metrics,
		corrected_metrics=corrected_metrics,
		completed_days=len(completed),
		validation_samples=len(validation),
		required_validation_samples=config.minimum_validation_days,
		candidate_correction_kwh=candidate,
		reason=reason_prefix+metric_reason+"korekta SPV przeszła bramkę jakości"
	)


def decide_forecast(history: list[DailyRecord],forecasts: ForecastSet,config: CalibrationConfig) -> CalibrationDecision:
	completed=_completed(history)
	model_weights=calculate_model_weights(completed,config)
	weighted_base=weighted_forecast(forecasts,model_weights)
	spv_validation=walk_forward(completed,config)[-config.validation_window_days:]
	ensemble_validation=ensemble_walk_forward(completed,config)[-config.validation_window_days:]
	if len(ensemble_validation) < config.minimum_validation_days:
		return _decide_spv(completed,forecasts,config,weighted_base,model_weights)
	raw_metrics=_metrics(spv_validation,False,config.over_penalty)
	spv_corrected_metrics=_metrics(spv_validation,True,config.over_penalty)
	baseline_metrics=spv_corrected_metrics if passes_gate(raw_metrics,spv_corrected_metrics) else raw_metrics
	ensemble_metrics=_metrics(ensemble_validation,True,config.over_penalty)
	if not passes_gate(baseline_metrics,ensemble_metrics):
		reason_prefix=(
			f"model ważony odrzucony: MAE {ensemble_metrics.mae:.4f} vs {baseline_metrics.mae:.4f} kWh, "
			f"koszt {ensemble_metrics.asymmetric_loss:.4f} vs {baseline_metrics.asymmetric_loss:.4f}; "
		)
		return _decide_spv(
			completed,
			forecasts,
			config,
			weighted_base,
			model_weights,
			reason_prefix
		)
	residuals=[sample.actual_kwh-sample.weighted_forecast_kwh for sample in ensemble_validation]
	candidate=_candidate_correction_from_residuals(residuals,config)
	return CalibrationDecision(
		forecast_kwh=weighted_base+candidate,
		correction_kwh=candidate,
		weighted_forecast_kwh=weighted_base,
		model_weights=model_weights,
		mode="calibrated_ensemble",
		raw_metrics=baseline_metrics,
		corrected_metrics=ensemble_metrics,
		completed_days=len(completed),
		validation_samples=len(ensemble_validation),
		required_validation_samples=config.minimum_validation_days,
		candidate_correction_kwh=candidate,
		reason="model ważony i jego korekta przeszły bramkę jakości względem najlepszego wariantu SPV"
	)


def completed_mae(history: list[DailyRecord],days: int) -> float | None:
	completed=_completed(history)[-days:]
	if not completed:
		return None
	return sum(abs(item.published_forecast_kwh-item.actual_kwh) for item in completed)/len(completed)
