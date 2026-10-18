from datetime import datetime, UTC
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
import re

State = Literal["found", "verified_absent", "not_observed", "inconclusive", "temporarily_unavailable", "blocked"]


def now():
    return datetime.now(UTC)


class Model(BaseModel):
    model_config = {"extra": "forbid", "str_strip_whitespace": True}


class Background(Model):
    subject: str = Field(min_length=2, max_length=180)
    specialization: str = Field(default="", max_length=180)


class RoleIntent(Model):
    raw_label: str = Field(min_length=2, max_length=120)
    concept_id: str | None = None
    confirmed: bool = False


class Skill(Model):
    label: str = Field(min_length=1, max_length=100)
    source: Literal["user"] = "user"


class Location(Model):
    preferred_regions: list[str] = Field(default_factory=list, max_length=5)
    relocate: bool = False
    strict: bool = False


class Profile(Model):
    profile_version: Literal[1] = 1
    background: Background
    role_intents: list[RoleIntent] = Field(default_factory=list, max_length=3)
    explore: bool = False
    career_stage: Literal["student", "graduate", "experienced", "career_changer"]
    skills: list[Skill] = Field(default_factory=list, max_length=20)
    experience_summary: str = Field(default="", max_length=500)
    preferred_industries: list[str] = Field(default_factory=list, max_length=5)
    certifications: list[str] = Field(default_factory=list, max_length=10)
    location: Location = Field(default_factory=Location)
    related_roles_enabled: bool = False

    @model_validator(mode="after")
    def intent_required(self):
        if not self.role_intents and not self.explore:
            raise ValueError("Choose at least one role or explore career options")
        return self

    def search_text(self):
        return "\n".join([
            "Roles: " + "; ".join(r.raw_label for r in self.role_intents),
            "Background: " + self.background.subject + "; " + self.background.specialization,
            "Skills: " + "; ".join(s.label for s in self.skills),
            "Experience: " + self.experience_summary,
            "Certifications: " + "; ".join(self.certifications),
        ])


class Identity(Model):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(max_length=254)

    @field_validator("email")
    @classmethod
    def email_shape(cls, value):
        value = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid email address")
        return value


class VisaContext(Model):
    route: str = Field(default="", max_length=80)
    expiry: str | None = None


class MatchRequest(Model):
    profile: Profile
    identity: Identity | None = None
    visa_context: VisaContext | None = None
    idempotency_key: str = Field(min_length=16, max_length=120)


class Claim(Model):
    id: str
    kind: Literal["activity", "function", "skill", "historical_role", "sponsorship_wording"]
    text: str
    concept_ids: list[str] = Field(default_factory=list)
    source_url: str = ""
    excerpt: str = ""
    observed_at: datetime | None = None
    source_kind: Literal["first_party", "ats", "third_party", "historical_import", "provided_csv", "demo"] = "historical_import"
    attribution: Literal["accepted", "unverified", "rejected"] = "unverified"
    state: State = "found"


class Channel(Model):
    kind: Literal["website", "email", "phone", "address", "careers", "linkedin_company", "linkedin_jobs", "linkedin_person", "job_board", "search_page"]
    value: str
    source_url: str = ""
    observed_at: datetime | None = None
    attribution: Literal["accepted", "unverified", "rejected"] = "unverified"
    state: State = "found"
    source_kind: Literal["first_party", "historical_import", "provided_csv"] = "historical_import"


class Membership(Model):
    route: str
    rating: str
    snapshot_date: str
    snapshot_id: str
    attribution: Literal["accepted", "unverified", "rejected"] = "unverified"


class Vacancy(Model):
    title: str
    url: str
    provider: str
    concept_ids: list[str] = Field(default_factory=list)
    observed_at: datetime | None = None
    closing_at: datetime | None = None
    verified: bool = False
    location: str = ""
    country: str = ""
    state: Literal["unverified", "open", "closed", "expired"] = "unverified"


class Employer(Model):
    id: str
    name: str
    town: str = ""
    county: str = ""
    company_number: str = ""
    identity_status: Literal["accepted", "unverified", "quarantined"] = "unverified"
    claims: list[Claim] = Field(default_factory=list)
    channels: list[Channel] = Field(default_factory=list)
    memberships: list[Membership] = Field(default_factory=list)
    vacancies: list[Vacancy] = Field(default_factory=list)
    workplace_locations: list[str] = Field(default_factory=list)
    source_namespace: str
    source_key: str
    is_demo: bool = False
    version: str = ""
    matching_basis: Literal["corroborated", "provided_csv"] = "corroborated"


class Feedback(Model):
    session_id: str
    employer_id: str
    event: Literal["impression", "save", "channel_click", "helpful", "not_relevant", "broken_link", "outreach", "reply", "application"]
    position: int | None = Field(default=None, ge=0, le=150)
    note: str = Field(default="", max_length=500)


class ShortlistRefresh(Model):
    profile: Profile | None = None
    visa_context: VisaContext | None = None
    idempotency_key: str = Field(min_length=16, max_length=120)


class SavedState(Model):
    saved: bool
