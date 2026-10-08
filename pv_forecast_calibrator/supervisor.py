from __future__ import annotations

from typing import Any


def normalize_supervisor_data(payload: dict[str,Any]) -> dict[str,Any]:
	value=payload.get("data",payload)
	if not isinstance(value,dict):
		raise ValueError("Supervisor response data must be an object")
	return value


class SupervisorClient:
	def __init__(self,session,token: str,base_url: str="http://supervisor"):
		self.session=session
		self.base_url=base_url.rstrip("/")
		self.headers={"Authorization":f"Bearer {token}","Content-Type":"application/json"}

	async def mqtt_service(self) -> dict[str,Any]:
		async with self.session.get(f"{self.base_url}/services/mqtt",headers=self.headers) as response:
			response.raise_for_status()
			return normalize_supervisor_data(await response.json())
