import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from io import BytesIO
import requests
import pytz

# ====== KONFIGURASI DASHBOARD ======
st.set_page_config(layout="wide", page_title="Dashboard Pemakaian Harian PLTU Anggrek", page_icon="📈")
st.markdown("<h1 style='text-align: center;'>📊 Dashboard Pemakaian Harian PLTU Anggrek</h1>", unsafe_allow_html=True)

# ====== CSS UNTUK STYLING CARDS ======
st.markdown("""
<style>
.metric-card {
    background-color: #1e1e2f;
    border-radius: 10px;
    padding: 15px;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.2);
    text-align: center;
    color: #ffffff;
    margin: 10px 0;
}
.metric-card h3 {
    font-size: 18px;
    margin-bottom: 10px;
    color: #a3bffa;
}
.metric-card p {
    font-size: 24px;
    font-weight: bold;
    margin: 0;
    color: #ffffff;
}
</style>
""", unsafe_allow_html=True)

# ====== AMBIL DATA DARI GOOGLE SHEET ======
@st.cache_data
def load_google_sheet():
    url = "https://docs.google.com/spreadsheets/d/1RgWa7PSEVr-rmftl1KmYrpH_04yERQ-ANNJJJBhlVLc/export?format=xlsx"
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Gagal mengunduh file dari Google Sheet.")
    return pd.read_excel(BytesIO(response.content), sheet_name='PLTU ANGGREK')

try:
    df = load_google_sheet()
    df['Tanggal'] = pd.to_datetime(df['Tanggal'], errors='coerce')
    df = df.dropna(subset=['Tanggal'])

    numeric_columns = ['PEMAKAIAN UNIT 1', 'PEMAKAIAN UNIT 2', 'TOTAL PEMAKAIAN', 'HOP\n (HARI)', 
                       'Flowrate (MT/hours)', 'DS (MT)', 'Durasi Bongkar (Hours)', 'Durasi Tunggu (Hours)']
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    tz = pytz.timezone("Asia/Jakarta")
    yesterday = datetime.now(tz).date() - timedelta(days=1)
    df_yesterday = df[df['Tanggal'].dt.date == yesterday]

    if not df_yesterday.empty:
        pemakaian1 = df_yesterday['PEMAKAIAN UNIT 1'].values[0]
        pemakaian2 = df_yesterday['PEMAKAIAN UNIT 2'].values[0]
        total_pemakaian = df_yesterday['TOTAL PEMAKAIAN'].values[0]
        rata_pemakaian = df_yesterday[['PEMAKAIAN UNIT 1', 'PEMAKAIAN UNIT 2']].mean(axis=1).values[0]
        hop = df_yesterday['HOP\n (HARI)'].values[0]
    else:
        pemakaian1 = pemakaian2 = total_pemakaian = rata_pemakaian = hop = None

    # ====== KARTU RINGKASAN ======
    st.markdown("### 🔢 Ringkasan Pemakaian Kemarin")
    col1, col2, col3, col4, col5 = st.columns(5)
    for col, judul, nilai, satuan in zip(
        [col1, col2, col3, col4, col5],
        ["⚡ Pemakaian Unit 1", "⚡ Pemakaian Unit 2", "📊 Total Pemakaian", "📈 Rata-rata Pemakaian", "⏳ HOP"],
        [pemakaian1, pemakaian2, total_pemakaian, rata_pemakaian, hop],
        ["MT", "MT", "MT", "MT", "Hari"]
    ):
        with col:
            st.markdown(
                f"""<div class=\"metric-card\"><h3>{judul}</h3><p>{nilai:.2f} {satuan}</p></div>""" 
                if nilai is not None else 
                f"""<div class=\"metric-card\"><h3>{judul}</h3><p>N/A</p></div>""", 
                unsafe_allow_html=True)

    # ====== PENGOLAHAN DATA ======
    df['Bulan'] = df['Tanggal'].dt.to_period('M').astype(str)
    df['Tahun'] = df['Tanggal'].dt.year.astype(str)
    current_month = datetime.now(tz).strftime('%Y-%m')
    df = df[df['Bulan'] <= current_month]

    monthly_avg = df.groupby('Bulan').agg({
        'Flowrate (MT/hours)': 'mean',
        'DS (MT)': 'mean',
        'Durasi Bongkar (Hours)': 'mean',
        'Durasi Tunggu (Hours)': 'mean'
    }).reset_index()
    monthly_avg['Flowrate (MT/day)'] = monthly_avg['Flowrate (MT/hours)'] * 24

    supplier_monthly_avg = df.groupby(['Bulan', 'Suppliers'])['Flowrate (MT/hours)'].mean().reset_index()

    # ====== TREND HARIAN DARI AWAL TAHUN ======
    st.markdown("### 📈 Trend Pemakaian Harian (Sejak Awal Tahun)")
    df_year = df[df['Tanggal'].dt.year == datetime.now(tz).year]
    if not df_year.empty:
        fig_trend = px.line(
            df_year, x='Tanggal', y=['PEMAKAIAN UNIT 1', 'PEMAKAIAN UNIT 2', 'TOTAL PEMAKAIAN'],
            labels={'value': 'Pemakaian (MT)', 'variable': 'Unit'}
        )
        fig_trend.update_traces(fill='tozeroy', line_shape='spline', opacity=0.4, showlegend=True)
        fig_trend.update_layout(
            template='plotly_dark',
            title=dict(text='Trend Pemakaian Harian per Unit (Sejak Awal Tahun)', x=0.5, xanchor='center'),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5),
            margin=dict(t=70)
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Data pemakaian harian tidak tersedia.")

    # ====== 2x2 GRAFIK TAMBAHAN ======
    st.markdown("### 📊 Analisis Bongkar Muat Rata-rata Per Bulan")
    col_graph1, col_graph2 = st.columns(2)
    col_graph3, col_graph4 = st.columns(2)

    # Grafik 1: Volume vs Flowrate
    with col_graph1:
        st.markdown("#### Perbandingan Rata-rata Volume vs Flowrate")
        flowrate_data = monthly_avg.dropna(subset=['DS (MT)', 'Flowrate (MT/day)'])
        if not flowrate_data.empty:
            fig_flowrate = go.Figure()
            fig_flowrate.add_trace(go.Bar(x=flowrate_data['Bulan'], y=flowrate_data['DS (MT)'], name='Volume (MT)', text=flowrate_data['DS (MT)'].round(2), textposition='auto', marker_color='rgba(75,192,192,0.7)'))
            fig_flowrate.add_trace(go.Scatter(x=flowrate_data['Bulan'], y=flowrate_data['Flowrate (MT/day)'], yaxis='y2', name='Flow Rate (MT/day)', mode='lines+markers+text', line=dict(color='deepskyblue'), text=flowrate_data['Flowrate (MT/day)'].round(2), textposition='top center'))
            fig_flowrate.update_layout(template='plotly_dark', barmode='overlay', yaxis=dict(title='Volume (MT/Day)'), yaxis2=dict(title='Flow Rate (MT/Day)', overlaying='y', side='right'), title=dict(text='Perbandingan Rata-rata Volume vs Flowrate per Bulan', x=0.5, xanchor='center'), legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5))
            st.plotly_chart(fig_flowrate, use_container_width=True)
        else:
            st.info("Data flowrate atau volume tidak tersedia.")

    # Grafik 2: Flowrate per Supplier
    with col_graph2:
        st.markdown("#### Rata-rata Flow Rate Unloading per Supplier")
        if not supplier_monthly_avg.empty:
            fig_supplier_bar = px.bar(supplier_monthly_avg, x='Bulan', y='Flowrate (MT/hours)', color='Suppliers', text='Flowrate (MT/hours)', barmode='group', labels={'Flowrate (MT/hours)': 'Flow Rate (MT/Jam)', 'Bulan': 'Bulan'}, title='Rata-rata Flow Rate Unloading per Supplier per Bulan')
            fig_supplier_bar.update_traces(texttemplate='%{text:.2f}', textposition='outside', opacity=0.8)
            fig_supplier_bar.update_layout(template='plotly_dark', title=dict(x=0.5, xanchor='center'), legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5))
            st.plotly_chart(fig_supplier_bar, use_container_width=True)
        else:
            st.info("Data supplier tidak tersedia.")

    # Grafik 3: Komposisi Total B/L per Supplier (Pie Chart)
    with col_graph3:
        st.markdown("#### Komposisi Total B/L per Supplier")
        total_ds_supplier = df.groupby('Suppliers')['DS (MT)'].sum().reset_index()
        total_ds_supplier = total_ds_supplier.dropna()
        if not total_ds_supplier.empty:
            fig_pie = px.pie(total_ds_supplier, names='Suppliers', values='DS (MT)', title='Komposisi Total B/L per Supplier', hole=0.3)
            fig_pie.update_traces(textinfo='percent+label')
            fig_pie.update_layout(template='plotly_dark', title=dict(x=0.5, xanchor='center'))
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Data DS tidak tersedia.")

    # Grafik 4: Volume Total per Supplier (Bar Blok)
    with col_graph4:
        st.markdown("#### Total Volume per Supplier")
        if not total_ds_supplier.empty:
            fig_bar = px.bar(total_ds_supplier, x='Suppliers', y='DS (MT)', text='DS (MT)', labels={'DS (MT)': 'Volume (MT)'}, title='Total Volume B/L per Supplier')
            fig_bar.update_traces(texttemplate='%{text:.2f}', textposition='outside', marker_color='skyblue')
            fig_bar.update_layout(template='plotly_dark', title=dict(x=0.5, xanchor='center'), xaxis_tickangle=-30)
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Data volume supplier tidak tersedia.")

except Exception as e:
    st.error(f"Gagal memproses data: {e}")
