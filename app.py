#!/usr/bin/env python3
"""
TEMAPEO VIEWER v7 - Dashboard con Descripciones y Filtros Mejorados
- Descripciones de índices espectrales
- Filtros en cascada (especie → variedad → cuartel)
- Selección múltiple de cuarteles
- Soporte para logo personalizado

Autor: TeMapeo SPA
Versión: 7.0
"""

import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
# Folium comentado - usando Plotly Mapbox (más estable en Streamlit Cloud)
# import folium
# from folium.plugins import Fullscreen
# from streamlit_folium import st_folium
from datetime import datetime
import os
import base64


def mostrar_mapa_seguro(fig, height, key):
    """Muestra el mapa Plotly con manejo de errores."""
    try:
        if fig is not None:
            st.plotly_chart(fig, use_container_width=True, key=key)
        else:
            st.warning("No hay datos para mostrar en el mapa")
    except Exception as e:
        st.info(f"""
        ⏳ **El mapa está tardando en cargar**
        
        Esto puede deberse a la velocidad de conexión. Mientras tanto, puedes revisar los datos en las tablas y gráficos.
        
        **Opciones:**
        - Refrescar la página (F5)
        - Reducir el número de cuarteles seleccionados
        """)
        if st.button(f"🔄 Reintentar", key=f"retry_{key}"):
            st.rerun()

# =============================================================================
# CONFIGURACIÓN DE PÁGINA
# =============================================================================
st.set_page_config(
    page_title="TeMapeo Viewer",
    page_icon="🌳",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {font-size: 2.2rem; font-weight: bold; color: #1a9641; text-align: center; padding: 0.5rem;}
    .sub-header {font-size: 1rem; color: #666; text-align: center; margin-bottom: 1rem;}
    
    /* Reducir tamaño de métricas KPI - más compacto */
    [data-testid="stMetricValue"] {
        font-size: 0.95rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.7rem !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.65rem !important;
    }
    div[data-testid="metric-container"] {
        padding: 0.2rem !important;
    }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# CONFIGURACIÓN - RUTAS PARA STREAMLIT CLOUD
# =============================================================================

GPKG_PATH = "datos/Individualizacion_consolidado_oct_dic.gpkg"
POLIGONOS_PATH = "datos/Poligonos_Abud.gpkg"

# Ruta al logo (PNG o JPG)
LOGO_PATH = 'datos/logo.png'

# =============================================================================
# COLORES Y CONFIGURACIÓN
# =============================================================================

COLORES_CLASE = {
    'Muy bajo': '#d7191c',
    'Bajo': '#fdae61', 
    'Medio': '#ffffbf',
    'Medio-alto': '#a6d96a',
    'Alto': '#1a9641',
    'Sin dato': '#969696'
}

# Información detallada de cada índice
INDICES_INFO = {
    'ndvi': {
        'nombre': 'NDVI',
        'nombre_completo': 'Índice de Vegetación de Diferencia Normalizada',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Mide la cantidad y vigor de la vegetación. Valores altos (>0.6) indican vegetación densa y saludable. Valores bajos (<0.3) indican estrés, suelo desnudo o vegetación escasa.',
        'interpretacion': {
            'Alto': 'Árbol con excelente vigor, follaje denso y buena actividad fotosintética',
            'Medio-alto': 'Buen estado general, follaje saludable',
            'Medio': 'Vigor moderado, puede requerir atención',
            'Bajo': 'Estrés vegetativo, posible déficit hídrico o nutricional',
            'Muy bajo': 'Estrés severo, requiere intervención inmediata'
        },
        'rango': '0 a 1'
    },
    'osavi': {
        'nombre': 'OSAVI',
        'nombre_completo': 'Índice de Vegetación Ajustado al Suelo Optimizado',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Similar al NDVI pero minimiza la influencia del suelo. Ideal para cultivos con cobertura parcial del suelo. Más estable que NDVI en condiciones de baja cobertura vegetal.',
        'interpretacion': {
            'Alto': 'Excelente cobertura vegetal y vigor',
            'Medio-alto': 'Buena cobertura, vegetación saludable',
            'Medio': 'Cobertura moderada',
            'Bajo': 'Baja cobertura o estrés',
            'Muy bajo': 'Muy baja cobertura o estrés severo'
        },
        'rango': '0 a 0.6'
    },
    'gndvi': {
        'nombre': 'GNDVI',
        'nombre_completo': 'Índice de Vegetación de Diferencia Normalizada Verde',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Usa la banda verde en lugar de roja. Más sensible a variaciones de clorofila que el NDVI. Útil para detectar diferencias sutiles en el contenido de clorofila.',
        'interpretacion': {
            'Alto': 'Alto contenido de clorofila, vegetación muy activa',
            'Medio-alto': 'Buen contenido de clorofila',
            'Medio': 'Contenido moderado de clorofila',
            'Bajo': 'Bajo contenido de clorofila',
            'Muy bajo': 'Deficiencia severa de clorofila'
        },
        'rango': '0 a 1'
    },
    'savi': {
        'nombre': 'SAVI',
        'nombre_completo': 'Índice de Vegetación Ajustado al Suelo',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Minimiza efectos del suelo mediante un factor de corrección (L=0.5). Recomendado cuando hay suelo visible entre las plantas.',
        'interpretacion': {
            'Alto': 'Excelente vigor vegetativo',
            'Medio-alto': 'Buen estado vegetativo',
            'Medio': 'Estado moderado',
            'Bajo': 'Estrés o baja cobertura',
            'Muy bajo': 'Estrés severo'
        },
        'rango': '0 a 0.5'
    },
    'msavi2': {
        'nombre': 'MSAVI2',
        'nombre_completo': 'Índice de Vegetación Ajustado al Suelo Modificado',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Versión mejorada del SAVI con factor de corrección automático. Reduce aún más la influencia del suelo sin necesidad de ajustar parámetros.',
        'interpretacion': {
            'Alto': 'Vegetación densa y vigorosa',
            'Medio-alto': 'Buena densidad vegetal',
            'Medio': 'Densidad moderada',
            'Bajo': 'Baja densidad o estrés',
            'Muy bajo': 'Muy baja densidad'
        },
        'rango': '0 a 0.5'
    },
    'evi2': {
        'nombre': 'EVI2',
        'nombre_completo': 'Índice de Vegetación Mejorado (2 bandas)',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Optimizado para áreas de alta biomasa donde el NDVI se satura. Mejor respuesta en vegetación densa. No requiere banda azul.',
        'interpretacion': {
            'Alto': 'Alta biomasa, vegetación muy densa',
            'Medio-alto': 'Buena biomasa',
            'Medio': 'Biomasa moderada',
            'Bajo': 'Baja biomasa',
            'Muy bajo': 'Muy baja biomasa'
        },
        'rango': '0 a 0.5'
    },
    'lci': {
        'nombre': 'LCI',
        'nombre_completo': 'Índice de Clorofila de Hoja',
        'categoria': 'Contenido de Clorofila',
        'descripcion': 'Estima el contenido de clorofila en las hojas usando bandas NIR y RedEdge. Correlaciona directamente con el contenido de nitrógeno foliar. Útil para gestión de fertilización.',
        'interpretacion': {
            'Alto': 'Alto contenido de clorofila, buena nutrición nitrogenada',
            'Medio-alto': 'Buen estado nutricional',
            'Medio': 'Nutrición moderada',
            'Bajo': 'Posible deficiencia de nitrógeno',
            'Muy bajo': 'Deficiencia severa, fertilizar con urgencia'
        },
        'rango': '0.1 a 0.85'
    },
    'ndre': {
        'nombre': 'NDRE',
        'nombre_completo': 'Índice de Diferencia Normalizada Red Edge',
        'categoria': 'Contenido de Clorofila',
        'descripcion': 'Usa la banda Red Edge, muy sensible al contenido de clorofila. Ideal para detectar estrés temprano antes de que sea visible. No se satura en vegetación densa.',
        'interpretacion': {
            'Alto': 'Excelente contenido de clorofila, planta muy sana',
            'Medio-alto': 'Buen contenido de clorofila',
            'Medio': 'Contenido normal',
            'Bajo': 'Bajo contenido, posible estrés inicial',
            'Muy bajo': 'Estrés significativo detectado'
        },
        'rango': '0.15 a 0.5'
    },
    'cirededge': {
        'nombre': 'CIRedEdge',
        'nombre_completo': 'Índice de Clorofila Red Edge',
        'categoria': 'Contenido de Clorofila',
        'descripcion': 'Altamente sensible a pequeños cambios en el contenido de clorofila. Excelente para monitoreo de salud del cultivo y detección temprana de problemas.',
        'interpretacion': {
            'Alto': 'Máxima actividad fotosintética',
            'Medio-alto': 'Buena actividad fotosintética',
            'Medio': 'Actividad normal',
            'Bajo': 'Reducción de actividad fotosintética',
            'Muy bajo': 'Actividad fotosintética muy reducida'
        },
        'rango': '0 a 1'
    },
    'mcari': {
        'nombre': 'MCARI',
        'nombre_completo': 'Índice de Absorción de Clorofila Modificado',
        'categoria': 'Estructura del Dosel',
        'descripcion': 'Sensible tanto al contenido de clorofila como a la estructura del dosel. Útil para evaluar la arquitectura de la copa del árbol.',
        'interpretacion': {
            'Alto': 'Dosel bien estructurado con alta clorofila',
            'Medio-alto': 'Buena estructura de dosel',
            'Medio': 'Estructura normal',
            'Bajo': 'Estructura de dosel reducida',
            'Muy bajo': 'Dosel muy reducido o dañado'
        },
        'rango': '0 a 1'
    }
}

# =============================================================================
# FUNCIONES BASE
# =============================================================================

def cargar_logo():
    """Carga el logo si existe."""
    if os.path.exists(LOGO_PATH):
        return LOGO_PATH
    return None


def mostrar_logo_sidebar():
    """Muestra el logo en el sidebar."""
    if os.path.exists(LOGO_PATH):
        try:
            st.image(LOGO_PATH, width=180)
        except:
            pass


def mostrar_logo_header():
    """Muestra el logo en el header."""
    if os.path.exists(LOGO_PATH):
        try:
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.image(LOGO_PATH, width=220)
        except:
            pass


@st.cache_data
def cargar_datos(ruta_gpkg):
    """Carga datos del GPKG."""
    try:
        gdf = gpd.read_file(ruta_gpkg)
        if gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        gdf['lon'] = gdf.geometry.x
        gdf['lat'] = gdf.geometry.y
        return pd.DataFrame(gdf.drop(columns='geometry'))
    except Exception as e:
        st.error(f"Error: {e}")
        return None


@st.cache_data
def cargar_poligonos(ruta_gpkg):
    """Carga polígonos de cuarteles."""
    try:
        if not os.path.exists(ruta_gpkg):
            return None
        gdf = gpd.read_file(ruta_gpkg)
        if gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        return gdf
    except Exception as e:
        st.warning(f"No se pudieron cargar polígonos: {e}")
        return None


def obtener_info_superficie(df_puntos, gdf_poligonos, cuarteles_filtrados=None):
    """Obtiene información de superficie de los cuarteles."""
    if gdf_poligonos is None:
        return None
    
    # Filtrar polígonos según cuarteles en los datos
    if cuarteles_filtrados is not None and len(cuarteles_filtrados) > 0:
        gdf_filtrado = gdf_poligonos[gdf_poligonos['Cuartel'].isin(cuarteles_filtrados)]
    else:
        cuarteles_en_datos = df_puntos['Cuartel'].unique() if 'Cuartel' in df_puntos.columns else []
        gdf_filtrado = gdf_poligonos[gdf_poligonos['Cuartel'].isin(cuarteles_en_datos)]
    
    if len(gdf_filtrado) == 0:
        return None
    
    # Calcular totales
    superficie_total = gdf_filtrado['Superficie_ha'].sum()
    n_arboles = len(df_puntos)
    arboles_por_ha = n_arboles / superficie_total if superficie_total > 0 else 0
    
    return {
        'superficie_total': superficie_total,
        'n_arboles': n_arboles,
        'arboles_por_ha': arboles_por_ha,
        'n_cuarteles': len(gdf_filtrado),
        'gdf': gdf_filtrado
    }


def asignar_color_hex(clase):
    """Asigna color según clase."""
    clase_str = str(clase).lower()
    if 'muy bajo' in clase_str:
        return COLORES_CLASE['Muy bajo']
    elif 'bajo' in clase_str and 'muy' not in clase_str and 'medio' not in clase_str:
        return COLORES_CLASE['Bajo']
    elif 'medio-alto' in clase_str or 'medio alto' in clase_str:
        return COLORES_CLASE['Medio-alto']
    elif 'medio' in clase_str:
        return COLORES_CLASE['Medio']
    elif 'alto' in clase_str:
        return COLORES_CLASE['Alto']
    return COLORES_CLASE['Sin dato']


def mostrar_descripcion_indice(indice):
    """Muestra la descripción del índice seleccionado."""
    if indice in INDICES_INFO:
        info = INDICES_INFO[indice]
        st.markdown(f"""
        <div class="indice-description">
            <strong>📊 {info['nombre_completo']} ({indice.upper()})</strong> | <em>{info['categoria']}</em><br>
            {info['descripcion']}<br>
            <small>Rango típico: {info['rango']}</small>
        </div>
        """, unsafe_allow_html=True)


def generar_analisis_automatico(df, indice, fechas_sel='Todas'):
    """Genera un análisis exploratorio automático basado en los datos usando componentes Streamlit."""
    
    if indice not in df.columns:
        return None
    
    col_clase = f"{indice}_clase"
    info_indice = INDICES_INFO.get(indice, {})
    nombre_indice = info_indice.get('nombre', indice.upper())
    categoria = info_indice.get('categoria', 'Vegetación')
    
    # Estadísticas básicas
    media = df[indice].mean()
    std = df[indice].std()
    mediana = df[indice].median()
    n_total = len(df)
    
    # Distribución por clases
    if col_clase in df.columns:
        n_muy_bajo = sum(1 for x in df[col_clase] if 'muy bajo' in str(x).lower())
        n_bajo = sum(1 for x in df[col_clase] if 'bajo' in str(x).lower() and 'muy' not in str(x).lower())
        n_medio = sum(1 for x in df[col_clase] if 'medio' in str(x).lower() and 'alto' not in str(x).lower())
        n_medio_alto = sum(1 for x in df[col_clase] if 'medio-alto' in str(x).lower() or 'medio alto' in str(x).lower())
        n_alto = sum(1 for x in df[col_clase] if 'alto' in str(x).lower() and 'medio' not in str(x).lower())
        
        pct_sanos = ((n_alto + n_medio_alto) / n_total * 100) if n_total > 0 else 0
        pct_problematicos = ((n_muy_bajo + n_bajo) / n_total * 100) if n_total > 0 else 0
    else:
        pct_sanos = 0
        pct_problematicos = 0
        n_muy_bajo = n_bajo = n_medio = n_medio_alto = n_alto = 0
    
    # Análisis por cuartel
    cuarteles_problematicos = []
    if 'Cuartel' in df.columns:
        cuartel_stats = df.groupby('Cuartel')[indice].agg(['mean', 'count']).round(3)
        media_general = df[indice].mean()
        
        for cuartel, row in cuartel_stats.iterrows():
            if row['mean'] < media_general - std:
                cuarteles_problematicos.append({
                    'nombre': cuartel,
                    'media': row['mean'],
                    'n': int(row['count']),
                    'diferencia': round((row['mean'] - media_general) / media_general * 100, 1)
                })
    
    # Determinar estado general
    if pct_sanos >= 80:
        estado_general = "EXCELENTE"
        color_estado = "green"
    elif pct_sanos >= 60:
        estado_general = "BUENO"
        color_estado = "green"
    elif pct_sanos >= 40:
        estado_general = "MODERADO"
        color_estado = "orange"
    elif pct_sanos >= 20:
        estado_general = "BAJO"
        color_estado = "orange"
    else:
        estado_general = "CRÍTICO"
        color_estado = "red"
    
    # Mostrar análisis usando componentes Streamlit
    st.markdown(f"### 📋 Análisis Automático - {nombre_indice}")
    
    st.markdown(f"**Estado General:** :{color_estado}[**{estado_general}**]")
    
    st.markdown(f"""
    El índice **{nombre_indice}** presenta un valor promedio de **{media:.3f}** 
    (mediana: {mediana:.3f}, desv. est.: {std:.3f}). 
    Esto indica un estado de {categoria.lower()} **{estado_general.lower()}** en el cultivo analizado.
    """)
    
    # Distribución
    st.markdown("#### 📊 Distribución del Cultivo:")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("✅ Sanos (Alto + Medio-Alto)", f"{pct_sanos:.1f}%", f"{n_alto + n_medio_alto:,} árboles")
    with col2:
        st.metric("⚠️ Monitorear (Medio)", f"{n_medio/n_total*100:.1f}%", f"{n_medio:,} árboles")
    with col3:
        st.metric("🚨 Problemáticos (Bajo + Muy Bajo)", f"{pct_problematicos:.1f}%", f"{n_muy_bajo + n_bajo:,} árboles")
    
    # Alertas
    if n_muy_bajo > 0:
        st.error(f"🚨 **Atención Prioritaria:** Se detectaron **{n_muy_bajo:,} árboles** en categoría **Muy Bajo** que requieren **intervención inmediata** ({n_muy_bajo/n_total*100:.2f}% del total).")
    
    # Cuarteles problemáticos
    if cuarteles_problematicos:
        st.warning("📍 **Cuarteles con Bajo Desempeño:**")
        for c in sorted(cuarteles_problematicos, key=lambda x: x['media'])[:5]:
            st.markdown(f"- **{c['nombre']}**: media {c['media']:.3f} ({c['diferencia']:+.1f}% vs promedio) - {c['n']:,} árboles")
    
    # Recomendaciones
    recomendaciones = []
    
    if 'clorofila' in categoria.lower() or indice in ['lci', 'ndre', 'cirededge']:
        if pct_problematicos > 10:
            recomendaciones.append("Evaluar programa de fertilización nitrogenada en áreas afectadas")
            recomendaciones.append("Realizar análisis foliar para confirmar deficiencias nutricionales")
        if n_muy_bajo > 0:
            recomendaciones.append("Aplicación urgente de fertilizante foliar en árboles críticos")
    
    if 'vigor' in categoria.lower() or indice in ['ndvi', 'osavi', 'gndvi', 'savi']:
        if pct_problematicos > 10:
            recomendaciones.append("Revisar sistema de riego en zonas con bajo vigor")
            recomendaciones.append("Evaluar presencia de plagas o enfermedades")
        if n_muy_bajo > 0:
            recomendaciones.append("Inspección de campo urgente en árboles con vigor muy bajo")
    
    if pct_sanos < 60:
        recomendaciones.append("Programar vuelo de seguimiento en 2-3 semanas para evaluar evolución")
    
    if recomendaciones:
        st.info("💡 **Recomendaciones:**")
        for rec in recomendaciones:
            st.markdown(f"- {rec}")
    
    return True  # Indica que ya se mostró


def generar_analisis_comparativo(df, indice, fecha1, fecha2):
    """Genera análisis comparativo entre dos vuelos usando componentes Streamlit."""
    
    if indice not in df.columns or 'fecha_vuelo' not in df.columns:
        return None
    
    col_clase = f"{indice}_clase"
    nombre_indice = INDICES_INFO.get(indice, {}).get('nombre', indice.upper())
    
    df1 = df[df['fecha_vuelo'].astype(str) == str(fecha1)]
    df2 = df[df['fecha_vuelo'].astype(str) == str(fecha2)]
    
    if len(df1) == 0 or len(df2) == 0:
        return None
    
    media1 = df1[indice].mean()
    media2 = df2[indice].mean()
    cambio = media2 - media1
    cambio_pct = (cambio / media1 * 100) if media1 != 0 else 0
    
    # Calcular % sanos en cada vuelo
    def calc_pct_sanos(df_temp):
        if col_clase not in df_temp.columns:
            return 0
        n_sanos = sum(1 for x in df_temp[col_clase] if 'alto' in str(x).lower() and 'bajo' not in str(x).lower())
        return (n_sanos / len(df_temp) * 100) if len(df_temp) > 0 else 0
    
    pct_sanos1 = calc_pct_sanos(df1)
    pct_sanos2 = calc_pct_sanos(df2)
    cambio_sanos = pct_sanos2 - pct_sanos1
    
    # Determinar tendencia
    if cambio_pct > 5:
        tendencia = "MEJORA SIGNIFICATIVA"
        emoji = "📈"
        color = "green"
    elif cambio_pct > 1:
        tendencia = "LEVE MEJORA"
        emoji = "📈"
        color = "green"
    elif cambio_pct > -1:
        tendencia = "ESTABLE"
        emoji = "➡️"
        color = "gray"
    elif cambio_pct > -5:
        tendencia = "LEVE DETERIORO"
        emoji = "📉"
        color = "orange"
    else:
        tendencia = "DETERIORO SIGNIFICATIVO"
        emoji = "📉"
        color = "red"
    
    # Mostrar usando componentes Streamlit
    st.markdown(f"### {emoji} Análisis Comparativo - {nombre_indice}")
    
    st.markdown(f"**Tendencia:** :{color}[**{tendencia}**]")
    
    # Tabla comparativa usando dataframe
    tabla_comp = pd.DataFrame({
        'Métrica': [f'{nombre_indice} Promedio', '% Árboles Sanos'],
        str(fecha1): [f"{media1:.3f}", f"{pct_sanos1:.1f}%"],
        str(fecha2): [f"{media2:.3f}", f"{pct_sanos2:.1f}%"],
        'Cambio': [f"{cambio:+.3f} ({cambio_pct:+.1f}%)", f"{cambio_sanos:+.1f}%"]
    })
    
    st.dataframe(tabla_comp, use_container_width=True, hide_index=True)
    
    # Interpretación
    if cambio_pct > 5:
        st.success(f"✅ **Interpretación:** El cultivo muestra una **mejora significativa** entre los vuelos. El incremento de {cambio_pct:.1f}% en {nombre_indice} sugiere que las condiciones han mejorado, posiblemente debido a mejoras en riego, fertilización o condiciones climáticas favorables.")
    elif cambio_pct > 1:
        st.success(f"✅ **Interpretación:** El cultivo muestra una **leve mejora** entre los vuelos. El incremento de {cambio_pct:.1f}% en {nombre_indice} indica una tendencia positiva.")
    elif cambio_pct < -5:
        st.error(f"⚠️ **Interpretación:** Se observa un **deterioro significativo** entre los vuelos. La disminución de {abs(cambio_pct):.1f}% en {nombre_indice} requiere atención. Se recomienda investigar posibles causas: estrés hídrico, problemas fitosanitarios, o deficiencias nutricionales.")
    elif cambio_pct < -1:
        st.warning(f"⚠️ **Interpretación:** Se observa un **leve deterioro** entre los vuelos. La disminución de {abs(cambio_pct):.1f}% en {nombre_indice} debe monitorearse.")
    else:
        st.info(f"ℹ️ **Interpretación:** El cultivo se mantiene **relativamente estable** entre los vuelos, con una variación de {cambio_pct:+.1f}% en {nombre_indice}. Continuar con el monitoreo regular.")
    
    return True  # Indica que ya se mostró


# =============================================================================
# COMPONENTES DE MAPA - PLOTLY MAPBOX
# =============================================================================

def crear_mapa_plotly(df, indice, radio_puntos=3, titulo="", gdf_poligonos=None):
    """Crea mapa con Plotly Mapbox (más estable que Folium)."""
    col_clase = f"{indice}_clase"
    if col_clase not in df.columns or len(df) == 0:
        return None
    
    # Preparar datos con colores
    df_plot = df.copy()
    df_plot['color'] = df_plot[col_clase].apply(asignar_color_hex)
    df_plot['indice_valor'] = df_plot[indice].round(3)
    
    # Manejar altura_m que puede no existir
    if 'altura_m' in df_plot.columns:
        df_plot['altura_str'] = df_plot['altura_m'].apply(lambda x: f"{x:.2f} m" if pd.notna(x) else "N/A")
    else:
        df_plot['altura_str'] = "N/A"
    
    # Texto para hover
    df_plot['hover_text'] = df_plot.apply(
        lambda row: f"<b>ID:</b> {row.get('id', 'N/A')}<br>" +
                    f"<b>Cuartel:</b> {row.get('Cuartel', 'N/A')}<br>" +
                    f"<b>Variedad:</b> {row.get('Variedad', 'N/A')}<br>" +
                    f"<b>{indice.upper()}:</b> {row['indice_valor']}<br>" +
                    f"<b>Clase:</b> {row.get(col_clase, 'N/A')}<br>" +
                    f"<b>Altura:</b> {row['altura_str']}",
        axis=1
    )
    
    # Crear figura base con scattermapbox
    fig = go.Figure()
    
    # Agregar polígonos de cuarteles primero (para que queden debajo)
    if gdf_poligonos is not None and len(gdf_poligonos) > 0:
        cuarteles_en_datos = df['Cuartel'].unique() if 'Cuartel' in df.columns else []
        gdf_filtrado = gdf_poligonos[gdf_poligonos['Cuartel'].isin(cuarteles_en_datos)]
        
        if len(gdf_filtrado) > 0:
            stats_cuartel = df.groupby('Cuartel')[indice].mean().to_dict()
            
            for _, row in gdf_filtrado.iterrows():
                cuartel_nombre = row['Cuartel']
                media_indice = stats_cuartel.get(cuartel_nombre, 0)
                
                # Extraer coordenadas del polígono
                geom = row.geometry
                if geom.geom_type == 'Polygon':
                    coords = list(geom.exterior.coords)
                elif geom.geom_type == 'MultiPolygon':
                    coords = list(geom.geoms[0].exterior.coords)
                else:
                    continue
                
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                
                # Hover text para polígono
                hover_poligono = (f"<b>{cuartel_nombre}</b><br>"
                                 f"Especie: {row.get('Especie', 'N/A')}<br>"
                                 f"Variedad: {row.get('Variedad', 'N/A')}<br>"
                                 f"Superficie: {row.get('Superficie_ha', 0):.2f} ha<br>"
                                 f"{indice.upper()} μ: {media_indice:.3f}")
                
                # Agregar polígono como línea cerrada
                fig.add_trace(go.Scattermapbox(
                    lon=lons,
                    lat=lats,
                    mode='lines',
                    line=dict(width=2, color='#0a12df'),
                    fill='none',
                    name=cuartel_nombre,
                    hoverinfo='text',
                    hovertext=hover_poligono,
                    showlegend=False
                ))
    
    # Agrupar puntos por clase para la leyenda
    def clasificar_punto(clase_str):
        clase_lower = str(clase_str).lower()
        if 'muy bajo' in clase_lower:
            return 'Muy bajo'
        elif 'medio-alto' in clase_lower or 'medio alto' in clase_lower:
            return 'Medio-alto'
        elif 'medio' in clase_lower:
            return 'Medio'
        elif 'bajo' in clase_lower:
            return 'Bajo'
        elif 'alto' in clase_lower:
            return 'Alto'
        return 'Sin dato'
    
    df_plot['clase_simple'] = df_plot[col_clase].apply(clasificar_punto)
    
    clases_orden = ['Muy bajo', 'Bajo', 'Medio', 'Medio-alto', 'Alto']
    
    for clase in clases_orden:
        df_clase = df_plot[df_plot['clase_simple'] == clase]
        if len(df_clase) == 0:
            continue
        
        color = COLORES_CLASE.get(clase, '#969696')
        
        fig.add_trace(go.Scattermapbox(
            lon=df_clase['lon'],
            lat=df_clase['lat'],
            mode='markers',
            marker=dict(
                size=radio_puntos * 3,
                color=color,
                opacity=0.8
            ),
            name=clase,
            hoverinfo='text',
            hovertext=df_clase['hover_text'],
            showlegend=True
        ))
    
    # Calcular centro y zoom
    center_lat = df['lat'].mean()
    center_lon = df['lon'].mean()
    
    # Calcular zoom basado en el rango de datos
    lat_range = df['lat'].max() - df['lat'].min()
    lon_range = df['lon'].max() - df['lon'].min()
    max_range = max(lat_range, lon_range)
    
    # Agregar margen para ver el polígono completo (15% extra)
    max_range = max_range * 1.15
    
    # Zoom ajustado para ver polígono completo
    if max_range < 0.003:
        zoom = 17
    elif max_range < 0.006:
        zoom = 16
    elif max_range < 0.01:
        zoom = 15
    elif max_range < 0.02:
        zoom = 14
    elif max_range < 0.05:
        zoom = 13
    elif max_range < 0.1:
        zoom = 12
    else:
        zoom = 11
    
    # Configurar layout del mapa
    fig.update_layout(
        mapbox=dict(
            style="carto-positron",  # Estilo gratuito sin token
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=500,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.8)",
            font=dict(size=10)
        ),
        hoverlabel=dict(
            bgcolor="white",
            font_size=11,
            font_family="Arial"
        )
    )
    
    return fig


def crear_mapa_plotly_satelite(df, indice, radio_puntos=3, titulo="", gdf_poligonos=None):
    """Crea mapa con Plotly usando tiles satelitales de Google."""
    col_clase = f"{indice}_clase"
    if col_clase not in df.columns or len(df) == 0:
        return None
    
    # Preparar datos con colores
    df_plot = df.copy()
    df_plot['color'] = df_plot[col_clase].apply(asignar_color_hex)
    df_plot['indice_valor'] = df_plot[indice].round(3)
    
    # Manejar altura_m que puede no existir
    if 'altura_m' in df_plot.columns:
        df_plot['altura_str'] = df_plot['altura_m'].apply(lambda x: f"{x:.2f} m" if pd.notna(x) else "N/A")
    else:
        df_plot['altura_str'] = "N/A"
    
    # Texto para hover
    df_plot['hover_text'] = df_plot.apply(
        lambda row: f"<b>ID:</b> {row.get('id', 'N/A')}<br>" +
                    f"<b>Cuartel:</b> {row.get('Cuartel', 'N/A')}<br>" +
                    f"<b>Variedad:</b> {row.get('Variedad', 'N/A')}<br>" +
                    f"<b>{indice.upper()}:</b> {row['indice_valor']}<br>" +
                    f"<b>Clase:</b> {row.get(col_clase, 'N/A')}<br>" +
                    f"<b>Altura:</b> {row['altura_str']}",
        axis=1
    )
    
    # Crear figura base
    fig = go.Figure()
    
    # Agregar polígonos de cuarteles primero
    if gdf_poligonos is not None and len(gdf_poligonos) > 0:
        cuarteles_en_datos = df['Cuartel'].unique() if 'Cuartel' in df.columns else []
        gdf_filtrado = gdf_poligonos[gdf_poligonos['Cuartel'].isin(cuarteles_en_datos)]
        
        if len(gdf_filtrado) > 0:
            stats_cuartel = df.groupby('Cuartel')[indice].mean().to_dict()
            
            for _, row in gdf_filtrado.iterrows():
                cuartel_nombre = row['Cuartel']
                media_indice = stats_cuartel.get(cuartel_nombre, 0)
                
                geom = row.geometry
                if geom.geom_type == 'Polygon':
                    coords = list(geom.exterior.coords)
                elif geom.geom_type == 'MultiPolygon':
                    coords = list(geom.geoms[0].exterior.coords)
                else:
                    continue
                
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                
                hover_poligono = (f"<b>{cuartel_nombre}</b><br>"
                                 f"Especie: {row.get('Especie', 'N/A')}<br>"
                                 f"Variedad: {row.get('Variedad', 'N/A')}<br>"
                                 f"Superficie: {row.get('Superficie_ha', 0):.2f} ha<br>"
                                 f"{indice.upper()} μ: {media_indice:.3f}")
                
                fig.add_trace(go.Scattermapbox(
                    lon=lons,
                    lat=lats,
                    mode='lines',
                    line=dict(width=3, color='#00BFFF'),
                    fill='none',
                    name=cuartel_nombre,
                    hoverinfo='text',
                    hovertext=hover_poligono,
                    showlegend=False
                ))
    
    # Agrupar puntos por clase usando la misma lógica que asignar_color_hex
    def clasificar_punto(clase_str):
        clase_lower = str(clase_str).lower()
        if 'muy bajo' in clase_lower:
            return 'Muy bajo'
        elif 'medio-alto' in clase_lower or 'medio alto' in clase_lower:
            return 'Medio-alto'
        elif 'medio' in clase_lower:
            return 'Medio'
        elif 'bajo' in clase_lower:
            return 'Bajo'
        elif 'alto' in clase_lower:
            return 'Alto'
        return 'Sin dato'
    
    df_plot['clase_simple'] = df_plot[col_clase].apply(clasificar_punto)
    
    clases_orden = ['Muy bajo', 'Bajo', 'Medio', 'Medio-alto', 'Alto']
    
    for clase in clases_orden:
        df_clase = df_plot[df_plot['clase_simple'] == clase]
        if len(df_clase) == 0:
            continue
        
        color = COLORES_CLASE.get(clase, '#969696')
        
        fig.add_trace(go.Scattermapbox(
            lon=df_clase['lon'],
            lat=df_clase['lat'],
            mode='markers',
            marker=dict(
                size=radio_puntos * 3,
                color=color,
                opacity=0.85
            ),
            name=clase,
            hoverinfo='text',
            hovertext=df_clase['hover_text'],
            showlegend=True
        ))
    
    center_lat = df['lat'].mean()
    center_lon = df['lon'].mean()
    
    lat_range = df['lat'].max() - df['lat'].min()
    lon_range = df['lon'].max() - df['lon'].min()
    max_range = max(lat_range, lon_range)
    
    # Agregar margen para ver el polígono completo (15% extra)
    max_range = max_range * 1.15
    
    # Zoom ajustado para ver polígono completo
    if max_range < 0.003:
        zoom = 17
    elif max_range < 0.006:
        zoom = 16
    elif max_range < 0.01:
        zoom = 15
    elif max_range < 0.02:
        zoom = 14
    elif max_range < 0.05:
        zoom = 13
    elif max_range < 0.1:
        zoom = 12
    else:
        zoom = 11
    
    # Usar estilo white-bg con capa satelital de Google
    fig.update_layout(
        mapbox=dict(
            style="white-bg",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom,
            layers=[{
                "below": "traces",
                "sourcetype": "raster",
                "sourceattribution": "Google",
                "source": [
                    "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
                ]
            }]
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=500,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.9)",
            font=dict(size=10)
        ),
        hoverlabel=dict(
            bgcolor="white",
            font_size=11,
            font_family="Arial"
        )
    )
    
    return fig


# =============================================================================
# COMPONENTES DE GRÁFICOS
# =============================================================================

def crear_grafico_distribucion(df, indice, titulo=""):
    """Gráfico de distribución por clase."""
    col_clase = f"{indice}_clase"
    if col_clase not in df.columns:
        return None
    
    conteo = df[col_clase].value_counts().reset_index()
    conteo.columns = ['Clase', 'Cantidad']
    conteo['Porcentaje'] = (conteo['Cantidad'] / conteo['Cantidad'].sum() * 100).round(1)
    
    # Orden correcto
    orden_clases = ['muy bajo', 'bajo', 'medio', 'medio-alto', 'alto']
    
    def obtener_orden(clase):
        clase_lower = str(clase).lower()
        for i, o in enumerate(orden_clases):
            if o in clase_lower:
                if o == 'medio' and 'alto' in clase_lower:
                    continue
                return i
        return 99
    
    conteo['orden'] = conteo['Clase'].apply(obtener_orden)
    conteo = conteo.sort_values('orden')
    conteo['Color'] = conteo['Clase'].apply(asignar_color_hex)
    
    def etiqueta_corta(clase):
        clase_lower = str(clase).lower()
        if 'muy bajo' in clase_lower:
            return 'Muy Bajo'
        elif 'medio-alto' in clase_lower or 'medio alto' in clase_lower:
            return 'Medio-Alto'
        elif 'bajo' in clase_lower:
            return 'Bajo'
        elif 'medio' in clase_lower:
            return 'Medio'
        elif 'alto' in clase_lower:
            return 'Alto'
        return str(clase)[:15]
    
    conteo['Etiqueta'] = conteo['Clase'].apply(etiqueta_corta)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=conteo['Etiqueta'], 
        y=conteo['Cantidad'],
        marker_color=conteo['Color'],
        text=conteo['Porcentaje'].apply(lambda x: f"{x}%"),
        textposition='outside',
        textfont=dict(size=11)
    ))
    
    y_max = conteo['Cantidad'].max() * 1.20
    
    fig.update_layout(
        title=dict(text=titulo or f"Distribución {indice.upper()}", font=dict(size=14)),
        xaxis_title="",
        yaxis_title="N° Árboles",
        yaxis=dict(range=[0, y_max]),
        showlegend=False,
        height=350,
        margin=dict(l=50, r=30, t=50, b=60),
        xaxis_tickangle=0
    )
    return fig


def crear_histograma(df, indice, titulo=""):
    """Histograma de valores."""
    if indice not in df.columns:
        return None
    
    fig = px.histogram(df, x=indice, nbins=40, color_discrete_sequence=['#1a9641'])
    media = df[indice].mean()
    fig.add_vline(x=media, line_dash="dash", line_color="red", annotation_text=f"μ={media:.3f}")
    fig.update_layout(title=titulo or f"Histograma {indice.upper()}", height=300, margin=dict(l=40, r=40, t=40, b=40))
    return fig


def crear_boxplot(df, indice, titulo=""):
    """Boxplot."""
    if indice not in df.columns or 'Cuartel' not in df.columns:
        return None
    
    fig = px.box(df, x='Cuartel', y=indice, color='Cuartel')
    fig.update_layout(title=titulo or f"Boxplot {indice.upper()}", height=300, showlegend=False, margin=dict(l=40, r=40, t=40, b=40))
    return fig


# =============================================================================
# FUNCIONES DE TABS
# =============================================================================

def mostrar_kpis(df, indice, prefix="", info_superficie=None):
    """Muestra KPIs incluyendo superficie si está disponible."""
    
    # Usar 2 filas para mejor visualización
    if info_superficie:
        # Primera fila: métricas principales
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(f"{prefix}🌳 Árboles", f"{len(df):,}")
        with col2:
            st.metric("📐 Superficie", f"{info_superficie['superficie_total']:.1f} ha")
        with col3:
            st.metric("🌿 Densidad", f"{info_superficie['arboles_por_ha']:,.0f} árb/ha")
        with col4:
            if 'Cuartel' in df.columns:
                st.metric("📍 Cuarteles", df['Cuartel'].nunique())
        
        # Segunda fila: métricas del índice
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if indice in df.columns:
                st.metric(f"📊 {indice.upper()} μ", f"{df[indice].mean():.3f}")
        with col2:
            col_clase = f"{indice}_clase"
            if col_clase in df.columns:
                pct = (df[col_clase].apply(lambda x: 'alto' in str(x).lower() and 'bajo' not in str(x).lower()).sum() / len(df) * 100)
                st.metric("✅ % Sanos", f"{pct:.1f}%")
        with col3:
            if 'altura_m' in df.columns and df['altura_m'].notna().any():
                st.metric("📏 Altura μ", f"{df['altura_m'].mean():.2f} m")
        with col4:
            if indice in df.columns:
                st.metric(f"📉 {indice.upper()} σ", f"{df[indice].std():.3f}")
    else:
        # Sin superficie - una sola fila
        cols = st.columns(5)
        with cols[0]:
            st.metric(f"{prefix}🌳 Árboles", f"{len(df):,}")
        with cols[1]:
            if indice in df.columns:
                st.metric(f"📊 {indice.upper()} μ", f"{df[indice].mean():.3f}")
        with cols[2]:
            col_clase = f"{indice}_clase"
            if col_clase in df.columns:
                pct = (df[col_clase].apply(lambda x: 'alto' in str(x).lower() and 'bajo' not in str(x).lower()).sum() / len(df) * 100)
                st.metric("✅ % Sanos", f"{pct:.1f}%")
        with cols[3]:
            if 'altura_m' in df.columns and df['altura_m'].notna().any():
                st.metric("📏 Altura μ", f"{df['altura_m'].mean():.2f} m")
        with cols[4]:
            if 'Cuartel' in df.columns:
                st.metric("📍 Cuarteles", df['Cuartel'].nunique())


def tab_resumen(df, indice, fechas_sel, radio_puntos, gdf_poligonos=None):
    """Tab Resumen con comparación lado a lado."""
    
    # Mostrar descripción del índice
    mostrar_descripcion_indice(indice)
    
    fechas_unicas = []
    if 'fecha_vuelo' in df.columns:
        fechas_unicas = sorted([str(f) for f in df['fecha_vuelo'].dropna().unique()])
    
    mostrar_comparacion = len(fechas_unicas) >= 2 and fechas_sel == 'Todas'
    
    # Obtener info de superficie
    info_sup = obtener_info_superficie(df, gdf_poligonos)
    
    if mostrar_comparacion:
        st.subheader("📊 Comparación de Vuelos")
        
        fecha1, fecha2 = fechas_unicas[0], fechas_unicas[1]
        df1 = df[df['fecha_vuelo'].astype(str) == fecha1]
        df2 = df[df['fecha_vuelo'].astype(str) == fecha2]
        
        # Info superficie para cada vuelo
        info_sup1 = obtener_info_superficie(df1, gdf_poligonos)
        info_sup2 = obtener_info_superficie(df2, gdf_poligonos)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"### 📅 Vuelo: {fecha1}")
            mostrar_kpis(df1, indice, info_superficie=info_sup1)
        with col2:
            st.markdown(f"### 📅 Vuelo: {fecha2}")
            mostrar_kpis(df2, indice, info_superficie=info_sup2)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**🗺️ Mapa - {fecha1}**")
            # Mostrar todos si hay menos de 10000, sino sampling a 8000
            df1_sample = df1.sample(n=min(8000, len(df1)), random_state=42) if len(df1) > 10000 else df1
            mapa1 = crear_mapa_plotly_satelite(df1_sample, indice, radio_puntos, f"{indice.upper()} - {fecha1}", gdf_poligonos)
            if mapa1:
                st.plotly_chart(mapa1, use_container_width=True, key="mapa1")
        
        with col2:
            st.markdown(f"**🗺️ Mapa - {fecha2}**")
            # Mostrar todos si hay menos de 10000, sino sampling a 8000
            df2_sample = df2.sample(n=min(8000, len(df2)), random_state=42) if len(df2) > 10000 else df2
            mapa2 = crear_mapa_plotly_satelite(df2_sample, indice, radio_puntos, f"{indice.upper()} - {fecha2}", gdf_poligonos)
            if mapa2:
                st.plotly_chart(mapa2, use_container_width=True, key="mapa2")
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        with col1:
            fig1 = crear_grafico_distribucion(df1, indice, f"Distribución - {fecha1}")
            if fig1:
                st.plotly_chart(fig1, use_container_width=True)
        with col2:
            fig2 = crear_grafico_distribucion(df2, indice, f"Distribución - {fecha2}")
            if fig2:
                st.plotly_chart(fig2, use_container_width=True)
    
    else:
        mostrar_kpis(df, indice, info_superficie=info_sup)
        st.markdown("---")
        
        cols = st.columns(4)
        campos = [('Especie', '🌿'), ('Variedad', '🍒'), ('Plantacion', '📅'), ('Patron', '🌱')]
        for i, (campo, emoji) in enumerate(campos):
            with cols[i]:
                if campo in df.columns:
                    valores = ', '.join(map(str, df[campo].dropna().unique()))
                    st.markdown(f"**{emoji} {campo}:** {valores}")
        
        st.markdown("---")
        
        # Análisis automático (ahora muestra directamente)
        generar_analisis_automatico(df, indice, fechas_sel)
        
        st.markdown("---")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.subheader(f"🗺️ Mapa - {indice.upper()}")
            st.caption("💡 Pasa el mouse sobre los puntos o polígonos para ver info")
            
            # Mostrar todos si hay menos de 12000, sino sampling a 10000
            df_mapa = df.sample(n=min(10000, len(df)), random_state=42) if len(df) > 12000 else df
            mapa = crear_mapa_plotly_satelite(df_mapa, indice, radio_puntos, gdf_poligonos=gdf_poligonos)
            if mapa:
                st.plotly_chart(mapa, use_container_width=True, key="mapa_single")
        
        with col2:
            st.subheader("📊 Distribución")
            fig = crear_grafico_distribucion(df, indice)
            if fig:
                fig.update_layout(height=550)
                st.plotly_chart(fig, use_container_width=True)
    
    # Tabla resumen por cuartel con superficie
    if info_sup and gdf_poligonos is not None:
        st.markdown("---")
        st.subheader("📋 Resumen por Cuartel")
        
        # Verificar si hay múltiples vuelos
        fechas_en_datos = []
        if 'fecha_vuelo' in df.columns:
            fechas_en_datos = sorted([str(f) for f in df['fecha_vuelo'].dropna().unique()])
        
        hay_multiples_vuelos = len(fechas_en_datos) >= 2
        
        # Crear tabla solo con cuarteles que tienen datos en el dataframe filtrado
        resumen_list = []
        
        if hay_multiples_vuelos:
            # Mostrar tabla con ambos vuelos para comparar
            for cuartel in df['Cuartel'].dropna().unique():
                for fecha in fechas_en_datos:
                    df_cuartel = df[(df['Cuartel'] == cuartel) & (df['fecha_vuelo'].astype(str) == fecha)]
                    
                    if len(df_cuartel) == 0:
                        continue
                    
                    especie_datos = df_cuartel['Especie'].iloc[0] if 'Especie' in df_cuartel.columns else 'N/A'
                    variedad_datos = df_cuartel['Variedad'].iloc[0] if 'Variedad' in df_cuartel.columns else 'N/A'
                    
                    poligono_info = gdf_poligonos[gdf_poligonos['Cuartel'] == cuartel]
                    sup_ha = poligono_info.iloc[0].get('Superficie_ha', 0) if len(poligono_info) > 0 else 0
                    
                    n_arboles = len(df_cuartel)
                    
                    col_clase = f"{indice}_clase"
                    pct_sanos = 0
                    if col_clase in df_cuartel.columns:
                        pct_sanos = (df_cuartel[col_clase].apply(
                            lambda x: 'alto' in str(x).lower() and 'bajo' not in str(x).lower()
                        ).sum() / len(df_cuartel) * 100)
                    
                    resumen_list.append({
                        'Vuelo': fecha,
                        'Cuartel': cuartel,
                        'Especie': especie_datos,
                        'Variedad': variedad_datos,
                        'Sup. (ha)': round(sup_ha, 1) if sup_ha > 0 else None,
                        'N° Árboles': n_arboles,
                        'Árb/ha': int(round(n_arboles / sup_ha, 0)) if sup_ha > 0 else None,
                        f'{indice.upper()} μ': round(df_cuartel[indice].mean(), 3),
                        '% Sanos': round(pct_sanos, 1)
                    })
        else:
            # Tabla simple sin columna de vuelo
            for cuartel in df['Cuartel'].dropna().unique():
                df_cuartel = df[df['Cuartel'] == cuartel]
                
                if len(df_cuartel) == 0:
                    continue
                
                especie_datos = df_cuartel['Especie'].iloc[0] if 'Especie' in df_cuartel.columns else 'N/A'
                variedad_datos = df_cuartel['Variedad'].iloc[0] if 'Variedad' in df_cuartel.columns else 'N/A'
                
                poligono_info = gdf_poligonos[gdf_poligonos['Cuartel'] == cuartel]
                
                if len(poligono_info) > 0:
                    row = poligono_info.iloc[0]
                    sup_ha = row.get('Superficie_ha', 0)
                    año_pol = row.get('Apla', 'N/A')
                else:
                    sup_ha = 0
                    año_pol = 'N/A'
                
                n_arboles = len(df_cuartel)
                
                col_clase = f"{indice}_clase"
                pct_sanos = 0
                if col_clase in df_cuartel.columns:
                    pct_sanos = (df_cuartel[col_clase].apply(
                        lambda x: 'alto' in str(x).lower() and 'bajo' not in str(x).lower()
                    ).sum() / len(df_cuartel) * 100)
                
                resumen_list.append({
                    'Cuartel': cuartel,
                    'Especie': especie_datos,
                    'Variedad': variedad_datos,
                    'Año': año_pol,
                    'Sup. (ha)': round(sup_ha, 1) if sup_ha > 0 else None,
                    'N° Árboles': n_arboles,
                    'Árb/ha': int(round(n_arboles / sup_ha, 0)) if sup_ha > 0 else None,
                    f'{indice.upper()} μ': round(df_cuartel[indice].mean(), 3),
                    '% Sanos': round(pct_sanos, 1)
                })
        
        if resumen_list:
            df_resumen = pd.DataFrame(resumen_list)
            if hay_multiples_vuelos:
                df_resumen = df_resumen.sort_values(['Cuartel', 'Vuelo'])
            else:
                df_resumen = df_resumen.sort_values('Cuartel')
            
            st.dataframe(
                df_resumen.style.format({
                    'Sup. (ha)': lambda x: '-' if pd.isna(x) else f'{x:.1f}',
                    'N° Árboles': lambda x: f'{x:,.0f}'.replace(',', '.'),
                    'Árb/ha': lambda x: '-' if pd.isna(x) else f'{x:,.0f}'.replace(',', '.'),
                    f'{indice.upper()} μ': '{:.3f}',
                    '% Sanos': '{:.1f}'
                }),
                use_container_width=True,
                hide_index=True
            )
    
    # Análisis comparativo al final (después de todo lo visual)
    if mostrar_comparacion:
        fecha1, fecha2 = fechas_unicas[0], fechas_unicas[1]
        st.markdown("---")
        generar_analisis_comparativo(df, indice, fecha1, fecha2)


def tab_analisis(df, indice, fechas_sel):
    """Tab Análisis."""
    
    mostrar_descripcion_indice(indice)
    
    fechas_unicas = []
    if 'fecha_vuelo' in df.columns:
        fechas_unicas = sorted([str(f) for f in df['fecha_vuelo'].dropna().unique()])
    
    mostrar_comparacion = len(fechas_unicas) >= 2 and fechas_sel == 'Todas'
    
    if mostrar_comparacion:
        fecha1, fecha2 = fechas_unicas[0], fechas_unicas[1]
        df1 = df[df['fecha_vuelo'].astype(str) == fecha1]
        df2 = df[df['fecha_vuelo'].astype(str) == fecha2]
        
        st.subheader("📊 Histogramas")
        col1, col2 = st.columns(2)
        with col1:
            fig1 = crear_histograma(df1, indice, f"Histograma - {fecha1}")
            if fig1:
                st.plotly_chart(fig1, use_container_width=True)
        with col2:
            fig2 = crear_histograma(df2, indice, f"Histograma - {fecha2}")
            if fig2:
                st.plotly_chart(fig2, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("📦 Distribución por Cuartel")
        col1, col2 = st.columns(2)
        with col1:
            fig1 = crear_boxplot(df1, indice, f"Por Cuartel - {fecha1}")
            if fig1:
                st.plotly_chart(fig1, use_container_width=True)
        with col2:
            fig2 = crear_boxplot(df2, indice, f"Por Cuartel - {fecha2}")
            if fig2:
                st.plotly_chart(fig2, use_container_width=True)
        
        st.markdown("---")
        
        st.subheader("📈 Estadísticas Comparativas")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"**{fecha1}**")
            stats1 = df1[indice].describe().round(3)
            st.dataframe(stats1)
        
        with col2:
            st.markdown(f"**{fecha2}**")
            stats2 = df2[indice].describe().round(3)
            st.dataframe(stats2)
    
    else:
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📊 Histograma")
            fig = crear_histograma(df, indice)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        with col2:
            st.subheader("📦 Por Cuartel")
            fig = crear_boxplot(df, indice)
            if fig:
                st.plotly_chart(fig, use_container_width=True)


def tab_comparacion(df, indice):
    """Tab Comparación."""
    
    if 'fecha_vuelo' not in df.columns:
        st.warning("No hay datos de múltiples vuelos")
        return
    
    fechas_unicas = sorted([str(f) for f in df['fecha_vuelo'].dropna().unique()])
    
    if len(fechas_unicas) < 2:
        st.warning("Se necesitan al menos 2 vuelos para comparar")
        return
    
    mostrar_descripcion_indice(indice)
    
    col_clase = f"{indice}_clase"
    
    st.subheader("📊 Comparación de Distribución entre Vuelos")
    
    df_valid = df[df['fecha_vuelo'].notna()].copy()
    pivot = df_valid.groupby(['fecha_vuelo', col_clase]).size().unstack(fill_value=0)
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    
    fig = go.Figure()
    for clase in pivot_pct.columns:
        fig.add_trace(go.Bar(
            name=clase, 
            x=[str(x) for x in pivot_pct.index], 
            y=pivot_pct[clase], 
            marker_color=asignar_color_hex(clase)
        ))
    fig.update_layout(barmode='stack', height=400, xaxis_title="Fecha de Vuelo", yaxis_title="Porcentaje (%)")
    st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("---")
    
    st.subheader("📋 Resumen Detallado por Vuelo y Cuartel")
    
    resumen_list = []
    for fecha in fechas_unicas:
        df_fecha = df[df['fecha_vuelo'].astype(str) == fecha]
        
        for cuartel in df_fecha['Cuartel'].dropna().unique():
            df_cuartel = df_fecha[df_fecha['Cuartel'] == cuartel]
            
            pct_sanos = 0
            if col_clase in df_cuartel.columns:
                pct_sanos = (df_cuartel[col_clase].apply(
                    lambda x: 'alto' in str(x).lower() and 'bajo' not in str(x).lower()
                ).sum() / len(df_cuartel) * 100)
            
            resumen_list.append({
                'Fecha': fecha,
                'Cuartel': cuartel,
                'N° Árboles': len(df_cuartel),
                'Media': round(df_cuartel[indice].mean(), 3),
                'Desv.Est': round(df_cuartel[indice].std(), 3),
                'Mín': round(df_cuartel[indice].min(), 3),
                'Máx': round(df_cuartel[indice].max(), 3),
                '% Sanos': round(pct_sanos, 1)
            })
    
    df_resumen = pd.DataFrame(resumen_list)
    df_resumen = df_resumen.sort_values(['Cuartel', 'Fecha'])
    
    st.dataframe(
        df_resumen.style.format({
            'N° Árboles': lambda x: f'{x:,.0f}'.replace(',', '.'),
            'Media': '{:.3f}',
            'Desv.Est': '{:.3f}',
            'Mín': '{:.3f}',
            'Máx': '{:.3f}',
            '% Sanos': '{:.1f}'
        }),
        use_container_width=True,
        hide_index=True
    )
    
    csv = df_resumen.to_csv(index=False)
    st.download_button("📥 Descargar Comparación CSV", csv, f"comparacion_{indice}_{datetime.now().strftime('%Y%m%d')}.csv", "text/csv")
    
    st.markdown("---")
    
    st.subheader("📈 Diferencias entre Vuelos")
    
    if len(fechas_unicas) >= 2:
        fecha1, fecha2 = fechas_unicas[0], fechas_unicas[1]
        
        df1_grouped = df[df['fecha_vuelo'].astype(str) == fecha1].groupby('Cuartel')[indice].mean()
        df2_grouped = df[df['fecha_vuelo'].astype(str) == fecha2].groupby('Cuartel')[indice].mean()
        
        diff_df = pd.DataFrame({
            'Cuartel': df1_grouped.index,
            f'{fecha1}': df1_grouped.values,
            f'{fecha2}': df2_grouped.reindex(df1_grouped.index).values,
        })
        diff_df['Diferencia'] = diff_df[f'{fecha2}'] - diff_df[f'{fecha1}']
        diff_df['Cambio %'] = ((diff_df['Diferencia'] / diff_df[f'{fecha1}']) * 100).round(1)
        diff_df = diff_df.round(3)
        
        st.dataframe(
            diff_df,
            use_container_width=True,
            hide_index=True
        )


def tab_datos(df, indices_disponibles):
    """Tab Datos."""
    
    st.subheader("🔍 Explorador de Datos")
    
    st.markdown("**Selecciona los índices a incluir:**")
    indices_sel = st.multiselect(
        "Índices",
        indices_disponibles,
        default=[indices_disponibles[0]] if indices_disponibles else [],
        format_func=lambda x: INDICES_INFO.get(x, {}).get('nombre', x.upper())
    )
    
    cols_base = ['id', 'Cuartel', 'Especie', 'Variedad', 'lat', 'lon']
    cols_base = [c for c in cols_base if c in df.columns]
    
    if 'fecha_vuelo' in df.columns:
        cols_base.append('fecha_vuelo')
    
    cols_indices = []
    for idx in indices_sel:
        if idx in df.columns:
            cols_indices.append(idx)
        col_clase = f"{idx}_clase"
        if col_clase in df.columns:
            cols_indices.append(col_clase)
    
    if 'altura_m' in df.columns:
        cols_base.append('altura_m')
    
    columnas = cols_base + cols_indices
    columnas = list(dict.fromkeys(columnas))
    
    st.markdown(f"**Mostrando {len(columnas)} columnas:**")
    
    df_mostrar = df[columnas].copy()
    
    if 'lat' in df_mostrar.columns:
        df_mostrar = df_mostrar.rename(columns={'lat': 'Latitud', 'lon': 'Longitud'})
    
    st.dataframe(df_mostrar, use_container_width=True, height=500)
    
    st.markdown("---")
    
    st.subheader("📥 Descargar Datos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        csv = df_mostrar.to_csv(index=False)
        st.download_button(
            "📥 Descargar datos mostrados (CSV)",
            csv,
            f"datos_{'_'.join(indices_sel)}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )
    
    with col2:
        csv_completo = df.to_csv(index=False)
        st.download_button(
            "📥 Descargar TODOS los datos (CSV)",
            csv_completo,
            f"datos_completos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )
    
    st.info("💡 Las coordenadas (Latitud, Longitud) están en formato WGS84 (EPSG:4326)")


# =============================================================================
# SIDEBAR CON FILTROS EN CASCADA
# =============================================================================

def crear_sidebar(df):
    """Sidebar con filtros en cascada."""
    df_filtrado = df.copy()
    fechas_sel = 'Todas'
    
    with st.sidebar:
        # Logo
        mostrar_logo_sidebar()
        
        st.markdown("---")
        st.header("🔍 Filtros")
        
        # 1. Filtro de fecha
        if 'fecha_vuelo' in df.columns:
            fechas = ['Todas'] + sorted([str(f) for f in df['fecha_vuelo'].dropna().unique()])
            fechas_sel = st.selectbox("📅 Fecha de Vuelo", fechas)
            if fechas_sel != 'Todas':
                df_filtrado = df_filtrado[df_filtrado['fecha_vuelo'].astype(str) == fechas_sel]
        
        # 2. Filtro de especie (sobre datos filtrados por fecha)
        if 'Especie' in df_filtrado.columns:
            especies = ['Todas'] + sorted(df_filtrado['Especie'].dropna().unique().tolist())
            especie_sel = st.selectbox("🌿 Especie", especies)
            if especie_sel != 'Todas':
                df_filtrado = df_filtrado[df_filtrado['Especie'] == especie_sel]
        
        # 3. Filtro de variedad (sobre datos filtrados por especie)
        if 'Variedad' in df_filtrado.columns:
            variedades = ['Todas'] + sorted(df_filtrado['Variedad'].dropna().unique().tolist())
            variedad_sel = st.selectbox("🍒 Variedad", variedades)
            if variedad_sel != 'Todas':
                df_filtrado = df_filtrado[df_filtrado['Variedad'] == variedad_sel]
        
        # 4. Filtro de cuarteles (MULTISELECT sobre datos filtrados)
        if 'Cuartel' in df_filtrado.columns:
            cuarteles_disponibles = sorted(df_filtrado['Cuartel'].dropna().unique().tolist())
            cuarteles_sel = st.multiselect(
                "📍 Cuarteles",
                cuarteles_disponibles,
                default=[],
                placeholder="Todos los cuarteles"
            )
            if cuarteles_sel:
                df_filtrado = df_filtrado[df_filtrado['Cuartel'].isin(cuarteles_sel)]
        
        st.markdown("---")
        st.header("📊 Índice")
        
        # Solo mostrar los 4 índices más relevantes para frutales
        INDICES_PERMITIDOS = ['ndvi', 'osavi', 'ndre', 'lci']
        indices = [k for k in INDICES_PERMITIDOS if k in df.columns and k in INDICES_INFO]
        
        indice_sel = st.selectbox(
            "Seleccionar", 
            indices, 
            format_func=lambda x: f"{INDICES_INFO[x]['nombre']} ({INDICES_INFO[x]['categoria']})"
        ) if indices else None
        
        st.markdown("---")
        st.header("⚙️ Visualización")
        radio_puntos = st.slider("Tamaño puntos", 1, 8, 3, 1)
        
        st.markdown("---")
        st.header("🎨 Leyenda")
        for clase, color in COLORES_CLASE.items():
            if clase != 'Sin dato':
                st.markdown(f'<span style="background-color:{color}; padding: 2px 10px; border-radius: 3px;">&nbsp;</span> {clase}', unsafe_allow_html=True)
        
        st.markdown("---")
        st.caption(f"📊 {len(df_filtrado):,} árboles filtrados")
    
    return df_filtrado, indice_sel, radio_puntos, fechas_sel, indices


# =============================================================================
# MAIN
# =============================================================================

def main():
    # Header con logo centrado
    mostrar_logo_header()
    st.markdown('<p class="sub-header">Dashboard de Individualización de Árboles Frutales</p>', unsafe_allow_html=True)
    
    # Cargar datos
    df = cargar_datos(GPKG_PATH)
    if df is None or len(df) == 0:
        st.error(f"No se pudieron cargar datos de: {GPKG_PATH}")
        return
    
    # Cargar polígonos
    gdf_poligonos = cargar_poligonos(POLIGONOS_PATH)
    if gdf_poligonos is not None:
        st.sidebar.success(f"✅ Polígonos cargados: {len(gdf_poligonos)} cuarteles")
    
    df_filtrado, indice_sel, radio_puntos, fechas_sel, indices_disponibles = crear_sidebar(df)
    
    if indice_sel is None:
        st.warning("No hay índices disponibles")
        return
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Resumen", "📈 Análisis", "📅 Comparación", "🔍 Datos"])
    
    with tab1:
        tab_resumen(df_filtrado, indice_sel, fechas_sel, radio_puntos, gdf_poligonos)
    
    with tab2:
        tab_analisis(df_filtrado, indice_sel, fechas_sel)
    
    with tab3:
        tab_comparacion(df_filtrado, indice_sel)
    
    with tab4:
        tab_datos(df_filtrado, indices_disponibles)
    
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: gray; padding: 10px;'>
        <p>Desarrollado por <strong>TeMapeo SPA</strong> | Servicios de Teledetección y Agricultura de Precisión</p>
        <p><a href="https://www.temapeo.com" target="_blank">www.temapeo.com</a></p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()