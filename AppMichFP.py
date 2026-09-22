"""
UNIVERSIDAD AUTÓNOMA DE LA CIUDAD DE MÉXICO (UACM)
Colegio de Ciencia y Tecnología
Maestría en Ingeniería Energética
Materia: Fundamentos de Ingeniería Eléctrica
"""

import math
import streamlit as st
from datetime import datetime
from io import BytesIO

# Configuración de página
st.set_page_config(page_title="UACM - Factor de Potencia", page_icon="⚡", layout="wide")

# Catálogo comercial de capacitores (kVAr)
CATALOGO_CAPACITORES = {
    "Baja Tensión (< 1 kV)": [5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 250, 300, 400, 500],
    "Media Tensión (1 kV - 35 kV)": [150, 300, 450, 600, 900, 1200, 1500, 1800, 2400, 3000, 3600, 4800],
    "Alta Tensión (> 35 kV)": [1200, 2400, 3600, 4800, 6000, 7200, 9600, 12000, 15000, 20000, 30000]
}

def calcular_recargo_bonificacion(fp_actual):
    if fp_actual < 0.90:
        rec = min((3.0 / 5.0) * ((0.90 / fp_actual) - 1.0) * 100.0, 120.0)
        return {"tipo": "Recargo", "porcentaje": rec}
    elif fp_actual > 0.90:
        bon = min((1.0 / 4.0) * (1.0 - (0.90 / fp_actual)) * 100.0, 2.5)
        return {"tipo": "Bonificación", "porcentaje": bon}
    return {"tipo": "Sin ajuste", "porcentaje": 0.0}

def seleccionar_banco(qc, nivel):
    cat = CATALOGO_CAPACITORES[nivel]
    for val in cat:
        if val >= qc:
            return val, f"1 banco comercial de {val} kVAr"
    max_val = cat[-1]
    nb = math.ceil(qc / max_val)
    return nb * max_val, f"{nb} bancos de {max_val} kVAr en paralelo"

def generar_pdf_bytes(datos):
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=35, leftMargin=35, topMargin=35, bottomMargin=35)
    story = []
    styles = getSampleStyleSheet()

    color_uacm = colors.HexColor("#7A1C20")
    color_gris = colors.HexColor("#F5F5F5")

    title_style = ParagraphStyle('UACMTitle', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=13, leading=16, textColor=color_uacm, alignment=1)
    sub_style = ParagraphStyle('UACMSub', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, alignment=1)
    h2_style = ParagraphStyle('UACMH2', parent=styles['Heading2'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=color_uacm)

    story.append(Paragraph("<b>UNIVERSIDAD AUTÓNOMA DE LA CIUDAD DE MÉXICO</b><br/>Colegio de Ciencia y Tecnología — Maestría en Ingeniería Energética<br/><b>MEMORIA TÉCNICA DE COMPENSACIÓN DE FACTOR DE POTENCIA (CÓDIGO DE RED 0.97)</b>", title_style))
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<b>Fecha:</b> {datetime.now().strftime('%d/%m/%Y %H:%M hrs')} | <b>Norma:</b> CRE RES/550/2021", sub_style))
    story.append(Spacer(1, 10))

    filas = [
        ["Demanda Máxima Promedio (P):", f"{datos['p_kw']:,.2f} kW"],
        ["Factor de Potencia Actual:", f"{datos['fp_act']:.4f}"],
        ["Factor de Potencia Objetivo:", "0.97 (Código de Red)"],
        ["Diagnóstico Tarifario CFE:", f"{datos['diag']['tipo']}: {datos['diag']['porcentaje']:.2f}%"],
        ["Potencia Reactiva Requerida (Qc):", f"{datos['qc']:,.2f} kVAr"],
        ["Banco Comercial Sugerido:", f"{datos['banco']:,.2f} kVAr ({datos['config']})"],
        ["FP Resultante con Banco:", f"{datos['fp_res']:.4f}"],
        ["Tensión Línea-Línea:", f"{datos['v_kv']:.2f} kV"],
        ["Corriente Motor Síncrono:", f"{datos['i_motor']:.2f} A"],
        ["Inversión Estimada Total:", f"${datos['inversion']:,.2f} MXN"],
        ["Ahorro por Penalización Evitada:", f"${datos['penalizacion']:,.2f} MXN/mes"],
        ["Retorno de Inversión Simple (ROI):", f"{datos['roi']:.1f} meses" if datos['roi'] != float('inf') else "N/A"]
    ]
    t = Table(filas, colWidths=[240, 260])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), color_gris),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    story.append(t)
    doc.build(story)
    buffer.seek(0)
    return buffer

# Encabezado UI
st.markdown("<h2 style='color:#7A1C20; margin-bottom:0;'>UNIVERSIDAD AUTÓNOMA DE LA CIUDAD DE MÉXICO</h2>", unsafe_allow_html=True)
st.markdown("<h4 style='color:#444; margin-top:0;'>Maestría en Ingeniería Energética | Fundamentos de Ingeniería Eléctrica</h4>", unsafe_allow_html=True)
st.markdown("**Cálculo de Bancos de Capacitores y Compensación (Código de Red: FP ≥ 0.97)**")
st.divider()

col1, col2 = st.columns([1, 1.2])

with col1:
    st.subheader("Parámetros de Entrada")
    p_kw = st.number_input("Demanda Máxima Promedio [kW]", min_value=1.0, value=500.0, step=10.0)
    fp_act = st.number_input("Factor de Potencia Actual (ej. 0.82)", min_value=0.10, max_value=0.99, value=0.82, step=0.01)
    nivel = st.selectbox("Nivel de Tensión", list(CATALOGO_CAPACITORES.keys()), index=1)
    v_kv = st.number_input("Tensión Línea a Línea [kV]", min_value=0.1, value=13.8, step=0.1)
    penalizacion = st.number_input("Penalización Mensual Actual [$ MXN]", min_value=0.0, value=25000.0, step=1000.0)
    costo_kvar = st.number_input("Costo Estimado [$ MXN / kVAr]", min_value=10.0, value=650.0, step=50.0)

with col2:
    st.subheader("Resultados de Compensación")
    fp_obj = 0.97
    
    if fp_act >= fp_obj:
        st.success(f"El factor de potencia actual ({fp_act}) ya cumple con el Código de Red (≥ 0.97).")
    else:
        # Cálculos
        th1, th2 = math.acos(fp_act), math.acos(fp_obj)
        qc = p_kw * (math.tan(th1) - math.tan(th2))
        banco, config = seleccionar_banco(qc, nivel)
        
        q1 = p_kw * math.tan(th1)
        q2 = max(q1 - banco, 0.0)
        fp_res = math.cos(math.atan(q2 / p_kw))
        
        i_motor = qc / (math.sqrt(3) * v_kv) if v_kv > 0 else 0.0
        inversion = banco * costo_kvar
        roi = (inversion / penalizacion) if penalizacion > 0 else float('inf')
        diag = calcular_recargo_bonificacion(fp_act)

        m1, m2 = st.columns(2)
        m1.metric("Reactivos Necesarios (Qc)", f"{qc:,.2f} kVAr")
        m2.metric("Banco Comercial", f"{banco:,.0f} kVAr")
        
        m3, m4 = st.columns(2)
        m3.metric("FP Resultante", f"{fp_res:.4f}")
        m4.metric("CFE Diagnóstico", f"{diag['tipo']} {diag['porcentaje']:.1f}%")

        st.info(f"**Configuración:** {config}")
        st.write(f"• **Motor Síncrono:** Debe entregar **{i_motor:.2f} A** reactivos en sobreexcitación.")
        st.write(f"• **Inversión Total:** **${inversion:,.2f} MXN** | **Retorno:** **{roi:.1f} meses**.")

        # Generador de PDF
        datos = {
            "p_kw": p_kw, "fp_act": fp_act, "diag": diag, "qc": qc,
            "banco": banco, "config": config, "fp_res": fp_res, "v_kv": v_kv,
            "i_motor": i_motor, "inversion": inversion, "penalizacion": penalizacion, "roi": roi
        }
        pdf_bytes = generar_pdf_bytes(datos)
        
        st.download_button(
            label="Descargar Memoria Técnica UACM (PDF)",
            data=pdf_bytes,
            file_name=f"Memoria_Tecnica_FP_UACM_{datetime.now().strftime('%Y%m%d')}.pdf",
            mime="application/pdf"
        )
    