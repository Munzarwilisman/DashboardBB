import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from io import BytesIO
import requests
import pytz
import anthropic

# ====== KONFIGURASI API ANTHROPIC ======
client = anthropic.Anthropic(api_key=st.secrets["anthropic"]["api_key"])

def analyze_with_ai(prompt_text):
    try:
        message = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=2000,
            temperature=0.3,
            system="""Anda adalah analis data ahli di bidang pembangkit listrik. Tugas Anda:
            1. Analisis semua visualisasi dashboard 
            2. Berikan insight dari cards dan grafik
            3. Hubungkan temuan antar visualisasi
            4. Berikan rekomendasi berbasis data
            5. Format output terstruktur dengan markdown""",
            messages=[
                {
                    "role": "user",
                    "content": prompt_text
                }
            ]
        )
        return message.content[0].text
    except Exception as e:
        return f"Gagal memproses AI: {str(e)}"

# ====== CONFIG DASHBOARD ======
st.set_page_config(layout="wide", page_title="DASHBOARD ENERGI PRIMER PLTU Anggrek", page_icon="📈")
st.markdown("<h1 style='text-align: center;'>📊 DASHBOARD ENERGI PRIMER PLTU Anggrek</h1>", unsafe_allow_html=True)

# ====== CSS STYLING ======
st.markdown("""
<style>
[data-testid="column"] {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
}
.css-1r6slb0 {
    flex-wrap: nowrap !important;
    overflow-x: auto;
}
.metric-card {
    min-width: 200px;
    flex-shrink: 0;
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
.block-container {
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}
.stPlotlyChart {
    width: 100% !important;
    height: auto !important;
}
</style>
""", unsafe_allow_html=True)

# ====== LOAD DATA ======
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
    today = datetime.now(tz).date()

    # ====== FILTER PERIODE ======
    col_period, _ = st.columns([1, 5])
    with col_period:
        st.markdown("#### 📆 Periode")
        periode_opsi = ["Kemarin", "1 Minggu Terakhir", "1 Bulan Terakhir", "Bulan Ini", "Tahun Ini"]
        periode_pilihan = st.selectbox(" ", options=periode_opsi, index=3, label_visibility="collapsed")

    def filter_by_periode(df, pilihan):
        if pilihan == "Kemarin":
            return df[df['Tanggal'].dt.date == today - timedelta(days=1)]
        elif pilihan == "1 Minggu Terakhir":
            return df[df['Tanggal'].dt.date >= today - timedelta(days=7)]
        elif pilihan == "1 Bulan Terakhir":
            return df[df['Tanggal'].dt.date >= today - timedelta(days=30)]
        elif pilihan == "Bulan Ini":
            return df[(df['Tanggal'].dt.month == today.month) & (df['Tanggal'].dt.year == today.year)]
        elif pilihan == "Tahun Ini":
            return df[df['Tanggal'].dt.year == today.year]
        return df.copy()

    df_filtered = filter_by_periode(df, periode_pilihan)

    # ====== SUMMARY CARDS ======
    st.markdown("### 🔢 Ringkasan Pemakaian")
    col1, col2, col3, col4, col5 = st.columns(5)

    if not df_filtered.empty:
        pemakaian1 = df_filtered['PEMAKAIAN UNIT 1'].sum()
        pemakaian2 = df_filtered['PEMAKAIAN UNIT 2'].sum()
        total_pemakaian = df_filtered['TOTAL PEMAKAIAN'].sum()
        rata_pemakaian = df_filtered[['PEMAKAIAN UNIT 1', 'PEMAKAIAN UNIT 2']].mean(axis=1).mean()
        hop = df_filtered['HOP\n (HARI)'].mean()
    else:
        pemakaian1 = pemakaian2 = total_pemakaian = rata_pemakaian = hop = None

    for col, judul, nilai, satuan in zip(
        [col1, col2, col3, col4, col5],
        ["⚡ Pemakaian Unit 1", "⚡ Pemakaian Unit 2", "📊 Total Pemakaian", "📈 Rata-rata Pemakaian", "⏳ HOP"],
        [pemakaian1, pemakaian2, total_pemakaian, rata_pemakaian, hop],
        ["MT", "MT", "MT", "MT", "Hari"]
    ):
        with col:
            st.markdown(
                f"""<div class="metric-card"><h3>{judul}</h3><p>{nilai:.2f} {satuan}</p></div>""" 
                if nilai is not None else 
                f"""<div class="metric-card"><h3>{judul}</h3><p>N/A</p></div>""", 
                unsafe_allow_html=True)

    # ====== TREND PEMAKAIAN ======
    st.markdown("### 📈 Trend Pemakaian Harian")
    if not df_filtered.empty:
        fig_trend = px.line(
            df_filtered, x='Tanggal', y=['PEMAKAIAN UNIT 1', 'PEMAKAIAN UNIT 2', 'TOTAL PEMAKAIAN'],
            labels={'value': 'Pemakaian (MT)', 'variable': 'Unit'}
        )
        fig_trend.update_traces(fill='tozeroy', line_shape='spline', opacity=0.4)
        fig_trend.update_layout(
            template='plotly_dark',
            title=dict(text='Trend Pemakaian Harian per Unit', x=0.5, xanchor='center'),
            legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig_trend, use_container_width=True)
    else:
        st.info("Data pemakaian harian tidak tersedia.")

    # ====== ANALISIS BONGKAR MUAT ======
    df['Bulan'] = df['Tanggal'].dt.to_period('M').astype(str)
    monthly_avg = df.groupby('Bulan').agg({
        'Flowrate (MT/hours)': 'mean',
        'DS (MT)': 'mean',
        'Durasi Bongkar (Hours)': 'mean',
        'Durasi Tunggu (Hours)': 'mean'
    }).reset_index()
    monthly_avg['Flowrate (MT/day)'] = monthly_avg['Flowrate (MT/hours)'] * 24

    supplier_monthly_avg = df.groupby(['Bulan', 'Suppliers'])['Flowrate (MT/hours)'].mean().reset_index()
    total_ds_supplier = df.groupby('Suppliers')['DS (MT)'].sum().reset_index().dropna()

    st.markdown("### 📊 Analisis Bongkar Muat Rata-rata Per Bulan")
    col_graph1, col_graph2 = st.columns(2)
    col_graph3, col_graph4 = st.columns(2)

    with col_graph1:
        st.markdown("#### Perbandingan Rata-rata Volume vs Flowrate")
        if not monthly_avg.empty:
            fig_flowrate = go.Figure()
            fig_flowrate.add_trace(go.Bar(x=monthly_avg['Bulan'], y=monthly_avg['DS (MT)'], name='Volume (MT)', 
                                        marker_color='rgba(75,192,192,0.7)', 
                                        text=monthly_avg['DS (MT)'].round(2), textposition='auto'))
            fig_flowrate.add_trace(go.Scatter(x=monthly_avg['Bulan'], y=monthly_avg['Flowrate (MT/day)'], 
                                   yaxis='y2', name='Flowrate (MT/day)', mode='lines+markers+text', 
                                   text=monthly_avg['Flowrate (MT/day)'].round(2), textposition='top center', 
                                   line=dict(color='deepskyblue')))
            fig_flowrate.update_layout(template='plotly_dark', 
                                     yaxis=dict(title='Volume (MT)'), 
                                     yaxis2=dict(title='Flow Rate (MT/day)', overlaying='y', side='right'), 
                                     title=dict(text='Volume vs Flowrate Bulanan', x=0.5, xanchor='center'))
            st.plotly_chart(fig_flowrate, use_container_width=True)

    with col_graph2:
        st.markdown("#### Rata-rata Flow Rate per Supplier")
        if not supplier_monthly_avg.empty:
            fig_supplier = px.bar(supplier_monthly_avg, x='Bulan', y='Flowrate (MT/hours)', 
                                 color='Suppliers', text='Flowrate (MT/hours)', barmode='group')
            fig_supplier.update_traces(texttemplate='%{text:.2f}', textposition='outside')
            fig_supplier.update_layout(template='plotly_dark', 
                                     title=dict(text='Flowrate per Supplier per Bulan', x=0.5, xanchor='center'))
            st.plotly_chart(fig_supplier, use_container_width=True)

    with col_graph3:
        st.markdown("#### Komposisi Total B/L per Supplier")
        if not total_ds_supplier.empty:
            fig_pie = px.pie(total_ds_supplier, names='Suppliers', values='DS (MT)', hole=0.3)
            fig_pie.update_traces(textinfo='percent+label')
            fig_pie.update_layout(template='plotly_dark', 
                                title=dict(text='Komposisi Total B/L per Supplier', x=0.5, xanchor='center'))
            st.plotly_chart(fig_pie, use_container_width=True)

    with col_graph4:
        st.markdown("#### Total Volume per Supplier")
        if not total_ds_supplier.empty:
            fig_bar = px.bar(total_ds_supplier, x='Suppliers', y='DS (MT)', text='DS (MT)', 
                            labels={'DS (MT)': 'Volume (MT)'})
            fig_bar.update_traces(texttemplate='%{text:.2f}', textposition='outside', marker_color='skyblue')
            fig_bar.update_layout(template='plotly_dark', 
                                title=dict(text='Total Volume per Supplier', x=0.5, xanchor='center'), 
                                xaxis_tickangle=-30)
            st.plotly_chart(fig_bar, use_container_width=True)

    # ====== AI ANALYSIS SECTION ======
    st.markdown("### 🤖 ANALYZE AI ANGGREK")
    
    if not df_filtered.empty:
        # Deskripsi semua visualisasi untuk AI
        visual_descriptions = f"""
## Deskripsi Visualisasi Dashboard:

### 1. Ringkasan Pemakaian (Cards):
- Periode: {periode_pilihan}
- ⚡ Pemakaian Unit 1: {pemakaian1:.2f} MT
- ⚡ Pemakaian Unit 2: {pemakaian2:.2f} MT
- 📊 Total Pemakaian: {total_pemakaian:.2f} MT
- 📈 Rata-rata Harian: {rata_pemakaian:.2f} MT
- ⏳ HOP Rata-rata: {hop:.2f} Hari

### 2. Trend Pemakaian Harian:
- Rentang: {df_filtered['Tanggal'].min().strftime('%d %b %Y')} hingga {df_filtered['Tanggal'].max().strftime('%d %b %Y')}
- {len(df_filtered)} hari data
- Tren Unit 1, Unit 2, dan Total

### 3. Analisis Bongkar Muat:
#### a. Volume vs Flowrate:
- Volume rata-rata: {monthly_avg['DS (MT)'].mean():.2f} MT
- Flowrate rata-rata: {monthly_avg['Flowrate (MT/day)'].mean():.2f} MT/hari
- Korelasi antara volume dan kecepatan bongkar

#### b. Flowrate per Supplier:
- Supplier: {', '.join(supplier_monthly_avg['Suppliers'].unique())}
- Variasi flowrate antar supplier

#### c. Komposisi Supplier:
- Distribusi persentase kontribusi supplier
- Supplier dominan: {total_ds_supplier.loc[total_ds_supplier['DS (MT)'].idxmax(), 'Suppliers']}

#### d. Total Volume per Supplier:
- Total volume per supplier
- Perbandingan absolut kontribusi
"""

        ai_prompt = f"""
{visual_descriptions}

## Permintaan Analisis:
1. Berikan ringkasan eksekutif dari seluruh dashboard
2. Analisis komparatif Unit 1 vs Unit 2:
   - Perbedaan konsumsi
   - Pola pemakaian
3. Evaluasi trend temporal:
   - Pola harian/mingguan
   - Anomali penting
4. Analisis bongkar muat:
   - Efisiensi operasional
   - Perbandingan supplier
5. Hitung metrik kunci:
   - Rasio pemakaian Unit1/Unit2
   - Efisiensi bongkar (volume/durasi)
   - Variasi HOP
6. Rekomendasi operasional spesifik

## Format Output:
### 🎯 Ringkasan Eksekutif
[1-2 paragraf ringkasan temuan utama]

### 📌 Insight Utama
- Poin 1: [Penting]
- Poin 2: [Menarik]
- Poin 3: [Kritis]

### 🔍 Analisis Mendalam
#### Unit 1 vs Unit 2
[Perbandingan rinci dengan data pendukung]

#### Trend Temporal
[Analisis pola dan anomali]

#### Kinerja Bongkar Muat
[Evaluasi supplier dan flowrate]

### 📊 Metrik Kunci
- Rasio Unit1/Unit2: [X:Y]
- Efisiensi Bongkar: [Y MT/jam]
- Variabilitas HOP: [Z%]

### 🚀 Rekomendasi
1. [Rekomendasi spesifik untuk Unit 1]
2. [Rekomendasi untuk peningkatan bongkar muat] 
3. [Saran optimasi supplier]
"""

    if st.button("🚀 Analisis Energi Primer Anggrek", type="primary"):
        with st.spinner("🧠 AI sedang menganalisis seluruh dashboard..."):
            hasil_ai = analyze_with_ai(ai_prompt)
        
        st.markdown("## 📝 Hasil Analisis Komprehensif")
        st.markdown("---")
        
        with st.expander("🔍 Baca Laporan Lengkap", expanded=True):
            st.markdown(hasil_ai)
        
        st.markdown("---")
        st.caption(f"Laporan dihasilkan otomatis pada {datetime.now().strftime('%d %B %Y %H:%M')} oleh Claude 3.5 Sonnet AI")
        
        # Tambahkan fitur download
        st.download_button(
            label="⬇️ Download Laporan",
            data=hasil_ai,
            file_name=f"Laporan_Analisis_PLTU_{today.strftime('%Y%m%d')}.md",
            mime="text/markdown"
        )
    else:
        st.info("ℹ️ Klik tombol di atas untuk menghasilkan laporan analisis komprehensif")

except Exception as e:
    st.error(f"⚠️ Error: {str(e)}")
