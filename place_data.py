import re
import os
from datetime import datetime
from font import *
from PIL import Image, ImageDraw

def place_model(canvas, pic, w, h, t, p, l_file, chosen_utc=None, current_path=None):
    font_obj = set_font(p)
    font_reg = regular(p)
    font_dat = date_font(p)
    size, d_size = font_size(p)

    if w > h:
        scale_up_factor = 1.30
        size = int(size * scale_up_factor)
        d_size = int(d_size * scale_up_factor)

    draw = ImageDraw.Draw(canvas)

    text_camera = pic.get_camera()
    text_info = f"f/{pic.get_f_number()}  {pic.get_shutter()}  ISO{pic.get_iso()}"

    text_lens = pic.get_lens() if hasattr(pic, "get_lens") else ""

    if text_lens:
        text_lens = text_lens.replace("\x00", "").strip()
        text_lens = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text_lens)

    if not text_lens:
        text_lens = "Lens Unspecified"

    utc_offset_str = chosen_utc if chosen_utc else "UTC+09:00"
    text_date = ""
    date_str = ""
    has_valid_gps = False

    try:
        with Image.open(current_path) as img_exif:
            exif_data = img_exif._getexif()
        if exif_data:
            from PIL.ExifTags import TAGS
            readable_exif = {TAGS.get(tag, tag): val for tag, val in exif_data.items()}
            date_str = readable_exif.get("DateTimeOriginal", "")
            gps_info = readable_exif.get("GPSInfo", {})
            coords = None
            if gps_info and 2 in gps_info and 4 in gps_info:
                try:
                    def to_degrees(value):
                        return float(value[0]) + (float(value[1]) / 60.0) + (float(value[2]) / 3600.0)

                    lat = to_degrees(gps_info[2])
                    if readable_exif.get("GPSLatitudeRef", "N") == "S": lat = -lat
                    lon = to_degrees(gps_info[4])
                    if readable_exif.get("GPSLongitudeRef", "E") == "W": lon = -lon
                    if abs(lat) > 0.001 and abs(lon) > 0.001:
                        coords = (lat, lon)
                except:
                    coords = None

            if coords:
                try:
                    from timezonefinder import TimezoneFinder
                    import pytz
                    tf = TimezoneFinder()
                    tz_name = tf.timezone_at(lat=coords[0], lng=coords[1])
                    if tz_name:
                        timezone = pytz.timezone(tz_name)
                        dt_obj = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                        aware_dt = timezone.localize(dt_obj)
                        utc_offset = aware_dt.utcoffset()
                        hours = int(utc_offset.total_seconds() / 3600)
                        minutes = int((utc_offset.total_seconds() % 3600) / 60)
                        utc_offset_str = f"UTC{'+' if hours >= 0 else ''}{hours:02d}:{abs(minutes):02d}"
                        has_valid_gps = True
                except:
                    pass
    except:
        pass

    if has_valid_gps and date_str:
        try:
            dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            text_date = dt.strftime(f"%Y-%b-%d %H:%M {utc_offset_str}")
        except:
            pass

    if not text_date:
        if date_str:
            try:
                dt = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                text_date = dt.strftime(f"%Y-%b-%d %H:%M {chosen_utc}")
            except:
                date_str = ""
        if not date_str:
            try:
                file_mtime = os.path.getmtime(current_path)
                dt = datetime.fromtimestamp(file_mtime)
                text_date = dt.strftime(f"%Y-%b-%d %H:%M {chosen_utc}")
            except:
                text_date = datetime.now().strftime(f"%Y-%b-%d %H:%M {chosen_utc}")

    line_spacing = int(size * 0.2)
    if w > h:
        gap = int(p * 0.12)
        start_y = h + t + gap
    else:
        start_y = h + (p - (size + line_spacing + d_size)) // 2

    visual_center_y = int(start_y + (size * 0.62))

    spacing = int(w * 0.01)
    current_x = t
    lens_left_x = t

    try:
        if l_file and os.path.exists(l_file):
            logo_img = Image.open(l_file).convert("RGBA")
            logo_h = int(size * 0.95)
            logo_w = int(logo_img.width * (logo_h / logo_img.height))
            logo_img = logo_img.resize((logo_w, logo_h), Image.Resampling.LANCZOS)

            logo_x = int(current_x)
            logo_y = int(visual_center_y - (logo_h // 2))
            canvas.paste(logo_img, (logo_x, logo_y), logo_img)

            lens_left_x = logo_x
            current_x = logo_x + logo_w + int(spacing * 0.7)
    except:
        pass

    info_x = t + w
    info_width = draw.textlength(text_info, font=font_reg)
    max_available_x = info_x - info_width - (spacing * 2)
    max_text_width = max_available_x - current_x
    current_text_width = draw.textlength(text_camera, font=font_obj)

    camera_stroke_width = 0

    if current_text_width > max_text_width:
        scale_factor = max(max_text_width / current_text_width, 0.4)
        new_size = int(size * scale_factor)
        font_obj = create_custom_font(new_size, is_bold=True)
        if scale_factor < 0.8:
            camera_stroke_width = max(1, int(new_size * 0.03))
    elif w > h:
        font_obj = create_custom_font(size, is_bold=True)
        font_reg = create_custom_font(int(size * 0.85), is_bold=False)
        font_dat = create_custom_font(int(size * 0.65), is_bold=False)

    draw.text(
        (int(current_x), int(start_y)),
        text_camera,
        fill=(0, 0, 0),
        font=font_obj,
        anchor="la",
        stroke_width=camera_stroke_width,
        stroke_fill=(0, 0, 0)
    )

    if text_lens:
        lens_y = int(start_y + size + int(size * 0.15))
        draw.text(
            (int(lens_left_x), lens_y),
            text_lens,
            fill=(140, 140, 140),
            font=font_dat,
            anchor="la"
        )

    draw.text((int(info_x), int(start_y)), text_info, fill=(50, 50, 50), font=font_reg, anchor="ra")

    if text_date:
        date_y = int(start_y + size + line_spacing)
        draw.text((int(info_x), date_y), text_date, fill=(140, 140, 140), font=font_dat, anchor="ra")

    return canvas