#!/usr/bin/env python3
"""
TEMAPEO VIEWER v8 - Dashboard con 7 Clases y Múltiples Cultivos
- Simbología de 7 clases estandarizada
- Soporte para Cerezos y Kiwis
- Filtro por cultivo
- Comparación temporal mejorada

Autor: TeMapeo SPA
Versión: 8.0
"""

import streamlit as st
import pandas as pd
import geopandas as gpd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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
    .main-header {font-size: 2.2rem; font-weight: bold; color: #1a9850; text-align: center; padding: 0.5rem;}
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

GPKG_PATH = "datos/BD_FINAL_todos_cultivos_vuelos.gpkg"
POLIGONOS_PATH = "datos/Poligonos_Abud.gpkg"

# Ruta al logo (PNG o JPG)
LOGO_PATH = 'datos/logo.png'

# =============================================================================
# COLORES Y CONFIGURACIÓN - 7 CLASES
# =============================================================================

COLORES_CLASE = {
    'Muy bajo': '#D73027',      # Rojo
    'Bajo': '#FC8D59',          # Naranja
    'Medio-bajo': '#FEE08B',    # Amarillo
    'Medio': '#D9EF8B',         # Verde amarillo
    'Medio-alto': '#91CF60',    # Verde claro
    'Alto': '#1A9850',          # Verde
    'Muy alto': '#006837',      # Verde oscuro
    'Sin dato': '#BDBDBD'       # Gris
}

# Orden de clases para gráficos
ORDEN_CLASES = ['Muy bajo', 'Bajo', 'Medio-bajo', 'Medio', 'Medio-alto', 'Alto', 'Muy alto', 'Sin dato']

# Información detallada de cada índice
INDICES_INFO = {
    'ndvi': {
        'nombre': 'NDVI',
        'nombre_completo': 'Índice de Vegetación de Diferencia Normalizada',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Mide la cantidad y vigor de la vegetación. Valores altos (>0.6) indican vegetación densa y saludable. Valores bajos (<0.3) indican estrés, suelo desnudo o vegetación escasa.',
        'interpretacion': {
            'Muy alto': 'Excelente vigor, máxima actividad fotosintética',
            'Alto': 'Árbol con excelente vigor, follaje denso',
            'Medio-alto': 'Buen estado general, follaje saludable',
            'Medio': 'Vigor moderado, puede requerir atención',
            'Medio-bajo': 'Vigor bajo, monitorear evolución',
            'Bajo': 'Estrés vegetativo, posible déficit hídrico o nutricional',
            'Muy bajo': 'Estrés severo, requiere intervención inmediata'
        },
        'rangos_7clases': ['≤0.30', '0.30-0.40', '0.40-0.50', '0.50-0.60', '0.60-0.70', '0.70-0.80', '≥0.80'],
        'rango': '0 a 1'
    },
    'osavi': {
        'nombre': 'OSAVI',
        'nombre_completo': 'Índice de Vegetación Ajustado al Suelo Optimizado',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Similar al NDVI pero minimiza la influencia del suelo. Ideal para cultivos con cobertura parcial del suelo.',
        'interpretacion': {
            'Muy alto': 'Máxima cobertura vegetal',
            'Alto': 'Excelente cobertura vegetal y vigor',
            'Medio-alto': 'Buena cobertura, vegetación saludable',
            'Medio': 'Cobertura moderada',
            'Medio-bajo': 'Cobertura limitada',
            'Bajo': 'Baja cobertura o estrés',
            'Muy bajo': 'Muy baja cobertura o estrés severo'
        },
        'rangos_7clases': ['≤0.15', '0.15-0.25', '0.25-0.35', '0.35-0.45', '0.45-0.55', '0.55-0.70', '≥0.70'],
        'rango': '0 a 1'
    },
    'gndvi': {
        'nombre': 'GNDVI',
        'nombre_completo': 'Índice de Vegetación de Diferencia Normalizada Verde',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Usa la banda verde en lugar de roja. Más sensible a variaciones de clorofila que el NDVI.',
        'interpretacion': {
            'Muy alto': 'Máximo contenido de clorofila',
            'Alto': 'Alto contenido de clorofila, vegetación muy activa',
            'Medio-alto': 'Buen contenido de clorofila',
            'Medio': 'Contenido moderado de clorofila',
            'Medio-bajo': 'Contenido bajo de clorofila',
            'Bajo': 'Bajo contenido de clorofila',
            'Muy bajo': 'Deficiencia severa de clorofila'
        },
        'rangos_7clases': ['≤0.30', '0.30-0.40', '0.40-0.50', '0.50-0.60', '0.60-0.70', '0.70-0.80', '≥0.80'],
        'rango': '0 a 1'
    },
    'savi': {
        'nombre': 'SAVI',
        'nombre_completo': 'Índice de Vegetación Ajustado al Suelo',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Minimiza efectos del suelo mediante un factor de corrección (L=0.5).',
        'interpretacion': {
            'Muy alto': 'Máximo vigor vegetativo',
            'Alto': 'Excelente vigor vegetativo',
            'Medio-alto': 'Buen estado vegetativo',
            'Medio': 'Estado moderado',
            'Medio-bajo': 'Estado bajo',
            'Bajo': 'Estrés o baja cobertura',
            'Muy bajo': 'Estrés severo'
        },
        'rangos_7clases': ['≤0.15', '0.15-0.25', '0.25-0.35', '0.35-0.45', '0.45-0.55', '0.55-0.70', '≥0.70'],
        'rango': '0 a 1'
    },
    'msavi2': {
        'nombre': 'MSAVI2',
        'nombre_completo': 'Índice de Vegetación Ajustado al Suelo Modificado',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Versión mejorada del SAVI con factor de corrección automático.',
        'interpretacion': {
            'Muy alto': 'Vegetación muy densa y vigorosa',
            'Alto': 'Vegetación densa y vigorosa',
            'Medio-alto': 'Buena densidad vegetal',
            'Medio': 'Densidad moderada',
            'Medio-bajo': 'Densidad baja',
            'Bajo': 'Baja densidad o estrés',
            'Muy bajo': 'Muy baja densidad'
        },
        'rangos_7clases': ['≤0.30', '0.30-0.40', '0.40-0.50', '0.50-0.60', '0.60-0.70', '0.70-0.80', '≥0.80'],
        'rango': '0 a 1'
    },
    'evi2': {
        'nombre': 'EVI2',
        'nombre_completo': 'Índice de Vegetación Mejorado (2 bandas)',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Optimizado para áreas de alta biomasa donde el NDVI se satura.',
        'interpretacion': {
            'Muy alto': 'Máxima biomasa',
            'Alto': 'Alta biomasa, vegetación muy densa',
            'Medio-alto': 'Buena biomasa',
            'Medio': 'Biomasa moderada',
            'Medio-bajo': 'Biomasa baja',
            'Bajo': 'Baja biomasa',
            'Muy bajo': 'Muy baja biomasa'
        },
        'rangos_7clases': ['≤0.25', '0.25-0.35', '0.35-0.45', '0.45-0.55', '0.55-0.65', '0.65-0.75', '≥0.75'],
        'rango': '0 a 1'
    },
    'lci': {
        'nombre': 'LCI',
        'nombre_completo': 'Índice de Clorofila de Hoja',
        'categoria': 'Contenido de Clorofila',
        'descripcion': 'Estima el contenido de clorofila en las hojas. Correlaciona con el contenido de nitrógeno foliar.',
        'interpretacion': {
            'Muy alto': 'Máximo contenido de clorofila y nitrógeno',
            'Alto': 'Alto contenido de clorofila, buena nutrición',
            'Medio-alto': 'Buen estado nutricional',
            'Medio': 'Nutrición moderada',
            'Medio-bajo': 'Nutrición limitada',
            'Bajo': 'Posible deficiencia de nitrógeno',
            'Muy bajo': 'Deficiencia severa, fertilizar con urgencia'
        },
        'rangos_7clases': ['≤0.30', '0.30-0.40', '0.40-0.50', '0.50-0.60', '0.60-0.70', '0.70-0.80', '≥0.80'],
        'rango': '0 a 1'
    },
    'ndre': {
        'nombre': 'NDRE',
        'nombre_completo': 'Índice de Diferencia Normalizada Red Edge',
        'categoria': 'Contenido de Clorofila',
        'descripcion': 'Muy sensible al contenido de clorofila. Ideal para detectar estrés temprano.',
        'interpretacion': {
            'Muy alto': 'Máximo contenido de clorofila',
            'Alto': 'Excelente contenido de clorofila, planta muy sana',
            'Medio-alto': 'Buen contenido de clorofila',
            'Medio': 'Contenido normal',
            'Medio-bajo': 'Contenido bajo',
            'Bajo': 'Bajo contenido, posible estrés inicial',
            'Muy bajo': 'Estrés significativo detectado'
        },
        'rangos_7clases': ['≤0.20', '0.20-0.30', '0.30-0.40', '0.40-0.50', '0.50-0.60', '0.60-0.70', '≥0.70'],
        'rango': '0 a 1'
    },
    'cirededge': {
        'nombre': 'CIRedEdge',
        'nombre_completo': 'Índice de Clorofila Red Edge',
        'categoria': 'Contenido de Clorofila',
        'descripcion': 'Altamente sensible a pequeños cambios en el contenido de clorofila.',
        'interpretacion': {
            'Muy alto': 'Máxima actividad fotosintética',
            'Alto': 'Excelente actividad fotosintética',
            'Medio-alto': 'Buena actividad fotosintética',
            'Medio': 'Actividad normal',
            'Medio-bajo': 'Actividad reducida',
            'Bajo': 'Reducción de actividad fotosintética',
            'Muy bajo': 'Actividad fotosintética muy reducida'
        },
        'rangos_7clases': ['≤0.50', '0.50-1.00', '1.00-1.50', '1.50-2.00', '2.00-2.50', '2.50-3.50', '≥3.50'],
        'rango': '0 a 5'
    },
    'cigreen': {
        'nombre': 'CIGreen',
        'nombre_completo': 'Índice de Clorofila Verde',
        'categoria': 'Contenido de Clorofila',
        'descripcion': 'Sensible al contenido de clorofila usando la banda verde.',
        'interpretacion': {
            'Muy alto': 'Máximo contenido de clorofila',
            'Alto': 'Alto contenido de clorofila',
            'Medio-alto': 'Buen contenido de clorofila',
            'Medio': 'Contenido normal',
            'Medio-bajo': 'Contenido bajo',
            'Bajo': 'Bajo contenido de clorofila',
            'Muy bajo': 'Deficiencia de clorofila'
        },
        'rangos_7clases': ['≤0.75', '0.75-1.50', '1.50-2.25', '2.25-3.00', '3.00-4.00', '4.00-5.00', '≥5.00'],
        'rango': '0 a 7'
    },
    'mcari': {
        'nombre': 'MCARI',
        'nombre_completo': 'Índice de Absorción de Clorofila Modificado',
        'categoria': 'Estructura del Dosel',
        'descripcion': 'Sensible al contenido de clorofila y a la estructura del dosel.',
        'interpretacion': {
            'Muy alto': 'Dosel óptimo con máxima clorofila',
            'Alto': 'Dosel bien estructurado con alta clorofila',
            'Medio-alto': 'Buena estructura de dosel',
            'Medio': 'Estructura normal',
            'Medio-bajo': 'Estructura limitada',
            'Bajo': 'Estructura de dosel reducida',
            'Muy bajo': 'Dosel muy reducido o dañado'
        },
        'rangos_7clases': ['≤0.30', '0.30-0.60', '0.60-1.00', '1.00-1.50', '1.50-2.00', '2.00-2.50', '≥2.50'],
        'rango': '0 a 3'
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
        if gdf.crs and gdf.crs.to_epsg() != 4326:
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
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        return gdf
    except:
        return None


def obtener_columna_clase(df, indice):
    """Obtiene el nombre de la columna de clase para un índice."""
    # Buscar variantes de nombre de columna
    variantes = [f"{indice}_class", f"{indice}_clase", f"{indice}_Class"]
    for var in variantes:
        if var in df.columns:
            return var
    return None


def normalizar_clases(df, col_clase):
    """Normaliza los nombres de las clases al estándar de 7 clases."""
    if col_clase not in df.columns:
        return df
    
    # Mapeo de nombres antiguos a nuevos
    mapeo = {
        'Muy bajo': 'Muy bajo',
        'Bajo': 'Bajo',
        'Medio-bajo': 'Medio-bajo',
        'Medio bajo': 'Medio-bajo',
        'Medio': 'Medio',
        'Medio-alto': 'Medio-alto',
        'Medio alto': 'Medio-alto',
        'Alto': 'Alto',
        'Muy alto': 'Muy alto',
        'Sin dato': 'Sin dato',
        None: 'Sin dato',
        '': 'Sin dato'
    }
    
    df[col_clase] = df[col_clase].map(lambda x: mapeo.get(x, x) if pd.notna(x) else 'Sin dato')
    return df


# =============================================================================
# FUNCIONES DE VISUALIZACIÓN
# =============================================================================

def crear_mapa_puntos(df, indice, radio_puntos=3, gdf_poligonos=None):
    """Crea mapa de puntos con Plotly."""
    
    col_clase = obtener_columna_clase(df, indice)
    if col_clase is None:
        st.warning(f"No se encontró columna de clase para {indice}")
        return None
    
    df = normalizar_clases(df, col_clase)
    
    # Preparar datos
    df_map = df.dropna(subset=['lat', 'lon']).copy()
    if len(df_map) == 0:
        return None
    
    # Limitar puntos si hay demasiados
    max_puntos = 50000
    if len(df_map) > max_puntos:
        df_map = df_map.sample(n=max_puntos, random_state=42)
    
    # Crear figura
    fig = go.Figure()
    
    # Agregar polígonos si existen
    if gdf_poligonos is not None:
        for idx, row in gdf_poligonos.iterrows():
            if row.geometry.geom_type == 'Polygon':
                coords = list(row.geometry.exterior.coords)
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                fig.add_trace(go.Scattermapbox(
                    lon=lons, lat=lats,
                    mode='lines',
                    line=dict(width=2, color='#333'),
                    hoverinfo='skip',
                    showlegend=False
                ))
    
    # Agregar puntos por clase
    for clase in ORDEN_CLASES:
        df_clase = df_map[df_map[col_clase] == clase]
        if len(df_clase) == 0:
            continue
        
        color = COLORES_CLASE.get(clase, '#999999')
        
        # Preparar hover text
        hover_text = []
        for _, row in df_clase.iterrows():
            text = f"<b>ID:</b> {row.get('id', 'N/A')}<br>"
            text += f"<b>Clase:</b> {clase}<br>"
            text += f"<b>{indice.upper()}:</b> {row.get(indice, 'N/A'):.3f}<br>" if pd.notna(row.get(indice)) else ""
            text += f"<b>Cuartel:</b> {row.get('Cuartel', 'N/A')}<br>"
            if 'cultivo' in row:
                text += f"<b>Cultivo:</b> {row.get('cultivo', 'N/A')}<br>"
            hover_text.append(text)
        
        fig.add_trace(go.Scattermapbox(
            lon=df_clase['lon'],
            lat=df_clase['lat'],
            mode='markers',
            marker=dict(size=radio_puntos, color=color),
            name=clase,
            text=hover_text,
            hoverinfo='text'
        ))
    
    # Configurar layout
    center_lat = df_map['lat'].mean()
    center_lon = df_map['lon'].mean()
    
    fig.update_layout(
        mapbox=dict(
            style='open-street-map',
            center=dict(lat=center_lat, lon=center_lon),
            zoom=14
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=500,
        legend=dict(
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01,
            bgcolor="rgba(255,255,255,0.8)"
        )
    )
    
    return fig


def crear_grafico_distribucion(df, indice):
    """Crea gráfico de distribución de clases."""
    
    col_clase = obtener_columna_clase(df, indice)
    if col_clase is None:
        return None
    
    df = normalizar_clases(df, col_clase)
    
    # Contar por clase
    conteos = df[col_clase].value_counts()
    
    # Ordenar según ORDEN_CLASES
    data = []
    for clase in ORDEN_CLASES:
        if clase in conteos.index:
            data.append({'Clase': clase, 'Cantidad': conteos[clase]})
    
    df_plot = pd.DataFrame(data)
    
    if len(df_plot) == 0:
        return None
    
    # Crear gráfico
    fig = px.bar(
        df_plot,
        x='Clase',
        y='Cantidad',
        color='Clase',
        color_discrete_map=COLORES_CLASE,
        category_orders={'Clase': ORDEN_CLASES}
    )
    
    fig.update_layout(
        showlegend=False,
        xaxis_title="",
        yaxis_title="Cantidad de árboles",
        height=300
    )
    
    return fig


def crear_grafico_pie(df, indice):
    """Crea gráfico de pie de distribución."""
    
    col_clase = obtener_columna_clase(df, indice)
    if col_clase is None:
        return None
    
    df = normalizar_clases(df, col_clase)
    
    # Contar por clase
    conteos = df[col_clase].value_counts()
    
    # Ordenar
    data = []
    colors = []
    for clase in ORDEN_CLASES:
        if clase in conteos.index and conteos[clase] > 0:
            data.append({'Clase': clase, 'Cantidad': conteos[clase]})
            colors.append(COLORES_CLASE.get(clase, '#999'))
    
    df_plot = pd.DataFrame(data)
    
    if len(df_plot) == 0:
        return None
    
    fig = px.pie(
        df_plot,
        values='Cantidad',
        names='Clase',
        color='Clase',
        color_discrete_map=COLORES_CLASE
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(height=350, showlegend=False)
    
    return fig


def mostrar_info_indice(indice):
    """Muestra información del índice seleccionado."""
    
    if indice not in INDICES_INFO:
        return
    
    info = INDICES_INFO[indice]
    
    with st.expander(f"ℹ️ Información sobre {info['nombre']}", expanded=False):
        st.markdown(f"**{info['nombre_completo']}**")
        st.markdown(f"*Categoría: {info['categoria']}*")
        st.markdown(info['descripcion'])
        
        if 'rangos_7clases' in info:
            st.markdown("**Rangos de clasificación (7 clases):**")
            cols = st.columns(7)
            for i, (clase, rango) in enumerate(zip(ORDEN_CLASES[:7], info['rangos_7clases'])):
                with cols[i]:
                    color = COLORES_CLASE.get(clase, '#999')
                    st.markdown(f'<span style="background-color:{color}; padding: 2px 6px; border-radius: 3px; font-size: 0.8em;">{rango}</span>', unsafe_allow_html=True)
                    st.caption(clase)


# =============================================================================
# TABS
# =============================================================================

def tab_resumen(df, indice, fechas_sel, radio_puntos, gdf_poligonos):
    """Tab Resumen."""
    
    col_clase = obtener_columna_clase(df, indice)
    
    # Info del índice
    mostrar_info_indice(indice)
    
    # KPIs
    st.subheader("📊 Métricas Clave")
    
    cols = st.columns(6)
    
    with cols[0]:
        st.metric("Total Árboles", f"{len(df):,}")
    
    with cols[1]:
        if indice in df.columns:
            media = df[indice].mean()
            st.metric(f"Media {indice.upper()}", f"{media:.3f}" if pd.notna(media) else "N/A")
    
    with cols[2]:
        if indice in df.columns:
            std = df[indice].std()
            st.metric("Desv. Estándar", f"{std:.3f}" if pd.notna(std) else "N/A")
    
    with cols[3]:
        if col_clase and col_clase in df.columns:
            df_norm = normalizar_clases(df.copy(), col_clase)
            buenos = df_norm[df_norm[col_clase].isin(['Alto', 'Muy alto', 'Medio-alto'])].shape[0]
            pct = (buenos / len(df)) * 100 if len(df) > 0 else 0
            st.metric("% Buen Estado", f"{pct:.1f}%")
    
    with cols[4]:
        if col_clase and col_clase in df.columns:
            df_norm = normalizar_clases(df.copy(), col_clase)
            criticos = df_norm[df_norm[col_clase].isin(['Muy bajo', 'Bajo'])].shape[0]
            pct = (criticos / len(df)) * 100 if len(df) > 0 else 0
            st.metric("% Crítico", f"{pct:.1f}%", delta_color="inverse")
    
    with cols[5]:
        if 'Cuartel' in df.columns:
            st.metric("Cuarteles", df['Cuartel'].nunique())
    
    st.markdown("---")
    
    # Mapa y gráficos
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("🗺️ Mapa de Distribución")
        fig_mapa = crear_mapa_puntos(df, indice, radio_puntos, gdf_poligonos)
        mostrar_mapa_seguro(fig_mapa, 500, "mapa_resumen")
    
    with col2:
        st.subheader("📊 Distribución por Clase")
        fig_pie = crear_grafico_pie(df, indice)
        if fig_pie:
            st.plotly_chart(fig_pie, use_container_width=True)
        
        fig_bar = crear_grafico_distribucion(df, indice)
        if fig_bar:
            st.plotly_chart(fig_bar, use_container_width=True)


def tab_analisis(df, indice, fechas_sel):
    """Tab Análisis."""
    
    st.subheader("📈 Análisis Detallado")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Histograma
        if indice in df.columns:
            st.markdown(f"**Distribución de valores {indice.upper()}**")
            fig_hist = px.histogram(
                df[df[indice].notna()],
                x=indice,
                nbins=50,
                color_discrete_sequence=['#1a9850']
            )
            fig_hist.update_layout(
                xaxis_title=indice.upper(),
                yaxis_title="Frecuencia",
                height=350
            )
            st.plotly_chart(fig_hist, use_container_width=True)
    
    with col2:
        # Box plot por cuartel
        if 'Cuartel' in df.columns and indice in df.columns:
            st.markdown(f"**{indice.upper()} por Cuartel**")
            fig_box = px.box(
                df[df[indice].notna()],
                x='Cuartel',
                y=indice,
                color='Cuartel'
            )
            fig_box.update_layout(
                showlegend=False,
                height=350
            )
            st.plotly_chart(fig_box, use_container_width=True)
    
    # Análisis por cultivo si existe
    if 'cultivo' in df.columns:
        st.markdown("---")
        st.markdown("**Comparación por Cultivo**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if indice in df.columns:
                fig_cult = px.box(
                    df[df[indice].notna()],
                    x='cultivo',
                    y=indice,
                    color='cultivo',
                    color_discrete_sequence=['#1a9850', '#fc8d59']
                )
                fig_cult.update_layout(height=300, showlegend=False)
                st.plotly_chart(fig_cult, use_container_width=True)
        
        with col2:
            # Tabla resumen por cultivo
            resumen = df.groupby('cultivo').agg({
                indice: ['mean', 'std', 'count']
            }).round(3)
            resumen.columns = ['Media', 'Desv.Std', 'N']
            st.dataframe(resumen, use_container_width=True)


def tab_comparacion(df, indice):
    """Tab Comparación temporal."""
    
    st.subheader("📅 Comparación Temporal")
    
    if 'fecha_vuelo' not in df.columns:
        st.warning("No hay datos de múltiples fechas para comparar")
        return
    
    fechas = sorted(df['fecha_vuelo'].dropna().unique())
    
    if len(fechas) < 2:
        st.warning("Se necesitan al menos 2 fechas de vuelo para comparar")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        fecha1 = st.selectbox("Fecha inicial", fechas, index=0)
    with col2:
        fecha2 = st.selectbox("Fecha final", fechas, index=len(fechas)-1)
    
    if fecha1 == fecha2:
        st.warning("Selecciona fechas diferentes")
        return
    
    # Filtrar datos
    df1 = df[df['fecha_vuelo'] == fecha1]
    df2 = df[df['fecha_vuelo'] == fecha2]
    
    st.markdown("---")
    
    # Comparación de distribución
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"**{fecha1}** ({len(df1):,} árboles)")
        fig1 = crear_grafico_pie(df1, indice)
        if fig1:
            st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown(f"**{fecha2}** ({len(df2):,} árboles)")
        fig2 = crear_grafico_pie(df2, indice)
        if fig2:
            st.plotly_chart(fig2, use_container_width=True)
    
    # Evolución temporal
    st.markdown("---")
    st.markdown("**Evolución temporal del índice**")
    
    if indice in df.columns:
        evol = df.groupby('fecha_vuelo')[indice].agg(['mean', 'std', 'count']).reset_index()
        evol.columns = ['Fecha', 'Media', 'Std', 'N']
        
        fig_evol = px.line(
            evol,
            x='Fecha',
            y='Media',
            markers=True,
            title=f"Evolución de {indice.upper()}"
        )
        fig_evol.update_layout(height=350)
        st.plotly_chart(fig_evol, use_container_width=True)
        
        # Tabla resumen
        st.dataframe(evol.round(3), use_container_width=True, hide_index=True)


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
    
    if 'cultivo' in df.columns:
        cols_base.insert(1, 'cultivo')
    
    if 'fecha_vuelo' in df.columns:
        cols_base.append('fecha_vuelo')
    
    cols_indices = []
    for idx in indices_sel:
        if idx in df.columns:
            cols_indices.append(idx)
        col_clase = obtener_columna_clase(df, idx)
        if col_clase and col_clase in df.columns:
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
        
        # 0. Filtro de cultivo (NUEVO)
        if 'cultivo' in df.columns:
            cultivos = ['Todos'] + sorted(df['cultivo'].dropna().unique().tolist())
            cultivo_sel = st.selectbox("🌱 Cultivo", cultivos)
            if cultivo_sel != 'Todos':
                df_filtrado = df_filtrado[df_filtrado['cultivo'] == cultivo_sel]
        
        # 1. Filtro de fecha
        if 'fecha_vuelo' in df_filtrado.columns:
            fechas = ['Todas'] + sorted([str(f) for f in df_filtrado['fecha_vuelo'].dropna().unique()])
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
        
        # Índices más relevantes para frutales
        INDICES_PERMITIDOS = ['ndvi', 'osavi', 'ndre', 'lci', 'gndvi', 'evi2']
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
        st.header("🎨 Leyenda (7 Clases)")
        for clase in ORDEN_CLASES:
            if clase != 'Sin dato':
                color = COLORES_CLASE.get(clase, '#999')
                st.markdown(f'<span style="background-color:{color}; padding: 2px 10px; border-radius: 3px;">&nbsp;</span> {clase}', unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Resumen de filtros
        st.caption(f"📊 {len(df_filtrado):,} árboles filtrados")
        if 'cultivo' in df_filtrado.columns:
            cultivos_uniq = df_filtrado['cultivo'].nunique()
            st.caption(f"🌱 {cultivos_uniq} cultivo(s)")
        if 'fecha_vuelo' in df_filtrado.columns:
            fechas_uniq = df_filtrado['fecha_vuelo'].nunique()
            st.caption(f"📅 {fechas_uniq} fecha(s)")
    
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
        st.info("Verifica que el archivo GPKG esté en la carpeta 'datos/'")
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
        <p><a href="https://www.temapeo.com" target="_blank">www.temapeo.com</a> | v8.0 - 7 Clases</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
