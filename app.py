import streamlit as st
import pandas as pd
import plotly.express as px

# [수정됨] 만원 이하 자투리 금액까지 정확하게 보여주도록 100% 한국어 패치
def format_won_korean(n):
    if pd.isna(n) or n == 0: return "0 원"
    
    sign = "-" if n < 0 else ""
    n = abs(int(n))
    
    eok = n // 100_000_000
    man = (n % 100_000_000) // 10_000
    rest = n % 10_000
    
    parts = []
    if eok > 0: parts.append(f"{eok:,}억")
    if man > 0: parts.append(f"{man:,}만")
    if rest > 0 or len(parts) == 0: parts.append(f"{rest:,}")
    
    return sign + " ".join(parts) + " 원"

# 1. 페이지 설정
st.set_page_config(page_title="충북학교안전공제회 자금운용 예측", layout="wide")
st.markdown("""
<style>
    /* Metric 가독성 향상 */
    [data-testid="stMetricValue"] {
        font-size: 28px !important;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 2026년도 자금운용 실시간 예측 시스템")
st.markdown("---")

# 2. 사이드바 - 데이터 파일 업로드
st.sidebar.header("📁 데이터 파일 업로드")
st.sidebar.caption("공제회 지출결의서(CSV)를 드래그해서 올려주세요.")
uploaded_file = st.sidebar.file_uploader("지출결의서 업로드", type=['csv', 'xlsx'])
skip_rows = st.sidebar.number_input("데이터 시작 전 불필요한 윗 줄 건너뛰기", value=7, step=1)

st.sidebar.markdown("---")
st.sidebar.header("🔍 시나리오 설정")

account_type = st.sidebar.selectbox("회계 구분 선택", ["공제회계", "수익회계"])
month = st.sidebar.select_slider("예측 대상 월", options=[f"{i}월" for i in range(5, 13)])

# 초기 잔액 설정
init_balance = 431159938 if account_type == "공제회계" else 365986609
current_cash = st.sidebar.number_input("현재 보통예금 잔액 (원)", value=init_balance, step=10000000)
income_maturity = st.sidebar.number_input("당월 예금 만기 유입액 (원)", value=0, step=10000000)

default_expense = 175000000 if account_type == "공제회계" else 15000000
target_expense = default_expense

# 3. 데이터 분석 로직
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('.csv'):
            try:
                df = pd.read_csv(uploaded_file, encoding='utf-8-sig', skiprows=skip_rows)
            except UnicodeDecodeError:
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding='cp949', skiprows=skip_rows)
        else:
            df = pd.read_excel(uploaded_file, skiprows=skip_rows)
        
        st.sidebar.success(f"✅ {uploaded_file.name} 로드 완료!")
        
        if '결의금액' in df.columns:
            df['금액_계산용'] = df['결의금액'].astype(str).str.replace(',', '')
            df['금액_계산용'] = pd.to_numeric(df['금액_계산용'], errors='coerce')
            
            total_sum = df['금액_계산용'].sum()
            avg_sum = int(total_sum / 9)
            target_expense = avg_sum
            
            st.sidebar.info(f"💡 분석 결과: 월 평균 약 {avg_sum:,.0f}원 지출 중")
            
    except Exception as e:
        st.sidebar.error(f"파일 분석 중 오류가 발생했습니다: {e}")

if month == "12월" and account_type == "수익회계":
    target_expense = 685000000
    
final_expense = st.sidebar.number_input(f"{month} 최종 예상 지출액 (원)", value=target_expense, step=10000000)

# 4. 결과 계산 및 메인 화면 출력
expected_end_balance = current_cash + income_maturity - final_expense

if expected_end_balance < 0:
    st.error(f"🚨 경고: {account_type} {month}말 예산 부족이 예상됩니다!")
elif expected_end_balance < 100000000:
    st.warning(f"⚠️ 주의: {account_type} {month}말 가용 현금이 1억 원 미만으로 유동성 확보가 필요합니다.")
else:
    st.success(f"✅ {account_type} {month} 자금 상태가 안정적입니다.")

st.markdown(f"## {account_type} {month}말 자금운용 예측 요약")

# [수정됨] 지저분하게 뜨던 화살표(delta) 옵션을 제거하여 깔끔하게 통일
c1, c2, c3, c4 = st.columns(4)
c1.metric("월초 보통예금", format_won_korean(current_cash))
c2.metric("당월 만기유입", format_won_korean(income_maturity))
c3.metric("당월 예상지출", format_won_korean(final_expense))
with c4:
    st.markdown(f"<p style='font-size:16px;'>월말 예측잔액</p><p style='font-size:32px; font-weight:bold; color:{'#FF4B4B' if expected_end_balance < 0 else '#1f77b4'}'>{format_won_korean(expected_end_balance)}</p>", unsafe_allow_html=True)

st.markdown("---")

st.subheader("📈 자금 구성 및 예측 잔액 흐름")

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
fig.update_layout(
    yaxis_title="금액 (원)",
    xaxis_title="",
    showlegend=False,
    shapes=[dict(type='line', yref='y', y0=0, y1=0, xref='paper', x0=0, x1=1, line=dict(color='black', width=1))]
)
fig.add_shape(type='line', x0=0, y0=100000000, x1=3, y1=100000000, line=dict(color='red', width=1, dash='dash'))
fig.add_annotation(x=0.5, y=110000000, text="안전자금 기준선 (1억)", showarrow=False, font=dict(color='red'))

st.plotly_chart(fig, use_container_width=True)