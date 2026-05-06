import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# ---------------------------------------------------------
# 1. 기본 설정 및 한국어 단위 변환 함수
# ---------------------------------------------------------
st.set_page_config(page_title="충북학교안전공제회 자금운용 대시보드", layout="wide")
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 28px !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

def format_won_korean(n):
    if pd.isna(n) or n == 0: return "0 원"
    sign = "-" if n < 0 else ""
    n = abs(int(n))
    eok, man, rest = n // 100_000_000, (n % 100_000_000) // 10_000, n % 10_000
    parts = []
    if eok > 0: parts.append(f"{eok:,}억")
    if man > 0: parts.append(f"{man:,}만")
    if rest > 0 or len(parts) == 0: parts.append(f"{rest:,}")
    return sign + " ".join(parts) + " 원"

# ---------------------------------------------------------
# 2. 구글 시트 데이터베이스 연결 (조회)
# ---------------------------------------------------------
# 주의: 실제 연동 전까지는 에러가 날 수 있으므로 예외 처리
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    db_data = conn.read(worksheet="Sheet1") 
    db_connected = True
except Exception as e:
    db_data = pd.DataFrame()
    db_connected = False

st.title("📊 2026년도 자금운용 실시간 예측 대시보드")
if not db_connected:
    st.warning("⚠️ 현재 구글 시트(DB)와 연결되어 있지 않습니다. 관리자 세팅을 완료해 주세요.")

st.markdown("---")

# ---------------------------------------------------------
# 3. 사이드바 - 관리자 로그인 및 기능 (업로드 & 저장)
# ---------------------------------------------------------
st.sidebar.header("🔐 관리자 메뉴")
admin_pw = st.sidebar.text_input("관리자 비밀번호 (일반 직원은 입력X)", type="password")

# [보안] 임시 비밀번호 설정 (원하시는 것으로 변경하세요)
is_admin = (admin_pw == "1234") 

if admin_pw != "" and not is_admin:
    st.sidebar.error("비밀번호가 일치하지 않습니다.")
elif is_admin:
    st.sidebar.success("✅ 관리자 모드 활성화")
    st.sidebar.markdown("### 📁 데이터 누적 업데이트")
    uploaded_file = st.sidebar.file_uploader("새 지출결의서 업로드", type=['csv', 'xlsx'])
    skip_rows = st.sidebar.number_input("윗 줄 건너뛰기", value=7, step=1)
    
    if uploaded_file is not None:
        try:
            if uploaded_file.name.endswith('.csv'):
                try:
                    new_df = pd.read_csv(uploaded_file, encoding='utf-8-sig', skiprows=skip_rows)
                except:
                    uploaded_file.seek(0)
                    new_df = pd.read_csv(uploaded_file, encoding='cp949', skiprows=skip_rows)
            else:
                new_df = pd.read_excel(uploaded_file, skiprows=skip_rows)
            
            st.sidebar.info(f"파일 인식 성공: 총 {len(new_df)}건의 데이터")
            
            # 구글 시트에 업데이트 하는 버튼
            if st.sidebar.button("💾 구글 시트에 데이터 추가하기"):
                if db_connected:
                    # 기존 데이터에 새 데이터를 아래로 이어붙임(누적)
                    updated_data = pd.concat([db_data, new_df], ignore_index=True)
                    # 구글 시트 원본에 덮어쓰기
                    conn.update(worksheet="Sheet1", data=updated_data)
                    st.sidebar.success("성공적으로 구글 시트에 누적되었습니다! (새로고침 해주세요)")
                else:
                    st.sidebar.error("시트 연결이 안 되어 있어 저장할 수 없습니다.")
        except Exception as e:
            st.sidebar.error(f"파일 분석 에러: {e}")

# ---------------------------------------------------------
# 4. 일반 사용자 화면 - 시나리오 설정 및 대시보드
# ---------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("🔍 예측 시나리오 설정")

account_type = st.sidebar.selectbox("회계 구분 선택", ["공제회계", "수익회계"])
month = st.sidebar.select_slider("예측 대상 월", options=[f"{i}월" for i in range(5, 13)])

init_balance = 431159938 if account_type == "공제회계" else 365986609
current_cash = st.sidebar.number_input("월초 보통예금 잔액", value=init_balance, step=10000000)
income_maturity = st.sidebar.number_input("당월 예금 만기 유입액", value=0, step=10000000)

# 구글 시트(db_data)에서 월평균 지출액 자동 계산
avg_sum = 175000000 if account_type == "공제회계" else 15000000 # 기본값
if db_connected and not db_data.empty and '결의금액' in db_data.columns:
    temp_df = db_data.copy()
    temp_df['금액_계산용'] = temp_df['결의금액'].astype(str).str.replace(',', '')
    temp_df['금액_계산용'] = pd.to_numeric(temp_df['금액_계산용'], errors='coerce')
    total_sum = temp_df['금액_계산용'].sum()
    avg_sum = int(total_sum / 9) # 4~12월 기준
    st.sidebar.caption(f"*(DB 연동) 누적 결의금액 바탕으로 월 평균 지출액이 자동 세팅되었습니다.*")

if month == "12월" and account_type == "수익회계":
    avg_sum = 685000000

final_expense = st.sidebar.number_input(f"{month} 최종 예상 지출액", value=avg_sum, step=10000000)

# 결과 출력부 (이전 코드와 동일)
expected_end_balance = current_cash + income_maturity - final_expense

st.markdown(f"## {account_type} {month}말 자금운용 예측 요약")
c1, c2, c3, c4 = st.columns(4)
c1.metric("월초 보통예금", format_won_korean(current_cash))
c2.metric("당월 만기유입", format_won_korean(income_maturity))
c3.metric("당월 예상지출", format_won_korean(final_expense))
with c4:
    st.markdown(f"<p style='font-size:16px;'>월말 예측잔액</p><p style='font-size:32px; font-weight:bold; color:{'#FF4B4B' if expected_end_balance < 0 else '#1f77b4'}'>{format_won_korean(expected_end_balance)}</p>", unsafe_allow_html=True)

chart_data = pd.DataFrame({
    '항목': ['월초 현금', '당월 유입', '예상 지출', '월말 예측잔액'],
    '금액': [current_cash, income_maturity, final_expense, expected_end_balance],
    '유형': ['가용자금', '가용자금', '유출자금', '최종결과']
})

fig = px.bar(chart_data, x='항목', y='금액', color='유형', 
             text=chart_data['금액'].apply(format_won_korean), 
             color_discrete_map={'가용자금': '#1f77b4', '유출자금': '#FF4B4B', '최종결과': '#FFAA00' if expected_end_balance < 100000000 else '#2ca02c'},
             height=500)
fig.update_traces(textposition='outside')
fig.update_layout(yaxis_title="금액 (원)", xaxis_title="", showlegend=False)
fig.add_shape(type='line', x0=0, y0=100000000, x1=3, y1=100000000, line=dict(color='red', width=1, dash='dash'))
st.plotly_chart(fig, use_container_width=True)