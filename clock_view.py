# -*- coding: utf-8 -*-
import os
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk  # type: ignore[reportMissingImports]
    PIL_AVAILABLE = True
except ImportError as e:
    PIL_AVAILABLE = False
    Image = None
    ImageDraw = None
    ImageFilter = None
    ImageFont = None
    ImageTk = None
    print(f"Warning: PIL not available ({e}). Install with: pip install Pillow")

class SevenSegmentClockView(tk.Canvas):
    """7セグメント風の時計を1枚のCanvasへ描画するクラス。"""

    DIGIT_SEGMENTS = {
        "0": (True, True, True, False, True, True, True),
        "1": (False, False, True, False, False, True, False),
        "2": (True, False, True, True, True, False, True),
        "3": (True, False, True, True, False, True, True),
        "4": (False, True, True, True, False, True, False),
        "5": (True, True, False, True, False, True, True),
        "6": (True, True, False, True, True, True, True),
        "7": (True, True, True, False, False, True, False),
        "8": (True, True, True, True, True, True, True),
        "9": (True, True, True, True, False, True, True),
    }

    DIGIT_WIDTH_UNIT = 1.0
    COLON_WIDTH_UNIT = 0.28
    GAP_UNIT = 0.12
    DIGIT_ASPECT = 1.82
    SECONDS_SMALL_SCALE = 0.5
    HIGH_QUALITY_SCALE = 3
    DATE_DISPLAY_TOP_PADDING = 4
    DATE_AREA_HEIGHT_RATIO = 0.26
    DATE_DIGIT_HEIGHT_AREA_RATIO = 0.82
    DATE_DIGIT_HEIGHT_CLOCK_RATIO = 0.36
    DATE_NORMAL_AREA_HEIGHT_RATIO = 0.36
    DATE_NORMAL_DIGIT_HEIGHT_AREA_RATIO = 0.90
    DATE_NORMAL_DIGIT_HEIGHT_CLOCK_RATIO = 0.78
    DATE_LABEL_FONT_RATIO = 0.52
    DATE_DIGIT_GAP_SCALE = 3.0
    DATE_SEGMENT_THICKNESS_RATIO = 0.145
    LED_GLOW_ALPHA = 190
    LED_GLOW_WIDE_RADIUS_RATIO = 0.014
    LED_GLOW_TIGHT_RADIUS_RATIO = 0.004
    HIDDEN_COLON = " "

    def __init__(self, master, segment_on, segment_off, background, **kwargs):
        super().__init__(
            master,
            bg=background,
            highlightthickness=0,
            bd=0,
            **kwargs,
        )
        self.segment_on = segment_on
        self.segment_off = segment_off
        self.background = background
        self.time_text = ""
        self.period_text = None
        self.seconds_size = "normal"
        self.date_info = None
        self.date_display = "off"
        self.date_size = "small"
        self.weekday_color_enabled = False
        self.high_quality_rendering = True
        self.led_glow_enabled = True
        self._rendered_image = None
        self._redraw_after_id = None
        self.bind("<Configure>", self._on_resize)

    def set_colors(self, segment_on, segment_off, background):
        self.segment_on = segment_on
        self.segment_off = segment_off
        self.background = background
        self.configure(bg=background)
        self.redraw()

    def set_seconds_size(self, seconds_size):
        self.seconds_size = seconds_size if seconds_size == "small" else "normal"
        self.redraw()

    def set_render_options(self, high_quality_rendering=True, led_glow_enabled=True):
        self.high_quality_rendering = bool(high_quality_rendering)
        self.led_glow_enabled = bool(led_glow_enabled)
        self.redraw()

    def set_time(
        self,
        time_text,
        period_text=None,
        seconds_size=None,
        date_info=None,
        date_display="off",
        weekday_color_enabled=False,
        date_size="small",
    ):
        if seconds_size is not None:
            normalized_seconds_size = seconds_size if seconds_size == "small" else "normal"
        else:
            normalized_seconds_size = self.seconds_size
        normalized_date_display = date_display if date_display in ("month_day", "month_day_weekday", "year_month_day", "full") else "off"
        normalized_date_size = "normal" if date_size == "normal" else "small"
        normalized_weekday_color_enabled = bool(weekday_color_enabled)

        if (
            self.time_text == time_text
            and self.period_text == period_text
            and self.seconds_size == normalized_seconds_size
            and self.date_info == date_info
            and self.date_display == normalized_date_display
            and self.date_size == normalized_date_size
            and self.weekday_color_enabled == normalized_weekday_color_enabled
        ):
            return

        self.time_text = time_text
        self.period_text = period_text
        self.seconds_size = normalized_seconds_size
        self.date_info = date_info
        self.date_display = normalized_date_display
        self.date_size = normalized_date_size
        self.weekday_color_enabled = normalized_weekday_color_enabled
        self.redraw()

    def redraw(self):
        self.delete("all")
        self.configure(bg=self.background)

        width = max(self.winfo_width(), 1)
        height = max(self.winfo_height(), 1)

        if not self.time_text or width < 20 or height < 20:
            return

        layout = self._calculate_layout(width, height)
        if layout is None:
            return

        if (self.high_quality_rendering or self.led_glow_enabled) and PIL_AVAILABLE:
            try:
                if self._redraw_high_quality(width, height, layout):
                    return
            except Exception:
                # Pillow描画に失敗しても、標準Canvas描画へ戻してアプリを継続する。
                pass

        self._draw_time_text(layout)
        if self.period_text:
            self._draw_period_text(layout)

        if layout["date_visible"]:
            self._draw_date(layout, width)

    def _on_resize(self, event):
        # リサイズ中に何度も再描画しすぎないよう、描画を少しだけまとめる。
        if self._redraw_after_id is not None:
            self.after_cancel(self._redraw_after_id)

        self._redraw_after_id = self.after_idle(self._redraw_from_idle)

    def _redraw_from_idle(self):
        self._redraw_after_id = None
        self.redraw()

    def _calculate_layout(self, canvas_width, canvas_height):
        date_visible = self.date_display != "off" and self.date_info is not None
        x_padding_ratio = 0.006 if date_visible else 0.035
        x_padding = max(1, min(10, canvas_width * x_padding_ratio))
        y_padding = max(1, min(5, canvas_height * 0.014))
        if date_visible and self.date_size == "normal":
            date_area_height = max(34, canvas_height * self.DATE_NORMAL_AREA_HEIGHT_RATIO)
            date_gap = max(5, min(14, canvas_height * 0.035))
        elif date_visible:
            date_area_height = max(22, min(58, canvas_height * self.DATE_AREA_HEIGHT_RATIO))
            date_gap = max(4, min(8, canvas_height * 0.035))
        else:
            date_area_height = 0
            date_gap = 0
        top_extra_padding = self.DATE_DISPLAY_TOP_PADDING if date_visible else 0

        available_width = canvas_width - x_padding * 2
        available_height = canvas_height - y_padding * 2 - date_area_height - date_gap - top_extra_padding

        if available_width <= 0 or available_height <= 0:
            return None

        main_text, seconds_text = self._split_time_text()
        small_seconds = bool(seconds_text) and self.seconds_size == "small"
        scale = self.SECONDS_SMALL_SCALE if small_seconds else 1.0

        if small_seconds:
            unit_width = self._text_unit_width(main_text) + self.GAP_UNIT + self._text_unit_width(seconds_text) * scale
        else:
            unit_width = self._text_unit_width(self.time_text)

        if unit_width <= 0:
            return None

        digit_width_by_width = available_width / unit_width
        digit_width_by_height = available_height / self.DIGIT_ASPECT
        digit_width = min(digit_width_by_width, digit_width_by_height)
        period_metrics = None

        # AM/PMは時計本体の左側に置くため、幅を含めて数字サイズを再計算する。
        for _ in range(3):
            digit_height = digit_width * self.DIGIT_ASPECT
            thickness = max(4, min(digit_width * 0.18, digit_height * 0.11))
            colon_width = digit_width * self.COLON_WIDTH_UNIT
            gap = digit_width * self.GAP_UNIT
            small_digit_width = digit_width * scale
            small_digit_height = digit_height * scale
            small_colon_width = colon_width * scale
            small_gap = gap * scale
            small_thickness = max(3, thickness * scale)

            if small_seconds:
                main_width = self._measure_text_width(main_text, digit_width, colon_width, gap)
                seconds_width = self._measure_text_width(seconds_text, small_digit_width, small_colon_width, small_gap)
                content_width = main_width + gap + seconds_width
            else:
                main_width = self._measure_text_width(self.time_text, digit_width, colon_width, gap)
                seconds_width = 0
                content_width = main_width

            period_metrics = self._make_period_metrics(digit_width, digit_height) if self.period_text else None
            period_width = period_metrics["width"] + period_metrics["gap"] if period_metrics else 0
            total_content_width = content_width + period_width

            if total_content_width <= available_width or total_content_width <= 0:
                break

            digit_width *= available_width / total_content_width

        content_left = x_padding + max(0, (available_width - total_content_width) / 2)
        if period_metrics:
            period_x = content_left
            start_x = period_x + period_metrics["width"] + period_metrics["gap"]
        else:
            period_x = None
            start_x = content_left

        start_y = y_padding + top_extra_padding + (available_height - digit_height) / 2
        seconds_y = start_y + digit_height - small_digit_height
        date_y = canvas_height - y_padding - date_area_height
        period_y = start_y + digit_height if period_metrics else None

        return {
            "x_padding": x_padding,
            "y_padding": y_padding,
            "start_x": start_x,
            "start_y": start_y,
            "seconds_y": seconds_y,
            "digit_width": digit_width,
            "digit_height": digit_height,
            "colon_width": colon_width,
            "gap": gap,
            "thickness": thickness,
            "small_seconds": small_seconds,
            "small_digit_width": small_digit_width,
            "small_digit_height": small_digit_height,
            "small_colon_width": small_colon_width,
            "small_gap": small_gap,
            "small_thickness": small_thickness,
            "main_text": main_text,
            "seconds_text": seconds_text,
            "main_width": main_width,
            "seconds_width": seconds_width,
            "period_metrics": period_metrics,
            "period_x": period_x,
            "period_y": period_y,
            "date_visible": date_visible,
            "date_area_height": date_area_height,
            "date_y": date_y,
        }

    def _split_time_text(self):
        if self.seconds_size != "small":
            return self.time_text, ""

        parts = self.time_text.split(":")
        if len(parts) != 3:
            return self.time_text, ""

        return f"{parts[0]}:{parts[1]}", f":{parts[2]}"
    
    def _is_colon_separator(self, char):
        return char == ":" or char == self.HIDDEN_COLON
    
    def _text_unit_width(self, text):
        visible_chars = [
            char for char in text
            if char in self.DIGIT_SEGMENTS or self._is_colon_separator(char)
        ]
        unit_width = 0

        for char in visible_chars:
            unit_width += self.COLON_WIDTH_UNIT if self._is_colon_separator(char) else self.DIGIT_WIDTH_UNIT

        if len(visible_chars) > 1:
            unit_width += self.GAP_UNIT * (len(visible_chars) - 1)

        return unit_width

    # def _text_unit_width(self, text):
    #     visible_chars = [char for char in text if char in self.DIGIT_SEGMENTS or char == ":"]
    #     unit_width = 0

    #     for char in visible_chars:
    #         unit_width += self.COLON_WIDTH_UNIT if char == ":" else self.DIGIT_WIDTH_UNIT

    #     if len(visible_chars) > 1:
    #         unit_width += self.GAP_UNIT * (len(visible_chars) - 1)

    #     return unit_width

    def _measure_text_width(self, text, digit_width, colon_width, gap):
        visible_chars = [
            char for char in text
            if char in self.DIGIT_SEGMENTS or self._is_colon_separator(char)
        ]
        width = 0

        for char in visible_chars:
            width += colon_width if self._is_colon_separator(char) else digit_width

        if len(visible_chars) > 1:
            width += gap * (len(visible_chars) - 1)

        return width


    # def _measure_text_width(self, text, digit_width, colon_width, gap):
    #     visible_chars = [char for char in text if char in self.DIGIT_SEGMENTS or char == ":"]
    #     width = 0

    #     for char in visible_chars:
    #         width += colon_width if char == ":" else digit_width

    #     if len(visible_chars) > 1:
    #         width += gap * (len(visible_chars) - 1)

    #     return width

    def _draw_time_text(self, layout):
        if layout["small_seconds"]:
            x = self._draw_text(
                layout["main_text"],
                layout["start_x"],
                layout["start_y"],
                layout["digit_width"],
                layout["digit_height"],
                layout["colon_width"],
                layout["gap"],
                layout["thickness"],
            )
            x += layout["gap"]
            self._draw_text(
                layout["seconds_text"],
                x,
                layout["seconds_y"],
                layout["small_digit_width"],
                layout["small_digit_height"],
                layout["small_colon_width"],
                layout["small_gap"],
                layout["small_thickness"],
            )
            return

        self._draw_text(
            self.time_text,
            layout["start_x"],
            layout["start_y"],
            layout["digit_width"],
            layout["digit_height"],
            layout["colon_width"],
            layout["gap"],
            layout["thickness"],
        )

    def _draw_text(self, text, x, y, digit_width, digit_height, colon_width, gap, thickness):
        for char in text:
            if self._is_colon_separator(char):
                if char == ":":
                    self._draw_colon(x, y, colon_width, digit_height, thickness)
                x += colon_width + gap
            elif char in self.DIGIT_SEGMENTS:
                self._draw_digit(char, x, y, digit_width, digit_height, thickness)
                x += digit_width + gap

        return x - gap

    # def _draw_text(self, text, x, y, digit_width, digit_height, colon_width, gap, thickness):
    #     for char in text:
    #         if char == ":":
    #             self._draw_colon(x, y, colon_width, digit_height, thickness)
    #             x += colon_width + gap
    #         elif char in self.DIGIT_SEGMENTS:
    #             self._draw_digit(char, x, y, digit_width, digit_height, thickness)
    #             x += digit_width + gap

    #     return x - gap

    def _draw_digit(self, digit, x, y, width, height, thickness):
        segment_states = self.DIGIT_SEGMENTS[digit]
        segment_points = (
            self._horizontal_segment(x, y + thickness / 2, width, thickness),
            self._vertical_segment(x + thickness / 2, y + thickness / 2, y + height / 2, thickness),
            self._vertical_segment(x + width - thickness / 2, y + thickness / 2, y + height / 2, thickness),
            self._horizontal_segment(x, y + height / 2, width, thickness),
            self._vertical_segment(x + thickness / 2, y + height / 2, y + height - thickness / 2, thickness),
            self._vertical_segment(x + width - thickness / 2, y + height / 2, y + height - thickness / 2, thickness),
            self._horizontal_segment(x, y + height - thickness / 2, width, thickness),
        )

        for points, is_on in zip(segment_points, segment_states):
            color = self.segment_on if is_on else self.segment_off
            self.create_polygon(points, fill=color, outline="")

    def _draw_colon(self, x, y, width, height, thickness):
        dot_size = max(4, thickness * 0.75)
        center_x = x + width / 2

        for center_y in (y + height * 0.35, y + height * 0.65):
            self.create_oval(
                center_x - dot_size / 2,
                center_y - dot_size / 2,
                center_x + dot_size / 2,
                center_y + dot_size / 2,
                fill=self.segment_on,
                outline="",
            )

    def _make_period_metrics(self, digit_width, digit_height):
        font_size = max(10, min(44, int(digit_height * 0.18)))
        font = tkfont.Font(family="Segoe UI", size=-font_size, weight="bold")
        return {
            "font": font,
            "font_size": font_size,
            "width": font.measure(self.period_text),
            "height": font.metrics("linespace"),
            "gap": max(5, digit_width * 0.12),
        }

    def _draw_period_text(self, layout):
        metrics = layout["period_metrics"]
        if not metrics:
            return

        self.create_text(
            layout["period_x"],
            layout["period_y"],
            text=self.period_text,
            fill=self.segment_on,
            anchor="sw",
            font=metrics["font"],
        )

    def _draw_date(self, layout, canvas_width):
        date_layout = self._calculate_date_layout(layout, canvas_width)
        if date_layout is None:
            return

        items = date_layout["items"]
        metrics = date_layout["metrics"]
        x = date_layout["x"]
        y = date_layout["y"]
        baseline_y = date_layout["baseline_y"]

        for index, (item_type, value) in enumerate(items):
            item_width = self._measure_date_item(
                item_type,
                value,
                metrics["digit_width"],
                metrics["colon_width"],
                metrics["gap"],
                metrics["font"],
            )

            if item_type == "digits":
                self._draw_text(
                    value,
                    x,
                    y,
                    metrics["digit_width"],
                    metrics["digit_height"],
                    metrics["colon_width"],
                    metrics["gap"],
                    metrics["thickness"],
                )
            else:
                self.create_text(
                    x,
                    baseline_y + metrics["label_y_offset"],
                    text=value,
                    fill=self._get_date_text_color(item_type),
                    anchor="sw",
                    font=metrics["font"],
                )

            x += item_width
            if index < len(items) - 1:
                x += metrics["item_gap"]

    def _calculate_date_layout(self, layout, canvas_width):
        items = self._get_date_items()
        if not items:
            return None

        available_width = canvas_width - layout["x_padding"] * 2
        if self.date_size == "normal":
            area_ratio = self.DATE_NORMAL_DIGIT_HEIGHT_AREA_RATIO
            clock_ratio = self.DATE_NORMAL_DIGIT_HEIGHT_CLOCK_RATIO
        else:
            area_ratio = self.DATE_DIGIT_HEIGHT_AREA_RATIO
            clock_ratio = self.DATE_DIGIT_HEIGHT_CLOCK_RATIO

        max_digit_height = max(
            10,
            min(
                layout["date_area_height"] * area_ratio,
                layout["digit_height"] * clock_ratio,
            ),
        )
        metrics = self._make_date_metrics(items, available_width, max_digit_height)
        x = (canvas_width - metrics["width"]) / 2
        content_height = max(metrics["digit_height"], metrics["label_height"])
        content_y = layout["date_y"] + max(0, (layout["date_area_height"] - content_height) / 2)
        baseline_y = min(layout["date_y"] + layout["date_area_height"], content_y + content_height)
        y = baseline_y - metrics["digit_height"]

        return {
            "items": items,
            "metrics": metrics,
            "x": x,
            "y": y,
            "baseline_y": baseline_y,
        }

    def _get_date_items(self):
        if self.date_info is None or self.date_display == "off":
            return []

        items = []

        if self.date_display in ("year_month_day", "full"):
            items.extend(
                [
                    ("digits", str(self.date_info["year"])),
                    ("text", "年"),
                ]
            )

        items.extend(
            [
                ("digits", str(self.date_info["month"])),
                ("text", "月"),
                ("digits", str(self.date_info["day"])),
                ("text", "日"),
            ]
        )

        if self.date_display in ("month_day_weekday", "full"):
            items.append(("weekday", f"{self.date_info['weekday']}曜日"))

        return items

    def _get_date_text_color(self, item_type):
        if item_type != "weekday" or not self.weekday_color_enabled or self.date_info is None:
            return self.segment_on

        if self.date_info["weekday"] == "土":
            return "#45a3ff"
        if self.date_info["weekday"] == "日":
            return "#ff5a5a"

        return self.segment_on

    def _make_date_metrics(self, items, available_width, digit_height):
        metrics = self._date_metrics_for_height(items, digit_height)

        if metrics["width"] > available_width and metrics["width"] > 0:
            digit_height *= available_width / metrics["width"]
            metrics = self._date_metrics_for_height(items, max(8, digit_height))

        return metrics

    def _date_metrics_for_height(self, items, digit_height):
        digit_width = digit_height / self.DIGIT_ASPECT
        colon_width = digit_width * self.COLON_WIDTH_UNIT
        gap = digit_width * self.GAP_UNIT * self.DATE_DIGIT_GAP_SCALE
        item_gap = max(3, digit_width * 0.18)
        thickness = max(2, digit_width * self.DATE_SEGMENT_THICKNESS_RATIO)
        font_size = max(8, int(digit_height * self.DATE_LABEL_FONT_RATIO))
        font = tkfont.Font(family="Yu Gothic", size=-font_size, weight="bold")
        label_height = font.metrics("linespace")
        label_y_offset = 0
        width = 0

        for index, (item_type, value) in enumerate(items):
            width += self._measure_date_item(item_type, value, digit_width, colon_width, gap, font)
            if index < len(items) - 1:
                width += item_gap

        return {
            "digit_width": digit_width,
            "digit_height": digit_height,
            "colon_width": colon_width,
            "gap": gap,
            "item_gap": item_gap,
            "thickness": thickness,
            "font": font,
            "font_size": font_size,
            "label_height": label_height,
            "label_y_offset": label_y_offset,
            "width": width,
        }

    def _measure_date_item(self, item_type, value, digit_width, colon_width, gap, font):
        if item_type == "digits":
            return self._measure_text_width(value, digit_width, colon_width, gap)

        return font.measure(value)

    def _redraw_high_quality(self, width, height, layout):
        render_scale = self._get_high_quality_scale(width, height)
        image_size = (max(1, width * render_scale), max(1, height * render_scale))
        background = self._color_to_rgba(self.background)
        image = Image.new("RGBA", image_size, background)

        if self.led_glow_enabled:
            glow_layer = Image.new("RGBA", image_size, (0, 0, 0, 0))
            self._draw_scene_pillow(glow_layer, layout, width, render_scale, glow_only=True)
            wide_blur_radius = max(4, int(min(width, height) * self.LED_GLOW_WIDE_RADIUS_RATIO * render_scale))
            tight_blur_radius = max(2, int(min(width, height) * self.LED_GLOW_TIGHT_RADIUS_RATIO * render_scale))
            image.alpha_composite(glow_layer.filter(ImageFilter.GaussianBlur(wide_blur_radius)))
            image.alpha_composite(glow_layer.filter(ImageFilter.GaussianBlur(tight_blur_radius)))

        self._draw_scene_pillow(image, layout, width, render_scale, glow_only=False)

        if render_scale != 1:
            resample_filter = getattr(Image, "Resampling", Image).BOX
            image = image.resize((width, height), resample_filter)
            if self.led_glow_enabled:
                # 発光で外側を光らせたあと、数字本体を等倍で描き直して輪郭を締める。
                self._draw_scene_pillow(image, layout, width, 1, glow_only=False)

        self._rendered_image = ImageTk.PhotoImage(image.convert("RGB"))
        self.create_image(0, 0, anchor=tk.NW, image=self._rendered_image)
        return True

    def _get_high_quality_scale(self, width, height):
        if not self.high_quality_rendering:
            return 1

        if width * height > 900000:
            return 2

        return self.HIGH_QUALITY_SCALE

    def _draw_scene_pillow(self, image, layout, canvas_width, render_scale, glow_only):
        draw = ImageDraw.Draw(image)
        self._draw_time_text_pillow(draw, layout, render_scale, glow_only)

        if self.period_text:
            self._draw_period_text_pillow(draw, layout, render_scale, glow_only)

        if layout["date_visible"]:
            self._draw_date_pillow(draw, layout, canvas_width, render_scale, glow_only)

    def _draw_time_text_pillow(self, draw, layout, render_scale, glow_only):
        if layout["small_seconds"]:
            x = self._draw_text_pillow(
                draw,
                layout["main_text"],
                layout["start_x"],
                layout["start_y"],
                layout["digit_width"],
                layout["digit_height"],
                layout["colon_width"],
                layout["gap"],
                layout["thickness"],
                render_scale,
                glow_only,
            )
            x += layout["gap"]
            self._draw_text_pillow(
                draw,
                layout["seconds_text"],
                x,
                layout["seconds_y"],
                layout["small_digit_width"],
                layout["small_digit_height"],
                layout["small_colon_width"],
                layout["small_gap"],
                layout["small_thickness"],
                render_scale,
                glow_only,
            )
            return

        self._draw_text_pillow(
            draw,
            self.time_text,
            layout["start_x"],
            layout["start_y"],
            layout["digit_width"],
            layout["digit_height"],
            layout["colon_width"],
            layout["gap"],
            layout["thickness"],
            render_scale,
            glow_only,
        )

    def _draw_text_pillow(self, draw, text, x, y, digit_width, digit_height, colon_width, gap, thickness, render_scale, glow_only):
        for char in text:
            if self._is_colon_separator(char):
                if char == ":":
                    self._draw_colon_pillow(draw, x, y, colon_width, digit_height, thickness, render_scale, glow_only)
                x += colon_width + gap
            elif char in self.DIGIT_SEGMENTS:
                self._draw_digit_pillow(draw, char, x, y, digit_width, digit_height, thickness, render_scale, glow_only)
                x += digit_width + gap

        return x - gap

    # def _draw_text_pillow(self, draw, text, x, y, digit_width, digit_height, colon_width, gap, thickness, render_scale, glow_only):
    #     for char in text:
    #         if char == ":":
    #             self._draw_colon_pillow(draw, x, y, colon_width, digit_height, thickness, render_scale, glow_only)
    #             x += colon_width + gap
    #         elif char in self.DIGIT_SEGMENTS:
    #             self._draw_digit_pillow(draw, char, x, y, digit_width, digit_height, thickness, render_scale, glow_only)
    #             x += digit_width + gap

    #     return x - gap

    def _draw_digit_pillow(self, draw, digit, x, y, width, height, thickness, render_scale, glow_only):
        segment_states = self.DIGIT_SEGMENTS[digit]
        segment_points = (
            self._horizontal_segment(x, y + thickness / 2, width, thickness),
            self._vertical_segment(x + thickness / 2, y + thickness / 2, y + height / 2, thickness),
            self._vertical_segment(x + width - thickness / 2, y + thickness / 2, y + height / 2, thickness),
            self._horizontal_segment(x, y + height / 2, width, thickness),
            self._vertical_segment(x + thickness / 2, y + height / 2, y + height - thickness / 2, thickness),
            self._vertical_segment(x + width - thickness / 2, y + height / 2, y + height - thickness / 2, thickness),
            self._horizontal_segment(x, y + height - thickness / 2, width, thickness),
        )

        for points, is_on in zip(segment_points, segment_states):
            if glow_only:
                if is_on:
                    draw.polygon(self._scale_points(points, render_scale), fill=self._color_to_rgba(self.segment_on, self.LED_GLOW_ALPHA))
                continue

            color = self.segment_on if is_on else self.segment_off
            draw.polygon(self._scale_points(points, render_scale), fill=self._color_to_rgba(color))

    def _draw_colon_pillow(self, draw, x, y, width, height, thickness, render_scale, glow_only):
        dot_size = max(4, thickness * 0.75)
        center_x = x + width / 2
        color = self._color_to_rgba(self.segment_on, self.LED_GLOW_ALPHA if glow_only else 255)

        for center_y in (y + height * 0.35, y + height * 0.65):
            bounds = self._scale_bounds(
                center_x - dot_size / 2,
                center_y - dot_size / 2,
                center_x + dot_size / 2,
                center_y + dot_size / 2,
                render_scale,
            )
            draw.ellipse(bounds, fill=color)

    def _draw_period_text_pillow(self, draw, layout, render_scale, glow_only):
        if glow_only or not layout["period_metrics"]:
            return

        metrics = layout["period_metrics"]
        font = self._get_pillow_font("Segoe UI", metrics["font_size"] * render_scale, bold=True)
        text_width, text_height = self._measure_pillow_text(draw, self.period_text, font)
        x = int(layout["period_x"] * render_scale)
        y = int(layout["period_y"] * render_scale - text_height)
        draw.text((x, y), self.period_text, fill=self._color_to_rgba(self.segment_on), font=font)

    def _draw_date_pillow(self, draw, layout, canvas_width, render_scale, glow_only):
        date_layout = self._calculate_date_layout(layout, canvas_width)
        if date_layout is None:
            return

        items = date_layout["items"]
        metrics = date_layout["metrics"]
        x = date_layout["x"]
        y = date_layout["y"]
        baseline_y = date_layout["baseline_y"]

        for index, (item_type, value) in enumerate(items):
            item_width = self._measure_date_item(
                item_type,
                value,
                metrics["digit_width"],
                metrics["colon_width"],
                metrics["gap"],
                metrics["font"],
            )

            if item_type == "digits":
                self._draw_text_pillow(
                    draw,
                    value,
                    x,
                    y,
                    metrics["digit_width"],
                    metrics["digit_height"],
                    metrics["colon_width"],
                    metrics["gap"],
                    metrics["thickness"],
                    render_scale,
                    glow_only,
                )
            elif not glow_only:
                font = self._get_pillow_font("Yu Gothic", metrics["font_size"] * render_scale, bold=True)
                text_width, text_height = self._measure_pillow_text(draw, value, font)
                text_x = int(x * render_scale)
                text_y = int((baseline_y + metrics["label_y_offset"]) * render_scale - text_height)
                draw.text((text_x, text_y), value, fill=self._color_to_rgba(self._get_date_text_color(item_type)), font=font)

            x += item_width
            if index < len(items) - 1:
                x += metrics["item_gap"]

    def _scale_points(self, points, render_scale):
        return [
            (int(round(points[index] * render_scale)), int(round(points[index + 1] * render_scale)))
            for index in range(0, len(points), 2)
        ]

    def _scale_bounds(self, left, top, right, bottom, render_scale):
        return (
            int(round(left * render_scale)),
            int(round(top * render_scale)),
            int(round(right * render_scale)),
            int(round(bottom * render_scale)),
        )

    def _color_to_rgba(self, color, alpha=255):
        try:
            red, green, blue = self.winfo_rgb(color)
            return red // 256, green // 256, blue // 256, alpha
        except tk.TclError:
            return 255, 255, 255, alpha

    def _get_pillow_font(self, family, size, bold=False):
        size = max(1, int(size))
        windows_fonts = Path(os.environ.get("WINDIR", "C:\\Windows")) / "Fonts"
        candidates = []

        if family == "Yu Gothic":
            candidates = ["YuGothB.ttc", "YuGothM.ttc", "meiryob.ttc", "meiryo.ttc"]
        elif family == "Segoe UI":
            candidates = ["segoeuib.ttf" if bold else "segoeui.ttf", "arialbd.ttf" if bold else "arial.ttf"]

        for font_name in candidates:
            font_path = windows_fonts / font_name
            if font_path.exists():
                try:
                    return ImageFont.truetype(str(font_path), size)
                except OSError:
                    pass

        return ImageFont.load_default()

    def _measure_pillow_text(self, draw, text, font):
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top

    def _horizontal_segment(self, x, center_y, width, thickness):
        left = x + thickness
        right = x + width - thickness
        half = thickness / 2

        return (
            left,
            center_y - half,
            x + thickness / 2,
            center_y,
            left,
            center_y + half,
            right,
            center_y + half,
            x + width - thickness / 2,
            center_y,
            right,
            center_y - half,
        )

    def _vertical_segment(self, center_x, top_y, bottom_y, thickness):
        half = thickness / 2

        return (
            center_x - half,
            top_y + thickness,
            center_x,
            top_y + thickness / 2,
            center_x + half,
            top_y + thickness,
            center_x + half,
            bottom_y - thickness,
            center_x,
            bottom_y - thickness / 2,
            center_x - half,
            bottom_y - thickness,
        )

