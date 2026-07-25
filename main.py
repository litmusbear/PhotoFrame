import uuid
import streamlit as st
import os
import io
import urllib.parse
import traceback
from PIL import Image

try:
    import piexif
    HAS_PIEXIF = True
except ImportError:
    HAS_PIEXIF = False

from timezones import timezone_options
from place_data import place_model
from get_data import ReturnPictureEXIF
from logo import logo
from border import *

# lenses.py 연동
try:
    from lenses import OLD_LENSES_BY_BRAND, MANUAL_F_NUMBERS, COMMON_EQUIV_FOCAL_LENGTHS
except ImportError:
    OLD_LENSES_BY_BRAND = {
        "EXIF 기본값": ["EXIF 정보 사용"],
        "직접 입력": ["사용자 지정 입력"],
        "Yashica / Contax": ["Yashica ML 50mm f/1.4", "Carl Zeiss Planar T* 50mm f/1.4 C/Y"],
        "Pentax / M42": ["Helios 44-2 58mm f/2.0", "Asahi Pentax Super-Takumar 50mm f/1.4"],
        "Leica / L39": ["Leica Summicron-M 50mm f/2.0"],
        "Canon FD": ["Canon FD 50mm f/1.4 SSC"],
        "Nikon F": ["Nikkor-S Auto 50mm f/1.4"]
    }
    MANUAL_F_NUMBERS = ["EXIF 유지", "f/1.2", "f/1.4", "f/1.8", "f/2.0", "f/2.8", "f/4.0", "f/5.6", "f/8.0"]
    COMMON_EQUIV_FOCAL_LENGTHS = ["EXIF 유지", "24mm", "28mm", "35mm", "40mm", "50mm", "58mm", "85mm", "135mm", "직접 입력"]

def clean_uploaded_filename(filename):
    """iOS/Safari 사진 앱 업로드 시 붙는 쿼리스트링 정제"""
    decoded = urllib.parse.unquote(filename)
    clean_name = decoded.split("?")[0].split("&")[0]
    if "uuid=" in clean_name and "code=" in clean_name:
        ext = os.path.splitext(clean_name)[1]
        return f"RAW_Image{ext}"
    return os.path.basename(clean_name)

def extract_exif_bytes(source_path):
    if HAS_PIEXIF:
        try:
            exif_dict = piexif.load(source_path)
            if "0th" in exif_dict and piexif.ImageIFD.Orientation in exif_dict["0th"]:
                exif_dict["0th"][piexif.ImageIFD.Orientation] = 1
            return piexif.dump(exif_dict)
        except Exception:
            pass

    try:
        with Image.open(source_path) as img:
            return img.info.get("exif")
    except Exception:
        pass

    return None

st.set_page_config(page_title="사진 데이터 프레임 생성기", layout="centered")

st.markdown("""
    <style>
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #FBF9F6 !important;
        color: #222222 !important;
    }
    h1, h2, h3, h4, h5, h6, p, span, label {
        color: #222222 !important;
    }
    .stFileUploader, [data-testid="stFileUploader"] {
        background-color: #ffffff !important;
        padding: 25px;
        border-radius: 16px;
        box-shadow: 0px 8px 24px rgba(149, 157, 165, 0.06);
        border: 1px dashed #E2DFD9 !important;
    }
    .info-text {
        color: #6E6E6E !important;
        font-size: 0.95rem;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📸 사진 데이터 프레임 생성기")
st.markdown('<p class="info-text">디지털 사진에 카메라 기종, 렌즈 정보, 촬영 정보(EXIF), 그리고 감성적인 즉석 인화 카메라 스타일 테두리를 입혀줍니다.</p>',
            unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    "사진들을 업로드하세요",
    type=["jpg", "jpeg", "png", "arw", "cr2", "cr3", "nef", "dng", "orf", "rw2"],
    accept_multiple_files=True
)

if uploaded_files:
    temp_file_paths = []

    # 세션 딕셔너리 초기화
    if "tz_dict" not in st.session_state:
        st.session_state.tz_dict = {}
    if "brand_dict" not in st.session_state:
        st.session_state.brand_dict = {}
    if "lens_dict" not in st.session_state:
        st.session_state.lens_dict = {}
    if "custom_lens_dict" not in st.session_state:
        st.session_state.custom_lens_dict = {}
    if "f_dict" not in st.session_state:
        st.session_state.f_dict = {}
    if "focal_dict" not in st.session_state:
        st.session_state.focal_dict = {}
    if "custom_focal_dict" not in st.session_state:
        st.session_state.custom_focal_dict = {}

    brand_list = list(OLD_LENSES_BY_BRAND.keys())

    for idx, uploaded_file in enumerate(uploaded_files):
        file_id = uploaded_file.name
        display_file_name = clean_uploaded_filename(uploaded_file.name)
        
        # 파일별 기본 세션 값 세팅
        if file_id not in st.session_state.tz_dict:
            st.session_state.tz_dict[file_id] = "UTC+09:00 (한국/일본/인도네시아 동부)"
        if file_id not in st.session_state.brand_dict:
            st.session_state.brand_dict[file_id] = brand_list[0] if brand_list else ""
        if file_id not in st.session_state.lens_dict:
            default_brand = st.session_state.brand_dict[file_id]
            default_lenses = OLD_LENSES_BY_BRAND.get(default_brand, ["EXIF 정보 사용"])
            st.session_state.lens_dict[file_id] = default_lenses[0] if default_lenses else "EXIF 정보 사용"
        if file_id not in st.session_state.custom_lens_dict:
            st.session_state.custom_lens_dict[file_id] = ""
        if file_id not in st.session_state.f_dict:
            st.session_state.f_dict[file_id] = "EXIF 유지"
        if file_id not in st.session_state.focal_dict:
            st.session_state.focal_dict[file_id] = "EXIF 유지"
        if file_id not in st.session_state.custom_focal_dict:
            st.session_state.custom_focal_dict[file_id] = ""

        unique_id = f"{uuid.uuid4().hex[:6]}_{idx}"
        temp_path = f"temp_{unique_id}.jpg"
        temp_file_paths.append(temp_path)

        try:
            save_uploaded_file_to_temp(uploaded_file, temp_path)
        except Exception as e:
            st.error(f"⚠️ '{display_file_name}' 파일 변환 실패: {e}")
            continue

        try:
            picture = ReturnPictureEXIF(temp_path)
            image = picture.get_image()
            if image is None:
                raise ValueError("이미지를 읽을 수 없습니다.")

            width = get_width(image)
            height = get_height(image)
            thickness = get_thickness(height)
            padding = get_padding(height)
            logo_file = logo(picture)

            st.subheader(f"🖼️ 원본 파일: {display_file_name}")

            # -------------------------------------------------------------
            # EXIF 정보 존재 유무 판별
            # -------------------------------------------------------------
            raw_lens_full = str(picture.get_lens() if hasattr(picture, "get_lens") else "").strip()
            exif_data_raw = picture.exif if hasattr(picture, "exif") else {}
            raw_lens_tag = str(exif_data_raw.get("LensModel", "")).strip()
            
            has_lens = bool(raw_lens_tag) and ("lens unspecified" not in raw_lens_full.lower()) and (raw_lens_tag.lower() not in ["none", "unknown", "?", "built-in"])

            eq_focal = exif_data_raw.get("FocalLengthIn35mmFilm", "")
            if not eq_focal or str(eq_focal) == "?":
                eq_focal = exif_data_raw.get("FocalLength", "")
            focal_val_str = str(eq_focal).strip()
            has_focal = bool(focal_val_str) and (focal_val_str not in ["?", "None", "0", "0.0"])

            raw_f_num = str(picture.get_f_number() if hasattr(picture, "get_f_number") else "").strip()
            has_f_num = bool(raw_f_num) and (raw_f_num not in ["?", "None", "0.0", "0", "f/0.0", "f/0"])

            # -------------------------------------------------------------
            # 수동 입력 UI 구성 (수동 렌즈 선택 시 화각 입력칸 항시 노출)
            # -------------------------------------------------------------
            with st.expander("⚙️ 촬영 및 렌즈/화각 정보 수동 입력", expanded=(not (has_lens and has_focal and has_f_num))):
                
                # 수동 렌즈 변경 필요 여부 혹은 사용자의 자유 조절을 위해 브랜드, 렌즈, 화각, 조리개 필드 표시
                cols = st.columns(4)

                # 1. 브랜드 선택
                with cols[0]:
                    cur_brand = st.session_state.brand_dict[file_id]
                    brand_idx = brand_list.index(cur_brand) if cur_brand in brand_list else 0

                    def make_brand_callback(fid=file_id, uid=unique_id):
                        def callback():
                            new_brand = st.session_state[f"brand_select_{uid}"]
                            st.session_state.brand_dict[fid] = new_brand
                            lenses_for_brand = OLD_LENSES_BY_BRAND.get(new_brand, ["EXIF 정보 사용"])
                            if lenses_for_brand:
                                st.session_state.lens_dict[fid] = lenses_for_brand[0]
                        return callback

                    selected_brand = st.selectbox(
                        "🏷️ 브랜드",
                        brand_list,
                        index=brand_idx,
                        key=f"brand_select_{unique_id}",
                        on_change=make_brand_callback()
                    )

                # 2. 렌즈 선택
                with cols[1]:
                    available_lenses = OLD_LENSES_BY_BRAND.get(selected_brand, ["EXIF 정보 사용"])
                    cur_lens = st.session_state.lens_dict[file_id]
                    
                    if cur_lens not in available_lenses:
                        cur_lens = available_lenses[0] if available_lenses else "EXIF 정보 사용"
                        st.session_state.lens_dict[file_id] = cur_lens

                    lens_idx = available_lenses.index(cur_lens)

                    def make_lens_callback(fid=file_id, uid=unique_id):
                        return lambda: st.session_state.lens_dict.update({fid: st.session_state[f"lens_select_{uid}"]})

                    selected_lens = st.selectbox(
                        "🎞️ 렌즈 선택",
                        options=available_lenses,
                        index=lens_idx,
                        key=f"lens_select_{unique_id}",
                        on_change=make_lens_callback()
                    )

                    if selected_lens == "사용자 지정 입력":
                        def make_custom_lens_callback(fid=file_id, uid=unique_id):
                            return lambda: st.session_state.custom_lens_dict.update({fid: st.session_state[f"custom_lens_{uid}"]})

                        st.text_input(
                            "렌즈명 직접 입력",
                            value=st.session_state.custom_lens_dict[file_id],
                            placeholder="예: Jupiter-8 50mm f/2.0",
                            key=f"custom_lens_{unique_id}",
                            on_change=make_custom_lens_callback()
                        )

                # 3. 화각 선택 (EXIF 유무 상관없이 수동 지정 및 변경 가능)
                with cols[2]:
                    cur_focal = st.session_state.focal_dict[file_id]
                    focal_idx = COMMON_EQUIV_FOCAL_LENGTHS.index(cur_focal) if cur_focal in COMMON_EQUIV_FOCAL_LENGTHS else 0

                    def make_focal_callback(fid=file_id, uid=unique_id):
                        return lambda: st.session_state.focal_dict.update({fid: st.session_state[f"focal_select_{uid}"]})

                    selected_focal = st.selectbox(
                        "📐 화각 선택",
                        COMMON_EQUIV_FOCAL_LENGTHS,
                        index=focal_idx,
                        key=f"focal_select_{unique_id}",
                        on_change=make_focal_callback()
                    )

                    if selected_focal == "직접 입력":
                        def make_custom_focal_callback(fid=file_id, uid=unique_id):
                            return lambda: st.session_state.custom_focal_dict.update({fid: st.session_state[f"custom_focal_{uid}"]})

                        st.text_input(
                            "화각 직접 입력",
                            value=st.session_state.custom_focal_dict[file_id],
                            placeholder="예: 40mm",
                            key=f"custom_focal_{unique_id}",
                            on_change=make_custom_focal_callback()
                        )

                # 4. 조리개 선택
                with cols[3]:
                    cur_f = st.session_state.f_dict[file_id]
                    f_idx = MANUAL_F_NUMBERS.index(cur_f) if cur_f in MANUAL_F_NUMBERS else 0

                    def make_f_callback(fid=file_id, uid=unique_id):
                        return lambda: st.session_state.f_dict.update({fid: st.session_state[f"f_select_{uid}"]})

                    st.selectbox(
                        "🔘 조리개(f/)",
                        MANUAL_F_NUMBERS,
                        index=f_idx,
                        key=f"f_select_{unique_id}",
                        on_change=make_f_callback()
                    )

            # -------------------------------------------------------------
            # 오버라이드 및 최종 전달 값 처리
            # -------------------------------------------------------------
            chosen_manual_lens = ""
            selected_lens_val = st.session_state.lens_dict[file_id]
            if selected_lens_val == "사용자 지정 입력":
                chosen_manual_lens = st.session_state.custom_lens_dict[file_id]
            elif selected_lens_val != "EXIF 정보 사용":
                chosen_manual_lens = selected_lens_val

            chosen_manual_focal = ""
            selected_focal_val = st.session_state.focal_dict[file_id]
            if selected_focal_val == "직접 입력":
                chosen_manual_focal = st.session_state.custom_focal_dict[file_id]
            elif selected_focal_val != "EXIF 유지":
                chosen_manual_focal = selected_focal_val

            chosen_manual_f = ""
            selected_f_val = st.session_state.f_dict[file_id]
            if selected_f_val != "EXIF 유지":
                chosen_manual_f = selected_f_val.replace("f/", "").strip()

            # -------------------------------------------------------------
            # 타임존 선택 UI (GPS 정보 유무 검출)
            # -------------------------------------------------------------
            show_timezone_selector = True
            try:
                with Image.open(temp_path) as img_exif:
                    exif_data = img_exif._getexif()
                if exif_data:
                    from PIL.ExifTags import TAGS
                    readable_exif = {TAGS.get(tag, tag): val for tag, val in exif_data.items()}
                    gps_info = readable_exif.get("GPSInfo", {})
                    if gps_info and 2 in gps_info and 4 in gps_info:
                        show_timezone_selector = False
            except Exception:
                pass

            if show_timezone_selector:
                def make_tz_callback(fid=file_id, uid=unique_id):
                    return lambda: st.session_state.tz_dict.update({fid: st.session_state[f"selectbox_{uid}"]})

                if st.session_state.tz_dict[file_id] in timezone_options:
                    current_index = timezone_options.index(st.session_state.tz_dict[file_id])
                else:
                    current_index = 0

                photo_timezone = st.selectbox(
                    f"⚠️ GPS 정보가 없습니다. 적용할 타임존을 선택하세요.",
                    timezone_options,
                    index=current_index,
                    key=f"selectbox_{unique_id}",
                    on_change=make_tz_callback()
                )

            single_chosen_utc = st.session_state.tz_dict[file_id].split(" ")[0]

            base_canvas = add_border(image, width, height, thickness, padding)

            # place_model에 수동 입력/오버라이드 값 전달
            final_canvas = place_model(
                base_canvas, picture, width, height, thickness, padding, logo_file,
                chosen_utc=single_chosen_utc, 
                current_path=temp_path,
                override_lens=chosen_manual_lens,
                override_f=chosen_manual_f,
                override_focal=chosen_manual_focal
            )

            st.image(final_canvas, caption=f"결과물: {display_file_name}", use_container_width=True)

            exif_bytes = extract_exif_bytes(temp_path)

            buf = io.BytesIO()
            if exif_bytes:
                try:
                    final_canvas.save(buf, format="JPEG", quality=95, exif=exif_bytes)
                except Exception:
                    final_canvas.save(buf, format="JPEG", quality=95)
            else:
                final_canvas.save(buf, format="JPEG", quality=95)

            clean_filename = os.path.splitext(display_file_name)[0]

            st.download_button(
                label=f"📥 {display_file_name} 저장",
                data=buf.getvalue(),
                file_name=f"result_{clean_filename}.jpg",
                key=f"btn_{unique_id}",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"⚠️ '{display_file_name}' 처리 중 오류 발생: {e}")
            st.code(traceback.format_exc())
            continue

        st.divider()

    for path in temp_file_paths:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
else:
    st.info("💡 위 박스에 사진을 업로드하면 촬영 정보가 담긴 폴라로이드 스타일 프레임이 실시간으로 생성됩니다.")
