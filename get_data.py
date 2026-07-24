import re
from datetime import datetime
import exifread
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS
import pytz
from timezonefinder import TimezoneFinder

try:
    from lenses import KNOWN_COMPACT_LENSES
except ImportError:
    KNOWN_COMPACT_LENSES = {}

def get_exif_data(image_path):
    exif_dict = {}
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            if tags:
                for tag, val in tags.items():
                    clean_tag = tag.split()[-1] if ' ' in tag else tag
                    exif_dict[clean_tag] = str(val)
                    exif_dict[tag] = str(val)
    except Exception:
        pass

    try:
        image = Image.open(image_path)
        info = image._getexif()
        if info:
            for tag, value in info.items():
                tag_name = TAGS.get(tag, tag)
                if tag_name not in exif_dict:
                    exif_dict[tag_name] = value
    except Exception:
        pass

    return exif_dict


BRANDS_SAFE_TO_STRIP = {"CANON", "PANASONIC", "SONY", "OLYMPUS", "RICOH"}

def clean_camera_name(exif):
    make = exif.get("Make", "")
    model = exif.get("Model", "Unknown Camera")

    if isinstance(make, bytes): make = make.decode('utf-8', errors='ignore')
    if isinstance(model, bytes): model = model.decode('utf-8', errors='ignore')

    if make:
        make_keyword = make.split()[0] if make.split() else make
        if make_keyword.upper() in BRANDS_SAFE_TO_STRIP:
            pattern = re.compile(r"^\s*" + re.escape(make_keyword) + r"\s+", re.IGNORECASE)
            model = pattern.sub("", model).strip()

    return model


def get_shutter(exif):
    shutter_raw = exif.get("ExposureTime", "")
    if not shutter_raw or shutter_raw == "?":
        return None

    val = None
    if isinstance(shutter_raw, tuple) and len(shutter_raw) == 2:
        val = shutter_raw[0] / shutter_raw[1] if shutter_raw[1] != 0 else None
    elif isinstance(shutter_raw, (int, float)):
        val = float(shutter_raw)
    elif isinstance(shutter_raw, str):
        if "/" in shutter_raw:
            try:
                n, d = shutter_raw.split("/")
                val = float(n) / float(d) if float(d) != 0 else None
            except Exception:
                val = None
        else:
            try:
                val = float(shutter_raw)
            except Exception:
                val = None

    if val is None or val == 0:
        return None

    if val < 1:
        denom = round(1 / val)
        return f"1/{denom}"
    else:
        return f"{round(val, 1)}\""


# --- 화각(Focal Length) 자동 추출 로직 (GPS 추출 방식과 동일) ---
def get_focal_length(exif):
    eq_focal = exif.get("FocalLengthIn35mmFilm", "")
    if isinstance(eq_focal, tuple) and len(eq_focal) == 2:
        eq_focal = eq_focal[0] / eq_focal[1] if eq_focal[1] != 0 else ""

    if not eq_focal or str(eq_focal) == "?":
        eq_focal = exif.get("FocalLength", "")
        if isinstance(eq_focal, tuple) and len(eq_focal) == 2:
            eq_focal = eq_focal[0] / eq_focal[1] if eq_focal[1] != 0 else ""

    try:
        val = int(float(eq_focal))
        return f"{val}mm" if val > 0 else None
    except Exception:
        return None


def lookup_known_lens(camera_model):
    if not camera_model:
        return None
    model_upper = camera_model.upper()
    for keyword, lens_spec in KNOWN_COMPACT_LENSES.items():
        if keyword.upper() in model_upper:
            return lens_spec
    return None


def get_lens(exif, camera_model=""):
    known = lookup_known_lens(camera_model)
    if known:
        return known

    lens = exif.get("LensModel", "")
    lens_str = str(lens).strip() if lens else ""

    if not lens_str or lens_str.lower() in ["none", "unknown", "?", "built-in"]:
        return None

    if camera_model:
        pattern = re.compile(re.escape(camera_model), re.IGNORECASE)
        lens_str = pattern.sub("", lens_str).strip()

    if "camera" in lens_str.lower():
        specs = re.findall(r'\d+(?:\.\d+)?\s*mm|\bf\/\d+(?:\.\d+)?', lens_str, re.IGNORECASE)
        if specs:
            lens_str = " ".join(specs).strip()
        else:
            return None
            
    cleaned = lens_str.strip(" ,-_")
    return cleaned if cleaned else None


def get_f_number(exif):
    f_val = exif.get("FNumber", None)
    if not f_val or f_val == "?":
        return None

    if isinstance(f_val, str) and "/" in f_val:
        try:
            num, den = f_val.split("/")
            f_val = float(num) / float(den) if float(den) != 0 else None
        except Exception:
            f_val = None
    elif isinstance(f_val, tuple) and len(f_val) == 2:
        try:
            f_val = f_val[0] / f_val[1] if f_val[1] != 0 else None
        except Exception:
            f_val = None

    try:
        if f_val is not None:
            return f"f/{float(f_val):.1f}"
    except Exception:
        pass
    return None


class ReturnPictureEXIF():
    def __init__(self, image_path):
        img = Image.open(image_path)
        self.image_path = image_path
        self.exif = get_exif_data(image_path)
        self.image = ImageOps.exif_transpose(img)
        self.camera = clean_camera_name(self.exif)
        self.iso = self.exif.get("ISOSpeedRatings", None)
        
        # 값이 없으면 None을 반환하도록 설정 (GPS 방식과 동일)
        self.f_number = get_f_number(self.exif)
        self.shutter = get_shutter(self.exif)
        self.lens = get_lens(self.exif, self.camera)
        self.focal_length = get_focal_length(self.exif)

    def get_image(self): return self.image
    def get_camera(self): return self.camera
    def get_iso(self): return self.iso
    def get_f_number(self): return self.f_number
    def get_shutter(self): return self.shutter
    def get_lens(self): return self.lens
    def get_focal_length(self): return self.focal_length
