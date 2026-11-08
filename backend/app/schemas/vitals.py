"""Validated input for CC-12. Shape and range checks only; authorization lives in the controller."""
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from app.schemas.contracts import Contract

Kind = Literal['bp', 'sugar', 'weight', 'spo2']

# Accepted units per kind. Weight is kg only and SpO2 is a percentage.
UNITS = {'bp': ('mmHg',), 'sugar': ('mg/dL', 'mmol/L'), 'weight': ('kg',), 'spo2': ('%',)}

# Plausibility limits (inclusive) for the primary value. They exist to catch typos such as
# 1200 instead of 120; they are not clinical normal ranges.
LIMITS = {('bp', 'mmHg'): (Decimal(50), Decimal(300)),
          ('sugar', 'mg/dL'): (Decimal(20), Decimal(800)),
          ('sugar', 'mmol/L'): (Decimal(1), Decimal(45)),
          ('weight', 'kg'): (Decimal(1), Decimal(400)),
          ('spo2', '%'): (Decimal(50), Decimal(100))}
DIASTOLIC_LIMITS = (Decimal(20), Decimal(200))

Number = Decimal  # always Decimal so 0.1 + 0.2 style float errors never reach a comparison


def number(**extra):
    return Field(max_digits=7, decimal_places=2, allow_inf_nan=False, **extra)


class VitalInput(Contract):
    kind: Kind
    unit: str
    value: Decimal = number(gt=0)
    secondary_value: Decimal | None = number(gt=0, default=None)
    observed_at: AwareDatetime | None = None  # omitted = now (server clock)

    @model_validator(mode='after')
    def consistent(self):
        if self.unit not in UNITS[self.kind]:
            raise ValueError('Unit is not valid for this measurement')
        low, high = LIMITS[(self.kind, self.unit)]
        if not low <= self.value <= high:
            raise ValueError('Value is outside the plausible range')
        if self.kind == 'bp':
            if self.secondary_value is None:
                raise ValueError('Blood pressure needs systolic and diastolic values')
            if not DIASTOLIC_LIMITS[0] <= self.secondary_value <= DIASTOLIC_LIMITS[1]:
                raise ValueError('Diastolic value is outside the plausible range')
            if self.value <= self.secondary_value:
                raise ValueError('Systolic must be higher than diastolic')
        elif self.secondary_value is not None:
            raise ValueError('Only blood pressure has a second value')
        return self


class TrendRule(Contract):
    min_readings: int = Field(default=3, ge=3, le=10)
    window_days: int = Field(default=14, ge=1, le=60)
    min_change: Decimal = number(gt=0)  # in the threshold's unit, on the primary value


class ThresholdInput(Contract):
    unit: str
    lower: Decimal | None = number(gt=0, default=None)
    upper: Decimal | None = number(gt=0, default=None)
    secondary_lower: Decimal | None = number(gt=0, default=None)
    secondary_upper: Decimal | None = number(gt=0, default=None)
    trend: TrendRule | None = None
