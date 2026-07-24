import streamlit as st
from PIL import Image
import os

# 데이터 처리 모듈 및 렌즈 목록 임포트
from get_data import ReturnPictureEXIF
from lenses import OLD_LENSES_BY_BRAND, COMMON_EQUIV_FOCAL_LENGTHS, MANUAL_F_NUMBERS

st.set_page_config(page_title="Photo EXIF Frame Generator", layout="centered")

st.title("📸 Photo EXIF Frame Generator")
st.write("사진을 업로드하면 EXIF 정보를 추출하여 프레임을 생성합니다.")

# 1. 파일 업로드
uploaded_file = st.file_uploader("사진을 선택하세요 (JPG, JPEG, PNG)", type=["jpg", "jpeg", "png"])

if uploaded_file is not None:
    # 임시 파일로 저장하여 EXIF 추출 모듈에 전달
    temp_dir = "temp"
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, uploaded_file.name)
    
    with open(temp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    # EXIF 데이터 객체 생성
    exif_data = ReturnPictureEXIF(temp_path)
    
    # 기본 이미지 및 카메라 정보 불러오기
    img = exif_data.get_image()
    camera_name = exif_data.get_camera()
    shutter_speed = exif_data.get_shutter()
    iso_val = exif_data.get_iso()
    datetime_str = exif_data.get_datetime()

    # EXIF에서 기본 추출된 렌즈, 화각, 조리개 값 (없으면 None)
    exif_lens = exif_data.get_lens()
    exif_focal = exif_data.get_focal_length()
    exif_f_num = exif_data.get_f_number()

    st.subheader("⚙️ EXIF 정보 확인 및 추가 입력")
    st.info(f"**카메라:** {camera_name} | **셔터스피드:** {shutter_speed or '?'} | **ISO:** {iso_val or '?'}")

    # -------------------------------------------------------------------
    # 2. 렌즈 정보 처리 (EXIF에 없으면 선택창 노출)
    # -------------------------------------------------------------------
    if not exif_lens:
        st.warning("렌즈 정보를 찾을 수 없습니다. 수동으로 선택해 주세요.")
        selected_brand = st.selectbox("렌즈 브랜드 / 마운트", list(OLD_LENSES_BY_BRAND.keys()))
        selected_lens_opt = st.selectbox("렌즈 선택", OLD_LENSES_BY_BRAND[selected_brand])
        
        if selected_lens_opt == "사용자 지정 입력":
            final_lens = st.text_input("렌즈 이름을 직접 입력하세요", "")
        elif selected_lens_opt == "EXIF 정보 사용":
            final_lens = "Lens Unspecified"
        else:
            final_lens = selected_lens_opt
    else:
        final_lens = exif_lens

    # -------------------------------------------------------------------
    # 3. 환산 화각 처리 (EXIF에 없으면 선택창 노출)
    # -------------------------------------------------------------------
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

    # -------------------------------------------------------------------
    # 4. 조리개 값(F-Number) 처리 (EXIF에 없으면 선택창 노출)
    # -------------------------------------------------------------------
    if not exif_f_num:
        selected_f_num = st.selectbox("조리개 값(F-Number) 선택", MANUAL_F_NUMBERS)
        if selected_f_num == "EXIF 유지":
            final_f_num = "?"
        else:
            final_f_num = selected_f_num
    else:
        final_f_num = exif_f_num

    # -------------------------------------------------------------------
    # 5. 최종 데이터 조합 및 출력 텍스트 구성
    # -------------------------------------------------------------------
    # 화각 조합 (렌즈명 뒤에 @35mm 형태로 결합)
    if final_focal and "@" not in final_lens:
        full_lens_display = f"{final_lens} @{final_focal}".strip()
    else:
        full_lens_display = final_lens

    st.markdown("---")
    st.subheader("🖼️ 액자에 들어갈 최종 텍스트 정보")
    
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**카메라:** {camera_name}")
        st.write(f"**렌즈:** {full_lens_display}")
        st.write(f"**조리개:** {final_f_num}")
    with col2:
        st.write(f"**셔터스피드:** {shutter_speed or '?'}")
        st.write(f"**ISO:** {iso_val or '?'}")
        st.write(f"**촬영일시:** {datetime_str or '?'}")

    # 이미지 프리뷰 표시
    st.image(img, caption="업로드한 이미지 프리뷰", use_column_width=True)

    # 사용 완료 후 임시 파일 삭제
    if os.path.exists(temp_path):
        os.remove(temp_path)    }
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

    # 세션 딕셔너리 초기화 (타임존 세션 저장 방식과 일치)
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

    brand_list = list(OLD_LENSES_BY_BRAND.keys())

    for idx, uploaded_file in enumerate(uploaded_files):
        file_id = uploaded_file.name
        
        # 파일별 기본 세션 값 세팅
        if file_id not in st.session_state.tz_dict:
            st.session_state.tz_dict[file_id] = "UTC+09:00 (한국/일본/인도네시아 동부)"
        if file_id not in st.session_state.brand_dict:
            st.session_state.brand_dict[file_id] = brand_list[0] if brand_list else ""
        if file_id not in st.session_state.lens_dict:
            st.session_state.lens_dict[file_id] = "EXIF 정보 사용"
        if file_id not in st.session_state.custom_lens_dict:
            st.session_state.custom_lens_dict[file_id] = ""
        if file_id not in st.session_state.f_dict:
            st.session_state.f_dict[file_id] = "EXIF 유지"

        unique_id = f"{uuid.uuid4().hex[:6]}_{idx}"
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

            # -------------------------------------------------------------
            # [개선] 브랜드별 렌즈 선택 UI
            # -------------------------------------------------------------
            with st.expander("⚙️ 렌즈 / 조리개 수동 변경 (올드렌즈 설정)", expanded=True):
                col_brand, col_lens, col_f = st.columns([1.2, 1.8, 1])

                # 1. 브랜드 선택
                with col_brand:
                    cur_brand = st.session_state.brand_dict[file_id]
                    brand_idx = brand_list.index(cur_brand) if cur_brand in brand_list else 0

                    def make_brand_callback(fid=file_id, uid=unique_id):
                        return lambda: st.session_state.brand_dict.update({fid: st.session_state[f"brand_select_{uid}"]})

                    selected_brand = st.selectbox(
                        "🏷️ 브랜드",
                        brand_list,
                        index=brand_idx,
                        key=f"brand_select_{unique_id}",
                        on_change=make_brand_callback()
                    )

                # 2. 선택된 브랜드에 종속된 렌즈 목록 선택
                with col_lens:
                    available_lenses = OLD_LENSES_BY_BRAND.get(selected_brand, ["EXIF 정보 사용"])
                    cur_lens = st.session_state.lens_dict[file_id]
                    lens_idx = available_lenses.index(cur_lens) if cur_lens in available_lenses else 0

                    def make_lens_callback(fid=file_id, uid=unique_id):
                        return lambda: st.session_state.lens_dict.update({fid: st.session_state[f"lens_select_{uid}"]})

                    selected_lens = st.selectbox(
                        "🎞️ 렌즈 선택",
                        options=available_lenses,
                        index=lens_idx,
                        key=f"lens_select_{unique_id}",
                        on_change=make_lens_callback()
                    )

                    # '사용자 지정 입력'일 때 직접 입력창 활성화
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

                # 3. 조리개 선택
                with col_f:
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
            # 세션 데이터에서 최종 전달 값 처리
            # -------------------------------------------------------------
            chosen_manual_lens = ""
            selected_lens_val = st.session_state.lens_dict[file_id]
            
            if selected_lens_val == "사용자 지정 입력":
                chosen_manual_lens = st.session_state.custom_lens_dict[file_id]
            elif selected_lens_val != "EXIF 정보 사용":
                chosen_manual_lens = selected_lens_val

            chosen_manual_f = ""
            selected_f_val = st.session_state.f_dict[file_id]
            if selected_f_val != "EXIF 유지":
                chosen_manual_f = selected_f_val.replace("f/", "").strip()

            # -------------------------------------------------------------
            # 타임존 선택 UI
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

            # place_model에 최종 덮어쓸 값 전달
            final_canvas = place_model(
                base_canvas, picture, width, height, thickness, padding, logo_file,
                chosen_utc=single_chosen_utc, 
                current_path=temp_path,
                override_lens=chosen_manual_lens,
                override_f=chosen_manual_f
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
