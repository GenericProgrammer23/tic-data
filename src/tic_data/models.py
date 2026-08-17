from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field, HttpUrl, model_validator


class OrganizationSelector(BaseModel):
    npis: list[str] = Field(default_factory=list)
    tins: list[str] = Field(default_factory=list)
    business_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_selector(self) -> "OrganizationSelector":
        if not (self.npis or self.tins or self.business_names):
            raise ValueError("Provide at least one NPI, TIN, or business name")
        self.npis = [normalize_id(v) for v in self.npis if normalize_id(v)]
        self.tins = [normalize_id(v) for v in self.tins if normalize_id(v)]
        self.business_names = [v.strip() for v in self.business_names if v.strip()]
        return self


class RateFilters(BaseModel):
    billing_codes: list[str] = Field(default_factory=list)
    billing_code_types: list[str] = Field(default_factory=list)
    service_codes: list[str] = Field(default_factory=list)
    billing_classes: list[str] = Field(default_factory=list)
    negotiated_types: list[str] = Field(default_factory=list)
    limit: int | None = Field(default=5000, ge=1, le=100_000)


class UrlExtractionRequest(BaseModel):
    url: HttpUrl
    organization: OrganizationSelector
    filters: RateFilters = Field(default_factory=RateFilters)


class TocRequest(BaseModel):
    url: HttpUrl
    plan_name: str | None = None
    issuer_name: str | None = None
    plan_id: str | None = None
    plan_sponsor_name: str | None = None


@dataclass(frozen=True)
class ProviderMatch:
    provider_group_id: int | str | None
    npi: str | None
    tin_type: str | None
    tin_value: str | None
    business_name: str | None
    network_names: tuple[str, ...] = ()


@dataclass
class ExtractionResult:
    metadata: dict[str, Any]
    matched_provider_group_ids: set[int | str]
    matched_providers: list[ProviderMatch]
    rates: list[dict[str, Any]]
    truncated: bool = False


def normalize_id(value: str | int | None) -> str:
    if value is None:
        return ""
    return "".join(ch for ch in str(value) if ch.isalnum()).lower()
