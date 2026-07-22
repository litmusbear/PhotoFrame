import uuid
import streamlit as st
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

def extract_exif_bytes(source_path):
    if HAS_PIEXIF:
        try:
            exif_dict = piexif.load(source_path)
            exif_dict["0th"][piexif.ImageIFD.Orientation] = 1
            return piexif.dump(exif_dict)
        except Exception:
            pass

    try:
        with Image.open(source_path) as img:
            exif_data = img.info.get("exif")
        if exif_data:
            return exif_data
    except Exception:
        pass

    return None

st.set_page_config(page_title="사진 데이터 프레임 생성기", layout="centered")

st.markdown("""
    <style>
    /* 다크모드 대응: 전체 배경 및 기본 글자색 고정 */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: #FBF9F6 !important;
        color: #222222 !important;
    }

    /* 헤더 및 각종 타이틀 텍스트 색상 고정 */
    h1, h2, h3, h4, h5, h6, p, span, label {
        color: #222222 !important;
    }

    /* 업로드 박스 디자인 고정 */
    .stFileUploader, [data-testid="stFileUploader"] {
        background-color: #ffffff !important;
        padding: 25px;
        border-radius: 16px;
        box-shadow: 0px 8px 24px rgba(149, 157, 165, 0.06);
        border: 1px dashed #E2DFD9 !important;
    }

    /* 안내 문구 스타일 고정 */
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

    if "tz_dict" not in st.session_state:
        st.session_state.tz_dict = {}

    for uploaded_file in uploaded_files:
        file_id = uploaded_file.name
        if file_id not in st.session_state.tz_dict:
            st.session_state.tz_dict[file_id] = "UTC+09:00 (한국/일본/인도네시아 동부)"

        unique_id = uuid.uuid4().hex
        temp_path = f"temp_{unique_id}.jpg"
        temp_file_paths.append(temp_path)

        try:
            save_uploaded_file_to_temp(uploaded_file, temp_path)
        except Exception as e:
            st.error(f"⚠️ '{uploaded_file.name}' 파일 변환 실패: {e}")
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

            st.subheader(f"🖼️ 원본 파일: {uploaded_file.name}")

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
            except:
                pass

            if show_timezone_selector:
                def make_callback(fid=file_id, uid=unique_id):
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
                    on_change=make_callback()
                )

            single_chosen_utc = st.session_state.tz_dict[file_id].split(" ")[0]

            base_canvas = add_border(image, width, height, thickness, padding)
            final_canvas = place_model(
                base_canvas, picture, width, height, thickness, padding, logo_file,
                chosen_utc=single_chosen_utc, current_path=temp_path
            )

            st.image(final_canvas, caption=f"결과물: {uploaded_file.name}", use_container_width=True)

            exif_bytes = extract_exif_bytes(temp_path)

            buf = io.BytesIO()
            if exif_bytes:
                try:
                    final_canvas.save(buf, format="JPEG", quality=95, exif=exif_bytes)
                except Exception:
                    final_canvas.save(buf, format="JPEG", quality=95)
            else:
                final_canvas.save(buf, format="JPEG", quality=95)

            clean_filename = os.path.splitext(uploaded_file.name)[0]

            st.download_button(
                label=f"📥 {uploaded_file.name} 저장",
                data=buf.getvalue(),
                file_name=f"result_{clean_filename}.jpg",
                key=f"btn_{unique_id}",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"⚠️ '{uploaded_file.name}' 처리 중 오류 발생: {e}")
            continue

        st.divider()

    for path in temp_file_paths:
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
else:
    st.info("💡 위 박스에 사진을 업로드하면 촬영 정보가 담긴 폴라로이드 스타일 프레임이 실시간으로 생성됩니다.")