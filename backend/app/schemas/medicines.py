import re
import unicodedata
from typing import Literal
from uuid import UUID
from pydantic import Field, field_validator, model_validator
from app.schemas.contracts import Contract, PrescriptionItemInput


def normalized(value: str) -> str:
    return ' '.join(unicodedata.normalize('NFKC', value).casefold().split())


class MedicineInput(Contract):
    generic_name: str = Field(min_length=1, max_length=160)
    brand_name: str = Field(min_length=1, max_length=160)
    strength: str = Field(min_length=1, max_length=60)
    form: Literal['tablet', 'capsule', 'liquid', 'drops', 'inhaler', 'injection', 'cream']
    source_name: str = Field(min_length=1, max_length=300)
    source_license: str = Field(min_length=1, max_length=200)

    @field_validator('*', mode='before')
    @classmethod
    def clean(cls, value):
        return ' '.join(value.split()) if isinstance(value, str) else value

    @field_validator('strength')
    @classmethod
    def strength_units(cls, value):
        # Explicit conservative import grammar; no guessed units or conversions.
        if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)?\s*(?:mg|mcg|g|ml|IU|%)(?:/[0-9]*(?:\.[0-9]+)?\s*(?:ml|g|dose))?', value):
            raise ValueError('Use a number and supported unit, e.g. 10 mg or 5 mg/5ml')
        if float(re.match(r'[0-9.]+', value)[0]) <= 0:
            raise ValueError('Strength must be positive')
        return value.replace(' ', '')


class ImportInput(Contract):
    csv_text: str = Field(min_length=1, max_length=500_000)


class RuleInput(Contract):
    medicine_a_id: UUID
    medicine_b_id: UUID
    severity: Literal['info', 'warning', 'critical']
    explanation: str = Field(min_length=5, max_length=1000)
    source: str = Field(min_length=5, max_length=300)

    @model_validator(mode='after')
    def different(self):
        if self.medicine_a_id == self.medicine_b_id:
            raise ValueError('Choose different medicines')
        if not self.source.strip() or not self.explanation.strip():
            raise ValueError('Source and explanation required')
        return self


class AllergyInput(Contract):
    generic_names: list[str] = Field(max_length=30)

    @field_validator('generic_names')
    @classmethod
    def names(cls, values):
        cleaned = sorted(set(normalized(v) for v in values))
        if any(not v or len(v) > 160 for v in cleaned):
            raise ValueError('Enter generic names, each up to 160 characters')
        return cleaned


class CheckInput(Contract):
    items: list[PrescriptionItemInput] = Field(min_length=1, max_length=20)
    replaces_version_id: UUID | None = None
    change_reason: str | None = Field(default=None, min_length=3, max_length=1000)
    ocr_draft_id: UUID | None = None

    @model_validator(mode='after')
    def revision_reason(self):
        if self.replaces_version_id is not None and (self.change_reason is None or len(self.change_reason.strip()) < 3):
            raise ValueError('A prescription revision needs a reason')
        return self


class ConfirmInput(Contract):
    check_id: UUID
    acknowledged_warning_ids: list[str] = Field(default_factory=list, max_length=1000)


class StopInput(Contract):
    expected_version_id: UUID
    reason: str = Field(min_length=3, max_length=1000)

    @field_validator('reason')
    @classmethod
    def nonblank(cls, value):
        if len(value.strip()) < 3:
            raise ValueError('Enter a reason for stopping')
        return value.strip()


class OcrReviewInput(Contract):
    reviewed_text: str = Field(min_length=1, max_length=20000)
    expected_revision: int = Field(ge=0)

    @field_validator('reviewed_text')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('Enter reviewed prescription text')
        return value.strip()
