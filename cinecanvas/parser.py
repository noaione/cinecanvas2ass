"""
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import pyexpat
import re
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from os import PathLike
from pathlib import Path
from typing import Literal, TypeAlias, Union
from uuid import uuid4

from fontTools.ttLib import TTFont

TICK_MS = 4


class TextEffect(str, Enum):
    No = "none"
    Border = "border"
    Shadow = "shadow"


class TextScript(str, Enum):
    Normal = "normal"
    Super = "super"
    Sub = "sub"


class TextWeight(str, Enum):
    Normal = "normal"
    Bold = "bold"


class TextDirection(str, Enum):
    Horizontal = "horizontal"
    Vertical = "vertical"


class TextAlignH(str, Enum):
    Left = "left"
    Right = "right"
    Center = "center"

    def to_shift(self) -> int:
        if self == TextAlignH.Left:
            return -1
        elif self == TextAlignH.Right:
            return 1
        else:
            return 0


class TextAlignV(str, Enum):
    Top = "top"
    Bottom = "bottom"
    Center = "center"


class RubyPosition(str, Enum):
    Top = "before"
    Bottom = "after"


@dataclass
class CineTiming:
    hours: int = 0
    minutes: int = 0
    seconds: int = 0
    miliseconds: int = 0

    def to_timedelta(self) -> timedelta:
        return timedelta(
            hours=self.hours,
            minutes=self.minutes,
            seconds=self.seconds,
            milliseconds=self.miliseconds,
        )

    def to_miliseconds(self) -> int:
        return (self.hours * 3600 + self.minutes * 60 + self.seconds) * 1000 + self.miliseconds

    @classmethod
    def from_xml(cls, value: str) -> "CineTiming":
        value = value.strip()

        # --- ticks only ---
        if value.isdigit():
            as_int = int(value)
            if as_int < 0 or as_int > 249:
                raise ValueError(f"Tick timing must be between 0 and 249, got {as_int} instead")
            return CineTiming(0, 0, 0, as_int * TICK_MS)

        # --- HH:MM:SS:TTT ---
        if matching := re.match(r"(\d+):(\d+):(\d+):(\d+)", value):
            hh, mm, ss, ticks = map(int, matching.groups())
            if ticks < 0 or ticks > 249:
                raise ValueError(f"Tick timing must be between 0 and 249, got {ticks} instead")
            return CineTiming(hh, mm, ss, ticks)

        if matching := re.match(r"(\d+):(\d+):(\d+)\.(\d+)", value):
            hh, mm, ss, ms = matching.groups()
            ms = int(ms.ljust(3, "0")[:3])
            return CineTiming(int(hh), int(mm), int(ss), ms)
        raise ValueError(f"Invalid CineCanvas timing value: {value}")


@dataclass
class Color:
    r: int = field(kw_only=True)
    g: int = field(kw_only=True)
    b: int = field(kw_only=True)
    a: int = field(kw_only=True)

    @classmethod
    def from_hex(cls, hex_data: str) -> "Color":
        if len(hex_data) != 8:
            raise ValueError(f"Hex data must be 8 characters long, got {len(hex_data)} instead")

        aa, rr, gg, bb = hex_data[0:2], hex_data[2:4], hex_data[4:6], hex_data[6:8]
        aa = int(aa, 16)
        rr = int(rr, 16)
        gg = int(gg, 16)
        bb = int(bb, 16)
        return cls(r=rr, g=gg, b=bb, a=aa)

    @classmethod
    def white(cls) -> "Color":
        return cls(r=255, g=255, b=255, a=255)

    @classmethod
    def black(cls) -> "Color":
        return cls(r=0, g=0, b=0, a=255)


@dataclass
class Font:
    font: str = field(kw_only=True)
    """Should be linked to the `id` in the :class:`FontFile`"""
    color: Color = field(default_factory=Color.white, kw_only=True)
    effect: TextEffect = field(default=TextEffect.Shadow, kw_only=True)
    effect_color: Color = field(default_factory=Color.black, kw_only=True)
    italic: bool = field(default=False, kw_only=True)
    weight: TextWeight = field(default=TextWeight.Normal, kw_only=True)
    script: TextScript = field(default=TextScript.Normal, kw_only=True)
    size: int = field(default=42, kw_only=True)
    aspect_adjust: float = field(default=1.0, kw_only=True)
    underlined: bool = field(default=False, kw_only=True)
    spacing: float = field(default=0.0, kw_only=True)
    """
    Additional spacing between the rendered characters.
    The spacing is specified in units of em.

    Negative value must not be smaller compared to -1.0em
    """

    def __post_init__(self):
        if self.spacing < -1.0:
            raise ValueError(f"Spacing must not be less than -1.0em, got {self.spacing}")
        if self.aspect_adjust < 0.25 or self.aspect_adjust > 4.0:
            raise ValueError(f"Aspect adjust must be between 0.25-4.0, got {self.aspect_adjust} instead")


@dataclass
class FontOverride:
    font: str | None = field(default=None, kw_only=True)
    color: Color | None = field(default=None, kw_only=True)
    effect: TextEffect | None = field(default=None, kw_only=True)
    effect_color: Color | None = field(default=None, kw_only=True)
    italic: bool | None = field(default=None, kw_only=True)
    weight: TextWeight | None = field(default=None, kw_only=True)
    script: TextScript | None = field(default=None, kw_only=True)
    size: int | None = field(default=None, kw_only=True)
    aspect_adjust: float | None = field(default=None, kw_only=True)
    underlined: bool | None = field(default=None, kw_only=True)
    spacing: float | None = field(default=None, kw_only=True)
    """
    Additional spacing between the rendered characters.
    The spacing is specified in units of em.

    Negative value must not be smaller compared to -1.0em
    """

    def __post_init__(self):
        if self.spacing is not None and self.spacing < -1.0:
            raise ValueError(f"Spacing must not be less than -1.0em, got {self.spacing}")
        if self.aspect_adjust is not None and (self.aspect_adjust < 0.25 or self.aspect_adjust > 4.0):
            raise ValueError(f"Aspect adjust must be between 0.25-4.0, got {self.aspect_adjust} instead")

    def with_parent(self, parent: "Font") -> "Font":
        return Font(
            font=self.font if self.font is not None else parent.font,
            color=self.color if self.color is not None else parent.color,
            effect=self.effect if self.effect is not None else parent.effect,
            effect_color=self.effect_color if self.effect_color is not None else parent.effect_color,
            italic=self.italic if self.italic is not None else parent.italic,
            weight=self.weight if self.weight is not None else parent.weight,
            script=self.script if self.script is not None else parent.script,
            size=self.size if self.size is not None else parent.size,
            aspect_adjust=self.aspect_adjust if self.aspect_adjust is not None else parent.aspect_adjust,
            underlined=self.underlined if self.underlined is not None else parent.underlined,
            spacing=self.spacing if self.spacing is not None else parent.spacing,
        )


@dataclass
class FontFile:
    id: str = field(kw_only=True)
    """ID of the font"""
    uri: str = field(kw_only=True)
    """URL relative from the subtitle file"""
    _font_data: TTFont | None = field(init=False)

    def __post_init__(self):
        self._font_data = None

    def get_font(self, root_dir: Path) -> TTFont:
        if self._font_data is not None:
            return self._font_data

        ttf = TTFont(root_dir / self.uri)
        self._font_data = ttf
        return ttf


@dataclass
class ContentWithFont:
    content: str
    font: FontOverride = field(kw_only=True)


@dataclass
class ContentWithRuby:
    base: str
    ruby: str
    size: float = field(default=0.5, kw_only=True)
    position: RubyPosition = field(default=RubyPosition.Top, kw_only=True)
    offset: float = field(default=0.0, kw_only=True)
    spacing: float = field(default=0.0, kw_only=True)
    aspect_adjust: float = field(default=1.0, kw_only=True)

    def __post_init__(self):
        if self.offset < -1.0:
            raise ValueError(f"Offset must not be less than -1.0em, got {self.offset}")
        if self.spacing < -1.0:
            raise ValueError(f"Spacing must not be less than -1.0em, got {self.spacing}")
        if self.aspect_adjust < 0.25 or self.aspect_adjust > 4.0:
            raise ValueError(f"Aspect adjust must be between 0.25-4.0, got {self.aspect_adjust} instead")


@dataclass
class ContentSpacing:
    size: float = 0.5


@dataclass
class ContentHGroup:
    text: str


@dataclass
class ContentRotate:
    text: str
    direction: Literal["left", "right"] | None = field(kw_only=True, default=None)


Content: TypeAlias = str


ContentType: TypeAlias = Union[Content, ContentWithFont, ContentWithRuby, ContentSpacing, ContentHGroup, ContentRotate]


@dataclass
class Text:
    contents: list[ContentType]
    align_h: TextAlignH = field(default=TextAlignH.Center, kw_only=True)
    position_h: float = field(default=0.0, kw_only=True)
    align_v: TextAlignV = field(default=TextAlignV.Center, kw_only=True)
    position_v: float = field(default=0.0, kw_only=True)
    direction: TextDirection = field(default=TextDirection.Horizontal, kw_only=True)
    font: FontOverride | None = field(default=None, kw_only=True)


@dataclass
class Subtitle:
    contents: list[Text] = field(kw_only=True)
    start: CineTiming = field(kw_only=True)
    end: CineTiming = field(kw_only=True)
    number: str | None = field(default=None, kw_only=True)
    font: Font | None = field(default=None, kw_only=True)
    """Wrapping font overrides"""
    fade_in: CineTiming = field(default_factory=lambda: CineTiming(0, 0, 0, 80), kw_only=True)
    """Default timing is 20 ticks, or 80ms"""
    fade_out: CineTiming = field(default_factory=lambda: CineTiming(0, 0, 0, 80), kw_only=True)
    """Default timing is 20 ticks, or 80ms"""


@dataclass
class DCSubtitle:
    id: str = field(default_factory=lambda: str(uuid4()), kw_only=True)
    title: str = field(kw_only=True)
    reel: int = field(kw_only=True)
    language: str = field(kw_only=True)
    contents: list[Subtitle] = field(kw_only=True)
    fonts: list[FontFile] = field(kw_only=True)
    version: Literal["1.0", "1.1"] = field(kw_only=True, default="1.1")


@dataclass
class _ParserState:
    version: Literal["1.0", "1.1"] | None = None
    subtitle_id: str | None = None
    title: str | None = None
    reel: int | None = None
    language: str | None = None
    fonts: list[FontFile] = field(default_factory=list)
    contents: list[Subtitle] = field(default_factory=list)
    current_font_stack: list[Font] = field(default_factory=list)
    current_subtitle: Subtitle | None = None
    current_text_attrs: dict | None = None
    current_text_contents: list[ContentType] | None = None
    plain_buffer: list[str] = field(default_factory=list)
    inline_font_stack: list[FontOverride] = field(default_factory=list)
    inline_font_buffers: list[list[str]] = field(default_factory=list)
    current_simple_tag: str | None = None
    simple_buffer: list[str] = field(default_factory=list)
    # Ruby parsing state
    current_ruby_attrs: dict | None = None
    ruby_base_buffer: list[str] | None = None
    ruby_text_buffer: list[str] | None = None
    # Space/HGroup/Rotate parsing state
    current_space_size: float | None = None
    hgroup_buffer: list[str] | None = None
    rotate_buffer: list[str] | None = None
    rotate_direction: Literal["left", "right"] | None = None


_SIMPLE_TEXT_TAGS = {"SubtitleID", "MovieTitle", "ReelNumber", "Language"}


def _parse_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    value = value.strip().lower()
    if value in {"yes", "true", "1"}:
        return True
    if value in {"no", "false", "0"}:
        return False
    return None


def _parse_text_effect(value: str | None) -> TextEffect | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == TextEffect.Border.value:
        return TextEffect.Border
    if normalized == TextEffect.Shadow.value:
        return TextEffect.Shadow
    if normalized == TextEffect.No.value:
        return TextEffect.No
    return None


def _parse_text_weight(value: str | None) -> TextWeight | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == TextWeight.Bold.value:
        return TextWeight.Bold
    if normalized == TextWeight.Normal.value:
        return TextWeight.Normal
    return None


def _parse_text_script(value: str | None) -> TextScript | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == TextScript.Super.value:
        return TextScript.Super
    if normalized == TextScript.Sub.value:
        return TextScript.Sub
    if normalized == TextScript.Normal.value:
        return TextScript.Normal
    return None


def _parse_color(value: str | None) -> Color | None:
    if value is None:
        return None
    return Color.from_hex(value.strip())


def _parse_font_override(attrs: dict[str, str]) -> FontOverride:
    lowered = {key.lower(): value for key, value in attrs.items()}
    return FontOverride(
        font=lowered.get("face") or lowered.get("font") or lowered.get("family"),
        color=_parse_color(lowered.get("color")),
        effect=_parse_text_effect(lowered.get("effect")),
        effect_color=_parse_color(lowered.get("effectcolor")),
        italic=_parse_bool(lowered.get("italic")),
        weight=_parse_text_weight(lowered.get("weight")),
        script=_parse_text_script(lowered.get("script")),
        size=int(lowered["size"]) if "size" in lowered else None,
        aspect_adjust=float(lowered["aspectadjust"]) if "aspectadjust" in lowered else None,
        underlined=_parse_bool(lowered.get("underlined")),
        spacing=float(lowered["spacing"]) if "spacing" in lowered else None,
    )


def _parse_font(attrs: dict[str, str]) -> Font:
    lowered = {key.lower(): value for key, value in attrs.items()}
    font_id = attrs.get("Id") or attrs.get("ID") or attrs.get("id")
    if font_id is None:
        font_id = lowered.get("font") or lowered.get("face") or ""
    return Font(
        font=font_id,
        color=_parse_color(lowered.get("color")) or Color.white(),
        effect=_parse_text_effect(lowered.get("effect")) or TextEffect.Shadow,
        effect_color=_parse_color(lowered.get("effectcolor")) or Color.black(),
        italic=_parse_bool(lowered.get("italic")) or False,
        weight=_parse_text_weight(lowered.get("weight")) or TextWeight.Normal,
        script=_parse_text_script(lowered.get("script")) or TextScript.Normal,
        size=int(lowered["size"]) if "size" in lowered else 42,
        aspect_adjust=float(lowered["aspectadjust"]) if "aspectadjust" in lowered else 1.0,
        underlined=_parse_bool(lowered.get("underlined")) or False,
        spacing=float(lowered["spacing"]) if "spacing" in lowered else 0.0,
    )


def _parse_align_h(value: str | None) -> TextAlignH | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == TextAlignH.Left.value:
        return TextAlignH.Left
    if normalized == TextAlignH.Right.value:
        return TextAlignH.Right
    if normalized == TextAlignH.Center.value:
        return TextAlignH.Center
    return None


def _parse_align_v(value: str | None) -> TextAlignV | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized == TextAlignV.Top.value:
        return TextAlignV.Top
    if normalized == TextAlignV.Bottom.value:
        return TextAlignV.Bottom
    if normalized == TextAlignV.Center.value:
        return TextAlignV.Center
    return None


def _parse_direction(value: str | None) -> TextDirection:
    if value is None:
        return TextDirection.Horizontal
    normalized = value.strip().lower()
    if normalized == TextDirection.Horizontal.value:
        return TextDirection.Horizontal
    if normalized == TextDirection.Vertical.value:
        return TextDirection.Vertical
    return TextDirection.Horizontal


def _parse_ruby_position(value: str | None) -> RubyPosition:
    if value is None:
        return RubyPosition.Top
    normalized = value.strip().lower()
    if normalized == RubyPosition.Top.value:
        return RubyPosition.Top
    if normalized == RubyPosition.Bottom.value:
        return RubyPosition.Bottom
    return RubyPosition.Top


def _flush_plain_text(state: _ParserState) -> None:
    if state.current_text_contents is None:
        state.plain_buffer.clear()
        return
    if not state.plain_buffer:
        return
    text = "".join(state.plain_buffer)
    if text:
        state.current_text_contents.append(text)
    state.plain_buffer.clear()


def parse_cinecanvas_xml(xml_content: str) -> DCSubtitle:
    state = _ParserState()

    def handle_start(name: str, attrs: dict[str, str]) -> None:
        if name == "DCSubtitle":
            version = attrs.get("Version") or attrs.get("version")
            if version == "1.0":
                state.version = "1.0"
            elif version == "1.1":
                state.version = "1.1"
            return

        if name in _SIMPLE_TEXT_TAGS:
            state.current_simple_tag = name
            state.simple_buffer.clear()
            return

        if name == "LoadFont":
            font_id = attrs.get("Id") or attrs.get("ID") or attrs.get("id")
            uri = attrs.get("URI") or attrs.get("uri")
            if font_id and uri:
                state.fonts.append(FontFile(id=font_id, uri=uri))
            return

        if name == "Font":
            if state.current_text_contents is not None:
                _flush_plain_text(state)
                override = _parse_font_override(attrs)
                state.inline_font_stack.append(override)
                state.inline_font_buffers.append([])
            else:
                state.current_font_stack.append(_parse_font(attrs))
            return

        if name == "Subtitle":
            time_in = attrs.get("TimeIn") or attrs.get("timein")
            time_out = attrs.get("TimeOut") or attrs.get("timeout")
            if time_in is None or time_out is None:
                raise ValueError("Subtitle is missing TimeIn/TimeOut attributes")
            fade_up = attrs.get("FadeUpTime") or attrs.get("fadeuptime")
            fade_down = attrs.get("FadeDownTime") or attrs.get("fadedowntime")
            state.current_subtitle = Subtitle(
                contents=[],
                start=CineTiming.from_xml(time_in),
                end=CineTiming.from_xml(time_out),
                number=attrs.get("SpotNumber") or attrs.get("spotnumber"),
                font=state.current_font_stack[-1] if state.current_font_stack else None,
                fade_in=CineTiming.from_xml(fade_up) if fade_up is not None else CineTiming(0, 0, 0, 80),
                fade_out=CineTiming.from_xml(fade_down) if fade_down is not None else CineTiming(0, 0, 0, 80),
            )
            return

        if name == "Text":
            align_h = _parse_align_h(attrs.get("HAlign") or attrs.get("halign"))
            align_v = _parse_align_v(attrs.get("VAlign") or attrs.get("valign"))
            text_direction = _parse_direction(attrs.get("Direction") or attrs.get("direction"))
            position_h = attrs.get("HPosition") or attrs.get("hposition")
            position_v = attrs.get("VPosition") or attrs.get("vposition")
            position_h_value = float(position_h) if position_h is not None else 0.0
            position_v_value = float(position_v) if position_v is not None else 0.0
            state.current_text_attrs = {
                "align_h": align_h,
                "align_v": align_v,
                "position_h": position_h_value,
                "position_v": position_v_value,
                "direction": text_direction,
            }
            state.current_text_contents = []
            state.plain_buffer.clear()
            return

        if name == "Ruby":
            # Ruby is only valid inside Text element
            if state.current_text_contents is None:
                return
            _flush_plain_text(state)
            state.current_ruby_attrs = {}
            state.ruby_base_buffer = []
            state.ruby_text_buffer = None
            return

        if name == "Rb":
            # Rb is only valid inside Ruby element
            if state.ruby_base_buffer is None:
                return
            state.ruby_base_buffer.clear()
            return

        if name == "Rt":
            # Rt is only valid inside Ruby element
            if state.current_ruby_attrs is None:
                return
            state.ruby_text_buffer = []
            # Parse Rt attributes
            lowered = {key.lower(): value for key, value in attrs.items()}
            size = float(lowered.get("size", "0.5").rstrip("em"))
            position = _parse_ruby_position(lowered.get("position"))
            offset = float(lowered.get("offset", "0").rstrip("em"))
            spacing = float(lowered.get("spacing", "0").rstrip("em"))
            aspect_adjust = float(lowered.get("aspectadjust", "1.0"))
            state.current_ruby_attrs["size"] = size
            state.current_ruby_attrs["position"] = position
            state.current_ruby_attrs["offset"] = offset
            state.current_ruby_attrs["spacing"] = spacing
            state.current_ruby_attrs["aspect_adjust"] = aspect_adjust
            return

        if name == "Space":
            # Space is only valid inside Text element
            if state.current_text_contents is None:
                return
            _flush_plain_text(state)
            lowered = {key.lower(): value for key, value in attrs.items()}
            size = float(lowered.get("size", "0.5").rstrip("em"))
            state.current_text_contents.append(ContentSpacing(size=size))
            return

        if name == "HGroup":
            # HGroup is only valid inside Text element
            if state.current_text_contents is None:
                return
            _flush_plain_text(state)
            state.hgroup_buffer = []
            return

        if name == "Rotate":
            # Rotate is only valid inside Text element
            if state.current_text_contents is None:
                return
            _flush_plain_text(state)
            state.rotate_buffer = []
            lowered = {key.lower(): value for key, value in attrs.items()}
            direction = lowered.get("direction", "none").strip().lower()
            if direction in {"left", "right"}:
                state.rotate_direction = direction  # type: ignore
            else:
                state.rotate_direction = None
            return

    def handle_end(name: str) -> None:
        if name in _SIMPLE_TEXT_TAGS and state.current_simple_tag == name:
            value = "".join(state.simple_buffer).strip()
            if name == "SubtitleID":
                state.subtitle_id = value
            elif name == "MovieTitle":
                state.title = value
            elif name == "ReelNumber":
                state.reel = int(value)
            elif name == "Language":
                state.language = value
            state.simple_buffer.clear()
            state.current_simple_tag = None
            return

        if name == "Font":
            if state.current_text_contents is not None and state.inline_font_stack:
                buffer = state.inline_font_buffers.pop()
                override = state.inline_font_stack.pop()
                content_text = "".join(buffer)
                state.current_text_contents.append(ContentWithFont(content=content_text, font=override))
            elif state.current_font_stack:
                state.current_font_stack.pop()
            return

        if name == "Rb":
            # Rb end - just keep the buffer
            return

        if name == "Rt":
            # Rt end - just keep the buffer
            return

        if name == "Ruby":
            # Ruby end - create ContentWithRuby from accumulated data
            if state.current_text_contents is None or state.current_ruby_attrs is None:
                return
            if state.ruby_base_buffer is None or state.ruby_text_buffer is None:
                return
            base_text = "".join(state.ruby_base_buffer)
            ruby_text = "".join(state.ruby_text_buffer)
            ruby_content = ContentWithRuby(
                base=base_text,
                ruby=ruby_text,
                size=state.current_ruby_attrs.get("size", 0.5),
                position=state.current_ruby_attrs.get("position", RubyPosition.Top),
                offset=state.current_ruby_attrs.get("offset", 0.0),
                spacing=state.current_ruby_attrs.get("spacing", 0.0),
                aspect_adjust=state.current_ruby_attrs.get("aspect_adjust", 1.0),
            )
            state.current_text_contents.append(ruby_content)
            state.current_ruby_attrs = None
            state.ruby_base_buffer = None
            state.ruby_text_buffer = None
            return

        if name == "HGroup":
            # HGroup end - create ContentHGroup from accumulated data
            if state.current_text_contents is None or state.hgroup_buffer is None:
                return
            text = "".join(state.hgroup_buffer)
            state.current_text_contents.append(ContentHGroup(text=text))
            state.hgroup_buffer = None
            return

        if name == "Rotate":
            # Rotate end - create ContentRotate from accumulated data
            if state.current_text_contents is None or state.rotate_buffer is None:
                return
            text = "".join(state.rotate_buffer)
            state.current_text_contents.append(ContentRotate(text=text, direction=state.rotate_direction))
            state.rotate_buffer = None
            state.rotate_direction = None
            return

        if name == "Text":
            _flush_plain_text(state)
            attrs = state.current_text_attrs or {}
            text_obj = Text(
                contents=state.current_text_contents or [],
                align_h=attrs.get("align_h", TextAlignH.Center),
                align_v=attrs.get("align_v", TextAlignV.Center),
                position_h=float(attrs.get("position_h", 0.0)),
                position_v=float(attrs.get("position_v", 0.0)),
                direction=attrs.get("direction", TextDirection.Horizontal),
            )
            if state.current_subtitle is None:
                raise ValueError("Text element found outside Subtitle")
            state.current_subtitle.contents.append(text_obj)
            state.current_text_attrs = None
            state.current_text_contents = None
            return

        if name == "Subtitle":
            if state.current_subtitle is None:
                return
            state.contents.append(state.current_subtitle)
            state.current_subtitle = None
            return

    def handle_char(data: str) -> None:
        if state.current_simple_tag is not None:
            state.simple_buffer.append(data)
            return
        if state.current_text_contents is None:
            return
        # Ruby element character routing
        if state.ruby_text_buffer is not None:
            state.ruby_text_buffer.append(data)
            return
        if state.ruby_base_buffer is not None:
            state.ruby_base_buffer.append(data)
            return
        # HGroup element character routing
        if state.hgroup_buffer is not None:
            state.hgroup_buffer.append(data)
            return
        # Rotate element character routing
        if state.rotate_buffer is not None:
            state.rotate_buffer.append(data)
            return
        # Normal text routing (includes inline Font elements)
        if state.inline_font_stack:
            state.inline_font_buffers[-1].append(data)
        else:
            state.plain_buffer.append(data)

    parser = pyexpat.ParserCreate()
    parser.StartElementHandler = handle_start
    parser.EndElementHandler = handle_end
    parser.CharacterDataHandler = handle_char
    parser.Parse(xml_content, True)

    if state.title is None or state.reel is None or state.language is None:
        raise ValueError("Missing required DCSubtitle metadata")

    return DCSubtitle(
        id=state.subtitle_id or str(uuid4()),
        title=state.title,
        reel=state.reel,
        language=state.language,
        contents=state.contents,
        fonts=state.fonts,
        version=state.version or "1.1",
    )


def parse_cinecanvas_file(file_path: str | PathLike[str]) -> DCSubtitle:
    with Path(file_path).open("r", encoding="utf-8") as handle:
        return parse_cinecanvas_xml(handle.read())
