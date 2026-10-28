from __future__ import annotations

import logging
from typing import Any

from .storage import JsonStateStore
from .supervisor import SupervisorClient


LOGGER=logging.getLogger(__name__)


async def reset_history_if_requested(
	options: dict[str,Any],
	store: JsonStateStore,
	supervisor: SupervisorClient
) -> bool:
	if options.get("reset_history_on_start") is not True:
		return False
	store.reset()
	updated_options=dict(options)
	updated_options["reset_history_on_start"]=False
	await supervisor.update_options(updated_options)
	LOGGER.warning("Jednorazowy reset historii zakończony - opcja reset_history_on_start ustawiona na off")
	return True
