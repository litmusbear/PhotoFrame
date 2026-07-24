import streamlit as st
from PIL import Image
import os

from get_data import ReturnPictureEXIF
from lenses import OLD_LENSES_BY_BRAND, COMMON_EQUIV_FOCAL_LENGTHS, MANUAL_F_NUMBERS

st.set_page_config(page_title="Photo EXIF Frame Generator", layout="centered")

st.title("📸 Photo EXIF Frame Generator")
st.write("사진을 업로드하면 EXIF 정보를 추출하여 프레임을 생성합니다.")

uploaded_file = st.file_uploader("사진을 선택하세요 (JPG, JPEG, PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, uploaded_file.name)
    
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    exif_data = ReturnPictureEXIF(temp_path)
    
    img = exif_data.get_image()
    camera_name = exif_data.get_camera()
    shutter_speed = exif_data.get_shutter()
    iso_val = exif_data.get_iso()
    datetime_str = exif_data.get_datetime()

    exif_lens = exif_data.get_lens()
    exif_focal = exif_data.get_focal_length()
    exif_f_num = exif_data.get_f_number()

    st.subheader("⚙️ EXIF 정보 확인 및 선택")
    
    # 1. 렌즈 정보 (기존 EXIF에 없으면 선택창)
    if not exif_lens:
        selected_brand = st.selectbox("렌즈 브랜드 / 마운트 선택", list(OLD_LENSES_BY_BRAND.keys()))
        selected_lens_opt = st.selectbox("렌즈 선택", OLD_LENSES_BY_BRAND[selected_brand])
        
        if selected_lens_opt == "사용자 지정 입력":
            final_lens = st.text_input("렌즈 이름을 직접 입력하세요", "")
        elif selected_lens_opt == "EXIF 정보 사용":
            final_lens = "Lens Unspecified"
        else:
            final_lens = selected_lens_opt
    else:
        final_lens = exif_lens

    # 2. 환산 화각 (기존 EXIF에 없으면 선택창)
    if not exif_focal:
        selected_focal = st.selectbox("환산 화각 선택 (35mm Equiv.)", COMMON_EQUIV_FOCAL_LENGTHS)
        if selected_focal == "직접 입력":
            custom_focal = st.text_input("환산 화각 직접 입력 (예: 40mm)", "")
            final_focal = custom_focal if custom_focal else ""
        elif selected_focal == "EXIF 유지":
            final_focal = ""
        else:
            final_focal = selected_focal
    else:
        final_focal = exif_focal

    # 3. 조리개 값 (기존 EXIF에 없으면 선택창)
    if not exif_f_num:
        selected_f_num = st.selectbox("조리개 값(F-Number) 선택", MANUAL_F_NUMBERS)
        if selected_f_num == "EXIF 유지":
            final_f_num = "?"
        else:
            final_f_num = selected_f_num
    else:
        final_f_num = exif_f_num

    # 최종 렌즈 정보 조합
    if final_focal and "@" not in final_lens:
        full_lens_display = f"{final_lens} @{final_focal}".strip()
    else:
        full_lens_display = final_lens

    st.markdown("---")
    st.subheader("🖼️ 추출 및 선택된 EXIF 정보")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**카메라:** {camera_name}")
        st.write(f"**렌즈:** {full_lens_display}")
        st.write(f"**조리개:** {final_f_num}")
    with col2:
        st.write(f"**셔터스피드:** {shutter_speed or '?'}")
        st.write(f"**ISO:** {iso_val or '?'}")
        st.write(f"**촬영일시:** {datetime_str or '?'}")

    st.image(img, caption="업로드한 이미지", use_column_width=True)

    if os.path.exists(temp_path):
        os.remove(temp_path)
