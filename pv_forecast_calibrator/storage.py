from __future__ import annotations

from dataclasses import dataclass,field
import json
import os
from pathlib import Path
import tempfile
from typing import Any
import logging

from .models import DailyRecord


LOGGER=logging.getLogger(__name__)


class StateFileError(ValueError):
	pass


@dataclass
class AppState:
	records: list[DailyRecord]=field(default_factory=list)
	production_date: str | None=None
	production_max_kwh: float | None=None

	def add_record(self,record: DailyRecord,history_limit_days: int) -> bool:
		if any(item.date == record.date for item in self.records):
			return False
		self.records.append(record)
		self.records.sort(key=lambda item:item.date)
		self.records=self.records[-history_limit_days:]
		return True

	def replace_record(self,record: DailyRecord) -> bool:
		for index,item in enumerate(self.records):
			if item.date == record.date:
				self.records[index]=record
				return True
		return False

	def record_for(self,date: str) -> DailyRecord | None:
		return next((item for item in self.records if item.date == date),None)

	def to_dict(self) -> dict[str,Any]:
		return {
			"version":2,
			"records":[item.to_dict() for item in self.records],
			"production_date":self.production_date,
			"production_max_kwh":self.production_max_kwh
		}

	@classmethod
	def from_dict(cls,value: dict[str,Any]) -> "AppState":
		return cls(
			records=[DailyRecord.from_dict(item) for item in value.get("records",[])],
			production_date=value.get("production_date"),
			production_max_kwh=value.get("production_max_kwh")
		)


class JsonStateStore:
	def __init__(self,path: Path):
		self.path=path

	def load(self) -> AppState:
		if not self.path.exists():
			LOGGER.info("Brak pliku stanu %s - rozpoczynam z pustą historią",self.path)
			return AppState()
		try:
			value=json.loads(self.path.read_text(encoding="utf-8"))
			if not isinstance(value,dict):
				raise ValueError("root must be an object")
			state=AppState.from_dict(value)
			LOGGER.debug(
				"Wczytano stan %s: rekordy=%d, data_produkcji=%s, maksimum=%s",
				self.path,
				len(state.records),
				state.production_date,
				state.production_max_kwh
			)
			return state
		except (OSError,ValueError,KeyError,TypeError) as error:
			raise StateFileError(f"Cannot load state file: {error}") from error

	def reset(self):
		try:
			self.path.unlink(missing_ok=True)
		except OSError as error:
			raise StateFileError(f"Cannot reset state file: {error}") from error
		LOGGER.warning("Usunięto historię i stan algorytmu z %s",self.path)

	def save(self,state: AppState):
		self.path.parent.mkdir(parents=True,exist_ok=True)
		descriptor,temp_name=tempfile.mkstemp(prefix=f".{self.path.name}.",suffix=".tmp",dir=self.path.parent)
		try:
			with os.fdopen(descriptor,"w",encoding="utf-8") as handle:
				json.dump(state.to_dict(),handle,ensure_ascii=False,indent=2,sort_keys=True)
				handle.flush()
				os.fsync(handle.fileno())
			os.replace(temp_name,self.path)
			LOGGER.debug("Zapisano stan %s: rekordy=%d",self.path,len(state.records))
		finally:
			if os.path.exists(temp_name):
				os.unlink(temp_name)
