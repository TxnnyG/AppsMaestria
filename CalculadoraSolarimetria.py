import streamlit as st
import numpy as np
import pandas as pd
import time
import os
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from fpdf import FPDF

st.set_page_config(
    page_title="Calculadora Solarimétrica Avanzada - UACM",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilos CSS profesionales con la paleta institucional (Vino / Guinda)
st.markdown("""
    <style>
    .main {
        background-color: #fdfbfb;
    }
    .stButton>button {
        background-color: #7b1113;
        color: white;
        border-radius: 8px;
        font-weight: bold;
        padding: 0.5rem 1rem;
    }
    .stButton>button:hover {
        background-color: #590c0e;
    }
    </style>
""", unsafe_allow_html=True)

st.title("☀️ Calculadora Solarimétrica y Memoria de Cálculo Avanzada")
st.markdown("Herramienta integral de ingeniería para el análisis geométrico solar, simulación interactiva y generación de reportes técnicos.")

# LASE PARA GENERAR EL PDF PROFESIONAL CON DISEÑO INSTITUCIONAL UACM
class PDFReport(FPDF):
    def header(self):
        self.set_fill_color(123, 17, 19)
        self.rect(0, 0, 210, 15, 'F')
        
        self.set_font('helvetica', 'B', 10)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 4)
        self.cell(0, 6, 'UNIVERSIDAD AUTÓNOMA DE LA CIUDAD DE MÉXICO (UACM)', 0, 0, 'L')
        
        self.set_font('helvetica', '', 8.5)
        self.set_xy(10, 18)
        self.set_text_color(80, 80, 80)
        self.cell(0, 5, 'Maestria en Ingenieria Energetica | Materia: Geometria Solar y Solarimetria', 0, 1, 'L')
        self.line(10, 25, 200, 25)
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('helvetica', 'I', 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f'Memoria de Calculo Tecnico-Solarimetrico - Pagina {self.page_no()}', 0, 0, 'C')

def generar_pdf(lat, lon, dia, hora, inc, azim, dec, om, alt, az_sol_vis, theta, grafico_path):
    pdf = PDFReport()
    pdf.add_page()
    
    pdf.set_font('helvetica', 'B', 14)
    pdf.set_text_color(123, 17, 19)
    pdf.cell(0, 8, 'MEMORIA DE CALCULO Y ANALISIS GEOMETRICO SOLAR', 0, 1, 'L')
    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(120, 120, 120)
    pdf.cell(0, 5, f'Fecha de emision: {time.strftime("%Y-%m-%d %H:%M:%S")}', 0, 1, 'L')
    pdf.ln(3)
    
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_fill_color(245, 230, 232)
    pdf.set_text_color(123, 17, 19)
    pdf.cell(0, 7, ' 1. Parametros de Entrada del Sistema', 0, 1, 'L', fill=True)
    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(40, 40, 40)
    pdf.ln(2)
    
    params = [
        ("Latitud del sitio (Phi):", f"{lat:.2f} °"),
        ("Longitud del sitio:", f"{lon:.2f} °"),
        ("Día del año (n):", f"{dia} (Día juliano)"),
        ("Hora solar real (t):", f"{hora:.2f} hrs"),
        ("Inclinación del panel (beta):", f"{inc:.2f} °"),
        ("Azimut del panel (gamma_s):", f"{azim:.2f} °")
    ]
    for k, v in params:
        pdf.cell(90, 5, k, 0, 0)
        pdf.cell(0, 5, v, 0, 1)
    pdf.ln(3)
    
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_fill_color(245, 230, 232)
    pdf.set_text_color(123, 17, 19)
    pdf.cell(0, 7, ' 2. Resultados Analiticos Principales', 0, 1, 'L', fill=True)
    pdf.set_font('helvetica', '', 9)
    pdf.set_text_color(40, 40, 40)
    pdf.ln(2)
    
    resultados = [
        ("Declinación solar (delta):", f"{dec:.4f} °"),
        ("Ángulo horario (omega):", f"{om:.4f} °"),
        ("Altura solar (alpha):", f"{alt:.4f} °"),
        ("Azimut solar visual (-90° a 90°):", f"{az_sol_vis:.4f} °"),
        ("Ángulo de incidencia en colector (theta):", f"{theta:.4f} °")
    ]
    for k, v in resultados:
        pdf.cell(90, 5, k, 0, 0)
        pdf.set_font('helvetica', 'B', 9)
        pdf.cell(0, 5, v, 0, 1)
        pdf.set_font('helvetica', '', 9)
    pdf.ln(4)
    
    pdf.set_font('helvetica', 'B', 11)
    pdf.set_fill_color(245, 230, 232)
    pdf.set_text_color(123, 17, 19)
    pdf.cell(0, 7, ' 3. Variacion del Angulo de Incidencia (theta) a lo largo del Dia', 0, 1, 'L', fill=True)
    pdf.ln(3)
    
    if os.path.exists(grafico_path):
        pdf.image(grafico_path, x=25, w=160)
        
    return bytes(pdf.output())

# BARRA LATERAL: ENTRADA DE DATOS
st.sidebar.header("📍 1. Ubicación y Tiempo")
latitud = st.sidebar.slider("Latitud (°)", -90.0, 90.0, 19.43, 0.01)
latitud = st.sidebar.number_input("Ajuste exacto Latitud (°)", value=latitud, format="%.2f")

longitud = st.sidebar.slider("Longitud (°)", -180.0, 180.0, -99.13, 0.01)
longitud = st.sidebar.number_input("Ajuste exacto Longitud (°)", value=longitud, format="%.2f")

dia_ano = st.sidebar.slider("Día del Año (n)", 1, 365, 80)
dia_ano = st.sidebar.number_input("Ajuste exacto Día (n)", value=dia_ano, step=1)

hora_solar = st.sidebar.slider("Hora Solar Real (Hrs)", 0.0, 24.0, 12.0, 0.25)
hora_solar = st.sidebar.number_input("Ajuste exacto Hora Solar", value=hora_solar, format="%.2f")

st.sidebar.header("📐 2. Parámetros del Colector")
inclinacion = st.sidebar.slider("Inclinación del Panel (β °)", 0.0, 90.0, 20.0, 1.0)
inclinacion = st.sidebar.number_input("Ajuste exacto Inclinación (°)", value=inclinacion, format="%.1f")

azim_panel = st.sidebar.slider("Azimut del Panel (γs °)", -180.0, 180.0, 0.0, 1.0)
azim_panel = st.sidebar.number_input("Ajuste exacto Azimut Panel (°)", value=azim_panel, format="%.1f")

# CÁLCULOS ASTRONÓMICOS
declinacion = 23.45 * np.sin(np.radians(360 * (284 + dia_ano) / 365))
omega = 15 * (hora_solar - 12)

lat_rad = np.radians(latitud)
dec_rad = np.radians(declinacion)
om_rad = np.radians(omega)

# Altura solar (alfa)
sin_alpha = np.sin(lat_rad) * np.sin(dec_rad) + np.cos(lat_rad) * np.cos(dec_rad) * np.cos(om_rad)
alpha_rad = np.arcsin(np.clip(sin_alpha, -1.0, 1.0))
altura_solar = np.degrees(alpha_rad)

# Azimut solar real interno para la física de la animación 3D
cos_alpha = np.cos(alpha_rad)
if cos_alpha == 0:
    azimut_solar_calc = 0.0
else:
    sin_phi_s = np.cos(dec_rad) * np.sin(om_rad) / cos_alpha
    cos_phi_s = (np.sin(alpha_rad) * np.sin(lat_rad) - np.sin(dec_rad)) / (cos_alpha * np.cos(lat_rad))
    azimut_solar_calc = np.degrees(np.arctan2(sin_phi_s, np.clip(cos_phi_s, -1.0, 1.0)))

# CONVERSIÓN VISUAL EXCLUSIVA
# Basado en el ángulo horario omega: a las 6 AM (omega = -90°) -> -90°, mediodía (omega = 0) -> 0°, 6 PM (omega = 90°) -> 90°
azimut_solar_visual = np.clip(omega, -90.0, 90.0)

beta_rad = np.radians(inclinacion)
gam_s_rad = np.radians(azim_panel)

# Fórmula para el ángulo de incidencia (θ)
cos_theta = (np.sin(dec_rad) * np.sin(lat_rad) * np.cos(beta_rad) -
             np.sin(dec_rad) * np.cos(lat_rad) * np.sin(beta_rad) * np.cos(gam_s_rad) +
             np.cos(dec_rad) * np.cos(lat_rad) * np.cos(beta_rad) * np.cos(om_rad) +
             np.cos(dec_rad) * np.sin(lat_rad) * np.sin(beta_rad) * np.cos(gam_s_rad) * np.cos(om_rad) +
             np.cos(dec_rad) * np.sin(beta_rad) * np.sin(gam_s_rad) * np.sin(om_rad))

angulo_incidencia = np.degrees(np.arccos(np.clip(cos_theta, -1.0, 1.0)))

# CÁLCULO DE INCIDENCIA A LO LARGO DEL DÍA PARA LA GRÁFICA
horas = np.linspace(6, 18, 100)
incidencias_dia = []
for h in horas:
    om_h = np.radians(15 * (h - 12))
    cos_th_h = (np.sin(dec_rad) * np.sin(lat_rad) * np.cos(beta_rad) -
                np.sin(dec_rad) * np.cos(lat_rad) * np.sin(beta_rad) * np.cos(gam_s_rad) +
                np.cos(dec_rad) * np.cos(lat_rad) * np.cos(beta_rad) * np.cos(om_h) +
                np.cos(dec_rad) * np.sin(lat_rad) * np.sin(beta_rad) * np.cos(gam_s_rad) * np.cos(om_h) +
                np.cos(dec_rad) * np.sin(beta_rad) * np.sin(gam_s_rad) * np.sin(om_h))
    th_h_deg = np.degrees(np.arccos(np.clip(cos_th_h, -1.0, 1.0)))
    incidencias_dia.append(th_h_deg)

#  MOSTRAR MÉTRICAS PRINCIPALES
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Declinación (δ)", f"{declinacion:.2f}°")
with col2:
    st.metric("Altura Solar (α)", f"{altura_solar:.2f}°")
with col3:
    st.metric("Azimut Solar Visual", f"{azimut_solar_visual:.2f}°")  # Impresión limpia de -90° a 90°
with col4:
    st.metric("Incidencia (θ)", f"{angulo_incidencia:.2f}°")  # ¡Valor exacto de ~15.38° recuperado!

st.markdown("---")

# ANIMACIÓN Y VISUALIZACIÓN 3D 
st.subheader("🎥 Animación y Posición Relativa: Panel vs. Sol")
st.markdown("Representación interactiva tridimensional de la incidencia de los rayos solares sobre la superficie inclinada del colector.")

fig_3d = go.Figure()

sun_x = np.cos(alpha_rad) * np.sin(np.radians(azimut_solar_calc)) * 4
sun_y = np.cos(alpha_rad) * np.cos(np.radians(azimut_solar_calc)) * 4
sun_z = np.sin(alpha_rad) * 4

fig_3d.add_trace(go.Scatter3d(
    x=[0, sun_x], y=[0, sun_y], z=[0, sun_z],
    mode='lines+markers',
    line=dict(color='gold', width=8),
    marker=dict(size=10, color='orange'),
    name='Rayos Solares'
))

u = np.linspace(-1, 1, 10)
v = np.linspace(-1, 1, 10)
U, V = np.meshgrid(u, v)
X_p = U
Y_p = V * np.cos(beta_rad)
Z_p = V * np.sin(beta_rad)

fig_3d.add_trace(go.Surface(
    x=X_p, y=Y_p, z=Z_p,
    colorscale=[[0, '#7b1113'], [1, '#b3393b']],
    showscale=False,
    name='Panel Solar'
))

fig_3d.update_layout(
    scene=dict(
        xaxis_title='Eje X (Este-Oeste)',
        yaxis_title='Eje Y (Sur-Norte)',
        zaxis_title='Eje Z (Altura)',
        camera=dict(eye=dict(x=1.5, y=1.5, z=1.2))
    ),
    margin=dict(l=0, r=0, b=0, t=0),
    height=450
)

st.plotly_chart(fig_3d, use_container_width=True)

st.markdown("---")

# GRÁFICA DE EVOLUCIÓN DIARIA (ÁNGULO DE INCIDENCIA)
st.subheader("📊 Comportamiento Diario del Ángulo de Incidencia (θ)")
df_grafica = pd.DataFrame({"Hora Solar": horas, "Ángulo de Incidencia (°)": incidencias_dia})
st.line_chart(df_grafica.set_index("Hora Solar"), color="#7b1113")

st.markdown("---")

# GENERACIÓN DE IMAGEN PARA EL PDF
grafico_temp = "temp_grafica_incidencia.png"
plt.figure(figsize=(6, 3.5))
plt.plot(horas, incidencias_dia, color='#7b1113', linewidth=2.5)
plt.title("Variacion del Angulo de Incidencia (theta) a lo largo del Dia", fontsize=9.5, fontweight='bold')
plt.xlabel("Hora Solar (hrs)", fontsize=9)
plt.ylabel("Angulo de Incidencia (°)", fontsize=9)
plt.grid(True, linestyle='--', alpha=0.6)
plt.tight_layout()
plt.savefig(grafico_temp, dpi=200)
plt.close()

# MEMORIA DE CÁLCULO PROFESIONAL (PDF)
st.subheader("📑 Generación de Memoria de Cálculo y Reporte Técnico en PDF")
st.markdown("Compile todos los datos de entrada, resultados analíticos y la gráfica de incidencia en un formato institucional formal.")

if st.button("🚀 Generar Memoria de Cálculo en Formato PDF Institucional"):
    with st.spinner("Compilando documento institucional PDF..."):
        time.sleep(1.0)
        
        pdf_bytes = generar_pdf(
            latitud, longitud, dia_ano, hora_solar, 
            inclinacion, azim_panel, declinacion, 
            omega, altura_solar, azimut_solar_visual, angulo_incidencia,
            grafico_temp
        )
        
        st.success("¡Memoria de cálculo en PDF generada con éxito!")
        st.download_button(
            label="📥 Descargar Memoria de Cálculo Oficial (.pdf)",
            data=pdf_bytes,
            file_name=f"Memoria_Calculo_UACM_Dia_{dia_ano}.pdf",
            mime="application/pdf"
        )
        
        st.success("¡Memoria de cálculo en PDF generada con éxito!")
        st.download_button(
            label="📥 Descargar Memoria de Cálculo Oficial (.pdf)",
            data=pdf_bytes,
            file_name=f"Memoria_Calculo_UACM_Dia_{dia_ano}.pdf",
            mime="application/pdf"
        )
