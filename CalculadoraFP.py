# -*- coding: utf-8 -*-
"""
UNIVERSIDAD AUTÓNOMA DE LA CIUDAD DE MÉXICO (UACM)
Colegio de Ciencia y Tecnología — Maestría en Ingeniería Energética
Materia: Fundamentos de Ingeniería Eléctrica

Herramienta: Ajuste del Factor de Potencia (FP)
Integración de Demanda Contratada y Criterios del ACUERDO CT/11.SE/8-2025
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

# Rutas locales de los logotipos institucionales
RUTA_LOGO_UACM = "logo_uacm.png"
RUTA_LOGO_PEUACM = "logo_peuacm.png"

# 1. CATÁLOGOS COMERCIALES DE BANCOS DE CAPACITORES (2026)

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
    [BancoCapacitor("Baja Tensión (< 1 kV)", v) for v in _BAJA_TENSION_KVAR]
    + [BancoCapacitor("Media Tensión (1 kV - 35 kV)", v) for v in _MEDIA_TENSION_KVAR]
    + [BancoCapacitor("Alta Tensión (> 35 kV)", v) for v in _ALTA_TENSION_KVAR]
)

NIVELES_TENSION = [
    "Baja Tensión (< 1 kV)",
    "Media Tensión (1 kV - 35 kV)",
    "Alta Tensión (> 35 kV)"
]

def seleccionar_banco_comercial(nivel_tension: str, q_compensar_kvar: float) -> Optional[float]:
    candidatos = sorted(
        b.kvar for b in BASE_CAPACITORES
        if b.nivel_tension == nivel_tension and b.kvar >= q_compensar_kvar
    )
    return candidatos[0] if candidatos else None

def banco_maximo_disponible(nivel_tension: str) -> float:
    valores = [b.kvar for b in BASE_CAPACITORES if b.nivel_tension == nivel_tension]
    return max(valores) if valores else 0.0


# 2. MOTOR DE CÁLCULO DE INGENIERÍA Y TARIFARIO

RECARGO_MAXIMO_PCT = 120.0
BONIFICACION_MAXIMA_PCT = 2.5

def determinar_fp_minimo_base(nivel_tension: str, demanda_contratada_kw: float, demanda_medida_kw: float) -> float:
    """
    Determina la base de factor de potencia mínimo regulatorio considerando
    la demanda contratada o la demanda máxima registrada:
    - Baja Tensión: 0.90
    - Media Tensión (< 1000 kW / 1 MW): 0.90
    - Media Tensión (>= 1000 kW / 1 MW): 0.97
    - Alta Tensión: 0.97
    """
    demanda_referencia = max(demanda_contratada_kw, demanda_medida_kw)
    if nivel_tension == "Baja Tensión (< 1 kV)":
        return 0.90
    elif nivel_tension == "Media Tensión (1 kV - 35 kV)":
        return 0.97 if demanda_referencia >= 1000.0 else 0.90
    else:  # Alta Tensión (> 35 kV)
        return 0.97

def calcular_demanda_facturable(demanda_medida_kw: float, demanda_contratada_kw: float) -> tuple[float, str]:
    """
    Fórmula tarifaria oficial CFE para exceso de demanda:
    Si DP <= DC -> DF = DP
    Si DP > DC -> DF = DC + 2 * (DP - DC)
    """
    if demanda_medida_kw <= demanda_contratada_kw:
        return demanda_medida_kw, "Normal (Demanda dentro del límite contratado)"
    else:
        df = demanda_contratada_kw + 2.0 * (demanda_medida_kw - demanda_contratada_kw)
        return df, "Penalización por exceso de demanda (DP > DC)"

def potencia_reactiva_a_compensar(demanda_max_kw: float, fp_actual: float, fp_objetivo: float) -> float:
    if not (0 < fp_actual <= 1) or not (0 < fp_objetivo <= 1):
        raise ValueError("El factor de potencia debe estar entre 0.0 y 1.0")
    if fp_actual >= fp_objetivo:
        return 0.0
    q = demanda_max_kw * (tan(acos(fp_actual)) - tan(acos(fp_objetivo)))
    return max(q, 0.0)

@dataclass
class ResultadoBonificacionRecargo:
    aplica: str
    porcentaje_recargo: Optional[float]
    porcentaje_bonificacion: Optional[float]
    detalle_recargo: str
    detalle_bonificacion: str
    formula_aplicada: str

def calcular_bonificacion_recargo(fp_actual: float, fp_base: float) -> ResultadoBonificacionRecargo:
    if not (0 < fp_actual <= 1):
        raise ValueError("El factor de potencia debe estar entre 0.0 y 1.0")

    if fp_actual <= 0.40:
        return ResultadoBonificacionRecargo(
            aplica="Recargo",
            porcentaje_recargo=120.0,
            porcentaje_bonificacion=None,
            detalle_recargo=f"FP crítico (≤ 0.40). Aplica el recargo máximo reglamentario de 120.00% con base a FP mínimo de {fp_base:.2f}.",
            detalle_bonificacion=f"No aplica (FP por debajo del umbral mínimo de {fp_base:.2f}).",
            formula_aplicada="Tope máximo 120% (FP crítico ≤ 0.40)"
        )
    elif fp_actual < fp_base:
        pct = (3.0 / 5.0) * ((fp_base / fp_actual) - 1.0) * 100.0
        pct = min(pct, RECARGO_MAXIMO_PCT)
        return ResultadoBonificacionRecargo(
            aplica="Recargo",
            porcentaje_recargo=round(pct, 2),
            porcentaje_bonificacion=None,
            detalle_recargo=f"Aplica recargo del {pct:.2f}% en la facturación de energía activa (Fórmula: 3/5·[({fp_base:.2f}/FP) − 1]·100).",
            detalle_bonificacion=f"No aplica (FP menor al mínimo requerido de {fp_base:.2f}).",
            formula_aplicada=f"3/5 · [({fp_base:.2f} / FP) − 1] · 100"
        )
    elif fp_actual > fp_base:
        pct = (1.0 / 4.0) * (1.0 - (fp_base / fp_actual)) * 100.0
        pct = min(pct, BONIFICACION_MAXIMA_PCT)
        return ResultadoBonificacionRecargo(
            aplica="Bonificación",
            porcentaje_recargo=None,
            porcentaje_bonificacion=round(pct, 2),
            detalle_recargo=f"Sin recargo (Cumple y supera el FP mínimo de {fp_base:.2f}).",
            detalle_bonificacion=f"Aplica bonificación del {pct:.2f}% en la facturación de energía activa (Fórmula: 1/4·[1 − ({fp_base:.2f}/FP)]·100).",
            formula_aplicada=f"1/4 · [1 − ({fp_base:.2f} / FP)] · 100"
        )
    else:
        return ResultadoBonificacionRecargo(
            aplica="Sin ajuste",
            porcentaje_recargo=0.0,
            porcentaje_bonificacion=0.0,
            detalle_recargo=f"Sin recargo (FP exacto en {fp_base:.2f}).",
            detalle_bonificacion=f"Sin bonificación (FP exacto en {fp_base:.2f}).",
            formula_aplicada=f"FP = {fp_base:.2f} (Punto neutro)"
        )

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
        return 0.0
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
    demanda_contratada_kw: float
    demanda_facturable_kw: float
    estatus_demanda: str
    factor_utilizacion_pct: float
    fp_actual: float
    fp_objetivo: float
    fp_minimo_base: float
    nivel_tension: str
    penalizacion_mensual_mxn: float = 0.0
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
    bon_rec = calcular_bonificacion_recargo(datos.fp_actual, datos.fp_minimo_base)
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

# 3. GENERADOR DE REPORTE PDF (ACUERDO CT/11.SE/8-2025)

COLOR_UACM_PDF = colors.HexColor("#8F141B")
COLOR_VERDE_PDF = colors.HexColor("#065F46")
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
    elementos.append(Spacer(1, 0.22 * cm))
    elementos.append(Paragraph(titulo, ParagraphStyle(
        "seccion", parent=styles["Heading2"], textColor=colors.white, fontSize=10,
        backColor=color_fondo, borderPadding=(4, 6, 4, 6), leading=13)))
    elementos.append(Spacer(1, 0.12 * cm))

def generar_reporte_pdf(datos: DatosEntrada, resultado: ResultadoIntegral, destino) -> None:
    doc = SimpleDocTemplate(
        destino, pagesize=letter,
        leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.2 * cm, bottomMargin=1.2 * cm,
        title="Memoria Técnica FP - UACM",
    )
    styles = getSampleStyleSheet()
    elementos = []

    img_uacm = RLImage(RUTA_LOGO_UACM, width=2.3 * cm, height=2.3 * cm) if os.path.exists(RUTA_LOGO_UACM) else Paragraph("", styles["Normal"])
    img_peuacm = RLImage(RUTA_LOGO_PEUACM, width=3.2 * cm, height=1.05 * cm) if os.path.exists(RUTA_LOGO_PEUACM) else Paragraph("", styles["Normal"])

    texto_header = Paragraph(
        "<b>UNIVERSIDAD AUTÓNOMA DE LA CIUDAD DE MÉXICO</b><br/>"
        "<font size=10.5 color='#8F141B'><b>Colegio de Ciencia y Tecnología — Maestría en Ingeniería Energética</b></font><br/>"
        "<font size=8.5 color='#065F46'><b>Programa de Energía UACM (PEUACM)</b></font> · <font size=8.5 color='#1A1A1A'>Fundamentos de Ingeniería Eléctrica</font>",
        ParagraphStyle("head_txt", parent=styles["Normal"], alignment=TA_CENTER, leading=12)
    )

    tabla_logos = Table([[img_uacm, texto_header, img_peuacm]], colWidths=[2.5 * cm, 11.0 * cm, 3.5 * cm])
    tabla_logos.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    elementos.append(tabla_logos)
    elementos.append(Spacer(1, 0.15 * cm))

    titulo = Paragraph(
        "<b>MEMORIA TÉCNICA: AJUSTE Y COMPENSACIÓN DE FACTOR DE POTENCIA</b><br/>"
        "<font size=8 color='#065F46'>Cálculo Integral de Capacidad bajo ACUERDO CT/11.SE/8-2025 (Tarifas Finales CFE SSB 2026)</font>",
        ParagraphStyle("titulo", parent=styles["Title"], alignment=TA_CENTER,
                        textColor=COLOR_UACM_PDF, fontSize=12, leading=14),
    )
    elementos.append(titulo)
    elementos.append(Paragraph(f"Fecha de emisión: {datetime.now().strftime('%d/%m/%Y %I:%M %p')}", ParagraphStyle(
        "fecha", parent=styles["Normal"], alignment=TA_CENTER, fontSize=7.5, textColor=COLOR_GRIS)))
    elementos.append(Spacer(1, 0.15 * cm))
    elementos.append(HRFlowable(width="100%", color=COLOR_UACM_PDF, thickness=1.5))
    elementos.append(Spacer(1, 0.2 * cm))

    _seccion(elementos, styles, "1. Datos Generales de Demanda y Tensión")
    elementos.append(_tabla_datos([
        ["Nivel de Tensión de la Instalación", datos.nivel_tension, "[1]"],
        ["Demanda Contratada (DC)", f"{datos.demanda_contratada_kw:,.2f}", "[kW]"],
        ["Demanda Máxima Medida (DP)", f"{datos.demanda_max_kw:,.2f}", "[kW]"],
        ["Demanda Facturable Estimada (DF)", f"{datos.demanda_facturable_kw:,.2f}", "[kW]"],
        ["Factor de Utilización de Capacidad", f"{datos.factor_utilizacion_pct:.1f}", "[%]"],
        ["Estatus de Demanda CFE", datos.estatus_demanda, ""],
        ["Factor de Potencia Mínimo Base Aplicable", f"{datos.fp_minimo_base:.2f}", "[1]"],
        ["Factor de Potencia Actual Medido", f"{datos.fp_actual:.3f}", "[1]"],
        ["Factor de Potencia Objetivo Requerido", f"{datos.fp_objetivo:.3f}", "[1]"],
        ["Penalización Actual Reportada en Recibo", f"${datos.penalizacion_mensual_mxn:,.2f}", "[MXN]"],
        ["Potencia Reactiva Neta a Compensar (Qc)", f"{resultado.q_compensar_kvar:,.2f}", "[kVAr]"],
    ]))

    _seccion(elementos, styles, f"2. Régimen Tarifario CFE (Base FP Mínimo: {datos.fp_minimo_base:.2f})", COLOR_VERDE_PDF)
    br = resultado.bonificacion_recargo
    estado_rec = f"{br.porcentaje_recargo:.2f} %" if br.porcentaje_recargo is not None else "No aplica"
    estado_bon = f"{br.porcentaje_bonificacion:.2f} %" if br.porcentaje_bonificacion is not None else "No aplica"
    elementos.append(_tabla_datos([
        ["Porcentaje de Recargo en Facturación", estado_rec, "[%]"],
        ["Porcentaje de Bonificación en Facturación", estado_bon, "[%]"],
        ["Fórmula de Ajuste Aplicada", br.formula_aplicada, ""],
    ]))

    _seccion(elementos, styles, "3. Dimensionamiento de Alternativas Técnicas")
    bc = resultado.banco_capacitores
    valor_bc = f"{bc.valor_comercial_kvar:,.0f}" if bc.valor_comercial_kvar else "Excede catálogo comercial"
    elementos.append(Paragraph("<b>Alternativa A: Banco de Capacitores</b>",
                                ParagraphStyle("sub", parent=styles["Normal"], fontSize=9, textColor=COLOR_UACM_PDF, spaceAfter=3)))
    elementos.append(_tabla_datos([
        ["Capacidad Comercial Estándar Sugerida", valor_bc, "[kVAr]"],
    ]))
    if bc.requiere_escalonar:
        elementos.append(Paragraph(
            "<i>Nota: La potencia a compensar supera el escalón comercial unitario más grande; "
            "se recomienda arreglo automático con varios bancos en paralelo.</i>",
            ParagraphStyle("nota", parent=styles["Normal"], fontSize=7.5, textColor=COLOR_GRIS)))

    elementos.append(Spacer(1, 0.15 * cm))
    elementos.append(Paragraph("<b>Alternativa B: Motor Síncrono (Sobreexcitado)</b>",
                                ParagraphStyle("sub2", parent=styles["Normal"], fontSize=9, textColor=COLOR_VERDE_PDF, spaceAfter=3)))
    elementos.append(_tabla_datos([
        ["Tensión de Operación Línea-Línea", f"{datos.v_ll_kv:,.2f}", "[kV]"],
        ["Corriente Reactiva a Entregar por el Motor", f"{resultado.corriente_motor_sincrono_a:,.2f}", "[A]"],
    ]))

    _seccion(elementos, styles, "4. Inversión Estimada y Retorno Simple (ROI)")
    cbc = resultado.costos_banco_capacitores
    cms = resultado.costos_motor_sincrono
    tabla_costos = Table(
        [["Concepto", "Banco de Capacitores", "Motor Síncrono"],
         ["Costo Unitario por kVAr [MXN]", f"${datos.costo_kvar_banco_capacitores_mxn:,.2f}", f"${datos.costo_kvar_motor_sincrono_mxn:,.2f}"],
         ["Inversión Total Aproximada [MXN]", f"${cbc.inversion_mxn:,.2f}", f"${cms.inversion_mxn:,.2f}"],
         ["Retorno de Inversión Simple (ROI)", f"{cbc.roi_meses:,.1f} meses" if cbc.roi_meses else "N/A", f"{cms.roi_meses:,.1f} meses" if cms.roi_meses else "N/A"]],
        colWidths=[6.8 * cm, 4.6 * cm, 4.6 * cm],
    )
    tabla_costos.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), COLOR_UACM_PDF),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, COLOR_UACM_CLARO]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
    ]))
    elementos.append(tabla_costos)

    elementos.append(Spacer(1, 0.3 * cm))
    elementos.append(HRFlowable(width="100%", color=COLOR_UACM_PDF, thickness=0.8))
    elementos.append(Spacer(1, 0.1 * cm))
    elementos.append(Paragraph(
        "Memoria de cálculo desarrollada en la Universidad Autónoma de la Ciudad de México (UACM) — Maestría en Ingeniería Energética. "
        "Fundamentada en el ACUERDO CT/11.SE/8-2025 de las tarifas de suministro básico CFE 2026. "
        f"Base de factor de potencia mínimo aplicable para esta instalación: {datos.fp_minimo_base:.2f}. "
        "Un factor de potencia inferior a dicho mínimo genera recargos automáticos en facturación y riesgo de sanciones administrativas de la CRE.",
        ParagraphStyle("footer", parent=styles["Normal"], fontSize=6.8, textColor=COLOR_GRIS)))

    doc.build(elementos)

# =======================================================================
# 4. INTERFAZ GRÁFICA STREAMLIT
# =======================================================================

st.set_page_config(
    page_title="Compensación FP — UACM",
    page_icon="⚡",
    layout="wide"
)

# Estilos CSS de alto contraste
st.markdown(
    "
    <style>
        .stApp {
            background-color: #F8FAFC !important;
            color: #0F172A !important;
        }
        .main .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 3rem !important;
            max-width: 1120px !important;
        }

        /* Banner Institucional */
        .header-solid-box {
            background-color: #FFFFFF !important;
            border: 2px solid #E2E8F0 !important;
            border-top: 6px solid #8F141B !important;
            border-radius: 12px !important;
            padding: 16px 24px !important;
            margin-bottom: 20px !important;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05) !important;
        }
        .header-title-uacm {
        
