# -*- coding: utf-8 -*-
import tkinter as tk
import tkinter.font as tkfont


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
        self.weekday_color_enabled = False
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

    def set_time(
        self,
        time_text,
        period_text=None,
        seconds_size=None,
        date_info=None,
        date_display="off",
        weekday_color_enabled=False,
    ):
        if seconds_size is not None:
            normalized_seconds_size = seconds_size if seconds_size == "small" else "normal"
        else:
            normalized_seconds_size = self.seconds_size
        normalized_date_display = date_display if date_display in ("month_day", "year_month_day", "full") else "off"
        normalized_weekday_color_enabled = bool(weekday_color_enabled)

        if (
            self.time_text == time_text
            and self.period_text == period_text
            and self.seconds_size == normalized_seconds_size
            and self.date_info == date_info
            and self.date_display == normalized_date_display
            and self.weekday_color_enabled == normalized_weekday_color_enabled
        ):
            return

        self.time_text = time_text
        self.period_text = period_text
        self.seconds_size = normalized_seconds_size
        self.date_info = date_info
        self.date_display = normalized_date_display
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

        self._draw_time_text(layout)

        if self.period_text:
            self._draw_period_text(width, layout["period_bottom_y"], layout["x_padding"])

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
        date_area_height = max(18, min(52, canvas_height * 0.24)) if date_visible else 0
        date_gap = max(1, min(5, canvas_height * 0.018)) if date_visible else 0

        available_width = canvas_width - x_padding * 2
        available_height = canvas_height - y_padding * 2 - date_area_height - date_gap

        if available_width <= 0 or available_height <= 0:
            return None

        main_text, seconds_text = self._split_time_text()
        visible_chars = [char for char in self.time_text if char in self.DIGIT_SEGMENTS or char == ":"]
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

        start_x = (canvas_width - content_width) / 2
        start_y = y_padding + (available_height - digit_height) / 2
        seconds_y = start_y + digit_height - small_digit_height
        date_y = canvas_height - y_padding - date_area_height

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
            "period_bottom_y": start_y + digit_height,
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

    def _text_unit_width(self, text):
        visible_chars = [char for char in text if char in self.DIGIT_SEGMENTS or char == ":"]
        unit_width = 0

        for char in visible_chars:
            unit_width += self.COLON_WIDTH_UNIT if char == ":" else self.DIGIT_WIDTH_UNIT

        if len(visible_chars) > 1:
            unit_width += self.GAP_UNIT * (len(visible_chars) - 1)

        return unit_width

    def _measure_text_width(self, text, digit_width, colon_width, gap):
        visible_chars = [char for char in text if char in self.DIGIT_SEGMENTS or char == ":"]
        width = 0

        for char in visible_chars:
            width += colon_width if char == ":" else digit_width

        if len(visible_chars) > 1:
            width += gap * (len(visible_chars) - 1)

        return width

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
            if char == ":":
                self._draw_colon(x, y, colon_width, digit_height, thickness)
                x += colon_width + gap
            elif char in self.DIGIT_SEGMENTS:
                self._draw_digit(char, x, y, digit_width, digit_height, thickness)
                x += digit_width + gap

        return x - gap

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

    def _draw_period_text(self, canvas_width, bottom_y, x_padding):
        font_size = max(8, int(min(canvas_width, bottom_y) * 0.055))
        self.create_text(
            canvas_width - x_padding,
            bottom_y,
            text=self.period_text,
            fill=self.segment_on,
            anchor="se",
            font=("Segoe UI", font_size, "bold"),
        )

    def _draw_date(self, layout, canvas_width):
        items = self._get_date_items()
        if not items:
            return

        available_width = canvas_width - layout["x_padding"] * 2
        max_digit_height = max(10, min(layout["date_area_height"] * 0.72, layout["digit_height"] * 0.32))
        metrics = self._make_date_metrics(items, available_width, max_digit_height)
        x = (canvas_width - metrics["width"]) / 2
        y = layout["date_y"] + (layout["date_area_height"] - metrics["digit_height"]) / 2
        baseline_y = y + metrics["digit_height"]

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

        if self.date_display == "full":
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
        gap = digit_width * self.GAP_UNIT * 2.4
        item_gap = max(3, digit_width * 0.18)
        thickness = max(2, digit_width * 0.16)
        font_size = max(8, int(digit_height * 0.58))
        font = tkfont.Font(family="Yu Gothic", size=font_size, weight="bold")
        label_y_offset = max(2, digit_height * 0.16)
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
            "label_y_offset": label_y_offset,
            "width": width,
        }

    def _measure_date_item(self, item_type, value, digit_width, colon_width, gap, font):
        if item_type == "digits":
            return self._measure_text_width(value, digit_width, colon_width, gap)

        return font.measure(value)

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
