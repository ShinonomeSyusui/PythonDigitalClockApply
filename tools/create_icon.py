# -*- coding: utf-8 -*-
import struct
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SOURCE_PNG_PATH = ROOT_DIR / "assets" / "app_icon.png"
OUTPUT_PATH = ROOT_DIR / "assets" / "app_icon.ico"
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def get_png_size(png_data):
    """PNGのヘッダーから画像サイズだけを読み取る。画像の加工は行わない。"""
    if not png_data.startswith(PNG_SIGNATURE):
        raise ValueError("assets/app_icon.png is not a PNG file.")

    if png_data[12:16] != b"IHDR":
        raise ValueError("assets/app_icon.png does not have a valid IHDR header.")

    return struct.unpack(">II", png_data[16:24])


def to_ico_size_byte(size):
    """ICOの幅・高さは1バイトなので、256以上は0として記録する。"""
    if size >= 256:
        return 0

    return size


def make_ico(png_data, width, height):
    """PNGデータをそのままICOコンテナへ格納する。"""
    header = struct.pack("<HHH", 0, 1, 1)
    image_offset = 6 + 16
    entry = struct.pack(
        "<BBBBHHII",
        to_ico_size_byte(width),
        to_ico_size_byte(height),
        0,
        0,
        1,
        32,
        len(png_data),
        image_offset,
    )

    return header + entry + png_data


def main():
    png_data = SOURCE_PNG_PATH.read_bytes()
    width, height = get_png_size(png_data)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_bytes(make_ico(png_data, width, height))
    print(f"Created {OUTPUT_PATH} from {SOURCE_PNG_PATH} without image processing.")


if __name__ == "__main__":
    main()