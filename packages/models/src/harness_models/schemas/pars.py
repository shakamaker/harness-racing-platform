"""Par-times DTO. The /tracks/{id}/pars endpoint returns these."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import computed_field

from ..time_utils import format_ss_ms
from ._base import BaseSchema


class ParTimesRead(BaseSchema):
    track_id: int
    distance_m: int
    race_gait_id: int
    start_type_id: int
    track_condition_id: int | None
    race_class_id: int | None
    age_class_id: int | None
    par_gross_time_s: Decimal | None
    par_lead_time_s: Decimal | None
    par_mile_rate_s: Decimal | None
    sample_size: int
    computed_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def par_gross_time_display(self) -> str | None:
        return format_ss_ms(self.par_gross_time_s)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def par_lead_time_display(self) -> str | None:
        return format_ss_ms(self.par_lead_time_s)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def par_mile_rate_display(self) -> str | None:
        return format_ss_ms(self.par_mile_rate_s)


__all__ = ["ParTimesRead"]
