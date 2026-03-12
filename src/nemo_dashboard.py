import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
import os
import ast
import numpy as np

# 페이지 설정
st.set_page_config(
    page_title="NemoStore 프리미엄 매물 대시보드",
    page_icon="🏠",
    layout="wide"
)

# 1. 데이터 로드 및 전처리 함수
@st.cache_data
def load_data():
    # 배포 환경과 로컬 환경을 모두 고려한 경로 설정
    possible_paths = [
        'nemostore/data/nemo_items.db',
        '../data/nemo_items.db',
        'data/nemo_items.db'
    ]
    
    db_path = None
    for p in possible_paths:
        if os.path.exists(p):
            db_path = p
            break
            
    if not db_path:
        st.error("❌ 데이터베이스 파일을 찾을 수 없습니다. GitHub 저장소에 `nemostore/data/nemo_items.db` 파일이 포함되어 있는지 확인해주세요.")
        # 현재 작업 디렉토리 출력을 통해 디버깅 지원
        st.info(f"현재 작업 디렉토리: {os.getcwd()}")
        return pd.DataFrame()
    
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql('SELECT * FROM nemo_stores', conn)
        conn.close()
    except Exception as e:
        st.error(f"❌ 데이터 로드 중 오류 발생: {e}")
        return pd.DataFrame()
    
    # 수치형 변환
    numeric_cols = ['deposit', 'monthlyRent', 'premium', 'sale', 'size', 'floor']
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 층 정보 카테고리화
    if 'floor' in df.columns:
        df['floor_cat'] = df['floor'].apply(lambda x: '지하' if x < 0 else ('지상 1층' if x == 1 else '지상 2층 이상'))
    
    # 문자열 리스트 -> 실제 리스트 변환 (사진 URL)
    def parse_list(x):
        try:
            return ast.literal_eval(x) if isinstance(x, str) and x.startswith('[') else []
        except:
            return []
            
    df['smallPhotoList'] = df['smallPhotoUrls'].apply(parse_list)
    df['originPhotoList'] = df['originPhotoUrls'].apply(parse_list)
    
    # 가상 위경도 생성 (망포역 중심: 37.245, 127.058)
    # 실제 데이터에 좌표가 없으므로 시각화를 위해 약간의 오프셋을 줌
    np.random.seed(42)
    df['lat'] = 37.245 + np.random.uniform(-0.005, 0.005, len(df))
    df['lon'] = 127.058 + np.random.uniform(-0.005, 0.005, len(df))
    
    return df

df = load_data()

# 커스텀 CSS
st.markdown("""
<style>
    .card {
        border: 1px solid #e6e9ef;
        border-radius: 10px;
        padding: 10px;
        background-color: white;
        transition: transform 0.2s;
        cursor: pointer;
    }
    .card:hover {
        transform: scale(1.02);
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .main-title {
        color: #fe2c54;
        font-weight: bold;
    }
    .metric-box {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# 2. 사이드바 검색 및 필터
st.sidebar.title("🔍 검색 및 필터")

if df.empty:
    st.warning("⚠️ 데이터를 불러오지 못했습니다. 데이터베이스 파일을 확인해주세요.")
    st.stop()

# 필수 컬럼 존재 여부 확인
required_cols = ['title', 'businessMiddleCodeName', 'monthlyRent', 'deposit', 'premium']
missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
    st.error(f"❌ 필수 컬럼이 누락되었습니다: {', '.join(missing_cols)}")
    st.stop()

search_query = st.sidebar.text_input("매물 제목 검색", "")
all_biz = sorted(df['businessMiddleCodeName'].unique())
selected_biz = st.sidebar.multiselect("업종 선택", all_biz, default=all_biz)

st.sidebar.subheader("💰 가격 범위 (만원)")
def sidebar_slider(label, col):
    m_min, m_max = int(df[col].min()), int(df[col].max())
    # min과 max가 같을 경우 처리
    if m_min == m_max:
        return (m_min, m_max)
    return st.sidebar.slider(label, m_min, m_max, (m_min, m_max))

rent_range = sidebar_slider("월세", "monthlyRent")
deposit_range = sidebar_slider("보증금", "deposit")
premium_range = sidebar_slider("권리금", "premium")

# 데이터 필터링
filtered_df = df[
    (df['title'].str.contains(search_query, case=False, na=False)) &
    (df['businessMiddleCodeName'].isin(selected_biz)) &
    (df['monthlyRent'].between(rent_range[0], rent_range[1])) &
    (df['deposit'].between(deposit_range[0], deposit_range[1])) &
    (df['premium'].between(premium_range[0], premium_range[1]))
]

# ----------------- 메인 화면 -----------------

# 세션 상태로 상세 페이지 관리
if 'selected_item_id' not in st.session_state:
    st.session_state.selected_item_id = None

# 상세 페이지 보기
if st.session_state.selected_item_id:
    item = df[df['id'] == st.session_state.selected_item_id].iloc[0]
    
    if st.button("← 목록으로 돌아가기"):
        st.session_state.selected_item_id = None
        st.rerun()
    
    st.title(f"🏠 {item['title']}")
    
    col_img, col_info = st.columns([1, 1])
    
    with col_img:
        photos = item['originPhotoList']
        if photos:
            st.image(photos[0], use_container_width=True, caption="대표 이미지")
            if len(photos) > 1:
                cols = st.columns(3)
                for i, p in enumerate(photos[1:7]):
                    cols[i % 3].image(p, use_container_width=True)
        else:
            st.warning("이미지가 없습니다.")
            
    with col_info:
        st.subheader("📍 매물 상세 정보")
        
        # 벤치마킹 지표 계산
        avg_rent = filtered_df[filtered_df['businessMiddleCodeName'] == item['businessMiddleCodeName']]['monthlyRent'].mean()
        avg_premium = filtered_df[filtered_df['businessMiddleCodeName'] == item['businessMiddleCodeName']]['premium'].mean()
        
        def get_diff_pct(val, avg):
            if avg == 0: return "N/A"
            diff = ((val - avg) / avg) * 100
            color = "red" if diff > 0 else "blue"
            sign = "+" if diff > 0 else ""
            return f":{color}[{sign}{diff:.1f}%]"

        rent_diff = get_diff_pct(item['monthlyRent'], avg_rent)
        premium_diff = get_diff_pct(item['premium'], avg_premium)

        st.markdown(f"""
        - **업종**: {item['businessMiddleCodeName']}
        - **가격 정보**:
            - **월세**: **{item['monthlyRent']:,}만원** (업종 평균 대비 {rent_diff})
            - **보증금**: **{item['deposit']:,}만원**
            - **권리금**: **{item['premium']:,}만원** (업종 평균 대비 {premium_diff})
        - **공간 정보**:
            - **전용면적**: {item['size']}㎡
            - **층수**: {item['floor_cat']} / 지상 {item['groundFloor']}층 건물
        - **입지**: {item['nearSubwayStation']}
        """)
        
        st.divider()
        st.info(f"💡 **분석 결과**: 본 매물은 동일 업종 평균 대비 월세가 {rent_diff.split('[')[1].split(']')[0]} 수준입니다.")

else:
    # 갤러리 뷰 메인
    st.title("🏙️ NemoStore 매물 갤러리 탐색")
    
    # 1. 지도 시각화 (Density Map)
    st.subheader("📍 지역별 매물 밀집도 (망포역 중심)")
    st.map(filtered_df[['lat', 'lon']], zoom=13)
    
    # 2. 통계 시각화
    st.divider()
    row1_c1, row1_c2 = st.columns(2)
    with row1_c1:
        # 층별 임대료 비교 분석
        floor_avg = filtered_df.groupby('floor_cat')[['monthlyRent', 'premium']].mean().reset_index()
        fig_floor = px.bar(floor_avg, x='floor_cat', y=['monthlyRent', 'premium'], 
                          barmode='group', title="층별 평균 임대료 및 권리금 비교",
                          labels={'value': '가액(만원)', 'floor_cat': '층수', 'variable': '항목'})
        st.plotly_chart(fig_floor, use_container_width=True)
    with row1_c2:
        # 업종별 권리금 분포
        fig_box = px.box(filtered_df, x='businessMiddleCodeName', y='premium', color='businessMiddleCodeName',
                        title="업종별 권리금 시세 분포")
        st.plotly_chart(fig_box, use_container_width=True)

    # 3. 갤러리 뷰 (이미지 기반 목록)
    st.divider()
    st.subheader(f"🖼️ 매물 갤러리 ({len(filtered_df)}건)")
    
    # 그리드 레이아웃 (3열)
    num_cols = 3
    rows = [filtered_df.iloc[i:i+num_cols] for i in range(0, len(filtered_df), num_cols)]
    
    for row in rows:
        cols = st.columns(num_cols)
        for i, (idx, item) in enumerate(row.iterrows()):
            with cols[i]:
                # 카드 형태의 이미지 및 정보
                img_url = item['previewPhotoUrl'] if item['previewPhotoUrl'] else "https://via.placeholder.com/300"
                st.image(img_url, use_container_width=True)
                st.markdown(f"**{item['title']}**")
                st.caption(f"{item['businessMiddleCodeName']} | {item['size']}㎡ | {item['floor_cat']}")
                st.write(f"💰 {item['deposit']:,} / {item['monthlyRent']:,} (권 {item['premium']:,})")
                
                if st.button(f"상세 정보 보기", key=f"btn_{item['id']}_{idx}"):
                    st.session_state.selected_item_id = item['id']
                    st.rerun()

    # 4. 상세 리스트 (한글 컬럼명 적용)
    st.divider()
    st.subheader("📋 전체 매물 상세 리스트")
    
    # 한글 컬럼명 매핑
    col_mapping = {
        'title': '매물명',
        'businessMiddleCodeName': '업종',
        'deposit': '보증금(만원)',
        'monthlyRent': '월세(만원)',
        'premium': '권리금(만원)',
        'size': '면적(㎡)',
        'floor_cat': '층구분',
        'nearSubwayStation': '인근역'
    }
    
    list_df = filtered_df[col_mapping.keys()].rename(columns=col_mapping)
    st.dataframe(list_df, use_container_width=True, hide_index=True)

st.markdown("---")
st.caption("NemoStore Advanced Dashboard v2.0 | Powered by Plotly & Streamlit")
