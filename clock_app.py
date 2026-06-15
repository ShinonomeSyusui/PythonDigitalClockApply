# -*- coding: utf-8 -*-
import json
import os
import threading
import tkinter as tk
import tkinter.font as tkfont
import sys
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox
from version import APP_VERSION

from clock_view import PIL_AVAILABLE, SevenSegmentClockView

try:
    import pystray
    from PIL import Image
    TRAY_AVAILABLE = True
except ImportError:
    pystray = None
    Image = None
    TRAY_AVAILABLE = False

from settings import (
    CUSTOM_THEME_SLOTS,
    DEFAULT_SETTINGS,
    get_settings_path,
    load_settings,
    normalize_settings,
    save_settings,
)


def get_resource_path(*parts):
    """PyInstaller実行時と通常実行時の両方でリソースの場所を返す。"""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base_dir = Path(sys._MEIPASS)
    else:
        base_dir = Path(__file__).resolve().parent

    return base_dir.joinpath(*parts)


APP_NAME = "7セグメント デジタル時計"
APP_VERSION = APP_VERSION
WINDOWS_APP_ID = "SevenSegmentClock.DesktopApp"

def set_windows_app_user_model_id():
    """WindowsのタスクバーでPython標準アイコンになりにくいよう、アプリIDを設定する。"""
    if os.name != "nt":
        return

    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(WINDOWS_APP_ID)
    except (AttributeError, OSError):
        pass

def set_windows_dpi_awareness():
    """WindowsにDPI対応アプリとして扱わせ、メニュー文字のにじみを抑える。"""
    if os.name != "nt":
        return

    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass

AUTO_DAY_THEME = "orange"
AUTO_NIGHT_THEME = "blue"
OPACITY_MIN_PERCENT = 50
OPACITY_MAX_PERCENT = 100
OPACITY_STEP_PERCENT = 5


THEMES = {
    "orange": {
        "label": "オレンジLED",
        "segment_on": "#ff9f1a",
        "segment_off": "#1f1f1f",
        "background": "#000000",
    },
    "blue": {
        "label": "ブルーLED",
        "segment_on": "#45d8ff",
        "segment_off": "#102636",
        "background": "#02070c",
    },
    "green": {
        "label": "グリーンLED",
        "segment_on": "#44ff70",
        "segment_off": "#0c2c18",
        "background": "#030503",
    },
    "red": {
        "label": "レッドLED",
        "segment_on": "#ff4545",
        "segment_off": "#2a1010",
        "background": "#050101",
    },
}


DATE_DISPLAY_LABELS = {
    "off": "非表示",
    "month_day": "月日",
    "month_day_weekday": "月日＋曜日",
    "year_month_day": "年月日",
    "full": "年月日＋曜日",
}

DATE_SIZE_LABELS = {
    "normal": "標準",
    "small": "小さめ",
}


LAYOUT_PRESETS = {
    "standard": {
        "label": "標準",
        "show_seconds": True,
        "seconds_size": "normal",
        "date_size": "small",
        "date_display": "off",
        "clock_only_mode": False,
        "always_on_top": False,
        "opacity_percent": 100,
    },
    "compact": {
        "label": "コンパクト",
        "show_seconds": False,
        "seconds_size": "normal",
        "date_size": "small",
        "date_display": "off",
        "clock_only_mode": False,
        "always_on_top": False,
        "opacity_percent": 100,
    },
    "date": {
        "label": "日付つき",
        "show_seconds": True,
        "seconds_size": "small",
        "date_size": "small",
        "date_display": "year_month_day",
        "clock_only_mode": False,
        "always_on_top": False,
        "opacity_percent": 100,
    },
    "clock_only": {
        "label": "時計のみ表示向け",
        "show_seconds": True,
        "seconds_size": "small",
        "date_size": "small",
        "date_display": "off",
        "clock_only_mode": True,
        "always_on_top": True,
        "opacity_percent": 90,
    },
}


class ClockApp(tk.Tk):
    """7セグメント風デジタル時計アプリ本体。"""

    def __init__(self):
        set_windows_app_user_model_id()
        set_windows_dpi_awareness()
        super().__init__()

        self.settings = load_settings()
        self._configure_ui_fonts()
        self._jst = timezone(timedelta(hours=9))
        self._last_display = None
        self._timer_after_id = None
        self._drag_offset_x = 0
        self._drag_offset_y = 0
        self._last_auto_theme_key = None
        self._tray_icon = None
        self._tray_thread = None
        self._is_quitting = False
        self._min_width = 340
        self._min_height = 105

        self.title(APP_NAME)
        self.minsize(self._min_width, self._get_min_height_for_date_display())
        self._restore_window_size()
        self._set_window_icon()

        self._ensure_valid_colors()

        self.always_on_top_var = tk.BooleanVar(value=self.settings["always_on_top"])
        self.show_seconds_var = tk.BooleanVar(value=self.settings["show_seconds"])
        self.use_24_hour_var = tk.BooleanVar(value=self.settings["use_24_hour"])
        self.clock_only_mode_var = tk.BooleanVar(value=self.settings["clock_only_mode"])
        self.seconds_size_var = tk.StringVar(value=self.settings["seconds_size"])
        self.date_size_var = tk.StringVar(value=self.settings["date_size"])
        self.theme_var = tk.StringVar(value=self.settings["theme"])
        self.opacity_percent_var = tk.IntVar(value=self.settings["opacity_percent"])
        self.date_display_var = tk.StringVar(value=self.settings["date_display"])
        self.weekday_color_enabled_var = tk.BooleanVar(value=self.settings["weekday_color_enabled"])
        self.layout_preset_var = tk.StringVar(value=self.settings["layout_preset"])
        self.start_with_windows_var = tk.BooleanVar(value=self.settings["start_with_windows"])
        self.close_to_tray_var = tk.BooleanVar(value=self.settings["close_to_tray"])
        self.auto_day_night_theme_var = tk.BooleanVar(value=self.settings["auto_day_night_theme"])
        self.high_quality_rendering_var = tk.BooleanVar(value=self.settings["high_quality_rendering"])
        self.led_glow_enabled_var = tk.BooleanVar(value=self.settings["led_glow_enabled"])

        self.configure(bg=self.settings["background"])
        self._create_menu()
        self._create_context_menu()
        self._create_clock_view()
        self._apply_window_options()
        self._apply_min_window_height()
        self._apply_clock_only_mode()
        self._apply_auto_day_night_theme(force=True)
        if self.settings["start_with_windows"]:
            self._apply_startup_registration(True, show_error=False)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        # self.bind("<Unmap>", self._on_window_unmap)
        self._setup_tray_icon()
        self._update_clock()

    def _on_tray_quit(self, icon=None, item=None):
        """トレイメニューからアプリを終了する。"""
        self.after(0, self._quit_app)

    def _on_tray_show(self, icon=None, item=None):
        """トレイメニューからウィンドウを表示する。"""
        self.after(0, self._show_window)

    def _on_tray_hide(self, icon=None, item=None):
        """トレイメニューからウィンドウを非表示にする。"""
        self.after(0, self._hide_window)

    def _show_window(self):
        """ウィンドウを表示して前面へ戻す。"""
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
            self._apply_window_options()
        except tk.TclError:
            pass

    def _hide_window(self):
        """ウィンドウを非表示にする。"""
        self.withdraw()

    # def _on_window_unmap(self, event):
    #     """ウィンドウ最小化時にトレイへ格納する。"""
    #     if event.widget is not self:
    #         return

    #     if self._is_quitting:
    #         return

    #     self.after(100, self._hide_to_tray_if_minimized)


    # def _hide_to_tray_if_minimized(self):
    #     """最小化状態であれば、タスクバーから隠してトレイへ格納する。"""
    #     if self._is_quitting:
    #         return

    #     try:
    #         if self.state() == "iconic":
    #             self.withdraw()
    #     except tk.TclError:
    #         pass

    def _on_tray_toggle_clock_only(self, icon=None, item=None):
        """トレイメニューから時計のみ表示を切り替える。"""
        self.after(0, self._toggle_clock_only_from_tray)


    def _toggle_clock_only_from_tray(self):
        """時計のみ表示を切り替える。"""
        self._set_clock_only_mode(not self.settings["clock_only_mode"])

    def _stop_tray_icon(self):
        """タスクトレイアイコンを停止する。"""
        if self._tray_icon is None:
            return
        
        try:
            self._tray_icon.stop()
        except Exception:
            pass
        self._tray_icon = None
        self._tray_thread = None

    def _configure_ui_fonts(self):
        """Tk標準メニューの文字を、Windowsで読みやすいフォントへ寄せる。"""
        try:
            scaling = max(1.0, self.winfo_fpixels("1i") / 72)
            self.tk.call("tk", "scaling", scaling)
        except tk.TclError:
            pass

        try:
            menu_font = tkfont.nametofont("TkMenuFont")
            menu_font.configure(family="Yu Gothic UI", size=10)
            self.option_add("*Menu.font", menu_font)
        except tk.TclError:
            pass

    def _create_menu(self):
        self.menu_bar = tk.Menu(self)

        settings_menu = tk.Menu(self.menu_bar, tearoff=False)
        settings_menu.add_command(label="色設定...", command=self._open_color_settings)
        theme_menu = tk.Menu(settings_menu, tearoff=False)
        theme_menu.add_radiobutton(
            label="カスタム（現在の色）",
            variable=self.theme_var,
            value="custom",
            command=self._on_theme_changed,
        )
        for theme_key, theme in THEMES.items():
            theme_menu.add_radiobutton(
                label=theme["label"],
                variable=self.theme_var,
                value=theme_key,
                command=self._on_theme_changed,
            )
        settings_menu.add_cascade(label="テーマ", menu=theme_menu)
        settings_menu.add_checkbutton(
            label="昼夜テーマ自動切替",
            variable=self.auto_day_night_theme_var,
            command=self._on_auto_day_night_theme_changed,
        )
        custom_theme_menu = tk.Menu(settings_menu, tearoff=False)
        for slot_index, slot_key in enumerate(CUSTOM_THEME_SLOTS, start=1):
            custom_theme_menu.add_command(
                label=f"自作テーマ{slot_index}を読込",
                command=lambda key=slot_key: self._load_custom_theme(key),
            )
            custom_theme_menu.add_command(
                label=f"現在の色を自作テーマ{slot_index}に保存",
                command=lambda key=slot_key: self._save_custom_theme(key),
            )
            if slot_index < len(CUSTOM_THEME_SLOTS):
                custom_theme_menu.add_separator()
        settings_menu.add_cascade(label="自作テーマ", menu=custom_theme_menu)
        settings_menu.add_separator()
        settings_menu.add_command(label="設定をエクスポート...", command=self._export_settings)
        settings_menu.add_command(label="設定をインポート...", command=self._import_settings)
        settings_menu.add_command(label="設定フォルダを開く", command=self._open_settings_folder)
        settings_menu.add_separator()
        reset_menu = tk.Menu(settings_menu, tearoff=False)
        reset_menu.add_command(label="色だけ初期化", command=self._reset_color_settings)
        reset_menu.add_command(label="表示設定だけ初期化", command=self._reset_display_settings)
        reset_menu.add_command(label="ウィンドウ位置だけ初期化", command=self._reset_window_placement)
        reset_menu.add_separator()
        reset_menu.add_command(label="すべて初期化", command=self._reset_all_settings)
        settings_menu.add_cascade(label="初期化", menu=reset_menu)
        settings_menu.add_checkbutton(
            label="Windows起動時に自動起動",
            variable=self.start_with_windows_var,
            command=self._on_startup_setting_changed,
        )
        settings_menu.add_checkbutton(
            label="閉じるボタンでタスクトレイに格納",
            variable=self.close_to_tray_var,
            command=self._on_close_to_tray_setting_changed,
        )
        settings_menu.add_command(label="画面中央へ戻す", command=self._center_window_now)
        settings_menu.add_separator()
        settings_menu.add_command(label="終了", command=self._on_close)
        self.menu_bar.add_cascade(label="設定", menu=settings_menu)

        view_menu = tk.Menu(self.menu_bar, tearoff=False)
        layout_preset_menu = tk.Menu(view_menu, tearoff=False)
        layout_preset_menu.add_radiobutton(
            label="カスタム（手動設定）",
            variable=self.layout_preset_var,
            value="custom",
            command=self._on_layout_preset_changed,
        )
        for preset_key, preset in LAYOUT_PRESETS.items():
            layout_preset_menu.add_radiobutton(
                label=preset["label"],
                variable=self.layout_preset_var,
                value=preset_key,
                command=self._on_layout_preset_changed,
            )
        view_menu.add_cascade(label="レイアウトプリセット", menu=layout_preset_menu)
        view_menu.add_separator()
        view_menu.add_checkbutton(
            label="最前面表示",
            variable=self.always_on_top_var,
            command=self._on_display_setting_changed,
        )
        view_menu.add_checkbutton(
            label="秒を表示",
            variable=self.show_seconds_var,
            command=self._on_display_setting_changed,
        )
        seconds_size_menu = tk.Menu(view_menu, tearoff=False)
        seconds_size_menu.add_radiobutton(
            label="標準",
            variable=self.seconds_size_var,
            value="normal",
            command=self._on_display_setting_changed,
        )
        seconds_size_menu.add_radiobutton(
            label="小さめ",
            variable=self.seconds_size_var,
            value="small",
            command=self._on_display_setting_changed,
        )
        view_menu.add_cascade(label="秒サイズ", menu=seconds_size_menu)
        view_menu.add_checkbutton(
            label="24時間表示（OFFで12時間）",
            variable=self.use_24_hour_var,
            command=self._on_display_setting_changed,
        )
        date_display_menu = tk.Menu(view_menu, tearoff=False)
        for value, label in DATE_DISPLAY_LABELS.items():
            date_display_menu.add_radiobutton(
                label=label,
                variable=self.date_display_var,
                value=value,
                command=self._on_display_setting_changed,
            )
        view_menu.add_cascade(label="日付表示", menu=date_display_menu)
        date_size_menu = tk.Menu(view_menu, tearoff=False)
        for value, label in DATE_SIZE_LABELS.items():
            date_size_menu.add_radiobutton(
                label=label,
                variable=self.date_size_var,
                value=value,
                command=self._on_display_setting_changed,
            )
        view_menu.add_cascade(label="日付サイズ", menu=date_size_menu)
        view_menu.add_checkbutton(
            label="曜日色（土曜青・日曜赤）",
            variable=self.weekday_color_enabled_var,
            command=self._on_display_setting_changed,
        )
        view_menu.add_command(label="透明度設定...", command=self._open_opacity_settings)
        view_menu.add_separator()
        view_menu.add_checkbutton(
            label="高画質描画",
            variable=self.high_quality_rendering_var,
            command=self._on_render_setting_changed,
        )
        view_menu.add_checkbutton(
            label="LED発光効果",
            variable=self.led_glow_enabled_var,
            command=self._on_render_setting_changed,
        )
        view_menu.add_separator()
        view_menu.add_checkbutton(
            label="時計のみ表示",
            variable=self.clock_only_mode_var,
            command=self._on_display_setting_changed,
        )
        self.menu_bar.add_cascade(label="表示", menu=view_menu)

        help_menu = tk.Menu(self.menu_bar, tearoff=False)
        help_menu.add_command(label="このアプリについて", command=self._show_about_dialog)
        self.menu_bar.add_cascade(label="ヘルプ", menu=help_menu)

        self.config(menu=self.menu_bar)

    def _create_context_menu(self):
        self.context_menu = tk.Menu(self, tearoff=False)
        self.context_menu.add_command(label="通常表示に戻す", command=lambda: self._set_clock_only_mode(False))
        self.context_menu.add_command(label="色設定...", command=self._open_color_settings)
        theme_menu = tk.Menu(self.context_menu, tearoff=False)
        theme_menu.add_radiobutton(
            label="カスタム（現在の色）",
            variable=self.theme_var,
            value="custom",
            command=self._on_theme_changed,
        )
        for theme_key, theme in THEMES.items():
            theme_menu.add_radiobutton(
                label=theme["label"],
                variable=self.theme_var,
                value=theme_key,
                command=self._on_theme_changed,
            )
        self.context_menu.add_cascade(label="テーマ", menu=theme_menu)
        custom_theme_menu = tk.Menu(self.context_menu, tearoff=False)
        for slot_index, slot_key in enumerate(CUSTOM_THEME_SLOTS, start=1):
            custom_theme_menu.add_command(
                label=f"自作テーマ{slot_index}を読込",
                command=lambda key=slot_key: self._load_custom_theme(key),
            )
            custom_theme_menu.add_command(
                label=f"現在の色を自作テーマ{slot_index}に保存",
                command=lambda key=slot_key: self._save_custom_theme(key),
            )
            if slot_index < len(CUSTOM_THEME_SLOTS):
                custom_theme_menu.add_separator()
        self.context_menu.add_cascade(label="自作テーマ", menu=custom_theme_menu)
        self.context_menu.add_checkbutton(
            label="昼夜テーマ自動切替",
            variable=self.auto_day_night_theme_var,
            command=self._on_auto_day_night_theme_changed,
        )
        self.context_menu.add_separator()
        layout_preset_menu = tk.Menu(self.context_menu, tearoff=False)
        layout_preset_menu.add_radiobutton(
            label="カスタム（手動設定）",
            variable=self.layout_preset_var,
            value="custom",
            command=self._on_layout_preset_changed,
        )
        for preset_key, preset in LAYOUT_PRESETS.items():
            layout_preset_menu.add_radiobutton(
                label=preset["label"],
                variable=self.layout_preset_var,
                value=preset_key,
                command=self._on_layout_preset_changed,
            )
        self.context_menu.add_cascade(label="レイアウトプリセット", menu=layout_preset_menu)
        self.context_menu.add_checkbutton(
            label="最前面表示",
            variable=self.always_on_top_var,
            command=self._on_display_setting_changed,
        )
        self.context_menu.add_checkbutton(
            label="秒を表示",
            variable=self.show_seconds_var,
            command=self._on_display_setting_changed,
        )
        seconds_size_menu = tk.Menu(self.context_menu, tearoff=False)
        seconds_size_menu.add_radiobutton(
            label="標準",
            variable=self.seconds_size_var,
            value="normal",
            command=self._on_display_setting_changed,
        )
        seconds_size_menu.add_radiobutton(
            label="小さめ",
            variable=self.seconds_size_var,
            value="small",
            command=self._on_display_setting_changed,
        )
        self.context_menu.add_cascade(label="秒サイズ", menu=seconds_size_menu)
        self.context_menu.add_checkbutton(
            label="24時間表示（OFFで12時間）",
            variable=self.use_24_hour_var,
            command=self._on_display_setting_changed,
        )
        date_display_menu = tk.Menu(self.context_menu, tearoff=False)
        for value, label in DATE_DISPLAY_LABELS.items():
            date_display_menu.add_radiobutton(
                label=label,
                variable=self.date_display_var,
                value=value,
                command=self._on_display_setting_changed,
            )
        self.context_menu.add_cascade(label="日付表示", menu=date_display_menu)
        date_size_menu = tk.Menu(self.context_menu, tearoff=False)
        for value, label in DATE_SIZE_LABELS.items():
            date_size_menu.add_radiobutton(
                label=label,
                variable=self.date_size_var,
                value=value,
                command=self._on_display_setting_changed,
            )
        self.context_menu.add_cascade(label="日付サイズ", menu=date_size_menu)
        self.context_menu.add_checkbutton(
            label="曜日色（土曜青・日曜赤）",
            variable=self.weekday_color_enabled_var,
            command=self._on_display_setting_changed,
        )
        self.context_menu.add_command(label="透明度設定...", command=self._open_opacity_settings)
        self.context_menu.add_separator()
        self.context_menu.add_checkbutton(
            label="高画質描画",
            variable=self.high_quality_rendering_var,
            command=self._on_render_setting_changed,
        )
        self.context_menu.add_checkbutton(
            label="LED発光効果",
            variable=self.led_glow_enabled_var,
            command=self._on_render_setting_changed,
        )
        self.context_menu.add_separator()
        self.context_menu.add_checkbutton(
            label="Windows起動時に自動起動",
            variable=self.start_with_windows_var,
            command=self._on_startup_setting_changed,
        )
        self.context_menu.add_command(label="設定をエクスポート...", command=self._export_settings)
        self.context_menu.add_command(label="設定をインポート...", command=self._import_settings)
        self.context_menu.add_command(label="設定フォルダを開く", command=self._open_settings_folder)
        self.context_menu.add_command(label="このアプリについて", command=self._show_about_dialog)
        self.context_menu.add_command(label="画面中央へ戻す", command=self._center_window_now)
        reset_menu = tk.Menu(self.context_menu, tearoff=False)
        reset_menu.add_command(label="色だけ初期化", command=self._reset_color_settings)
        reset_menu.add_command(label="表示設定だけ初期化", command=self._reset_display_settings)
        reset_menu.add_command(label="ウィンドウ位置だけ初期化", command=self._reset_window_placement)
        reset_menu.add_separator()
        reset_menu.add_command(label="すべて初期化", command=self._reset_all_settings)
        self.context_menu.add_cascade(label="初期化", menu=reset_menu)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="終了", command=self._on_close)

    def _create_clock_view(self):
        self.clock_view = SevenSegmentClockView(
            self,
            segment_on=self.settings["segment_on"],
            segment_off=self.settings["segment_off"],
            background=self.settings["background"],
        )
        self._apply_render_settings()
        self.clock_view.pack(fill=tk.BOTH, expand=True)
        self.clock_view.bind("<Button-3>", self._show_context_menu)
        self.clock_view.bind("<ButtonPress-1>", self._start_window_move)
        self.clock_view.bind("<B1-Motion>", self._move_window)
        self.bind("<Escape>", self._restore_normal_window)
        self.bind_all("<F11>", self._toggle_clock_only_shortcut)
        self.bind_all("<KeyPress-t>", self._toggle_always_on_top_shortcut)
        self.bind_all("<KeyPress-T>", self._toggle_always_on_top_shortcut)
        self.bind_all("<KeyPress-s>", self._toggle_seconds_shortcut)
        self.bind_all("<KeyPress-S>", self._toggle_seconds_shortcut)

    def _open_color_settings(self):
        original_settings = self.settings.copy()
        dialog = tk.Toplevel(self)
        dialog.title("色設定")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        frame = tk.Frame(dialog, padx=16, pady=14)
        frame.pack(fill=tk.BOTH, expand=True)

        color_rows = [
            ("segment_on", "セグメント点灯色"),
            ("segment_off", "セグメント消灯色"),
            ("background", "背景色"),
        ]
        swatches = {}

        for row_index, (key, label_text) in enumerate(color_rows):
            label = tk.Label(frame, text=label_text, anchor="w")
            label.grid(row=row_index, column=0, sticky="w", padx=(0, 12), pady=6)

            swatch = tk.Label(
                frame,
                width=8,
                relief=tk.SOLID,
                bd=1,
                bg=self.settings[key],
                text=self.settings[key],
            )
            swatch.grid(row=row_index, column=1, sticky="ew", padx=(0, 12), pady=6)
            swatches[key] = swatch

            button = tk.Button(
                frame,
                text="選択",
                command=lambda color_key=key: self._choose_color(color_key, swatches),
            )
            button.grid(row=row_index, column=2, sticky="ew", pady=6)

        button_frame = tk.Frame(frame)
        button_frame.grid(row=len(color_rows), column=0, columnspan=3, sticky="e", pady=(14, 0))

        tk.Button(
            button_frame,
            text="初期値に戻す",
            command=lambda: self._preview_default_colors(swatches),
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(
            button_frame,
            text="キャンセル",
            command=lambda: self._cancel_color_settings(dialog, original_settings),
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(
            button_frame,
            text="適用して保存",
            command=lambda: self._save_color_settings(dialog),
        ).pack(side=tk.LEFT)

        dialog.protocol("WM_DELETE_WINDOW", lambda: self._cancel_color_settings(dialog, original_settings))
        self._center_child_window(dialog)

    def _choose_color(self, color_key, swatches):
        _, selected_color = colorchooser.askcolor(
            color=self.settings[color_key],
            parent=self,
            title="色を選択",
        )

        if not selected_color:
            return

        self._disable_auto_day_night_theme()
        self.settings["theme"] = "custom"
        self.theme_var.set("custom")
        self.settings[color_key] = selected_color
        self._remember_custom_colors()
        swatches[color_key].configure(bg=selected_color, text=selected_color)
        self._apply_visual_settings()

    def _preview_default_colors(self, swatches):
        self._disable_auto_day_night_theme()
        self.settings["theme"] = "custom"
        self.theme_var.set("custom")
        for key in ("segment_on", "segment_off", "background"):
            self.settings[key] = DEFAULT_SETTINGS[key]
            swatches[key].configure(bg=DEFAULT_SETTINGS[key], text=DEFAULT_SETTINGS[key])

        self._remember_custom_colors()
        self._apply_visual_settings()

    def _cancel_color_settings(self, dialog, original_settings):
        self.settings = original_settings
        self._sync_menu_variables()
        self._apply_visual_settings()
        dialog.destroy()

    def _save_color_settings(self, dialog):
        if self._save_settings_with_notice():
            dialog.destroy()

    def _open_opacity_settings(self):
        original_opacity = self.settings["opacity_percent"]
        dialog = tk.Toplevel(self)
        dialog.withdraw()
        dialog.title("透明度設定")
        dialog.resizable(False, False)
        dialog.transient(self)        
        dialog.grab_set()

        try:
            dialog.attributes("-alpha", 1.0)
        except tk.TclError:
            pass

        frame = tk.Frame(dialog, padx=18, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        opacity_value_var = tk.IntVar(value=original_opacity)
        value_label = tk.Label(frame, text=f"{original_opacity}%", width=5, anchor="e")

        tk.Label(frame, text="透明度", anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 12))
        value_label.grid(row=0, column=1, sticky="e")

        scale = tk.Scale(
            frame,
            from_=OPACITY_MIN_PERCENT,
            to=OPACITY_MAX_PERCENT,
            resolution=OPACITY_STEP_PERCENT,
            orient=tk.HORIZONTAL,
            variable=opacity_value_var,
            showvalue=False,
            length=260,
            command=lambda value: self._preview_opacity_percent(value, value_label, dialog),
        )
        scale.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        guide_frame = tk.Frame(frame)
        guide_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        tk.Label(guide_frame, text=f"{OPACITY_MIN_PERCENT}%").pack(side=tk.LEFT)
        tk.Label(guide_frame, text=f"{OPACITY_MAX_PERCENT}%").pack(side=tk.RIGHT)

        button_frame = tk.Frame(frame)
        button_frame.grid(row=3, column=0, columnspan=2, sticky="e", pady=(14, 0))

        tk.Button(
            button_frame,
            text="100%に戻す",
            command=lambda: self._reset_opacity_preview(opacity_value_var, value_label, dialog),
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(
            button_frame,
            text="キャンセル",
            command=lambda: self._cancel_opacity_settings(dialog, original_opacity),
        ).pack(side=tk.LEFT, padx=(0, 8))
        tk.Button(
            button_frame,
            text="適用して保存",
            command=lambda: self._save_opacity_settings(dialog),
        ).pack(side=tk.LEFT)
        
        dialog.protocol("WM_DELETE_WINDOW", lambda: self._cancel_opacity_settings(dialog, original_opacity))
        self._center_child_window(dialog)

        if self.settings["always_on_top"]:
            dialog.attributes("-topmost", True)

        dialog.deiconify()
        dialog.lift()
        dialog.focus_force()

        # dialog.protocol("WM_DELETE_WINDOW", lambda: self._cancel_opacity_settings(dialog, original_opacity))
        # self._center_child_window(dialog)
        # self._keep_dialog_in_front(dialog)

    def _preview_opacity_percent(self, value, value_label, dialog=None):
        percent = self._normalize_opacity_percent(int(float(value)))
        self.settings["opacity_percent"] = percent
        self.opacity_percent_var.set(percent)
        value_label.configure(text=f"{percent}%")
        self._apply_window_options()
        self._keep_dialog_in_front(dialog)

    def _reset_opacity_preview(self, opacity_value_var, value_label, dialog=None):
        opacity_value_var.set(100)
        self._preview_opacity_percent(100, value_label, dialog)

    def _keep_dialog_in_front(self, dialog):
        if dialog is None:
            return

        try:
            if self.settings["always_on_top"]:
                dialog.attributes("-topmost", True)

            dialog.lift(self)
            dialog.focus_force()
        except tk.TclError:
            pass

    def _cancel_opacity_settings(self, dialog, original_opacity):
        self.settings["opacity_percent"] = original_opacity
        self.opacity_percent_var.set(original_opacity)
        self._apply_window_options()
        dialog.destroy()

    def _save_opacity_settings(self, dialog):
        self.settings["layout_preset"] = "custom"
        self.layout_preset_var.set("custom")
        self.settings["opacity_percent"] = self._normalize_opacity_percent(self.opacity_percent_var.get())
        self.opacity_percent_var.set(self.settings["opacity_percent"])
        self._apply_window_options()
        self._keep_dialog_in_front(dialog)
        if self._save_settings_with_notice():
            dialog.destroy()

    def _reset_all_settings(self):
        if not messagebox.askyesno("確認", "すべての設定を初期値に戻しますか？", parent=self):
            return

        self._apply_startup_registration(False, show_error=False)
        self.settings = deepcopy(DEFAULT_SETTINGS)
        self._sync_menu_variables()
        self._ensure_valid_colors()
        self._apply_visual_settings()
        self._apply_render_settings()
        self._apply_window_options()
        self._apply_min_window_height()
        self._restore_window_size()
        self._apply_clock_only_mode()
        self._center_window_now(save=False)
        self._force_clock_redraw()
        self._save_settings_with_notice()

    def _reset_color_settings(self):
        if not messagebox.askyesno("確認", "現在の色設定を初期値に戻しますか？", parent=self):
            return

        self.settings["theme"] = "custom"
        self.settings["auto_day_night_theme"] = DEFAULT_SETTINGS["auto_day_night_theme"]
        for key in ("segment_on", "segment_off", "background"):
            self.settings[key] = DEFAULT_SETTINGS[key]
        self._remember_custom_colors()
        self._sync_menu_variables()
        self._apply_visual_settings()
        self._force_clock_redraw()
        self._save_settings_with_notice()

    def _reset_display_settings(self):
        if not messagebox.askyesno("確認", "表示設定を初期値に戻しますか？", parent=self):
            return

        for key in (
            "always_on_top",
            "show_seconds",
            "use_24_hour",
            "clock_only_mode",
            "seconds_size",
            "date_size",
            "opacity_percent",
            "date_display",
            "weekday_color_enabled",
            "high_quality_rendering",
            "led_glow_enabled",
            "layout_preset",
        ):
            self.settings[key] = DEFAULT_SETTINGS[key]

        self._sync_menu_variables()
        self._apply_window_options()
        self._apply_min_window_height()
        self._apply_clock_only_mode()
        self._apply_render_settings()
        self._force_clock_redraw()
        self._save_settings_with_notice()

    def _reset_window_placement(self):
        if not messagebox.askyesno("確認", "ウィンドウのサイズと位置を初期値に戻しますか？", parent=self):
            return

        self.settings["window_width"] = DEFAULT_SETTINGS["window_width"]
        self.settings["window_height"] = DEFAULT_SETTINGS["window_height"]
        self.settings["window_x"] = DEFAULT_SETTINGS["window_x"]
        self.settings["window_y"] = DEFAULT_SETTINGS["window_y"]
        self._restore_window_size()
        self._center_window_now()

    def _export_settings(self):
        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="設定をエクスポート",
            defaultextension=".json",
            filetypes=(("JSONファイル", "*.json"), ("すべてのファイル", "*.*")),
            initialfile="SevenSegmentClock_settings.json",
        )
        if not file_path:
            return

        self._remember_window_size()
        settings_to_write = normalize_settings(self.settings)

        try:
            with Path(file_path).open("w", encoding="utf-8") as file:
                json.dump(settings_to_write, file, ensure_ascii=False, indent=2)
        except OSError as error:
            messagebox.showwarning(
                "エクスポートエラー",
                f"設定を書き出せませんでした。\n\n詳細:\n{error}",
                parent=self,
            )
            return

        messagebox.showinfo("設定エクスポート", "設定を書き出しました。", parent=self)

    def _import_settings(self):
        file_path = filedialog.askopenfilename(
            parent=self,
            title="設定をインポート",
            filetypes=(("JSONファイル", "*.json"), ("すべてのファイル", "*.*")),
        )
        if not file_path:
            return

        try:
            with Path(file_path).open("r", encoding="utf-8") as file:
                loaded_data = json.load(file)
        except (OSError, json.JSONDecodeError, TypeError) as error:
            messagebox.showwarning(
                "インポートエラー",
                f"設定ファイルを読み込めませんでした。\n\n詳細:\n{error}",
                parent=self,
            )
            return

        if not messagebox.askyesno("確認", "現在の設定を読み込んだ設定で置き換えますか？", parent=self):
            return

        self.settings = normalize_settings(loaded_data)
        self._sync_menu_variables()
        self._ensure_valid_colors()
        self._apply_visual_settings()
        self._apply_render_settings()
        self._apply_window_options()
        self._apply_min_window_height()
        self._restore_window_size()
        self._apply_clock_only_mode()
        self._apply_startup_registration(self.settings["start_with_windows"], show_error=False)
        self._apply_auto_day_night_theme(force=True)
        self._force_clock_redraw()

        if self._save_settings_with_notice():
            messagebox.showinfo("設定インポート", "設定を読み込みました。", parent=self)

    def _open_settings_folder(self):
        folder_path = get_settings_path().parent
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
            os.startfile(str(folder_path))
        except (OSError, AttributeError) as error:
            messagebox.showwarning(
                "設定フォルダ",
                f"設定フォルダを開けませんでした。\n\n場所:\n{folder_path}\n\n詳細:\n{error}",
                parent=self,
            )

    def _show_about_dialog(self):
        settings_path = get_settings_path()
        messagebox.showinfo(
            "このアプリについて",
            (
                f"{APP_NAME}\n"
                f"Version {APP_VERSION}\n\n"
                "Tkinter製の7セグメント風デジタル時計です。\n\n"
                f"設定ファイル:\n{settings_path}\n\n"
                "ショートカット:\n"
                "F11: 時計のみ表示切替\n"
                "T: 最前面表示切替\n"
                "S: 秒表示切替"
            ),
            parent=self,
        )

    def _toggle_clock_only_shortcut(self, event=None):
        self.clock_only_mode_var.set(not self.settings["clock_only_mode"])
        self._on_display_setting_changed()
        return "break"

    def _toggle_always_on_top_shortcut(self, event=None):
        self.always_on_top_var.set(not self.settings["always_on_top"])
        self._on_display_setting_changed()
        return "break"

    def _toggle_seconds_shortcut(self, event=None):
        self.show_seconds_var.set(not self.settings["show_seconds"])
        self._on_display_setting_changed()
        return "break"

    def _on_auto_day_night_theme_changed(self):
        enabled = self.auto_day_night_theme_var.get()
        if enabled and self.settings["theme"] == "custom":
            self._remember_custom_colors()

        self.settings["auto_day_night_theme"] = enabled
        self._last_auto_theme_key = None

        if enabled:
            self._apply_auto_day_night_theme(force=True)
            self._force_clock_redraw()

        self._save_settings_with_notice()

    def _apply_auto_day_night_theme(self, now=None, force=False):
        if not self.settings["auto_day_night_theme"]:
            return

        now = now or datetime.now(tz=self._jst)
        theme_key = AUTO_DAY_THEME if 6 <= now.hour < 18 else AUTO_NIGHT_THEME
        if not force and theme_key == self._last_auto_theme_key:
            return

        theme = THEMES[theme_key]
        self.settings["theme"] = theme_key
        self.theme_var.set(theme_key)
        self.settings["segment_on"] = theme["segment_on"]
        self.settings["segment_off"] = theme["segment_off"]
        self.settings["background"] = theme["background"]
        self._last_auto_theme_key = theme_key
        self._last_display = None
        self._apply_visual_settings()

    def _disable_auto_day_night_theme(self):
        self.settings["auto_day_night_theme"] = False
        self.auto_day_night_theme_var.set(False)
        self._last_auto_theme_key = None

    def _on_display_setting_changed(self):
        self.settings["layout_preset"] = "custom"
        self.settings["always_on_top"] = self.always_on_top_var.get()
        self.settings["show_seconds"] = self.show_seconds_var.get()
        self.settings["use_24_hour"] = self.use_24_hour_var.get()
        self.settings["clock_only_mode"] = self.clock_only_mode_var.get()
        self.settings["seconds_size"] = self._normalize_seconds_size(self.seconds_size_var.get())
        self.settings["date_size"] = self._normalize_date_size(self.date_size_var.get())
        self.settings["opacity_percent"] = self._normalize_opacity_percent(self.opacity_percent_var.get())
        self.settings["date_display"] = self._normalize_date_display(self.date_display_var.get())
        self.settings["weekday_color_enabled"] = self.weekday_color_enabled_var.get()
        self.layout_preset_var.set("custom")
        self.seconds_size_var.set(self.settings["seconds_size"])
        self.date_size_var.set(self.settings["date_size"])
        self.opacity_percent_var.set(self.settings["opacity_percent"])
        self.date_display_var.set(self.settings["date_display"])

        self._apply_window_options()
        self._apply_min_window_height()
        self._apply_clock_only_mode()
        self._apply_render_settings()
        self._force_clock_redraw()
        self._save_settings_with_notice()

    def _on_render_setting_changed(self):
        if not PIL_AVAILABLE:
            messagebox.showwarning(
                "高画質描画",
                "高画質描画にはPillowが必要です。\n\nVSCodeのPython環境を確認するか、次のコマンドで依存関係を入れてください。\npython -m pip install -r requirements.txt",
                parent=self,
            )
            self.high_quality_rendering_var.set(False)
            self.led_glow_enabled_var.set(False)
            self.settings["high_quality_rendering"] = False
            self.settings["led_glow_enabled"] = False
            self._apply_render_settings()
            self._save_settings_with_notice()
            return

        self.settings["high_quality_rendering"] = self.high_quality_rendering_var.get()
        self.settings["led_glow_enabled"] = self.led_glow_enabled_var.get()
        self._apply_render_settings()
        self._force_clock_redraw()
        self._save_settings_with_notice()

    def _on_layout_preset_changed(self):
        preset_key = self.layout_preset_var.get()
        if preset_key not in LAYOUT_PRESETS:
            self.settings["layout_preset"] = "custom"
            self.layout_preset_var.set("custom")
            self._save_settings_with_notice()
            return

        self.settings["layout_preset"] = preset_key
        for key, value in LAYOUT_PRESETS[preset_key].items():
            if key != "label":
                self.settings[key] = value

        self._sync_menu_variables()
        self._apply_window_options()
        self._apply_min_window_height()
        self._apply_clock_only_mode()
        self._apply_render_settings()
        self._force_clock_redraw()
        self._save_settings_with_notice()

    def _save_custom_theme(self, slot_key):
        if slot_key not in CUSTOM_THEME_SLOTS:
            return

        self.settings["custom_themes"][slot_key] = {
            "segment_on": self.settings["segment_on"],
            "segment_off": self.settings["segment_off"],
            "background": self.settings["background"],
        }
        self._remember_custom_colors()
        slot_number = CUSTOM_THEME_SLOTS.index(slot_key) + 1
        if self._save_settings_with_notice():
            messagebox.showinfo("自作テーマ", f"自作テーマ{slot_number}に現在の色を保存しました。", parent=self)

    def _load_custom_theme(self, slot_key):
        if slot_key not in CUSTOM_THEME_SLOTS:
            return

        theme = self.settings["custom_themes"].get(slot_key)
        if not isinstance(theme, dict):
            return

        self._disable_auto_day_night_theme()
        for key in ("segment_on", "segment_off", "background"):
            self.settings[key] = theme.get(key, DEFAULT_SETTINGS[key])

        self.settings["theme"] = "custom"
        self._remember_custom_colors()
        self._sync_menu_variables()
        self._apply_visual_settings()
        self._force_clock_redraw()
        self._save_settings_with_notice()

    def _on_startup_setting_changed(self):
        enabled = self.start_with_windows_var.get()
        if self._apply_startup_registration(enabled):
            self.settings["start_with_windows"] = enabled
            self._save_settings_with_notice()
            return

        self.start_with_windows_var.set(self.settings["start_with_windows"])

    def _apply_startup_registration(self, enabled, show_error=True):
        try:
            startup_script_path = self._get_startup_script_path()
            if enabled:
                startup_script_path.parent.mkdir(parents=True, exist_ok=True)
                startup_script_path.write_text(self._make_startup_script_text(), encoding="utf-8")
            elif startup_script_path.exists():
                startup_script_path.unlink()
        except OSError as error:
            if show_error:
                messagebox.showwarning(
                    "自動起動設定エラー",
                    f"Windows自動起動の設定を変更できませんでした。\n\n詳細:\n{error}",
                    parent=self,
                )
            return False

        return True

    def _get_startup_script_path(self):
        appdata = os.environ.get("APPDATA")
        if not appdata:
            raise OSError("APPDATA環境変数が見つかりません。")

        return (
            Path(appdata)
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
            / "SevenSegmentClock.cmd"
        )

    def _make_startup_script_text(self):
        if getattr(sys, "frozen", False):
            target_path = Path(sys.executable).resolve()
            return f'@echo off\nstart "" "{target_path}"\n'

        app_dir = Path(__file__).resolve().parent
        return f'@echo off\ncd /d "{app_dir}"\nstart "" python main.py\n'

    def _update_clock(self):
        now = datetime.now(tz=self._jst)
        self._apply_auto_day_night_theme(now)
        time_text, period_text = self._make_time_text(now)
        date_info = self._make_date_info(now)
        display_key = (
            time_text,
            period_text,
            self.settings["seconds_size"],
            self.settings["date_size"],
            self.settings["date_display"],
            self.settings["weekday_color_enabled"],
            self._date_info_key(date_info),
        )

        if display_key != self._last_display:
            self.clock_view.set_time(
                time_text,
                period_text,
                self.settings["seconds_size"],
                date_info,
                self.settings["date_display"],
                self.settings["weekday_color_enabled"],
                self.settings["date_size"],
            )
            self._last_display = display_key

        self._timer_after_id = self.after(1000, self._update_clock)

    def _make_time_text(self, now):
        hour = now.hour
        period_text = None

        if self.settings["use_24_hour"]:
            # 24時間表示でも一桁時は先頭ゼロなしにし、07/08/09の見づらさを避ける。
            hour_text = str(hour)
        else:
            period_text = "AM" if hour < 12 else "PM"
            display_hour = hour % 12
            if display_hour == 0:
                display_hour = 12
            # 12時間表示は先頭ゼロなし。10/11/12時だけ自然に2桁になる。
            hour_text = str(display_hour)

        if self.settings["show_seconds"]:
            return f"{hour_text}:{now.minute:02d}:{now.second:02d}", period_text

        return f"{hour_text}:{now.minute:02d}", period_text

    def _make_date_info(self, now):
        if self.settings["date_display"] == "off":
            return None

        weekdays = ["月", "火", "水", "木", "金", "土", "日"]
        return {
            "year": now.year,
            "month": now.month,
            "day": now.day,
            "weekday": weekdays[now.weekday()],
        }

    def _date_info_key(self, date_info):
        if date_info is None:
            return None

        return (
            date_info["year"],
            date_info["month"],
            date_info["day"],
            date_info["weekday"],
        )

    def _force_clock_redraw(self):
        self._last_display = None
        now = datetime.now(tz=self._jst)
        time_text, period_text = self._make_time_text(now)
        date_info = self._make_date_info(now)
        self.clock_view.set_time(
            time_text,
            period_text,
            self.settings["seconds_size"],
            date_info,
            self.settings["date_display"],
            self.settings["weekday_color_enabled"],
            self.settings["date_size"],
        )
        self._last_display = (
            time_text,
            period_text,
            self.settings["seconds_size"],
            self.settings["date_size"],
            self.settings["date_display"],
            self.settings["weekday_color_enabled"],
            self._date_info_key(date_info),
        )

    def _apply_visual_settings(self):
        self._ensure_valid_colors()
        self.configure(bg=self.settings["background"])
        self.clock_view.set_colors(
            self.settings["segment_on"],
            self.settings["segment_off"],
            self.settings["background"],
        )

    def _apply_render_settings(self):
        self.clock_view.set_render_options(
            self.settings["high_quality_rendering"],
            self.settings["led_glow_enabled"],
        )

    def _apply_window_options(self):
        self.attributes("-topmost", self.settings["always_on_top"])
        self.attributes("-alpha", self.settings["opacity_percent"] / 100)

    def _apply_min_window_height(self):
        min_height = self._get_min_height_for_date_display()
        self.minsize(self._min_width, min_height)

        current_width = self.winfo_width()
        current_height = self.winfo_height()
        if current_height > 1 and current_height < min_height:
            self.geometry(f"{max(self._min_width, current_width)}x{min_height}")

    def _get_min_height_for_date_display(self):
        if self.settings["date_display"] == "month_day":
            return 115
        if self.settings["date_display"] == "year_month_day":
            return 125
        if self.settings["date_display"] == "month_day_weekday":
            return 125
        if self.settings["date_display"] == "full":
            return 135

        return self._min_height

    def _restore_window_size(self):
        width = max(self._min_width, self.settings["window_width"])
        height = max(self._get_min_height_for_date_display(), self.settings["window_height"])
        window_x = self.settings["window_x"]
        window_y = self.settings["window_y"]

        if window_x >= 0 and window_y >= 0:
            if not self._is_window_position_visible(window_x, window_y, width, height):
                window_x, window_y = self._calculate_center_position(width, height)
            self.geometry(f"{width}x{height}+{window_x}+{window_y}")
        else:
            self.geometry(f"{width}x{height}")

    def _is_window_position_visible(self, x, y, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        visible_width = min(width, 80)
        visible_height = min(height, 60)

        return (
            x + visible_width > 0
            and y + visible_height > 0
            and x < screen_width - 40
            and y < screen_height - 40
        )

    def _calculate_center_position(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = max((screen_width - width) // 2, 0)
        y = max((screen_height - height) // 2, 0)
        return x, y

    def _center_window_now(self, save=True):
        self.update_idletasks()
        width = max(self._min_width, self.winfo_width())
        height = max(self._get_min_height_for_date_display(), self.winfo_height())
        x, y = self._calculate_center_position(width, height)
        self.geometry(f"{width}x{height}+{x}+{y}")

        if save:
            self._remember_window_size()
            self._save_settings_with_notice()

    def _remember_window_size(self):
        # 閉じる直前のサイズだけ保存し、リサイズ中のJSON書き込みを避ける。
        width, height, x, y = self._get_current_window_geometry()
        self.settings["window_width"] = width
        self.settings["window_height"] = height
        self.settings["window_x"] = x
        self.settings["window_y"] = y

    def _get_current_window_geometry(self):
        self.update_idletasks()
        return (
            max(self._min_width, self.winfo_width()),
            max(self._get_min_height_for_date_display(), self.winfo_height()),
            self.winfo_x(),
            self.winfo_y(),
        )

    def _restore_window_geometry(self, geometry):
        width, height, x, y = geometry
        width = max(self._min_width, width)
        height = max(self._get_min_height_for_date_display(), height)
        self.geometry(f"{width}x{height}+{x}+{y}")
        self.update_idletasks()

    def _apply_clock_only_mode(self):
        # タイトルバー・メニューの切り替えでウィンドウ寸法が目減りしないよう、切替前の寸法を戻す。
        geometry_before = self._get_current_window_geometry()

        if self.settings["clock_only_mode"]:
            self.config(menu="")
            self.overrideredirect(True)
        else:
            self.overrideredirect(False)
            self.config(menu=self.menu_bar)

        self.update_idletasks()
        self._restore_window_geometry(geometry_before)

    def _set_clock_only_mode(self, enabled):
        self.settings["layout_preset"] = "custom"
        self.layout_preset_var.set("custom")
        self.clock_only_mode_var.set(enabled)
        self.settings["clock_only_mode"] = enabled
        self._apply_clock_only_mode()
        self._apply_render_settings()
        self._force_clock_redraw()
        self._save_settings_with_notice()

    def _show_context_menu(self, event):
        if not self.settings["clock_only_mode"]:
            return

        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _start_window_move(self, event):
        if not self.settings["clock_only_mode"]:
            return

        self._drag_offset_x = event.x_root - self.winfo_x()
        self._drag_offset_y = event.y_root - self.winfo_y()

    def _move_window(self, event):
        if not self.settings["clock_only_mode"]:
            return

        x = event.x_root - self._drag_offset_x
        y = event.y_root - self._drag_offset_y
        self.geometry(f"+{x}+{y}")

    def _restore_normal_window(self, event=None):
        if self.settings["clock_only_mode"]:
            self._set_clock_only_mode(False)

    def _sync_menu_variables(self):
        self.always_on_top_var.set(self.settings["always_on_top"])
        self.show_seconds_var.set(self.settings["show_seconds"])
        self.use_24_hour_var.set(self.settings["use_24_hour"])
        self.clock_only_mode_var.set(self.settings["clock_only_mode"])
        self.seconds_size_var.set(self.settings["seconds_size"])
        self.date_size_var.set(self.settings["date_size"])
        self.theme_var.set(self.settings["theme"])
        self.opacity_percent_var.set(self.settings["opacity_percent"])
        self.date_display_var.set(self.settings["date_display"])
        self.weekday_color_enabled_var.set(self.settings["weekday_color_enabled"])
        self.layout_preset_var.set(self.settings["layout_preset"])
        self.start_with_windows_var.set(self.settings["start_with_windows"])
        self.auto_day_night_theme_var.set(self.settings["auto_day_night_theme"])
        self.high_quality_rendering_var.set(self.settings["high_quality_rendering"])
        self.led_glow_enabled_var.set(self.settings["led_glow_enabled"])
        self.close_to_tray_var.set(self.settings["close_to_tray"])

    def _normalize_seconds_size(self, seconds_size):
        return "small" if seconds_size == "small" else "normal"

    def _normalize_date_size(self, date_size):
        return "normal" if date_size == "normal" else "small"

    def _normalize_opacity_percent(self, opacity_percent):
        if type(opacity_percent) is not int:
            return 100

        clamped_opacity = min(OPACITY_MAX_PERCENT, max(OPACITY_MIN_PERCENT, opacity_percent))
        return round(clamped_opacity / OPACITY_STEP_PERCENT) * OPACITY_STEP_PERCENT

    def _normalize_date_display(self, date_display):
        if date_display in DATE_DISPLAY_LABELS:
            return date_display

        return "off"

    def _on_theme_changed(self):
        self._disable_auto_day_night_theme()
        theme_key = self.theme_var.get()
        self.settings["theme"] = theme_key if theme_key in THEMES else "custom"
        self.theme_var.set(self.settings["theme"])

        if self.settings["theme"] in THEMES:
            theme = THEMES[self.settings["theme"]]
            self.settings["segment_on"] = theme["segment_on"]
            self.settings["segment_off"] = theme["segment_off"]
            self.settings["background"] = theme["background"]
        else:
            self._restore_custom_colors()

        self._apply_visual_settings()
        self._force_clock_redraw()
        self._save_settings_with_notice()

    def _remember_custom_colors(self):
        self.settings["custom_segment_on"] = self.settings["segment_on"]
        self.settings["custom_segment_off"] = self.settings["segment_off"]
        self.settings["custom_background"] = self.settings["background"]

    def _restore_custom_colors(self):
        self.settings["segment_on"] = self.settings["custom_segment_on"]
        self.settings["segment_off"] = self.settings["custom_segment_off"]
        self.settings["background"] = self.settings["custom_background"]

    def _ensure_valid_colors(self):
        for key in ("segment_on", "segment_off", "background"):
            color = self.settings.get(key, DEFAULT_SETTINGS[key])
            try:
                self.winfo_rgb(color)
            except tk.TclError:
                self.settings[key] = DEFAULT_SETTINGS[key]

    def _save_settings_with_notice(self):
        try:
            save_settings(self.settings)
        except OSError as error:
            messagebox.showwarning(
                "設定保存エラー",
                f"設定ファイルを保存できませんでした。\n\n保存先:\n{get_settings_path()}\n\n詳細:\n{error}",
                parent=self,
            )
            return False

        return True

    def _setup_tray_icon(self):
        """タスクトレイアイコンを初期化して表示する。"""
        if not TRAY_AVAILABLE:
            return

        if self._tray_icon is not None:
            return

        icon_path = get_resource_path("assets", "app_icon.png")
        if not icon_path.exists():
            return

        try:
            image = Image.open(icon_path)
        except OSError:
            return

        menu = pystray.Menu(
            pystray.MenuItem("表示", self._on_tray_show),
            pystray.MenuItem("非表示", self._on_tray_hide),
            pystray.MenuItem("時計のみ表示切替", self._on_tray_toggle_clock_only),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("終了", self._on_tray_quit)
        )

        self._tray_icon = pystray.Icon(
            "SevenSegmentClock",
            image,
            APP_NAME,
            menu
        )

        self._tray_thread = threading.Thread(
            target=self._tray_icon.run,
            daemon=True
        )
        self._tray_thread.start()

    def _set_window_icon(self):
        png_path = get_resource_path("assets", "app_icon.png")
        if png_path.exists():
            try:
                self._window_icon = tk.PhotoImage(file=str(png_path))
                self.iconphoto(True, self._window_icon)
                return
            except tk.TclError:
                pass

        icon_path = get_resource_path("assets", "app_icon.ico")
        if not icon_path.exists():
            return

        try:
            self.iconbitmap(default=str(icon_path))
        except tk.TclError:
            pass

    def _center_child_window(self, child):
        self.update_idletasks()
        child.update_idletasks()

        parent_x = self.winfo_rootx()
        parent_y = self.winfo_rooty()
        parent_width = self.winfo_width()
        parent_height = self.winfo_height()

        child_width = child.winfo_width()
        child_height = child.winfo_height()

        # 親ウィンドウの中央から少し右下へずらす
        x = parent_x + (parent_width - child_width) // 2 + 24
        y = parent_y + (parent_height - child_height) // 2 + 24

        # 画面左上より外へ出ないようにする
        x = max(x, 0)
        y = max(y, 0)

        child.geometry(f"+{x}+{y}")
        child.lift()
        child.focus_set()
        # child.update_idletasks()
        # parent_x = self.winfo_rootx()
        # parent_y = self.winfo_rooty()
        # parent_width = self.winfo_width()
        # parent_height = self.winfo_height()
        # child_width = child.winfo_width()
        # child_height = child.winfo_height()

        # x = parent_x + (parent_width - child_width) // 2
        # y = parent_y + (parent_height - child_height) // 2
        # child.geometry(f"+{max(x, 0)}+{max(y, 0)}")

    # def _on_close(self):
    #     if self._timer_after_id is not None:
    #         self.after_cancel(self._timer_after_id)
    #         self._timer_after_id = None

    #     self._remember_window_size()
    #     self._save_settings_with_notice()
    #     self.destroy()

    def _on_close_to_tray_setting_changed(self):
        self.settings["close_to_tray"] = self.close_to_tray_var.get()
        self._save_settings_with_notice()

    def _on_close(self):
        if self.settings["close_to_tray"] and TRAY_AVAILABLE and self._tray_icon is not None:
            self._hide_window()
            return
        self._quit_app()


    def _quit_app(self):
        """アプリを完全に終了する。"""
        if self._is_quitting:
            return

        self._is_quitting = True

        if self._timer_after_id is not None:
            self.after_cancel(self._timer_after_id)
            self._timer_after_id = None

        self._remember_window_size()
        self._save_settings_with_notice()
        self._stop_tray_icon()
        self.destroy()