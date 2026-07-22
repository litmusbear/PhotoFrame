import re
from datetime import datetime
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS
import pytz
from timezonefinder import TimezoneFinder
from lenses import KNOWN_COMPACT_LENSES

def get_exif_data(image_path):
    image = Image.open(image_path)
    info = image._getexif()
    exif_dict = {}
    if info:
        for tag, value in info.items():
            tag_name = TAGS.get(tag, tag)
            exif_dict[tag_name] = value
    return exif_dict


BRANDS_SAFE_TO_STRIP = {
    "CANON",
    "PANASONIC",
    "SONY",
    "OLYMPUS",
    "RICOH",
}


def clean_camera_name(exif):
    make = exif.get("Make", "")
    model = exif.get("Model", "Unknown Camera")

    if make:
        make_keyword = make.split()[0] if make.split() else make
        if make_keyword.upper() in BRANDS_SAFE_TO_STRIP:
            pattern = re.compile(r"^\s*" + re.escape(make_keyword) + r"\s+", re.IGNORECASE)
            model = pattern.sub("", model).strip()

    return model


def get_shutter(exif):
    shutter = exif.get("ExposureTime", "?")
    if shutter:
        if isinstance(shutter, tuple):
            shutter = shutter[0] / shutter[1]
        if shutter < 1:
            denom = round(1 / shutter)
            shutter = f"1/{denom}"
        else:
            shutter = f"{shutter}\""
    else:
        shutter = "?"
    return shutter


def convert_to_degrees(value):
    d = float(value[0])
    m = float(value[1])
    s = float(value[2])
    return d + (m / 60.0) + (s / 3600.0)


def get_gps(exif):
    gps_info = exif.get("GPSInfo", {})
    if not gps_info:
        return None
    try:
        lat = convert_to_degrees(gps_info[2])
        if gps_info[1] == 'S': lat = -lat
        lon = convert_to_degrees(gps_info[4])
        if gps_info[3] == 'W': lon = -lon
        return lat, lon
    except:
        return None


def get_datetime(exif):
    date_str = exif.get("DateTimeOriginal", "")
    if not date_str: return ""

    dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
    coords = get_gps(exif)
    utc_offset_str = "UTC+00:00"

    if coords:
        tf = TimezoneFinder()
        tz_name = tf.timezone_at(lat=coords[0], lng=coords[1])
        if tz_name:
            timezone = pytz.timezone(tz_name)
            aware_dt = timezone.localize(dt)
            utc_offset = aware_dt.utcoffset()
            hours = int(utc_offset.total_seconds() / 3600)
            minutes = int((utc_offset.total_seconds() % 3600) / 60)
            utc_offset_str = f"UTC{'+' if hours >= 0 else ''}{hours:02d}:{abs(minutes):02d}"

    return dt.strftime(f"%Y-%b-%d %H:%M {utc_offset_str}")


def lookup_known_lens(camera_model):
    if not camera_model:
        return ""
    model_upper = camera_model.upper()
    for keyword, lens_spec in KNOWN_COMPACT_LENSES.items():
        if keyword.upper() in model_upper:
            return lens_spec
    return ""


def get_lens(exif, camera_model=""):
    known = lookup_known_lens(camera_model)
    if known:
        return known

    lens = exif.get("LensModel", "")
    lens_str = str(lens).strip() if lens else ""

    if not lens_str or lens_str.lower() in ["none", "unknown", "?", "built-in"]:
        return ""

    if camera_model:
        pattern = re.compile(re.escape(camera_model), re.IGNORECASE)
        lens_str = pattern.sub("", lens_str).strip()

    if "camera" in lens_str.lower():
        specs = re.findall(r'\d+(?:\.\d+)?\s*mm|\bf\/\d+(?:\.\d+)?', lens_str, re.IGNORECASE)
        if specs:
            lens_str = " ".join(specs).strip()
        else:
            lens_str = ""
    return lens_str.strip(" ,-_")


class ReturnPictureEXIF():
    def __init__(self, image_path):
        img = Image.open(image_path)
        self.image_path = image_path
        self.exif = get_exif_data(image_path)
        self.image = ImageOps.exif_transpose(img)
        self.camera = clean_camera_name(self.exif)
        self.iso = self.exif.get("ISOSpeedRatings", "?")

        f_val = self.exif.get("FNumber", "?")
        if isinstance(f_val, tuple) and len(f_val) == 2:
            f_val = f_val[0] / f_val[1]
        self.f_number = float(round(f_val, 1)) if isinstance(f_val, (int, float)) else f_val

        self.shutter = get_shutter(self.exif)
        self.datetime = get_datetime(self.exif)

        base_lens = get_lens(self.exif, self.camera)

        eq_focal = self.exif.get("FocalLengthIn35mmFilm", "")
        if isinstance(eq_focal, tuple) and len(eq_focal) == 2:
            eq_focal = eq_focal[0] / eq_focal[1]

        if not eq_focal or str(eq_focal) == "?":
            eq_focal = self.exif.get("FocalLength", "")
            if isinstance(eq_focal, tuple) and len(eq_focal) == 2:
                eq_focal = eq_focal[0] / eq_focal[1]

        focal_str = f"@{int(float(eq_focal))}mm" if eq_focal and str(eq_focal) != "?" else ""

        if base_lens:
            self.lens = f"{base_lens} {focal_str}".strip()
        else:
            self.lens = f"Lens Unspecified {focal_str}".strip()

    def get_image(self):
        return self.image

    def get_camera(self):
        return self.camera

    def get_iso(self):
        return self.iso

    def get_f_number(self):
        return self.f_number

    def get_shutter(self):
        return self.shutter

    def get_datetime(self):
        return self.datetime

    def get_lens(self):
        return self.lens