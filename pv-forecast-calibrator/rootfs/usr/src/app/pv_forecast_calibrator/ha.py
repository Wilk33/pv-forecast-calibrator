from __future__ import annotations

from datetime import datetime
import math
from typing import Any
from urllib.parse import quote


def parse_numeric_state(payload: dict[str,Any]) -> float | None:
	try:
		value=float(str(payload.get("state","")).replace(",","."))
	except (TypeError,ValueError):
		return None
	if not math.isfinite(value) or value < 0:
		return None
	return value


def history_maximum(payload: list[list[dict[str,Any]]]) -> float | None:
	values=[]
	for series in payload:
		for item in series:
			value=parse_numeric_state(item)
			if value is not None:
				values.append(value)
	return max(values) if values else None


class HomeAssistantClient:
	def __init__(self,session,token: str,base_url: str="http://supervisor/core/api"):
		self.session=session
		self.base_url=base_url.rstrip("/")
		self.headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"}

	async def get_state(self,entity_id: str) -> dict[str,Any]:
		url=f"{self.base_url}/states/{quote(entity_id,safe='')}"
		async with self.session.get(url,headers=self.headers) as response:
			response.raise_for_status()
			return await response.json()

	async def history_max(self,entity_id: str,start: datetime,end: datetime) -> float | None:
		url=f"{self.base_url}/history/period/{quote(start.isoformat(),safe='')}"
		params={
			"end_time":end.isoformat(),
			"filter_entity_id":entity_id,
			"minimal_response":"",
			"no_attributes":"",
			"significant_changes_only":""
		}
		async with self.session.get(url,headers=self.headers,params=params) as response:
			response.raise_for_status()
			return history_maximum(await response.json())
