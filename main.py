import uuid
import streamlit as st
import os
import io
import re
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
    COMMON_EQUIV_FOCAL_LENGTHS = ["EXIF 유지", "24mm", "28mm", "35mm", "40mm", "50mm", "58mm", "75mm", "85mm", "135mm", "직접 입력"]

def clean_uploaded_filename(filename):
    """iOS/Safari 사진 앱 업로드 시 붙는 쿼리스트링 정제"""
    decoded = urllib.parse.unquote(filename)
    clean_name = decoded.split("?")[0].split("&")[0]
    if "uuid=" in clean_name and "code=" in clean_name:
        ext = os.path.splitext(clean_name)[1]
        return f"RAW_Image{ext}"
    return os.path.basename(clean_name)


# =====================================================================
# 🚀 최적화 1: 무거운 이미지 렌더링 작업을 캐싱하여 재실행 방지
# =====================================================================
@st.cache_data(show_spinner="이미지 프레임 생성 중...")
def render_processed_image(file_bytes, single_chosen_utc, override_lens, override_f, override_focal):
    """
    동일한 파라미터 조합일 때 이미 연산된 결과물을 캐시에서 가져옵니다.
    디스크 파일 대신 메모리(io.BytesIO)를 활용합니다.
    """
    # BytesIO를 통해 임시 파일 생성 없이 메모리에서 연산
    file_stream = io.BytesIO(file_bytes)
    
    # ReturnPictureEXIF가 파일 경로 대신 Stream/Bytes도 지원하는지 확인 필요.
    # 만약 파일 경로만 지원한다면 임시 파일 처리를 내부로 고립시킵니다.
    temp_path = f"temp_cache_{uuid.uuid4().hex}.jpg"
    with open(temp_path, "wb") as f:
        f.write(file_bytes)

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

        base_canvas = add_border(image, width, height, thickness, padding)

        final_canvas = place_model(
            base_canvas, picture, width, height, thickness, padding, logo_file,
            chosen_utc=single_chosen_utc, 
            current_path=temp_path,
            override_lens=override_lens,
            override_f=override_f,
            override_focal=override_focal
        )

        # -------------------------------------------------------------
        # EXIF 바이너리 업데이트 및 최종 이미지 JPEG 변환
        # -------------------------------------------------------------
        updated_exif_bytes = update_and_extract_exif_bytes(
            temp_path,
            override_lens=override_lens,
            override_f=override_f,
            override_focal=override_focal
        )

        buf = io.BytesIO()
        if updated_exif_bytes:
            try:
                final_canvas.save(buf, format="JPEG", quality=95, exif=updated_exif_bytes)
            except Exception:
                final_canvas.save(buf, format="JPEG", quality=95)
        else:
            final_canvas.save(buf, format="JPEG", quality=95)

        return buf.getvalue()

    finally:
        # 캐싱 함수 완료 후 임시 파일 즉시 삭제
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def update_and_extract_exif_bytes(source_path, override_lens="", override_f="", override_focal=""):
    if not HAS_PIEXIF:
        try:
            with Image.open(source_path) as img:
                return img.info.get("exif")
        except Exception:
            return None

    try:
        exif_dict = piexif.load(source_path)
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    if "0th" in exif_dict and piexif.ImageIFD.Orientation in exif_dict["0th"]:
        exif_dict["0th"][piexif.ImageIFD.Orientation] = 1

    if override_lens:
        exif_dict["Exif"][piexif.ExifIFD.LensModel] = override_lens.encode('utf-8')

    if override_f:
        try:
            f_val = float(override_f.replace("f/", "").strip())
            exif_dict["Exif"][piexif.ExifIFD.FNumber] = (int(round(f_val * 10)), 10)
        except Exception:
            pass

    if override_focal:
        try:
            focal_num = float(re.sub(r'[^0-9.]', '', override_focal))
            exif_dict["Exif"][piexif.ExifIFD.FocalLength] = (int(round(focal_num * 10)), 10)
            exif_dict["Exif"][piexif.ExifIFD.FocalLengthIn35mmFilm] = int(round(focal_num))
        except Exception:
            pass

    try:
        return piexif.dump(exif_dict)
    except Exception:
        return None


# =====================================================================
# UI 레이아웃
# =====================================================================
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
    # 세션 딕셔너리 초기화
    if "tz_dict" not in st.session_state: st.session_state.tz_dict = {}
    if "brand_dict" not in st.session_state: st.session_state.brand_dict = {}
    if "lens_dict" not in st.session_state: st.session_state.lens_dict = {}
    if "custom_lens_dict" not in st.session_state: st.session_state.custom_lens_dict = {}
    if "f_dict" not in st.session_state: st.session_state.f_dict = {}
    if "focal_dict" not in st.session_state: st.session_state.focal_dict = {}
    if "custom_focal_dict" not in st.session_state: st.session_state.custom_focal_dict = {}

    brand_list = list(OLD_LENSES_BY_BRAND.keys())

    for idx, uploaded_file in enumerate(uploaded_files):
        file_id = uploaded_file.name
        display_file_name = clean_uploaded_filename(uploaded_file.name)
        
        # 바이너리 데이터 추출 (캐시 함수의 입력값으로 활용)
        file_bytes = uploaded_file.getvalue()

        # 기본 세션 값 처리
        if file_id not in st.session_state.tz_dict:
            st.session_state.tz_dict[file_id] = "UTC+09:00 (한국/일본/인도네시아 동부)"
        if file_id not in st.session_state.brand_dict:
            st.session_state.brand_dict[file_id] = brand_list[0] if brand_list else ""
        if file_id not in st.session_state.lens_dict:
            default_brand = st.session_state.brand_dict[file_id]
            default_lenses = OLD_LENSES_BY_BRAND.get(default_brand, ["EXIF 정보 사용"])
            st.session_state.lens_dict[file_id] = default_lenses[0] if default_lenses else "EXIF 정보 사용"
        if file_id not in st.session_state.custom_lens_dict: st.session_state.custom_lens_dict[file_id] = ""
        if file_id not in st.session_state.f_dict: st.session_state.f_dict[file_id] = "EXIF 유지"
        if file_id not in st.session_state.focal_dict: st.session_state.focal_dict[file_id] = "EXIF 유지"
        if file_id not in st.session_state.custom_focal_dict: st.session_state.custom_focal_dict[file_id] = ""

        unique_id = f"{hash(file_id)}_{idx}"

        try:
            st.subheader(f"🖼️ 원본 파일: {display_file_name}")

            # -------------------------------------------------------------
            # 수동 입력 옵션 드롭다운 (UI 제어)
            # -------------------------------------------------------------
            with st.expander("⚙️ 촬영 및 렌즈/화각 정보 수동 입력", expanded=False):
                cols = st.columns(4)

                # 브랜드
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
                        "🏷️ 브랜드", brand_list, index=brand_idx,
                        key=f"brand_select_{unique_id}", on_change=make_brand_callback()
                    )

                # 렌즈
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
                        "🎞️ 렌즈 선택", options=available_lenses, index=lens_idx,
                        key=f"lens_select_{unique_id}", on_change=make_lens_callback()
                    )

                    if selected_lens == "사용자 지정 입력":
                        def make_custom_lens_callback(fid=file_id, uid=unique_id):
                            return lambda: st.session_state.custom_lens_dict.update({fid: st.session_state[f"custom_lens_{uid}"]})

                        st.text_input(
                            "렌즈명 직접 입력", value=st.session_state.custom_lens_dict[file_id],
                            placeholder="예: Jupiter-8 50mm f/2.0", key=f"custom_lens_{unique_id}",
                            on_change=make_custom_lens_callback()
                        )

                # 화각
                with cols[2]:
                    cur_focal = st.session_state.focal_dict[file_id]
                    focal_idx = COMMON_EQUIV_FOCAL_LENGTHS.index(cur_focal) if cur_focal in COMMON_EQUIV_FOCAL_LENGTHS else 0

                    def make_focal_callback(fid=file_id, uid=unique_id):
                        return lambda: st.session_state.focal_dict.update({fid: st.session_state[f"focal_select_{uid}"]})

                    selected_focal = st.selectbox(
                        "📐 화각 선택", COMMON_EQUIV_FOCAL_LENGTHS, index=focal_idx,
                        key=f"focal_select_{unique_id}", on_change=make_focal_callback()
                    )

                    if selected_focal == "직접 입력":
                        def make_custom_focal_callback(fid=file_id, uid=unique_id):
                            return lambda: st.session_state.custom_focal_dict.update({fid: st.session_state[f"custom_focal_{uid}"]})

                        st.text_input(
                            "화각 직접 입력", value=st.session_state.custom_focal_dict[file_id],
                            placeholder="예: 40mm", key=f"custom_focal_{unique_id}",
                            on_change=make_custom_focal_callback()
                        )

                # 조리개
                with cols[3]:
                    cur_f = st.session_state.f_dict[file_id]
                    f_idx = MANUAL_F_NUMBERS.index(cur_f) if cur_f in MANUAL_F_NUMBERS else 0

                    def make_f_callback(fid=file_id, uid=unique_id):
                        return lambda: st.session_state.f_dict.update({fid: st.session_state[f"f_select_{uid}"]})

                    st.selectbox(
                        "🔘 조리개(f/)", MANUAL_F_NUMBERS, index=f_idx,
                        key=f"f_select_{unique_id}", on_change=make_f_callback()
                    )

            # 수동 데이터 정제
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

            # 타임존 설정
            def make_tz_callback(fid=file_id, uid=unique_id):
                return lambda: st.session_state.tz_dict.update({fid: st.session_state[f"selectbox_{uid}"]})

            current_index = timezone_options.index(st.session_state.tz_dict[file_id]) if st.session_state.tz_dict[file_id] in timezone_options else 0

            st.selectbox(
                f"🌐 적용할 타임존 선택",
                timezone_options, index=current_index,
                key=f"selectbox_{unique_id}", on_change=make_tz_callback()
            )

            single_chosen_utc = st.session_state.tz_dict[file_id].split(" ")[0]

            # -------------------------------------------------------------
            # 🚀 최적화 2: 캐싱된 이미지 연산 실행
            # -------------------------------------------------------------
            final_jpeg_bytes = render_processed_image(
                file_bytes=file_bytes,
                single_chosen_utc=single_chosen_utc,
                override_lens=chosen_manual_lens,
                override_f=chosen_manual_f,
                override_focal=chosen_manual_focal
            )

            # 결과 화면 출력
            st.image(final_jpeg_bytes, caption=f"결과물: {display_file_name}", use_container_width=True)

            clean_filename = os.path.splitext(display_file_name)[0]

            # 다운로드 버튼
            st.download_button(
                label=f"📥 {display_file_name} 저장",
                data=final_jpeg_bytes,
                file_name=f"result_{clean_filename}.jpg",
                key=f"btn_{unique_id}",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"⚠️ '{display_file_name}' 처리 중 오류 발생: {e}")
            st.code(traceback.format_exc())
            continue

        st.divider()

else:
    st.info("💡 위 박스에 사진을 업로드하면 촬영 정보가 담긴 폴라로이드 스타일 프레임이 실시간으로 생성됩니다.")
