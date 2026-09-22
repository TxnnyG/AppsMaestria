# -*- coding: utf-8 -*-
"""
Herramienta de Ajuste de Factor de Potencia — versión web (Streamlit)
UACM — Maestría en Ingeniería Energética / Fundamentos de Ingeniería Eléctrica
Diseño de alto contraste y legibilidad reforzada.
"""

import io
import os
from dataclasses import dataclass
from datetime import datetime
from math import acos, tan, sqrt
from typing import List, Optional

import streamlit as st
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image as RLImage
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# Rutas de logotipos locales
RUTA_LOGO_UACM = "logo_uacm.png"
RUTA_LOGO_PEUACM = "logo_peuacm.png"

# =======================================================================
# 1. BASE DE DATOS DE BANCOS DE CAPACITORES COMERCIALES (2026)
# =======================================================================

@dataclass(frozen=True)
class BancoCapacitor:
    nivel_tension: str
    kvar: float

_BAJA_TENSION_KVAR = [
    5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75,
    90, 100, 105, 120, 125, 135, 150, 175, 180, 200, 225, 250, 275, 300,
]
_MEDIA_TENSION_KVAR = [
    150, 180, 200, 225, 240, 250, 300, 360, 400, 450, 500,
    600, 750, 800, 900, 1000, 1200, 1500, 1800, 2000, 2400, 3000,
]
_ALTA_TENSION_KVAR = [
    1200, 1500, 1800, 2400, 3000, 3600, 4000, 5000, 6000, 7200, 8000, 9600, 12000,
]

BASE_CAPACITORES: List[BancoCapacitor] = (
    [BancoCapacitor("Baja Tensión", v) for v in _BAJA_TENSION_KVAR]
    + [BancoCapacitor("Media Tensión", v) for v in _MEDIA_TENSION_KVAR]
    + [BancoCapacitor("Alta Tensión", v) for v in _ALTA_TENSION_KVAR]
)

def niveles_disponibles() -> List[str]:
    return ["Baja Tensión", "Media Tensión", "Alta Tensión"]

def seleccionar_banco_comercial(nivel_tension: str, q_compensar_kvar: float) -> Optional[float]:
    candidatos = sorted(
        b.kvar for b in BASE_CAPACITORES
        if b.nivel_tension == nivel_tension and b.kvar >= q_compensar_kvar
    )
    return candidatos[0] if candidatos else None

def banco_maximo_disponible(nivel_tension: str) -> float:
    valores = [b.kvar for b in BASE_CAPACITORES if b.nivel_tension == nivel_tension]
    return max(valores) if valores else 0.0

# =======================================================================
# 2. MOTOR DE CÁLCULO
# =======================================================================

FP_REFERENCIA_FACTURACION = 0.90
BONIFICACION_MAXIMA_PCT = 2.5
RECARGO_MAXIMO_PCT = 120.0
FP_OBJETIVO_ACTUAL = 0.97

def potencia_reactiva_a_compensar(demanda_max_kw: float, fp_actual: float, fp_objetivo: float) -> float:
    if not (0 < fp_actual <= 1) or not (0 < fp_objetivo <= 1):
        raise ValueError("El factor de potencia debe estar entre 0.0 y 1.0")
    q = demanda_max_kw * (tan(acos(fp_actual)) - tan(acos(fp_objetivo)))
    return max(q, 0.0)

@dataclass
class ResultadoBonificacionRecargo:
    aplica: str
    porcentaje: float

def calcular_bonificacion_recargo(fp_actual: float) -> ResultadoBonificacionRecargo:
    if not (0 < fp_actual <= 1):
        raise ValueError("El factor de potencia debe estar entre 0.0 y 1.0")
    if fp_actual < FP_REFERENCIA_FACTURACION:
        pct = (3 / 5) * ((FP_REFERENCIA_FACTURACION / fp_actual) - 1) * 100
        return ResultadoBonificacionRecargo("Recargo", round(min(pct, RECARGO_MAXIMO_PCT), 2))
    pct = (1 / 4) * (1 - (FP_REFERENCIA_FACTURACION / fp_actual)) * 100
    return ResultadoBonificacionRecargo("Bonificación", round(min(pct, BONIFICACION_MAXIMA_PCT), 2))

@dataclass
class ResultadoBancoCapacitores:
    nivel_tension: str
    q_compensar_kvar: float
    valor_comercial_kvar: Optional[float]
    requiere_escalonar: bool

def dimensionar_banco_capacitores(nivel_tension: str, q_compensar_kvar: float) -> ResultadoBancoCapacitores:
    valor = seleccionar_banco_comercial(nivel_tension, q_compensar_kvar)
    if valor is None:
        return ResultadoBancoCapacitores(nivel_tension, q_compensar_kvar, None, True)
    return ResultadoBancoCapacitores(nivel_tension, q_compensar_kvar, valor, False)

def corriente_motor_sincrono(q_compensar_kvar: float, v_ll_kv: float) -> float:
    if v_ll_kv <= 0:
        raise ValueError("La tensión línea-línea debe ser mayor que 0")
    return q_compensar_kvar / (sqrt(3) * v_ll_kv)

@dataclass
class ResultadoCostos:
    inversion_mxn: float
    roi_meses: Optional[float]

def calcular_inversion_y_roi(q_compensar_kvar: float, costo_por_kvar_mxn: float,
                              penalizacion_mensual_mxn: float) -> ResultadoCostos:
    inversion = costo_por_kvar_mxn * q_compensar_kvar
    if penalizacion_mensual_mxn <= 0:
        return ResultadoCostos(round(inversion, 2), None)
    return ResultadoCostos(round(inversion, 2), round(inversion / penalizacion_mensual_mxn, 1))

@dataclass
class DatosEntrada:
    demanda_max_kw: float
    fp_actual: float
    fp_objetivo: float = FP_OBJETIVO_ACTUAL
    penalizacion_mensual_mxn: float = 0.0
    nivel_tension: str = "Media Tensión"
    v_ll_kv: float = 13.8
    costo_kvar_banco_capacitores_mxn: float = 0.0
    costo_kvar_motor_sincrono_mxn: float = 0.0

@dataclass
class ResultadoIntegral:
    q_compensar_kvar: float
    bonificacion_recargo: ResultadoBonificacionRecargo
    banco_capacitores: ResultadoBancoCapacitores
    corriente_motor_sincrono_a: float
    costos_banco_capacitores: ResultadoCostos
    costos_motor_sincrono: ResultadoCostos

def calcular_todo(datos: DatosEntrada) -> ResultadoIntegral:
    q = potencia_reactiva_a_compensar(datos.demanda_max_kw, datos.fp_actual, datos.fp_objetivo)
    bon_rec = calcular_bonificacion_recargo(datos.fp_actual)
    banco = dimensionar_banco_capacitores(datos.nivel_tension, q)
    corriente_ms = corriente_motor_sincrono(q, datos.v_ll_kv)
    costos_bc = calcular_inversion_y_roi(q, datos.costo_kvar_banco_capacitores_mxn, datos.penalizacion_mensual_mxn)
    costos_ms = calcular_inversion_y_roi(q, datos.costo_kvar_motor_sincrono_mxn, datos.penalizacion_mensual_mxn)
    return ResultadoIntegral(
        q_compensar_kvar=round(q, 2),
        bonificacion_recargo=bon_rec,
        banco_capacitores=banco,
        corriente_motor_sincrono_a=round(corriente_ms, 2),
        costos_banco_capacitores=costos_bc,
        costos_motor_sincrono=costos_ms,
    )

# =======================================================================
# 3. GENERADOR DE REPORTE PDF (MEMBRETE OFICIAL UACM)
# =======================================================================

COLOR_UACM_PDF = colors.HexColor("#8F141B")
COLOR_VERDE_PDF = colors.HexColor("#0D9488")
COLOR_UACM_CLARO = colors.HexColor("#FDF8F8")
COLOR_GRIS = colors.HexColor("#2B2B2B")

def _tabla_datos(filas, col_widths=(9.5 * cm, 3 * cm, 2 * cm)):
    t = Table(filas, colWidths=list(col_widths))
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#1A1A1A")),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, COLOR_UACM_CLARO]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ]))
    return t

def _seccion(elementos, styles, titulo, color_fondo=COLOR_UACM_PDF):
    elementos.append(Spacer(1, 0.25 * cm))
    elementos.append(Paragraph(titulo, ParagraphStyle(
        "seccion", parent=styles["Heading2"], textColor=colors.white, fontSize=10.5,
        backColor=color_fondo, borderPadding=(4, 6, 4, 6), leading=13)))
    elementos.append(Spacer(1, 0.15 * cm))

def generar_reporte_pdf(datos: DatosEntrada, resultado: ResultadoIntegral, destino) -> None:
    doc = SimpleDocTemplate(
        destino, pagesize=letter,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
        title="Herramienta: Ajuste del Factor de Potencia (FP) - UACM",
    )
    styles = getSampleStyleSheet()
    elementos = []

    img_uacm = RLImage(RUTA_LOGO_UACM, width=2.4 * cm, height=2.4 * cm) if os.path.exists(RUTA_LOGO_UACM) else Paragraph("", styles["Normal"])
    img_peuacm = RLImage(RUTA_LOGO_PEUACM, width=3.4 * cm, height=1.1 * cm) if os.path.exists(RUTA_LOGO_PEUACM) else Paragraph("", styles["Normal"])

    texto_header = Paragraph(
        "<b>UNIVERSIDAD AUTÓNOMA DE LA CIUDAD DE MÉXICO</b><br/>"
        "<font size=11 color='#8F141B'><b>Colegio de Ciencia y Tecnología — Maestría en Ingeniería Energética</b></font><br/>"
        "<font size=8.5 color='#0D9488'><b>Programa de Energía UACM (PEUACM)</b></font> · <font size=8.5 color='#1A1A1A'>Fundamentos de Ingeniería Eléctrica</font>",
        ParagraphStyle("head_txt", parent=styles["Normal"], alignment=TA_CENTER, leading=12)
    )

    tabla_logos = Table([[img_uacm, texto_header, img_peuacm]], colWidths=[2.6 * cm, 10.8 * cm, 3.6 * cm])
    tabla_logos.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    elementos.append(tabla_logos)
    elementos.append(Spacer(1, 0.2 * cm))

    titulo = Paragraph(
        "<b>MEMORIA TÉCNICA: COMPENSACIÓN DE FACTOR DE POTENCIA</b><br/>"
        "<font size=8.5 color='#0D9488'>Ajuste para Mitigación de Multas y Optimización de Reactivos</font>",
        ParagraphStyle("titulo", parent=styles["Title"], alignment=TA_CENTER,
                        textColor=COLOR_UACM_PDF, fontSize=12.5, leading=15),
    )
    elementos.append(titulo)
    elementos.append(Spacer(1, 0.1 * cm))
    elementos.append(Paragraph(f"Fecha de emisión: {datetime.now().strftime('%d/%m/%Y %I:%M %p')}", ParagraphStyle(
        "fecha", parent=styles["Normal"], alignment=TA_CENTER, fontSize=8, textColor=COLOR_GRIS)))
    elementos.append(Spacer(1, 0.2 * cm))
    elementos.append(HRFlowable(width="100%", color=COLOR_UACM_PDF, thickness=1.5))
    elementos.append(Spacer(1, 0.25 * cm))

    _seccion(elementos, styles, "1. Datos Generales de la Instalación")
    elementos.append(_tabla_datos([
        ["Demanda Máxima Promedio", f"{datos.demanda_max_kw:,.2f}", "[kW]"],
        ["Factor de Potencia Actual", f"{datos.fp_actual:.3f}", "[1]"],
        ["Factor de Potencia Objetivo Requerido", f"{datos.fp_objetivo:.3f}", "[1]"],
        ["Penalización mensual actual en facturación", f"${datos.penalizacion_mensual_mxn:,.2f}", "[MXN]"],
        ["Potencia Reactiva a Compensar (Qc)", f"{resultado.q_compensar_kvar:,.2f}", "[kVAr]"],
    ]))

    _seccion(elementos, styles, "2. Diagnóstico Tarifario en Facturación (CFE)", COLOR_VERDE_PDF)
    br = resultado.bonificacion_recargo
    elementos.append(_tabla_datos([
        [f"{br.aplica} en facturación", f"{br.porcentaje:.2f}", "[%]"],
        ["Fórmula tarifaria aplicada",
         "3/5·[(90/FP)-1]·100 (FP < 0.90)" if br.aplica == "Recargo"
         else "1/4·[1-(90/FP)]·100 (FP ≥ 0.90)", ""],
    ]))

    _seccion(elementos, styles, "3. Alternativas para el Ajuste del Factor de Potencia")
    bc = resultado.banco_capacitores
    valor_bc = f"{bc.valor_comercial_kvar:,.0f}" if bc.valor_comercial_kvar else "Excede catálogo"
    elementos.append(Paragraph("<b>Alternativa A: Instalación de Banco de Capacitores</b>",
                                ParagraphStyle("sub", parent=styles["Normal"], fontSize=9.5,
                                               textColor=COLOR_UACM_PDF, spaceAfter=4)))
    elementos.append(_tabla_datos([
        ["Nivel de Tensión de Operación", datos.nivel_tension, "[1]"],
        ["Valor Comercial sugerido (unidad estándar)", valor_bc, "[kVAr]"],
    ]))
    if bc.requiere_escalonar:
        elementos.append(Paragraph(
            "<i>Nota técnica: la potencia reactiva a compensar supera el escalón comercial unitario más grande; "
            "se recomienda arreglo automático por etapas en paralelo.</i>",
            ParagraphStyle("nota", parent=styles["Normal"], fontSize=7.8, textColor=COLOR_GRIS)))

    elementos.append(Spacer(1, 0.2 * cm))
    elementos.append(Paragraph("<b>Alternativa B: Motor Síncrono (Sobreexcitado)</b>",
                                ParagraphStyle("sub2", parent=styles["Normal"], fontSize=9.5,
                                               textColor=COLOR_VERDE_PDF, spaceAfter=4)))
    elementos.append(_tabla_datos([
        ["Tensión de operación (L-L)", f"{datos.v_ll_kv:,.2f}", "[kV]"],
        ["Corriente reactiva entregada por el motor", f"{resultado.corriente_motor_sincrono_a:,.2f}", "[A]"],
    ]))

    _seccion(elementos, styles, "4. Inversión Estimada y Retorno de Inversión Simple (ROI)")
    cbc = resultado.costos_banco_capacitores
    cms = resultado.costos_motor_sincrono
    tabla_costos = Table(
        [["Concepto", "Banco de Capacitores", "Motor Síncrono"],
         ["Costo por kVAr compensado [MXN]",
          f"${datos.costo_kvar_banco_capacitores_mxn:,.2f}",
          f"${datos.costo_kvar_motor_sincrono_mxn:,.2f}"],
         ["Inversión aproximada [MXN]", f"${cbc.inversion_mxn:,.2f}", f"${cms.inversion_mxn:,.2f}"],
         ["Retorno de inversión simple [meses]",
          f"{cbc.roi_meses:,.1f}" if cbc.roi_meses is not None else "N/A",
          f"{cms.roi_meses:,.1f}" if cms.roi_meses is not None else "N/A"]],
        colWidths=[6.8 * cm, 4.6 * cm, 4.6 * cm],
    )
    tabla_costos.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_UACM_PDF),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_UACM_CLARO]),
        ("TOPPADDING", (0, 0), (-1, -1), 4.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
    ]))
    elementos.append(tabla_costos)

    elementos.append(Spacer(1, 0.35 * cm))
    elementos.append(HRFlowable(width="100%", color=COLOR_UACM_PDF, thickness=0.8))
    elementos.append(Spacer(1, 0.15 * cm))
    elementos.append(Paragraph(
        "Memoria de cálculo desarrollada en la Universidad Autónoma de la Ciudad de México (UACM) — Maestría en Ingeniería Energética. "
        "El factor de potencia menor a 0.97 en atraso se encuentra sujeto a procedimientos de inspección, requerimientos de compensación "
        "y posibles sanciones o multas administrativas estipuladas por la CRE bajo el marco regulatorio del Código de Red.",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=7.2, textColor=COLOR_GRIS)))

    doc.build(elementos)

# =======================================================================
# 4. INTERFAZ WEB STREAMLIT (COLORES SÓLIDOS Y ALTO CONTRASTE)
# =======================================================================

st.set_page_config(
    page_title="Compensación de Factor de Potencia — UACM",
    page_icon="⚡",
    layout="wide"
)

# Inyección de estilos de alto contraste
st.markdown(
    """
    <style>
        /* 1. Fondo principal y texto general */
        .stApp {
            background-color: #F8FAFC !important;
            color: #0F172A !important;
        }

        .main .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 3rem !important;
            max-width: 1100px !important;
        }

        /* 2. Encabezado Institucional Sólido */
        .header-solid-box {
            background-color: #FFFFFF !important;
            border: 2px solid #E2E8F0 !important;
            border-top: 6px solid #8F141B !important;
            border-radius: 12px !important;
            padding: 18px 24px !important;
            margin-bottom: 20px !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05) !important;
        }
        .header-title-uacm {
            color: #8F141B !important;
            font-size: 24px !important;
            font-weight: 900 !important;
            margin: 0 !important;
            letter-spacing: -0.2px !important;
            text-align: center;
        }
        .header-sub-peuacm {
            color: #065F46 !important;
            font-size: 15px !important;
            font-weight: 700 !important;
            margin: 4px 0 !important;
            text-align: center;
        }
        .header-desc {
            color: #334155 !important;
            font-size: 13.5px !important;
            font-weight: 600 !important;
            margin: 0 !important;
            text-align: center;
        }

        /* 3. Inputs y selectores con tipografía oscura destacada */
        div[data-baseweb="input"], div[data-baseweb="input"] > div {
            background-color: #FFFFFF !important;
            border: 2px solid #CBD5E1 !important;
            border-radius: 8px !important;
        }
        div[data-baseweb="input"]:focus-within {
            border-color: #8F141B !important;
            box-shadow: 0 0 0 2px rgba(143, 20, 27, 0.2) !important;
        }
        input {
            color: #0F172A !important;
            font-weight: 800 !important;
            font-size: 16px !important;
        }
        button[data-testid="stNumberInputStepDown"], button[data-testid="stNumberInputStepUp"] {
            background-color: #F1F5F9 !important;
            color: #0F172A !important;
            border-left: 1px solid #CBD5E1 !important;
        }
        label, p[data-testid="stWidgetLabel"] {
            color: #0F172A !important;
            font-weight: 800 !important;
            font-size: 14.5px !important;
        }

        /* Selectores */
        div[data-baseweb="select"] > div {
            background-color: #FFFFFF !important;
            border: 2px solid #CBD5E1 !important;
            border-radius: 8px !important;
            color: #0F172A !important;
            font-weight: 700 !important;
        }

        /* 4. Pestañas (Tabs) en botones de alto contraste */
        button[data-baseweb="tab"] {
            background-color: #E2E8F0 !important;
            border: 1.5px solid #CBD5E1 !important;
            border-radius: 8px !important;
            color: #0F172A !important;
            font-weight: 800 !important;
            font-size: 13.5px !important;
            padding: 8px 18px !important;
            margin-right: 6px !important;
            transition: all 0.15s ease !important;
        }
        button[data-baseweb="tab"]:hover {
            background-color: #CBD5E1 !important;
            color: #8F141B !important;
        }
        button[data-baseweb="tab"][aria-selected="true"] {
            background-color: #8F141B !important;
            color: #FFFFFF !important;
            border-color: #8F141B !important;
        }

        /* 5. Tarjetas de métricas */
        .metric-card-box {
            background: #FFFFFF !important;
            border-radius: 10px !important;
            padding: 16px 20px !important;
            border: 1.5px solid #CBD5E1 !important;
            box-shadow: 0 3px 8px rgba(0, 0, 0, 0.05) !important;
        }
        .metric-card-uacm {
            border-left: 6px solid #8F141B !important;
        }
        .metric-card-green {
            border-left: 6px solid #065F46 !important;
        }
        .metric-label {
            font-size: 13px !important;
            font-weight: 800 !important;
            color: #334155 !important;
            text-transform: uppercase !important;
            letter-spacing: 0.5px !important;
            margin-bottom: 4px !important;
        }
        .metric-num-uacm {
            font-size: 30px !important;
            font-weight: 900 !important;
            color: #8F141B !important;
            margin: 0 !important;
            line-height: 1.1 !important;
        }
        .metric-num-green {
            font-size: 30px !important;
            font-weight: 900 !important;
            color: #065F46 !important;
            margin: 0 !important;
            line-height: 1.1 !important;
        }
        .metric-foot {
            font-size: 12.5px !important;
            color: #475569 !important;
            margin-top: 4px !important;
            font-weight: 600 !important;
        }

        /* 6. Botones de acción */
        div.stButton > button {
            background-color: #8F141B !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 800 !important;
            font-size: 15px !important;
            padding: 12px 28px !important;
            box-shadow: 0 4px 10px rgba(143, 20, 27, 0.3) !important;
        }
        div.stButton > button:hover {
            background-color: #6E0E14 !important;
        }
        div[data-testid="stDownloadButton"] > button {
            background-color: #065F46 !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            font-weight: 800 !important;
            font-size: 15px !important;
            padding: 12px 28px !important;
            box-shadow: 0 4px 10px rgba(6, 95, 70, 0.3) !important;
        }
        div[data-testid="stDownloadButton"] > button:hover {
            background-color: #044332 !important;
        }

        /* 7. Bloques informativos */
        .info-dark-box {
            background-color: #FFFFFF !important;
            border: 1.5px solid #CBD5E1 !important;
            border-radius: 8px !important;
            padding: 14px 18px !important;
            margin-top: 12px !important;
            color: #0F172A !important;
            font-size: 14px !important;
            font-weight: 600 !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# Encabezado estructurado en bloque sólido
st.markdown('<div class="header-solid-box">', unsafe_allow_html=True)
col_h1, col_h2, col_h3 = st.columns([1.2, 5, 1.5])

with col_h1:
    if os.path.exists(RUTA_LOGO_UACM):
        st.image(RUTA_LOGO_UACM, width=120)

with col_h2:
    st.markdown(
        """
        <div class="header-title-uacm">UNIVERSIDAD AUTÓNOMA DE LA CIUDAD DE MÉXICO</div>
        <div class="header-sub-peuacm">Maestría en Ingeniería Energética | Fundamentos de Ingeniería Eléctrica</div>
        <div class="header-desc">Herramienta de Ajuste y Compensación de Factor de Potencia · Programa de Energía (PEUACM)</div>
        """,
        unsafe_allow_html=True
    )

with col_h3:
    if os.path.exists(RUTA_LOGO_PEUACM):
        st.image(RUTA_LOGO_PEUACM, width=145)

st.markdown('</div>', unsafe_allow_html=True)

with st.expander("📌 Consideraciones del Código de Red y Sanciones por Incumplimiento", expanded=False):
    st.markdown(
        """
        * **Requisito Técnico:** Las disposiciones del **Código de Red** emitidas por la Comisión Reguladora de Energía (CRE) 
          establecen que los Centros de Carga conectados en Media y Alta Tensión deben mantener permanentemente un factor de potencia 
          mínimo de **0.97 en atraso** (evaluado con permanencia del 95% en ventanas de medición de 5 minutos).
        * **Riesgo Regulatorio y Multas:** Operar con un factor de potencia **menor a 0.97** no solo genera recargos en el recibo de suministro, 
          sino que representa un incumplimiento al Código de Red susceptible a **requerimientos de corrección obligatoria y multas administrativas** 
          por parte de la CRE conforme a la Ley de la Industria Eléctrica.
        * **Esquema Tarifario CFE:** La bonificación o recargo facturado por CFE Suministrador de Servicios Básicos continúa calculándose 
          tomando como base de referencia el estándar del **0.90**.
        """
    )

if "pdf_bytes" not in st.session_state:
    st.session_state.pdf_bytes = None

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1️⃣ Datos Generales",
    "2️⃣ Recargo / Bonificación",
    "3️⃣ Banco de Capacitores",
    "4️⃣ Motor Síncrono",
    "5️⃣ Inversión y Reporte"
])

with tab1:
    st.markdown("<h4 style='color:#8F141B; font-weight:800; margin-bottom:12px;'>Parámetros del Recibo Eléctrico</h4>", unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        demanda = st.number_input("Demanda Máxima Promedio [kW]", min_value=1.0, value=1800.0, step=10.0)
        fp_actual = st.number_input("Factor de Potencia Actual (0.100 - 1.000)", min_value=0.10, max_value=1.0, value=0.85, step=0.01, format="%.3f")
    with col2:
        fp_objetivo = st.number_input("Factor de Potencia Objetivo Requerido", min_value=0.10, max_value=1.0, value=FP_OBJETIVO_ACTUAL, step=0.01, format="%.3f", help="Requisito normativo mínimo para evitar multas: 0.97")
        penalizacion = st.number_input("Penalización/Recargo Mensual en Recibo [$ MXN]", min_value=0.0, value=18000.0, step=500.0)
    
    q_compensar = potencia_reactiva_a_compensar(demanda, fp_actual, fp_objetivo)
    
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    mcol1, mcol2 = st.columns(2)
    with mcol1:
        st.markdown(
            f"""
            <div class="metric-card-box metric-card-uacm">
                <div class="metric-label">Potencia Reactiva Neta a Compensar</div>
                <div class="metric-num-uacm">{q_compensar:,.2f} <span style="font-size:18px;">kVAr</span></div>
                <div class="metric-foot">Reactivos requeridos para alcanzar la meta</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with mcol2:
        st.markdown(
            f"""
            <div class="metric-card-box metric-card-green">
                <div class="metric-label">Factor de Potencia Requerido</div>
                <div class="metric-num-green">{fp_objetivo:.2f} <span style="font-size:18px;">FP</span></div>
                <div class="metric-foot">Umbral técnico para prevenir sanciones y multas</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    st.markdown(
        f"""
        <div class="info-dark-box">
            <span style="color:#0F172A; font-weight:800;">📐 Ecuación del Triángulo de Potencias:</span><br/>
            <code style="color:#8F141B; font-weight:800; font-size:14px;">Qc = P · [tan(arccos(FP_actual)) − tan(arccos(FP_objetivo))]</code>
        </div>
        """,
        unsafe_allow_html=True
    )

with tab2:
    st.markdown("<h4 style='color:#8F141B; font-weight:800; margin-bottom:12px;'>Diagnóstico Tarifario CFE</h4>", unsafe_allow_html=True)
    br = calcular_bonificacion_recargo(fp_actual)
    
    col_br1, col_br2 = st.columns([1, 1.2])
    with col_br1:
        clase_num = "metric-num-uacm" if br.aplica == "Recargo" else "metric-num-green"
        clase_border = "metric-card-uacm" if br.aplica == "Recargo" else "metric-card-green"
        st.markdown(
            f"""
            <div class="metric-card-box {clase_border}">
                <div class="metric-label">Ajuste en Facturación ({br.aplica})</div>
                <div class="{clase_num}">{br.porcentaje:.2f} <span style="font-size:18px;">%</span></div>
                <div class="metric-foot">Impacto sobre el costo de potencia activa facturada</div>
            </div>
            """,
            unsafe_allow_html=True
        )
    with col_br2:
        formula_txt = "3/5 · [(90 / FP) − 1] · 100" if br.aplica == "Recargo" else "1/4 · [1 − (90 / FP)] · 100"
        st.markdown(
            f"""
            <div class="info-dark-box">
                <b style="color:#065F46;">Fórmula Tarifaria Oficial:</b> <code>{formula_txt}</code><br/><br/>
                <span style="color:#334155;">
                    • <b>FP &lt; 0.90:</b> Aplica recargo de hasta el 120 %.<br/>
                    • <b>FP &ge; 0.90:</b> Bonificación máxima permitida de 2.5 %.<br/>
                    • <i>Nota:</i> Un FP menor a 0.97 adicionalmente incurre en riesgo de sanciones por Código de Red.
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )

with tab3:
    st.markdown("<h4 style='color:#8F141B; font-weight:800; margin-bottom:12px;'>Alternativa A: Banco de Capacitores Comerciales</h4>", unsafe_allow_html=True)
    nivel_tension = st.selectbox("Nivel de Tensión de la Instalación", niveles_disponibles(), index=1)
    banco = dimensionar_banco_capacitores(nivel_tension, q_compensar)
    
    col_bc1, col_bc2 = st.columns(2)
    with col_bc1:
        if banco.valor_comercial_kvar:
            st.markdown(
                f"""
                <div class="metric-card-box metric-card-uacm">
                    <div class="metric-label">Banco Comercial Sugerido</div>
                    <div class="metric-num-uacm">{banco.valor_comercial_kvar:,.0f} <span style="font-size:18px;">kVAr</span></div>
                    <div class="metric-foot">Escalón comercial estándar inmediato para cubrir {q_compensar:,.2f} kVAr</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        else:
            maximo = banco_maximo_disponible(nivel_tension)
            st.error(f"La demanda de {q_compensar:,.2f} kVAr supera el escalón comercial unitario máximo de {maximo:,.0f} kVAr en {nivel_tension}.")
    with col_bc2:
        if banco.requiere_escalonar:
            st.warning("⚠️ **Recomendación de Ingeniería:** La capacidad demandada requiere configurar un banco automático multietapas con pasos en paralelo.")
        else:
            st.success("✅ **Selección Óptima:** Capacidad comercial estándar unitaria disponible de fábrica.")
            
    with st.expander("🔍 Explorar catálogo comercial estandarizado (2026)"):
        for niv in niveles_disponibles():
            vals = sorted(b.kvar for b in BASE_CAPACITORES if b.nivel_tension == niv)
            st.write(f"• **{niv}:** {', '.join(f'{v:g}' for v in vals)} kVAr")

with tab4:
    st.markdown("<h4 style='color:#8F141B; font-weight:800; margin-bottom:12px;'>Alternativa B: Motor Síncrono en Sobreexcitación</h4>", unsafe_allow_html=True)
    v_ll = st.number_input("Tensión de Línea a Línea del Sistema [kV]", min_value=0.1, value=13.8, step=0.1)
    corriente_ms = corriente_motor_sincrono(q_compensar, v_ll)
    
    st.markdown(
        f"""
        <div class="metric-card-box metric-card-green" style="max-width: 540px;">
            <div class="metric-label">Corriente Reactiva Capacitiva</div>
            <div class="metric-num-green">{corriente_ms:,.2f} <span style="font-size:18px;">A</span></div>
            <div class="metric-foot">Corriente reactiva que el motor síncrono debe inyectar a la red interna</div>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.markdown(
        f"""
        <div class="info-dark-box">
            <b>Fórmula de Corriente Trifásica:</b> <code>I = Qc / (√3 · V_LL)</code>
        </div>
        """,
        unsafe_allow_html=True
    )

with tab5:
    st.markdown("<h4 style='color:#8F141B; font-weight:800; margin-bottom:12px;'>Costos de Inversión y Retorno Simple (ROI)</h4>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        costo_bc = st.number_input("Costo Unitario Banco de Capacitores [$ MXN / kVAr]", min_value=0.0, value=1700.0, step=50.0)
    with c2:
        costo_ms = st.number_input("Costo Unitario Motor Síncrono [$ MXN / kVAr]", min_value=0.0, value=5100.0, step=50.0)

    r_bc = calcular_inversion_y_roi(q_compensar, costo_bc, penalizacion)
    r_ms = calcular_inversion_y_roi(q_compensar, costo_ms, penalizacion)

    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    res_col1, res_col2 = st.columns(2)
    with res_col1:
        roi_txt_bc = f"{r_bc.roi_meses:,.1f} meses" if r_bc.roi_meses else "N/A"
        st.markdown(
            f"""
            <div class="info-dark-box" style="border-top: 5px solid #8F141B;">
                <b style="color:#8F141B; font-size:16px;">Opción A: Banco de Capacitores</b><br/><br/>
                • <b>Inversión Total:</b> <span style="color:#0F172A; font-weight:800;">${r_bc.inversion_mxn:,.2f} MXN</span><br/>
                • <b>Payback Simple:</b> <span style="color:#065F46; font-weight:800;">{roi_txt_bc}</span>
            </div>
            """,
            unsafe_allow_html=True
        )
    with res_col2:
        roi_txt_ms = f"{r_ms.roi_meses:,.1f} meses" if r_ms.roi_meses else "N/A"
        st.markdown(
            f"""
            <div class="info-dark-box" style="border-top: 5px solid #065F46;">
                <b style="color:#065F46; font-size:16px;">Opción B: Motor Síncrono</b><br/><br/>
                • <b>Inversión Total:</b> <span style="color:#0F172A; font-weight:800;">${r_ms.inversion_mxn:,.2f} MXN</span><br/>
                • <b>Payback Simple:</b> <span style="color:#065F46; font-weight:800;">{roi_txt_ms}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    st.markdown("<hr style='border: 1px solid #CBD5E1; margin: 22px 0;'>", unsafe_allow_html=True)
    st.markdown("<h4 style='color:#8F141B; font-weight:800;'>Memoria Técnica en PDF (Formato Oficial UACM)</h4>", unsafe_allow_html=True)
    
    if st.button("📄 Generar Memoria Técnica Institucional (PDF)", use_container_width=True):
        datos = DatosEntrada(
            demanda_max_kw=demanda, fp_actual=fp_actual, fp_objetivo=fp_objetivo,
            penalizacion_mensual_mxn=penalizacion, nivel_tension=nivel_tension, v_ll_kv=v_ll,
            costo_kvar_banco_capacitores_mxn=costo_bc, costo_kvar_motor_sincrono_mxn=costo_ms,
        )
        resultado = calcular_todo(datos)
        buffer = io.BytesIO()
        generar_reporte_pdf(datos, resultado, buffer)
        buffer.seek(0)
        st.session_state.pdf_bytes = buffer.getvalue()
        st.success("Memoria técnica generada con éxito con membrete institucional de la UACM y del PEUACM.")

    if st.session_state.pdf_bytes:
        nombre_pdf = f"Reporte_FP_UACM_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        st.download_button(
            "⬇️ Descargar Reporte Técnico (PDF)",
            data=st.session_state.pdf_bytes,
            file_name=nombre_pdf,
            mime="application/pdf",
            use_container_width=True
        )

st.markdown("<br><hr style='border: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
st.caption(
    "Universidad Autónoma de la Ciudad de México (UACM) · Posgrado en Ingeniería Energética · "
    "Materia: Fundamentos de Ingeniería Eléctrica. Herramienta de dimensionamiento de reactivos para cumplimiento técnico y mitigación de sanciones regulatorias."
)