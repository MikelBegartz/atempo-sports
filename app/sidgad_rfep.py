"""Compat RFEP: wrapper del cliente genérico."""

from app.sidgad import CalendarMatch, parse_calendar
from app.sidgad import SidgadClient as GenericSidgadClient


class SidgadClient(GenericSidgadClient):
    def __init__(self, sleep_s: float = 0.25) -> None:
        super().__init__("rfep", sleep_s=sleep_s)


__all__ = ["CalendarMatch", "SidgadClient", "parse_calendar"]
