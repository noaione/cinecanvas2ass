from os import PathLike
from pathlib import Path

from ass import Dialogue, Document, Style
from ass_tag_analyzer.ass_item.ass_item import AssTag, AssTagListEnding, AssTagListOpening, AssText
from ass_tag_analyzer.ass_item.ass_tag_alignment import Alignment
from ass_tag_analyzer.ass_item.ass_valid_tag.ass_valid_tag_alignment import AssValidTagAlignment
from ass_tag_analyzer.ass_item.ass_valid_tag.ass_valid_tag_alpha import (
    AssValidTagBackgroundAlpha,
    AssValidTagOutlineAlpha,
    AssValidTagPrimaryAlpha,
)
from ass_tag_analyzer.ass_item.ass_valid_tag.ass_valid_tag_border import AssValidTagBorder
from ass_tag_analyzer.ass_item.ass_valid_tag.ass_valid_tag_color import (
    AssValidTagBackgroundColor,
    AssValidTagOutlineColor,
    AssValidTagPrimaryColor,
)
from ass_tag_analyzer.ass_item.ass_valid_tag.ass_valid_tag_fade import AssValidTagFade
from ass_tag_analyzer.ass_item.ass_valid_tag.ass_valid_tag_font_scale import (
    AssValidTagFontXScale,
    AssValidTagFontYScale,
)
from ass_tag_analyzer.ass_item.ass_valid_tag.ass_valid_tag_general import (
    AssValidTagBold,
    AssValidTagFontName,
    AssValidTagFontSize,
    AssValidTagItalic,
    AssValidTagLetterSpacing,
    AssValidTagResetStyle,
    AssValidTagUnderline,
)
from ass_tag_analyzer.ass_item.ass_valid_tag.ass_valid_tag_position import AssValidTagPosition
from ass_tag_analyzer.ass_item.ass_valid_tag.ass_valid_tag_rotation import AssValidTagZRotation
from ass_tag_analyzer.ass_item.ass_valid_tag.ass_valid_tag_shadow import AssValidTagShadow
from ass_tag_analyzer.ass_parser import ass_item_to_text

from cinecanvas.parser import (
    Color,
    Content,
    ContentHGroup,
    ContentRotate,
    ContentSpacing,
    ContentType,
    ContentWithFont,
    ContentWithRuby,
    Font,
    FontOverride,
    RubyPosition,
    Text,
    TextAlignH,
    TextAlignV,
    TextDirection,
    TextEffect,
    TextWeight,
    parse_cinecanvas_file,
)


def get_alignment(text: Text) -> AssValidTagAlignment:
    match text.align_v:
        case TextAlignV.Center:
            # Only \an4, \an5, \an6
            base = 5 + text.align_h.to_shift()
            return AssValidTagAlignment(Alignment(base))
        case TextAlignV.Bottom:
            # Only \an1, \an2, \an3
            base = 2 + text.align_h.to_shift()
            return AssValidTagAlignment(Alignment(base))
        case TextAlignV.Top:
            # Only \an7, \an8, \an9
            base = 8 + text.align_h.to_shift()
            return AssValidTagAlignment(Alignment(base))
    return AssValidTagAlignment(Alignment(2))


def maybe_merge_font(base_font: Font | FontOverride | None = None, root_font: Font | None = None) -> Font:
    if base_font is None and root_font is not None:
        return root_font
    if isinstance(base_font, Font):
        return base_font
    if isinstance(base_font, FontOverride) and isinstance(root_font, FontOverride):
        return base_font.with_parent(root_font)
    if isinstance(base_font, FontOverride) and root_font is None:
        if base_font.font is not None:
            simple_upgrade = Font(font=base_font.font)  # Make dummy font
            return base_font.with_parent(simple_upgrade)  # Upgrade
    if isinstance(root_font, Font):
        return root_font
    raise ValueError("Missing font styling needed")


def color_to_ass_color(color: Color, effect: TextEffect = TextEffect.No) -> list[AssTag]:
    match effect:
        case TextEffect.Border:
            return [AssValidTagOutlineColor(color.r, color.g, color.b), AssValidTagOutlineAlpha(255 - color.a)]
        case TextEffect.Shadow:
            return [AssValidTagBackgroundColor(color.r, color.g, color.b), AssValidTagBackgroundAlpha(255 - color.a)]
        case _:
            return [AssValidTagPrimaryColor(True, color.r, color.g, color.b), AssValidTagPrimaryAlpha(255 - color.a)]


def calculate_effect_size(font_size: float, width: int, height: int) -> float:
    base_width = 1920
    base_height = 1080
    scale = min(width / base_width, height / base_height)

    base_ratio = 0.08
    min_size = 1.0
    max_ratio = 0.2

    effect_size = font_size * base_ratio * scale
    effect_size = max(effect_size, min_size)
    effect_size = min(effect_size, font_size * max_ratio)

    return round(effect_size, 2)


def calculate_positioning(
    position_x: float,
    position_y: float,
    width: int,
    height: int,
    align_h: TextAlignH,
    align_v: TextAlignV,
) -> tuple[float, float]:
    # position_x is percentage, basically 0-100% of the screen width
    # same with position_y
    match align_h:
        case TextAlignH.Left:
            clamped_x = max(0.0, min(float(position_x), 100.0))
            pos_x = (clamped_x / 100.0) * width
        case TextAlignH.Right:
            clamped_x = max(0.0, min(float(position_x), 100.0))
            pos_x = width - (clamped_x / 100.0) * width
        case TextAlignH.Center:
            clamped_x = max(-100.0, min(float(position_x), 100.0))
            pos_x = (width / 2.0) + (clamped_x / 100.0) * width
        case _:
            clamped_x = max(0.0, min(float(position_x), 100.0))
            pos_x = (clamped_x / 100.0) * width

    match align_v:
        case TextAlignV.Top:
            clamped_y = max(0.0, min(float(position_y), 100.0))
            pos_y = (clamped_y / 100.0) * height
        case TextAlignV.Bottom:
            clamped_y = max(0.0, min(float(position_y), 100.0))
            pos_y = height - (clamped_y / 100.0) * height
        case TextAlignV.Center:
            clamped_y = max(-100.0, min(float(position_y), 100.0))
            pos_y = (height / 2.0) + (clamped_y / 100.0) * height
        case _:
            clamped_y = max(0.0, min(float(position_y), 100.0))
            pos_y = (clamped_y / 100.0) * height

    return round(pos_x, 2), round(pos_y, 2)


def calculate_ruby_ass_offset(
    base_w: float,
    base_h: float,
    ruby_scale: float,
    num_ruby_chars: int,
    alignment: int = 2,  # Standard ASS Numpad Alignment (1-9)
    direction: TextDirection = TextDirection.Horizontal,
    ruby_pos: RubyPosition = RubyPosition.Top,
    buffer: float = 4.0,
    is_cjk_ruby: bool = False,
) -> tuple[float, float]:
    """Created by Gemini without too much modifications, looks shit so I'll probably rework this later"""

    # --- 1. Calculate Ruby Dimensions ---
    # In vertical mode, "Width" is the thickness, "Height" is the length
    if direction == TextDirection.Horizontal:
        ruby_h = base_h * ruby_scale
        aspect = 1.0 if is_cjk_ruby else 0.6
        ruby_w = (ruby_h * aspect) * num_ruby_chars
    else:
        # Vertical: "Height" of font becomes width of the column
        ruby_w = base_w * ruby_scale
        aspect = 1.0 if is_cjk_ruby else 0.6
        ruby_h = (ruby_w * aspect) * num_ruby_chars

    # --- 2. Determine Anchor Multipliers ---
    # Convert Numpad Alignment (1-9) to X/Y multipliers (0.0 to 1.0)
    # 7 8 9  (Top)    -> Y=0.0
    # 4 5 6  (Center) -> Y=0.5
    # 1 2 3  (Bottom) -> Y=1.0

    align_map = {
        1: (0.0, 1.0),
        2: (0.5, 1.0),
        3: (1.0, 1.0),
        4: (0.0, 0.5),
        5: (0.5, 0.5),
        6: (1.0, 0.5),
        7: (0.0, 0.0),
        8: (0.5, 0.0),
        9: (1.0, 0.0),
    }

    # Default to Bottom-Center (2) if invalid
    anchor_x_mult, anchor_y_mult = align_map.get(alignment, (0.5, 1.0))

    # --- 3. Calculate "Center-to-Center" Distance ---
    # We first align the centers of Base and Ruby, then shift.

    # Distance from Base Anchor to Base Center
    # If Anchor is Bottom-Left (0,1), Center is (W/2, -H/2) relative to it.
    base_center_x = base_w * (0.5 - anchor_x_mult)
    base_center_y = base_h * (0.5 - anchor_y_mult)

    # Current Ruby Center is now at (base_center_x, base_center_y)
    # We now apply the "Push" to move Ruby outside the Base box.

    push_x = 0.0
    push_y = 0.0

    if direction == TextDirection.Horizontal:
        # Push Up or Down
        # Total distance needed from center: (Base_H / 2) + Buffer + (Ruby_H / 2)
        dist = (base_h / 2) + buffer + (ruby_h / 2)

        if ruby_pos == RubyPosition.Top:  # Top
            push_y = -dist
        else:  # Bottom
            push_y = dist

    else:  # VERTICAL
        # Push Left or Right
        # Total distance needed from center: (Base_W / 2) + Buffer + (Ruby_W / 2)
        dist = (base_w / 2) + buffer + (ruby_w / 2)

        if ruby_pos == RubyPosition.Top:  # Right (Standard for Japanese Vert)
            push_x = dist
        else:  # Left
            push_x = -dist

    # --- 4. Final Coordinates ---
    # The Ruby's anchor point will likely match the Base's alignment.
    # So we are calculating the position of the Ruby's Anchor.

    final_x = base_center_x + push_x
    final_y = base_center_y + push_y

    return final_x, final_y


def make_directional_text(content: str, direction: TextDirection) -> AssText:
    content = content.replace("\n", "\\N")
    if direction == TextDirection.Vertical:
        # Split each characters and add \N for new line
        strings: list[str] = list(content)
        return AssText("".join(list(map(lambda char: f"{char}\\N", strings))))
    return AssText(content)


class ASSConverter:
    def __init__(self, input_file: str | PathLike[str], *, width: int, height: int) -> None:
        self._input_file = Path(input_file).resolve()
        self._root_dir = self._input_file.parent

        self._subtitle = parse_cinecanvas_file(self._input_file)
        self._doc = Document()
        self._init_styles()
        self._is_done = False

        self._w = width
        self._h = height

        self._doc.play_res_x = width
        self._doc.play_res_y = height
        self._doc.info.title = self._subtitle.title

        self._process_ruby = False

    def _init_styles(self):
        styles: list[Style] = []

        for font in self._subtitle.fonts:
            loaded = font.get_font(self._root_dir)
            # Get actual font name that is used in ASS file
            name = loaded["name"].getDebugName(4)
            new_style = Style(
                name=font.id, fontname=name, margin_l=0, margin_r=0, margin_v=0, alignment=2, outline=0, shadow=0
            )
            styles.append(new_style)
        self._doc.styles = styles

    @property
    def process_ruby(self) -> bool:
        """Process ruby text (Experimental)"""
        return self._process_ruby

    @process_ruby.setter
    def process_ruby(self, data: bool) -> None:
        if isinstance(data, bool):
            self._process_ruby = data

    def generate_tags_from_font(
        self, final_font: Font, root_font: Font | None = None, *, override_font_size: float | None = None
    ) -> tuple[list[AssTag], str]:
        color_text = color_to_ass_color(final_font.color)
        text_size = AssValidTagFontSize(override_font_size or float(final_font.size))

        merged_tags = [*color_text, text_size]
        final_font_name = None
        if root_font is not None:
            final_font_name = root_font.font
        if root_font is not None and root_font.font != final_font.font:
            merged_tags.append(AssValidTagFontName(final_font.font))
            final_font_name = final_font.font
        if not final_font_name:
            final_font_name = final_font.font
        match final_font.weight:
            case TextWeight.Normal:
                merged_tags.append(AssValidTagBold(0))
            case TextWeight.Bold:
                merged_tags.append(AssValidTagBold(1))
        merged_tags.append(AssValidTagItalic(final_font.italic))
        merged_tags.append(AssValidTagUnderline(final_font.underlined))
        if final_font.effect != TextEffect.No:
            effect_text = color_to_ass_color(final_font.effect_color, final_font.effect)
            merged_tags.extend(effect_text)
            eff_amount = calculate_effect_size(override_font_size or final_font.size, self._w, self._h)
            match final_font.effect:
                case TextEffect.Shadow:
                    merged_tags.append(AssValidTagShadow(eff_amount))
                case TextEffect.Border:
                    merged_tags.append(AssValidTagBorder(eff_amount))
        return merged_tags, final_font_name

    def format_text(
        self,
        content: ContentType,
        text: Text,
        *,
        base_font: Font | FontOverride | None = None,
        root_font: Font | None = None,
        force_direction: TextDirection | None = None,
        additional_tags: list[AssTag] | None = None,
    ) -> tuple[list[AssTag], AssText, str]:
        if isinstance(content, Content):
            final_font = maybe_merge_font(base_font, root_font)
            merged_tags, final_font_name = self.generate_tags_from_font(final_font, root_font)
            if final_font.spacing != 0.0:
                merged_tags.append(AssValidTagLetterSpacing(final_font.spacing))
            if final_font.aspect_adjust != 0.0:
                scaler = AssValidTagFontXScale if text.direction == TextDirection.Horizontal else AssValidTagFontYScale
                merged_tags.append(scaler(final_font.aspect_adjust * 100))  # fsc{x,y} at 100 for "normal"
            if isinstance(additional_tags, list):
                merged_tags.extend(additional_tags)
            return merged_tags, make_directional_text(content, force_direction or text.direction), final_font_name
        elif isinstance(content, ContentWithFont):
            final_font = maybe_merge_font(content.font, root_font)
            return self.format_text(content.content, text, base_font=final_font, root_font=root_font)
        elif isinstance(content, ContentWithRuby):
            return self.format_text(content.base, text, base_font=base_font, root_font=root_font)
        elif isinstance(content, ContentSpacing):
            # Just add spacing
            final_font = maybe_merge_font(base_font, root_font)
            merged_tags = [
                AssValidTagResetStyle(final_font.font),
                AssValidTagFontXScale(content.size * 100),
            ]
            return merged_tags, AssText("\\h"), final_font.font
        elif isinstance(content, ContentHGroup):
            return self.format_text(
                content.text, text, base_font=base_font, root_font=root_font, force_direction=TextDirection.Horizontal
            )
        elif isinstance(content, ContentRotate):
            rotation = 90 if content.direction == "left" else 270
            return self.format_text(
                content.text,
                text,
                base_font=base_font,
                root_font=root_font,
                additional_tags=[AssValidTagZRotation(False, rotation)],
            )
        else:
            raise TypeError(f"Unsupported type of {type(content)} found")

    def format_ruby_text(
        self,
        content: ContentType,
        text: Text,
        *,
        root_pos: tuple[float, float],
        alignment: int = 2,
        base_font: Font | FontOverride | None = None,
        root_font: Font | None = None,
    ) -> tuple[list[AssTag], AssText, str] | None:
        if not isinstance(content, ContentWithRuby):
            return None
        final_font = maybe_merge_font(base_font, root_font)
        font_size = final_font.size * content.size
        merged_tags, final_font_name = self.generate_tags_from_font(final_font, root_font, override_font_size=font_size)
        if content.spacing != 0.0:
            merged_tags.append(AssValidTagLetterSpacing(content.spacing))
        if content.aspect_adjust != 0.0:
            scaler = AssValidTagFontXScale if text.direction == TextDirection.Horizontal else AssValidTagFontYScale
            merged_tags.append(scaler(content.aspect_adjust * 100))  # fsc{x,y} at 100 for "normal"
        offseting = final_font.size / 100.0 * (content.offset * final_font.size)
        shift_x, shift_y = calculate_ruby_ass_offset(
            base_w=self._w / final_font.size * 0.8,
            base_h=self._h / final_font.size * 1.6,
            ruby_scale=content.size,
            num_ruby_chars=len(content.ruby),
            alignment=alignment,
            direction=text.direction,
            buffer=offseting,
        )
        root_x, root_y = root_pos
        merged_tags.append(AssValidTagPosition(root_x + shift_x, root_y + shift_y))
        return merged_tags, make_directional_text(content.ruby, text.direction), final_font_name

    def convert(self) -> Document:
        if self._is_done:
            return self._doc

        self._doc.events = []
        for subtitle in self._subtitle.contents:
            root_font = subtitle.font
            start_ms = subtitle.start.to_timedelta()
            end_ms = subtitle.end.to_timedelta()

            fade_in = subtitle.fade_in.to_miliseconds()
            fade_out = subtitle.fade_out.to_miliseconds()
            base_ass_tags = []
            if fade_in > 0 or fade_out > 0:
                base_ass_tags.append(AssValidTagFade(fade_in, fade_out))
            for idx, sub in enumerate(subtitle.contents, start=1):
                pos_x, pos_y = calculate_positioning(
                    sub.position_h,
                    sub.position_v,
                    self._w,
                    self._h,
                    sub.align_h,
                    sub.align_v,
                )

                alignment = get_alignment(sub)
                final_tags = [
                    AssTagListOpening(),
                    *base_ass_tags,
                    alignment,
                    AssValidTagPosition(pos_x, pos_y),
                    AssTagListEnding(),
                ]
                base_font = root_font if root_font is not None else sub.font

                prefer_style_name = None
                ruby_text_queues = []
                for text in sub.contents:
                    part_tags, text_itself, style_name = self.format_text(
                        text,
                        sub,
                        base_font=base_font,
                        root_font=root_font if root_font is not None else base_font,  # type: ignore
                    )
                    final_tags.append(AssTagListOpening())
                    final_tags.extend(part_tags)
                    final_tags.append(AssTagListEnding())
                    final_tags.append(text_itself)
                    if prefer_style_name is None:
                        prefer_style_name = style_name

                    ruby_text_info = self.format_ruby_text(
                        text,
                        sub,
                        root_pos=(pos_x, pos_y),
                        alignment=alignment.alignment.value,
                        base_font=base_font,
                        root_font=root_font if root_font is not None else base_font,  # type: ignore
                    )
                    if ruby_text_info is not None and self._process_ruby:
                        ruby_tags, ruby_itself, ruby_style_name = ruby_text_info

                        wrapped_tags = [
                            AssTagListOpening(),
                            alignment,
                            *ruby_tags,
                            AssTagListEnding(),
                            ruby_itself,
                        ]
                        ruby_text_queues.append(
                            Dialogue(
                                start=start_ms,
                                end=end_ms,
                                style=ruby_style_name or prefer_style_name,
                                text=ass_item_to_text(wrapped_tags),
                                layer=idx + 100,
                                effect="Ruby"
                            )
                        )

                into_line = ass_item_to_text(final_tags)
                self._doc.events.append(
                    Dialogue(start=start_ms, end=end_ms, style=prefer_style_name, text=into_line, layer=idx)
                )
                self._doc.events.extend(ruby_text_queues)
        self._is_done = True
        return self._doc

    def save(self, output_file: str | PathLike[str]) -> None:
        self.convert()

        output_file = Path(output_file)
        with output_file.open("w", encoding="utf-8-sig") as fp:
            self._doc.dump_file(fp)


# if __name__ == "__main__":
#     print("Running")
#     open_file = Path("signs_swe.xml")
#     processor = ASSConverter(open_file, width=1998, height=1080)
#     processor.save("signs_swe.ass")
