import streamlit as st
import numpy as np
import matplotlib.pyplot as plt

# Configuración general de la página
st.set_page_config(page_title="Calculadora de Incidencia Solar", page_icon="☀️", layout="wide")

st.title("☀️ Calculadora Didáctica de Incidencia Solar")
st.markdown("### Herramienta interactiva para comprender cómo los rayos del Sol impactan sobre una superficie inclinada.")

# Sección educativa desplegable para personas sin experiencia previa
with st.expander("💡 ¿Qué significan estos conceptos? (Guía rápida para principiantes)", expanded=True):
    st.markdown("""
    * **Ángulo de Incidencia ($\Theta$):** Es el ángulo que forman los rayos del Sol con una línea imaginaria perpendicular (normal) a la superficie del panel. 
        * **Si $\ theta = 0^\circ$:** Los rayos caen de forma perfectamente perpendicular, logrando el mayor aprovechamiento energético.
        * **Si $\ theta$ se acerca a $90^\circ$:** Los rayos rozan la superficie y la energía captada es casi nula.
    * **Latitud ($\Phi$):** La posición geográfica del lugar respecto al ecuador de la Tierra.
    * **Declinación Solar ($\Delta$):** El ángulo de inclinación estacional de la Tierra frente al Sol (varía entre $-23.45^\circ$ y $+23.45^\circ$ a lo largo del año).
    * **Inclinación del Panel ($\Beta$):** Qué tan levantado o acostado está el colector respecto al suelo horizontal.
    * **Azimut de la Superficie ($r$):** La orientación horizontal del panel ($0^\circ$ apunta exactamente al Sur geográfico).
    """)

# Panel lateral con controles visuales (Sliders)
st.sidebar.header("🎛️ Panel de Control")

lat_deg = st.sidebar.slider("Latitud del lugar (°)", min_value=-90.0, max_value=90.0, value=19.43, step=0.1, help="Ej. Ciudad de México ≈ 19.4°")
decl_deg = st.sidebar.slider("Declinación solar (°)", min_value=-23.45, max_value=23.45, value=0.0, step=0.1, help="0° en equinoccios")
incl_deg = st.sidebar.slider("Inclinación de la superficie / Panel (°)", min_value=0.0, max_value=90.0, value=20.0, step=1.0)
azim_deg = st.sidebar.slider("Azimut de la superficie (°)", min_value=-180.0, max_value=180.0, value=0.0, step=1.0, help="0° = Orientado al Sur")
omega_deg = st.sidebar.slider("Ángulo horario (Hora del día)", min_value=-75.0, max_value=75.0, value=0.0, step=1.0, help="0° = Mediodía solar exacto")

# --- BLOQUE DE CÁLCULO (Basado en la fórmula geométrica del Excel) ---
phi = np.radians(decl_deg)
Phi = np.radians(lat_deg)
beta = np.radians(incl_deg)
r = np.radians(azim_deg)
omega = np.radians(omega_deg)

cos_theta = (
    np.sin(phi) * np.sin(Phi) * np.cos(beta) -
    np.sin(phi) * np.cos(Phi) * np.sin(beta) * np.cos(r) +
    np.cos(phi) * np.cos(Phi) * np.cos(beta) * np.cos(omega) +
    np.cos(phi) * np.sin(Phi) * np.sin(beta) * np.cos(r) * np.cos(omega) +
    np.cos(phi) * np.sin(beta) * np.sin(r) * np.sin(omega)
)

cos_theta = np.clip(cos_theta, -1.0, 1.0)
theta_deg = np.degrees(np.arccos(cos_theta))

# Estructura visual de resultados en dos columnas
col1, col2 = st.columns([1, 2])

with col1:
    st.metric(label="Ángulo de Incidencia ($\ theta$)", value=f"{theta_deg:.2f}°")
    
    # Interpretación intuitiva en formato de alerta visual
    if theta_deg > 90:
        st.error("⚠️ **Incidencia posterior:** El sol está por detrás de la superficie (sombra propia).")
    elif theta_deg < 15:
        st.success("🌟 **¡Excelente!** Incidencia casi perpendicular; captación máxima.")
    elif theta_deg < 45:
        st.info("👍 **Alta eficiencia:** Buena aprovechabilidad de la radiación directa.")
    elif theta_deg < 75:
        st.warning("⚡ **Moderada:** La energía empieza a reducirse por el efecto coseno.")
    else:
        st.warning("🔻 **Rasante:** La radiación aprovechable es muy baja.")

with col2:
    st.subheader("📈 Variación Diaria del Ángulo")
    horas_solar = np.linspace(-75, 75, 100)
    horas_reloj = 12.0 + (horas_solar / 15.0)
    
    angulos_diarios = []
    for h in horas_solar:
        om = np.radians(h)
        ct = (
            np.sin(phi) * np.sin(Phi) * np.cos(beta) -
            np.sin(phi) * np.cos(Phi) * np.sin(beta) * np.cos(r) +
            np.cos(phi) * np.cos(Phi) * np.cos(beta) * np.cos(om) +
            np.cos(phi) * np.sin(Phi) * np.sin(beta) * np.cos(r) * np.cos(om) +
            np.cos(phi) * np.sin(Phi) * np.sin(r) * np.sin(om)
        )
        angulos_diarios.append(np.degrees(np.arccos(np.clip(ct, -1.0, 1.0))))

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(horas_reloj, angulos_diarios, color='#ff4b4b', linewidth=2.5, label='Curva de $\theta$')
    ax.axhline(90, color='gray', linestyle='--', alpha=0.7, label='Límite de sombra ($90^\circ$)')
    ax.scatter([12.0 + (omega_deg/15.0)], [theta_deg], color='black', s=60, zorder=5, label='Valor actual')
    ax.set_xlabel("Hora Solar Aproximada", fontsize=9)
    ax.set_ylabel("Ángulo $\Theta$ (°)", fontsize=9)
    ax.grid(True, linestyle=':', alpha=0.6)
    ax.legend(fontsize=8)
    st.pyplot(fig)
