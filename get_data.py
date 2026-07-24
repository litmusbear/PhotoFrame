import re
from datetime import datetime
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS
import pytz
from timezonefinder import TimezoneFinder

# PyExifTool 시도 (RAW 메타데이터 완벽 대응)
try:
    import exiftool
    HAS_EXIFTOOL = True
except ImportError:
    HAS_EXIFTOOL = False

import exifread


def get_exif_data(image_path):
    """
    확장자 구분 없이 RAW, JPG, PNG 등 모든 이미지의 메타데이터를 가져오는 통합 함수
    """
    exif_dict = {}

    # 1. [우선순위 1] ExifTool 사용 (설치되어 있다면 RAW/JPG 구분 없이 100% 읽어옴)
    if HAS_EXIFTOOL:
        try:
            with exiftool.ExifToolHelper() as et:
                metadata = et.get_metadata(image_path)[0]
                
                # ExifTool 태그 매핑
                exif_dict["Make"] = metadata.get("EXIF:Make") or metadata.get("MakerNotes:Make") or ""
                exif_dict["Model"] = metadata.get("EXIF:Model") or metadata.get("MakerNotes:Model") or ""
                exif_dict["ExposureTime"] = metadata.get("EXIF:ExposureTime") or metadata.get("Composite:ShutterSpeed") or ""
                exif_dict["FNumber"] = metadata.get("EXIF:FNumber") or metadata.get("Composite:Aperture") or ""
                exif_dict["ISOSpeedRatings"] = metadata.get("EXIF:ISO") or metadata.get("EXIF:ISOSpeedRatings") or ""
                exif_dict["DateTimeOriginal"] = metadata.get("EXIF:DateTimeOriginal") or metadata.get("EXIF:CreateDate") or ""
                exif_dict["LensModel"] = metadata.get("EXIF:LensModel") or metadata.get("Composite:LensID") or metadata.get("MakerNotes:LensModel") or ""
                exif_dict["FocalLength"] = metadata.get("EXIF:FocalLength") or metadata.get("Composite:FocalLength") or ""
                exif_dict["FocalLengthIn35mmFilm"] = metadata.get("EXIF:FocalLengthIn35mmFormat") or metadata.get("Composite:FocalLength35efl") or ""
                
                # GPS
                if "EXIF:GPSLatitude" in metadata and "EXIF:GPSLongitude" in metadata:
                    exif_dict["GPSInfo"] = {
                        1: metadata.get("EXIF:GPSLatitudeRef", "N"),
                        2: metadata.get("EXIF:GPSLatitude"),
                        3: metadata.get("EXIF:GPSLongitudeRef", "E"),
                        4: metadata.get("EXIF:GPSLongitude")
                    }
                return exif_dict
        except Exception:
            pass # 실패 시 순수 파이썬 로직으로 넘어감

    # 2. [우선순위 2] ExifTool이 없거나 실패할 경우 Pure Python (exifread 정밀 스캔)
    try:
        with open(image_path, 'rb') as f:
            tags = exifread.process_file(f, details=True, stop_tag=None)
            if tags:
                for tag, val in tags.items():
                    val_str = str(val).strip()
                    clean_tag = tag.split()[-1] if ' ' in tag else tag
                    
                    exif_dict[clean_tag] = val_str
                    exif_dict[tag] = val_str

                    # RAW 바이너리 특수 태그 동적 매핑
                    if "Model" in tag and "Model" not in exif_dict: exif_dict["Model"] = val_str
                    if "Make" in tag and "Make" not in exif_dict: exif_dict["Make"] = val_str
                    if "FNumber" in tag or "Aperture" in tag: 
                        if "FNumber" not in exif_dict: exif_dict["FNumber"] = val_str
                    if "FocalLength" in tag and "FocalLength" not in exif_dict: exif_dict["FocalLength"] = val_str
                    if "ISO" in tag and "ISOSpeedRatings" not in exif_dict: exif_dict["ISOSpeedRatings"] = val_str
                    if ("Lens" in tag or "LensModel" in tag) and "LensModel" not in exif_dict: exif_dict["LensModel"] = val_str
    except Exception:
        pass

    # 3. [우선순위 3] PIL 기본 EXIF 보완 (JPG 등 일반 이미지)
    try:
        image = Image.open(image_path)
        info = image._getexif()
        if info:
            for tag, value in info.items():
                tag_name = TAGS.get(tag, tag)
                if tag_name not in exif_dict or not exif_dict[tag_name]:
                    exif_dict[tag_name] = value
    except Exception:
        pass

    return exif_dict
