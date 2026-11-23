from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Block(Model):
    text: str = Field(min_length=1, max_length=52)
    role: Literal["title", "middle", "keyword", "ending"] = "middle"

    @field_validator("text")
    @classmethod
    def printable(cls, text):
        if (
            not text.strip()
            or any(ord(c) < 32 for c in text)
            or any(c in text for c in "{}\\")
        ):
            raise ValueError(
                "Use plain text without control characters, braces or backslashes."
            )
        return text.strip()


Style = Literal["clean_pop", "cinematic", "kinetic"]


class Task(Model):
    asset_pool: str = "."
    music_id: str
    duration_s: float = Field(default=20, ge=10, le=60)
    music_offset_s: float = Field(default=0, ge=0)
    fps: Literal[24, 25, 30, 60] = 30
    aspect_ratio: Literal["9:16"] = "9:16"
    resolution: Literal[720, 1080] = 1080
    cut_density: Literal["low", "medium", "high"] = "medium"
    variation_strength: float = Field(default=0.6, ge=0, le=1)
    random_seed: int = 1
    rotation_window_days: int = Field(default=7, ge=0, le=365)
    fit: Literal["contain_blur", "cover_crop"] = "contain_blur"
    text_style: Style = "clean_pop"
    text_blocks: list[Block] = Field(default_factory=list, max_length=8)
    manual_bpm: float | None = Field(default=None, ge=35, le=240)
    theme: str = ""
    tone: str = ""
    audience: str = ""
    language: str = "zh-CN"
    forbidden_terms: list[str] = Field(default_factory=list)


class Shot(Model):
    asset_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)
    source_in_frames: int = Field(ge=0)
    motion: Literal["in", "out"] = "in"
    transition: Literal["cut"] = "cut"


class TextEvent(Block):
    start_frame: int = Field(ge=0)
    duration_frames: int = Field(gt=0)
    template: Style


class Music(Model):
    asset_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    offset_frames: int = Field(ge=0)


class CutPoint(Model):
    frame: int = Field(gt=0)
    kind: Literal["detected", "manual", "uniform", "edited", "source_limit"]
    candidate_s: float | None = Field(default=None, ge=0)
    error_frames: float | None = Field(default=None, ge=0)


class Plan(Model):
    schema_version: Literal["1.0"] = "1.0"
    seed: int
    fps: Literal[24, 25, 30, 60]
    total_frames: int = Field(ge=240, le=3600)
    resolution: Literal[720, 1080]
    fit: Literal["contain_blur", "cover_crop"]
    music: Music
    shots: list[Shot] = Field(min_length=1, max_length=150)
    text_events: list[TextEvent] = Field(max_length=8)
    cut_points: list[CutPoint]
    history_snapshot: dict[str, int]
    warnings: list[str]
