# -*- coding: utf-8 -*-
import json
import sys
from copy import deepcopy
from pathlib import Path


SETTINGS_FILE_NAME = "settings.json"
CUSTOM_THEME_SLOTS = ("custom1", "custom2", "custom3")

DEFAULT_SETTINGS = {
    "segment_on": "#ff9f1a",
    "segment_off": "#1f1f1f",
    "background": "#000000",
    "custom_segment_on": "#ff9f1a",
    "custom_segment_off": "#1f1f1f",
    "custom_background": "#000000",
    "always_on_top": False,
    "show_seconds": True,
    "use_24_hour": True,
    "clock_only_mode": False,
    "seconds_size": "normal",
    "date_size": "small",
    "theme": "custom",
    "custom_themes": {
        "custom1": {
            "segment_on": "#ff9f1a",
            "segment_off": "#1f1f1f",
            "background": "#000000",
        },
        "custom2": {
            "segment_on": "#45d8ff",
            "segment_off": "#102636",
            "background": "#02070c",
        },
        "custom3": {
            "segment_on": "#44ff70",
            "segment_off": "#0c2c18",
            "background": "#030503",
        },
    },
    "opacity_percent": 100,
    "date_display": "off",
    "weekday_color_enabled": False,
    "high_quality_rendering": False,
    "led_glow_enabled": False,
    "layout_preset": "custom",
    "start_with_windows": False,
    "auto_day_night_theme": False,
    "window_width": 680,
    "window_height": 220,
    "window_x": -1,
    "window_y": -1,
}

ALLOWED_VALUES = {
    "seconds_size": ("normal", "small"),
    "date_size": ("normal", "small"),
    "theme": ("custom", "orange", "blue", "green", "red"),
    "opacity_percent": (70, 80, 90, 100),
    "date_display": ("off", "month_day", "month_day_weekday", "year_month_day", "full"),
    "layout_preset": ("custom", "standard", "compact", "date", "clock_only"),
}


def get_settings_path():
    """設定ファイルの保存先を返す。exe化後はexeと同じ場所を使う。"""
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path(__file__).resolve().parent

    return base_dir / SETTINGS_FILE_NAME


def _normalize_settings(data):
    settings = deepcopy(DEFAULT_SETTINGS)

    if not isinstance(data, dict):
        return settings

    for key, default_value in DEFAULT_SETTINGS.items():
        value = data.get(key, default_value)

        if isinstance(default_value, bool):
            settings[key] = value if isinstance(value, bool) else default_value
        elif isinstance(default_value, int):
            if key in ALLOWED_VALUES:
                settings[key] = value if type(value) is int and value in ALLOWED_VALUES[key] else default_value
            elif key in ("window_x", "window_y"):
                settings[key] = value if type(value) is int else default_value
            else:
                settings[key] = value if type(value) is int and value > 0 else default_value
        elif isinstance(default_value, str):
            if key in ALLOWED_VALUES:
                settings[key] = value if value in ALLOWED_VALUES[key] else default_value
            else:
                settings[key] = value if isinstance(value, str) and value else default_value
        elif isinstance(default_value, dict):
            if key == "custom_themes":
                settings[key] = _normalize_custom_themes(value)

    return settings


def normalize_settings(data):
    """外部ファイルから読み込んだ設定も、安全な形に補正して返す。"""
    return _normalize_settings(data)


def _normalize_custom_themes(value):
    themes = deepcopy(DEFAULT_SETTINGS["custom_themes"])

    if not isinstance(value, dict):
        return themes

    for slot in CUSTOM_THEME_SLOTS:
        slot_value = value.get(slot)
        if not isinstance(slot_value, dict):
            continue

        for color_key in ("segment_on", "segment_off", "background"):
            color_value = slot_value.get(color_key)
            if isinstance(color_value, str) and color_value:
                themes[slot][color_key] = color_value

    return themes


def load_settings():
    """JSONから設定を読み込む。壊れている場合は初期値で起動する。"""
    path = get_settings_path()

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError, TypeError):
        return deepcopy(DEFAULT_SETTINGS)

    return _normalize_settings(data)


def save_settings(settings):
    """設定をJSONへ保存する。失敗時は呼び出し元で通知できるよう例外を渡す。"""
    normalized_settings = _normalize_settings(settings)
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(normalized_settings, file, ensure_ascii=False, indent=2)
