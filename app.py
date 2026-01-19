#!/usr/bin/env python3
"""
TEMAPEO VIEWER v9.3 - Dashboard con Zonas de Manejo
- Simbología de 7 clases para puntos individuales
- Zonas de Manejo (3 clases) para gestión operativa
- Soporte para Cerezos y Kiwis
- Comparación temporal de hasta 3 vuelos

FIXES v9.1:
- Corregido visualización de polígonos de zonas de manejo
- Mejoradas etiquetas de gráficos con % y superficie

FIXES v9.2:
- Filtros de cuartel/variedad ahora aplican también a zonas de manejo
- Sincronización completa entre puntos y polígonos de zonas

FIXES v9.3:
- Filtro de cultivo aplicado a zonas de manejo
- Tab Comparación mejorado con eje X categórico ordenado por fecha
- Tab Comparación con análisis comparativo completo (métricas, tabla, evolución)
- Tab Análisis muestra comparación de los 3 vuelos lado a lado

Autor: TeMapeo SPA
Versión: 9.3
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

GPKG_PATH = "datos/BD_FINAL_todos_cultivos_vuelos.gpkg"
POLIGONOS_PATH = "datos/Poligonos_Abud.gpkg"
ZONAS_MANEJO_PATH = "datos/Zonas_Manejo_TODOS.gpkg"

# Ruta al logo (PNG o JPG)
LOGO_PATH = 'datos/logo.png'

# =============================================================================
# COLORES Y CONFIGURACIÓN
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
ORDEN_CLASES = ['Muy bajo', 'Bajo', 'Medio-bajo', 'Medio', 'Medio-alto', 'Alto', 'Muy alto']

# Colores para Zonas de Manejo (3 clases - semáforo)
COLORES_ZONAS_MANEJO = {
    1: '#D73027',  # Baja - Rojo
    2: '#FEE04F',  # Media - Amarillo
    3: '#1A9850',  # Alta - Verde
}

NOMBRES_ZONAS_MANEJO = {
    1: 'Baja',
    2: 'Media',
    3: 'Alta'
}

# Rangos por índice para zonas de manejo
RANGOS_ZONAS_MANEJO = {
    'ndvi': {'baja': '< 0.50', 'media': '0.50 - 0.70', 'alta': '> 0.70'},
    'osavi': {'baja': '< 0.40', 'media': '0.40 - 0.60', 'alta': '> 0.60'},
    'ndre': {'baja': '< 0.35', 'media': '0.35 - 0.55', 'alta': '> 0.55'},
    'lci': {'baja': '< 0.45', 'media': '0.45 - 0.65', 'alta': '> 0.65'},
}

# Información detallada de cada índice
INDICES_INFO = {
    'ndvi': {
        'nombre': 'NDVI',
        'nombre_completo': 'Índice de Vegetación de Diferencia Normalizada',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Mide la cantidad y vigor de la vegetación. Valores altos (>0.6) indican vegetación densa y saludable.',
        'rango': '0 a 1'
    },
    'osavi': {
        'nombre': 'OSAVI',
        'nombre_completo': 'Índice de Vegetación Ajustado al Suelo Optimizado',
        'categoria': 'Vigor Vegetativo',
        'descripcion': 'Similar al NDVI pero minimiza la influencia del suelo. Ideal para cultivos con cobertura parcial.',
        'rango': '0 a 0.6'
    },
    'ndre': {
        'nombre': 'NDRE',
        'nombre_completo': 'Índice de Diferencia Normalizada Red Edge',
        'categoria': 'Contenido de Clorofila',
        'descripcion': 'Muy sensible al contenido de clorofila. Ideal para detectar estrés temprano.',
        'rango': '0.15 a 0.5'
    },
    'lci': {
        'nombre': 'LCI',
        'nombre_completo': 'Índice de Clorofila de Hoja',
        'categoria': 'Contenido de Clorofila',
        'descripcion': 'Estima el contenido de clorofila. Correlaciona con nitrógeno foliar.',
        'rango': '0.1 a 0.85'
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
    """Carga datos del GPKG y extrae coordenadas de la geometría."""
    try:
        gdf = gpd.read_file(ruta_gpkg)
        if gdf.crs is not None and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        
        if 'geometry' in gdf.columns and gdf.geometry is not None:
            gdf['lon'] = gdf.geometry.x
            gdf['lat'] = gdf.geometry.y
        
        return pd.DataFrame(gdf.drop(columns='geometry', errors='ignore'))
    except Exception as e:
        st.error(f"Error cargando datos: {e}")
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


@st.cache_data
def cargar_zonas_manejo(ruta_gpkg):
    """Carga zonas de manejo."""
    try:
        if not os.path.exists(ruta_gpkg):
            return None
        gdf = gpd.read_file(ruta_gpkg)
        if gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        return gdf
    except Exception as e:
        return None


def obtener_info_superficie(df_puntos, gdf_poligonos, cuarteles_filtrados=None):
    """Obtiene información de superficie de los cuarteles."""
    if gdf_poligonos is None:
        return None
    
    if cuarteles_filtrados is not None and len(cuarteles_filtrados) > 0:
        gdf_filtrado = gdf_poligonos[gdf_poligonos['Cuartel'].isin(cuarteles_filtrados)]
    else:
        cuarteles_en_datos = df_puntos['Cuartel'].unique() if 'Cuartel' in df_puntos.columns else []
        gdf_filtrado = gdf_poligonos[gdf_poligonos['Cuartel'].isin(cuarteles_en_datos)]
    
    if len(gdf_filtrado) == 0:
        return None
    
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
    """Asigna color según clase (7 clases)."""
    if pd.isna(clase):
        return COLORES_CLASE['Sin dato']
    
    try:
        clase_num = int(float(clase))
        mapeo_num = {1: 'Muy bajo', 2: 'Bajo', 3: 'Medio-bajo', 4: 'Medio',
                     5: 'Medio-alto', 6: 'Alto', 7: 'Muy alto'}
        clase_texto = mapeo_num.get(clase_num, 'Sin dato')
        return COLORES_CLASE.get(clase_texto, COLORES_CLASE['Sin dato'])
    except (ValueError, TypeError):
        pass
    
    clase_str = str(clase).lower()
    if 'muy bajo' in clase_str:
        return COLORES_CLASE['Muy bajo']
    elif 'medio-bajo' in clase_str:
        return COLORES_CLASE['Medio-bajo']
    elif 'bajo' in clase_str:
        return COLORES_CLASE['Bajo']
    elif 'muy alto' in clase_str:
        return COLORES_CLASE['Muy alto']
    elif 'medio-alto' in clase_str:
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
        <div style="background-color: #f0f2f6; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
            <strong>📊 {info['nombre_completo']} ({indice.upper()})</strong> | <em>{info['categoria']}</em><br>
            {info['descripcion']}<br>
            <small>Rango típico: {info['rango']}</small>
        </div>
        """, unsafe_allow_html=True)


def clasificar_punto(clase_valor):
    """Clasifica un valor de clase a etiqueta estándar."""
    if pd.isna(clase_valor):
        return 'Sin dato'
    
    try:
        clase_num = int(float(clase_valor))
        mapeo_num = {1: 'Muy bajo', 2: 'Bajo', 3: 'Medio-bajo', 4: 'Medio',
                     5: 'Medio-alto', 6: 'Alto', 7: 'Muy alto'}
        return mapeo_num.get(clase_num, 'Sin dato')
    except (ValueError, TypeError):
        pass
    
    clase_lower = str(clase_valor).lower()
    if 'muy bajo' in clase_lower:
        return 'Muy bajo'
    elif 'medio-bajo' in clase_lower:
        return 'Medio-bajo'
    elif 'bajo' in clase_lower:
        return 'Bajo'
    elif 'muy alto' in clase_lower:
        return 'Muy alto'
    elif 'medio-alto' in clase_lower:
        return 'Medio-alto'
    elif 'medio' in clase_lower:
        return 'Medio'
    elif 'alto' in clase_lower:
        return 'Alto'
    return 'Sin dato'


def calcular_pct_sanos(df, indice):
    """Calcula el porcentaje de árboles sanos."""
    col_clase = f"{indice}_clase"
    if col_clase not in df.columns or len(df) == 0:
        return 0
    
    def es_sano(valor):
        if pd.isna(valor):
            return False
        try:
            clase_num = int(float(valor))
            return clase_num >= 5
        except (ValueError, TypeError):
            pass
        valor_lower = str(valor).lower()
        return ('alto' in valor_lower and 'bajo' not in valor_lower)
    
    n_sanos = df[col_clase].apply(es_sano).sum()
    return (n_sanos / len(df) * 100) if len(df) > 0 else 0


# =============================================================================
# FUNCIONES DE MAPAS
# =============================================================================

def crear_mapa_plotly_satelite(df, indice, radio_puntos=3, titulo="", gdf_poligonos=None, center_lat=None, center_lon=None, zoom=None):
    """Crea mapa con Plotly usando tiles satelitales de Google."""
    col_clase = f"{indice}_clase"
    if col_clase not in df.columns or len(df) == 0:
        return None
    
    df_plot = df.copy()
    df_plot['color'] = df_plot[col_clase].apply(asignar_color_hex)
    df_plot['indice_valor'] = df_plot[indice].round(3)
    
    if 'altura_m' in df_plot.columns:
        df_plot['altura_str'] = df_plot['altura_m'].apply(lambda x: f"{x:.2f} m" if pd.notna(x) else "N/A")
    else:
        df_plot['altura_str'] = "N/A"
    
    df_plot['hover_text'] = df_plot.apply(
        lambda row: f"<b>ID:</b> {row.get('id', 'N/A')}<br>" +
                    f"<b>Cuartel:</b> {row.get('Cuartel', 'N/A')}<br>" +
                    f"<b>{indice.upper()}:</b> {row['indice_valor']}<br>" +
                    f"<b>Clase:</b> {row.get(col_clase, 'N/A')}",
        axis=1
    )
    
    fig = go.Figure()
    
    # Agregar polígonos de cuarteles
    if gdf_poligonos is not None and len(gdf_poligonos) > 0:
        cuarteles_en_datos = df['Cuartel'].unique() if 'Cuartel' in df.columns else []
        gdf_filtrado = gdf_poligonos[gdf_poligonos['Cuartel'].isin(cuarteles_en_datos)]
        
        if len(gdf_filtrado) > 0:
            for _, row in gdf_filtrado.iterrows():
                geom = row.geometry
                if geom.geom_type == 'Polygon':
                    coords = list(geom.exterior.coords)
                elif geom.geom_type == 'MultiPolygon':
                    coords = list(geom.geoms[0].exterior.coords)
                else:
                    continue
                
                lons = [c[0] for c in coords]
                lats = [c[1] for c in coords]
                
                fig.add_trace(go.Scattermapbox(
                    lon=lons, lat=lats,
                    mode='lines',
                    line=dict(width=3, color='#00BFFF'),
                    fill='none',
                    name=row['Cuartel'],
                    showlegend=False
                ))
    
    # Agregar puntos por clase
    df_plot['clase_simple'] = df_plot[col_clase].apply(clasificar_punto)
    
    for clase in ORDEN_CLASES:
        df_clase = df_plot[df_plot['clase_simple'] == clase]
        if len(df_clase) == 0:
            continue
        
        df_clase = df_clase[df_clase['lat'].notna() & df_clase['lon'].notna()]
        if len(df_clase) == 0:
            continue
        
        color = COLORES_CLASE.get(clase, '#969696')
        
        fig.add_trace(go.Scattermapbox(
            lon=df_clase['lon'], lat=df_clase['lat'],
            mode='markers',
            marker=dict(size=radio_puntos * 4, color=color, opacity=0.9),
            name=clase,
            hoverinfo='text',
            hovertext=df_clase['hover_text'],
            showlegend=True
        ))
    
    # Calcular centro y zoom
    if center_lat is None or center_lon is None:
        center_lat = df['lat'].mean()
        center_lon = df['lon'].mean()
    
    if zoom is None:
        lat_range = df['lat'].max() - df['lat'].min()
        lon_range = df['lon'].max() - df['lon'].min()
        max_range = max(lat_range, lon_range) * 1.15
        
        if max_range < 0.003: zoom = 17
        elif max_range < 0.006: zoom = 16
        elif max_range < 0.01: zoom = 15
        elif max_range < 0.02: zoom = 14
        elif max_range < 0.05: zoom = 13
        else: zoom = 12
    
    fig.update_layout(
        mapbox=dict(
            style="white-bg",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom,
            layers=[{
                "below": "traces",
                "sourcetype": "raster",
                "source": ["https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"]
            }]
        ),
        margin=dict(l=0, r=0, t=0, b=0),
        height=500,
        legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(255,255,255,0.9)", font=dict(size=10))
    )
    
    return fig


def crear_mapa_zonas_manejo(gdf_zonas, indice, titulo="", center_lat=None, center_lon=None, zoom=None):
    """
    Crea mapa de zonas de manejo con polígonos coloreados.
    FIX v9.1: Uso de Choroplethmapbox para mejor renderizado de polígonos.
    """
    if gdf_zonas is None or len(gdf_zonas) == 0:
        return None
    
    gdf_filtrado = gdf_zonas[gdf_zonas['indice'] == indice].copy()
    
    if len(gdf_filtrado) == 0:
        return None
    
    fig = go.Figure()
    
    # Obtener rangos para el índice
    rangos = RANGOS_ZONAS_MANEJO.get(indice, {})
    
    # Agregar polígonos por clase - FIX: Iterar correctamente y usar fill='toself'
    for clase in [1, 2, 3]:
        gdf_clase = gdf_filtrado[gdf_filtrado['clase'] == clase]
        if len(gdf_clase) == 0:
            continue
        
        color = COLORES_ZONAS_MANEJO.get(clase, '#888888')
        nombre_clase = NOMBRES_ZONAS_MANEJO.get(clase, f'Clase {clase}')
        
        if clase == 1: 
            rango_texto = rangos.get('baja', '')
        elif clase == 2: 
            rango_texto = rangos.get('media', '')
        else: 
            rango_texto = rangos.get('alta', '')
        
        # Procesar cada polígono de esta clase
        for idx, row in gdf_clase.iterrows():
            geom = row.geometry
            
            if geom is None or geom.is_empty:
                continue
            
            # Obtener lista de polígonos (manejar Polygon y MultiPolygon)
            if geom.geom_type == 'Polygon':
                polygons = [geom]
            elif geom.geom_type == 'MultiPolygon':
                polygons = list(geom.geoms)
            else:
                continue
            
            for poly in polygons:
                try:
                    # Obtener coordenadas del exterior
                    exterior_coords = list(poly.exterior.coords)
                    lons = [c[0] for c in exterior_coords]
                    lats = [c[1] for c in exterior_coords]
                    
                    # Cerrar el polígono explícitamente
                    if lons[0] != lons[-1] or lats[0] != lats[-1]:
                        lons.append(lons[0])
                        lats.append(lats[0])
                    
                    # Datos para hover
                    area_ha = row.get('area_ha', 0)
                    pct_area = row.get('pct_area', 0)
                    cuartel = row.get('cuartel', 'N/A')
                    
                    hover_text = (f"<b>Zona: {nombre_clase}</b><br>"
                                 f"Rango {indice.upper()}: {rango_texto}<br>"
                                 f"Cuartel: {cuartel}<br>"
                                 f"Área: {area_ha:.2f} ha ({pct_area:.1f}%)")
                    
                    # Agregar polígono con fill
                    fig.add_trace(go.Scattermapbox(
                        lon=lons,
                        lat=lats,
                        mode='lines',
                        fill='toself',
                        fillcolor=f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.6)',
                        line=dict(width=2, color=color),
                        name=nombre_clase,
                        hoverinfo='text',
                        hovertext=hover_text,
                        showlegend=False
                    ))
                    
                except Exception as e:
                    # Si falla un polígono, continuar con el siguiente
                    continue
    
    # Agregar leyenda (trazos invisibles solo para mostrar leyenda)
    for clase in [1, 2, 3]:
        color = COLORES_ZONAS_MANEJO.get(clase, '#888888')
        nombre_clase = NOMBRES_ZONAS_MANEJO.get(clase, f'Clase {clase}')
        
        if clase == 1: 
            rango_texto = rangos.get('baja', '')
        elif clase == 2: 
            rango_texto = rangos.get('media', '')
        else: 
            rango_texto = rangos.get('alta', '')
        
        fig.add_trace(go.Scattermapbox(
            lon=[None], 
            lat=[None],
            mode='markers',
            marker=dict(size=15, color=color),
            name=f"{nombre_clase} ({rango_texto})",
            showlegend=True
        ))
    
    # Calcular centro y zoom
    if center_lat is None or center_lon is None:
        all_bounds = gdf_filtrado.total_bounds  # [minx, miny, maxx, maxy]
        center_lon = (all_bounds[0] + all_bounds[2]) / 2
        center_lat = (all_bounds[1] + all_bounds[3]) / 2
    
    if zoom is None:
        all_bounds = gdf_filtrado.total_bounds
        lat_range = all_bounds[3] - all_bounds[1]
        lon_range = all_bounds[2] - all_bounds[0]
        max_range = max(lat_range, lon_range) * 1.15
        
        if max_range < 0.003: zoom = 17
        elif max_range < 0.006: zoom = 16
        elif max_range < 0.01: zoom = 15
        elif max_range < 0.02: zoom = 14
        elif max_range < 0.05: zoom = 13
        else: zoom = 12
    
    fig.update_layout(
        mapbox=dict(
            style="white-bg",
            center=dict(lat=center_lat, lon=center_lon),
            zoom=zoom,
            layers=[{
                "below": "traces",
                "sourcetype": "raster",
                "source": ["https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"]
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
            font=dict(size=11)
        )
    )
    
    return fig


def mostrar_metricas_zonas_manejo(gdf_zonas, indice, fecha=None):
    """Muestra métricas de zonas de manejo por superficie."""
    if gdf_zonas is None or len(gdf_zonas) == 0:
        return
    
    gdf_filtrado = gdf_zonas[gdf_zonas['indice'] == indice].copy()
    
    if fecha and 'fecha_vuelo' in gdf_filtrado.columns:
        gdf_filtrado = gdf_filtrado[gdf_filtrado['fecha_vuelo'].astype(str) == str(fecha)]
    
    if len(gdf_filtrado) == 0:
        return
    
    resumen = gdf_filtrado.groupby('clase').agg({
        'area_ha': 'sum',
        'n_arboles': 'sum'
    }).reset_index()
    
    total_ha = resumen['area_ha'].sum()
    
    cols = st.columns(4)
    
    with cols[0]:
        st.metric("📐 Superficie Total", f"{total_ha:.2f} ha")
    
    for i, clase in enumerate([1, 2, 3]):
        row = resumen[resumen['clase'] == clase]
        if len(row) > 0:
            area = row['area_ha'].values[0]
            pct = (area / total_ha * 100) if total_ha > 0 else 0
            nombre = NOMBRES_ZONAS_MANEJO.get(clase, f'Clase {clase}')
            
            with cols[i + 1]:
                st.metric(f"{nombre}", f"{area:.2f} ha", f"{pct:.1f}%")


def mostrar_explicacion_zonas_manejo():
    """Muestra explicación de qué son las zonas de manejo."""
    st.info("""
    **📍 ¿Qué son las Zonas de Manejo?**
    
    Las Zonas de Manejo agrupan la información de los índices espectrales en **3 categorías operativas** 
    (Baja, Media, Alta) para facilitar la **toma de decisiones agronómicas** a nivel de campo.
    
    A diferencia del análisis por árbol individual, las zonas de manejo representan **superficies continuas** 
    donde se puede aplicar un manejo diferenciado:
    
    - 🔴 **Zona Baja**: Requiere intervención prioritaria (fertilización, riego, control fitosanitario)
    - 🟡 **Zona Media**: Monitorear evolución, manejo estándar
    - 🟢 **Zona Alta**: Mantener manejo actual, vegetación en óptimas condiciones
    
    Esta zonificación permite planificar aplicaciones de **dosis variable** y optimizar recursos.
    """)


# =============================================================================
# COMPONENTES DE GRÁFICOS
# =============================================================================

def crear_grafico_distribucion(df, indice, titulo=""):
    """Gráfico de distribución por clase."""
    col_clase = f"{indice}_clase"
    if col_clase not in df.columns:
        return None
    
    df_plot = df.copy()
    df_plot['clase_simple'] = df_plot[col_clase].apply(clasificar_punto)
    
    conteo = df_plot['clase_simple'].value_counts().reset_index()
    conteo.columns = ['Clase', 'Cantidad']
    conteo['Porcentaje'] = (conteo['Cantidad'] / conteo['Cantidad'].sum() * 100).round(1)
    
    # Ordenar
    orden_map = {c: i for i, c in enumerate(ORDEN_CLASES)}
    conteo['orden'] = conteo['Clase'].map(lambda x: orden_map.get(x, 99))
    conteo = conteo.sort_values('orden')
    conteo['Color'] = conteo['Clase'].apply(lambda x: COLORES_CLASE.get(x, '#999'))
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=conteo['Clase'], 
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
        margin=dict(l=50, r=30, t=50, b=60)
    )
    return fig


def crear_grafico_zonas_manejo(gdf_zonas, indice, titulo=""):
    """
    Gráfico de distribución de zonas de manejo por área.
    FIX v9.1: Etiquetas muestran % y superficie (ha)
    """
    if gdf_zonas is None or len(gdf_zonas) == 0:
        return None
    
    gdf_filtrado = gdf_zonas[gdf_zonas['indice'] == indice].copy()
    
    if len(gdf_filtrado) == 0:
        return None
    
    resumen = gdf_filtrado.groupby('clase').agg({'area_ha': 'sum'}).reset_index()
    resumen['nombre'] = resumen['clase'].map(NOMBRES_ZONAS_MANEJO)
    resumen['color'] = resumen['clase'].map(COLORES_ZONAS_MANEJO)
    resumen['pct'] = (resumen['area_ha'] / resumen['area_ha'].sum() * 100).round(1)
    resumen = resumen.sort_values('clase')
    
    # FIX: Crear etiqueta con % y superficie
    resumen['etiqueta'] = resumen.apply(
        lambda row: f"{row['pct']:.1f}%<br>{row['area_ha']:.2f} ha", 
        axis=1
    )
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=resumen['nombre'],
        y=resumen['area_ha'],
        marker_color=resumen['color'],
        text=resumen['etiqueta'],
        textposition='outside',
        textfont=dict(size=11)
    ))
    
    # Ajustar rango Y para que quepan las etiquetas
    y_max = resumen['area_ha'].max() * 1.35
    
    fig.update_layout(
        title=dict(text=titulo or f"Zonas de Manejo - {indice.upper()}", font=dict(size=14)),
        xaxis_title="",
        yaxis_title="Superficie (ha)",
        yaxis=dict(range=[0, y_max]),
        showlegend=False,
        height=350,
        margin=dict(l=50, r=30, t=50, b=60)
    )
    
    return fig


def mostrar_kpis(df, indice, prefix="", info_superficie=None):
    """Muestra KPIs."""
    if info_superficie:
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
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if indice in df.columns:
                st.metric(f"📊 {indice.upper()} μ", f"{df[indice].mean():.3f}")
        with col2:
            pct_sanos = calcular_pct_sanos(df, indice)
            st.metric("✅ % Sanos", f"{pct_sanos:.1f}%")
        with col3:
            if 'altura_m' in df.columns and df['altura_m'].notna().any():
                st.metric("📏 Altura μ", f"{df['altura_m'].mean():.2f} m")
        with col4:
            if indice in df.columns:
                st.metric(f"📉 {indice.upper()} σ", f"{df[indice].std():.3f}")
    else:
        cols = st.columns(5)
        with cols[0]:
            st.metric(f"{prefix}🌳 Árboles", f"{len(df):,}")
        with cols[1]:
            if indice in df.columns:
                st.metric(f"📊 {indice.upper()} μ", f"{df[indice].mean():.3f}")
        with cols[2]:
            pct_sanos = calcular_pct_sanos(df, indice)
            st.metric("✅ % Sanos", f"{pct_sanos:.1f}%")
        with cols[3]:
            if 'altura_m' in df.columns and df['altura_m'].notna().any():
                st.metric("📏 Altura μ", f"{df['altura_m'].mean():.2f} m")
        with cols[4]:
            if 'Cuartel' in df.columns:
                st.metric("📍 Cuarteles", df['Cuartel'].nunique())


# =============================================================================
# TAB RESUMEN CON ZONAS DE MANEJO
# =============================================================================

def filtrar_zonas_manejo(gdf_zonas, df_puntos_filtrado, fechas_sel=None, cultivo_sel=None):
    """
    Filtra las zonas de manejo según los mismos criterios aplicados a los puntos.
    Esto asegura que ambas visualizaciones (puntos y zonas) muestren los mismos cuarteles/fechas/cultivo.
    """
    if gdf_zonas is None or len(gdf_zonas) == 0:
        return None
    
    gdf_filtrado = gdf_zonas.copy()
    
    # Filtrar por cultivo si está disponible
    if cultivo_sel and cultivo_sel != 'Todos':
        if 'cultivo' in gdf_filtrado.columns:
            gdf_filtrado = gdf_filtrado[gdf_filtrado['cultivo'] == cultivo_sel]
        elif 'Cultivo' in gdf_filtrado.columns:
            gdf_filtrado = gdf_filtrado[gdf_filtrado['Cultivo'] == cultivo_sel]
    
    # Filtrar por cuarteles presentes en los puntos filtrados
    if 'Cuartel' in df_puntos_filtrado.columns and 'cuartel' in gdf_filtrado.columns:
        cuarteles_en_puntos = df_puntos_filtrado['Cuartel'].unique().tolist()
        gdf_filtrado = gdf_filtrado[gdf_filtrado['cuartel'].isin(cuarteles_en_puntos)]
    
    # Filtrar por fechas seleccionadas
    if fechas_sel and len(fechas_sel) > 0 and 'fecha_vuelo' in gdf_filtrado.columns:
        gdf_filtrado = gdf_filtrado[gdf_filtrado['fecha_vuelo'].astype(str).isin(fechas_sel)]
    
    return gdf_filtrado if len(gdf_filtrado) > 0 else None


def tab_resumen(df, indice, fechas_sel, radio_puntos, gdf_poligonos=None, gdf_zonas_manejo=None, cultivo_sel=None):
    """Tab Resumen con comparación lado a lado y zonas de manejo."""
    
    # Filtrar zonas de manejo según los mismos criterios que los puntos
    gdf_zonas_filtrado = filtrar_zonas_manejo(gdf_zonas_manejo, df, fechas_sel, cultivo_sel)
    
    mostrar_descripcion_indice(indice)
    
    fechas_unicas = []
    if 'fecha_vuelo' in df.columns:
        fechas_unicas = sorted([str(f) for f in df['fecha_vuelo'].dropna().unique()])
    
    n_vuelos = len(fechas_unicas)
    mostrar_comparacion = n_vuelos >= 2
    
    info_sup = obtener_info_superficie(df, gdf_poligonos)
    
    # Calcular centro y zoom común para mapas sincronizados
    all_lats = df['lat'].dropna()
    all_lons = df['lon'].dropna()
    
    if len(all_lats) > 0 and len(all_lons) > 0:
        center_lat = all_lats.mean()
        center_lon = all_lons.mean()
        lat_range = all_lats.max() - all_lats.min()
        lon_range = all_lons.max() - all_lons.min()
        max_range = max(lat_range, lon_range) * 1.15
        
        if max_range < 0.003: zoom_comun = 17
        elif max_range < 0.006: zoom_comun = 16
        elif max_range < 0.01: zoom_comun = 15
        elif max_range < 0.02: zoom_comun = 14
        elif max_range < 0.05: zoom_comun = 13
        else: zoom_comun = 12
    else:
        center_lat, center_lon, zoom_comun = -35.01, -71.34, 14
    
    if mostrar_comparacion:
        st.subheader(f"📊 Comparación de {n_vuelos} Vuelos")
        
        # Preparar datos para cada vuelo
        dfs_vuelos = []
        infos_sup = []
        for fecha in fechas_unicas:
            df_vuelo = df[df['fecha_vuelo'].astype(str) == fecha]
            dfs_vuelos.append(df_vuelo)
            infos_sup.append(obtener_info_superficie(df_vuelo, gdf_poligonos))
        
        # KPIs por vuelo
        cols = st.columns(n_vuelos)
        for i, (fecha, df_vuelo, info_sup_vuelo) in enumerate(zip(fechas_unicas, dfs_vuelos, infos_sup)):
            with cols[i]:
                st.markdown(f"### 📅 Vuelo: {fecha}")
                mostrar_kpis(df_vuelo, indice, info_superficie=info_sup_vuelo)
        
        st.markdown("---")
        st.subheader("🗺️ Mapas de Puntos Individuales")
        
        # Mapas de puntos
        cols = st.columns(n_vuelos)
        for i, (fecha, df_vuelo) in enumerate(zip(fechas_unicas, dfs_vuelos)):
            with cols[i]:
                st.markdown(f"**{fecha}**")
                df_sample = df_vuelo.sample(n=min(8000, len(df_vuelo)), random_state=42) if len(df_vuelo) > 10000 else df_vuelo
                mapa = crear_mapa_plotly_satelite(
                    df_sample, indice, radio_puntos, 
                    f"{indice.upper()} - {fecha}", gdf_poligonos,
                    center_lat=center_lat, center_lon=center_lon, zoom=zoom_comun
                )
                if mapa:
                    mapa.update_layout(uirevision='mapas_sincronizados')
                    st.plotly_chart(mapa, use_container_width=True, key=f"mapa_puntos_{i}")
        
        st.markdown("---")
        
        # Gráficos de distribución
        cols = st.columns(n_vuelos)
        for i, (fecha, df_vuelo) in enumerate(zip(fechas_unicas, dfs_vuelos)):
            with cols[i]:
                fig = crear_grafico_distribucion(df_vuelo, indice, f"Distribución - {fecha}")
                if fig:
                    fig.update_layout(height=300)
                    st.plotly_chart(fig, use_container_width=True, key=f"dist_{i}")
        
        # === SECCIÓN ZONAS DE MANEJO ===
        if gdf_zonas_filtrado is not None and len(gdf_zonas_filtrado) > 0:
            st.markdown("---")
            st.subheader("📍 Zonas de Manejo")
            mostrar_explicacion_zonas_manejo()
            
            # Métricas por vuelo
            cols = st.columns(n_vuelos)
            for i, fecha in enumerate(fechas_unicas):
                with cols[i]:
                    st.markdown(f"**📊 Métricas - {fecha}**")
                    mostrar_metricas_zonas_manejo(gdf_zonas_filtrado, indice, fecha)
            
            st.markdown("---")
            
            # Mapas de zonas de manejo
            cols = st.columns(n_vuelos)
            for i, fecha in enumerate(fechas_unicas):
                with cols[i]:
                    st.markdown(f"**🗺️ Zonas - {fecha}**")
                    gdf_zm = gdf_zonas_filtrado[
                        (gdf_zonas_filtrado['indice'] == indice) & 
                        (gdf_zonas_filtrado['fecha_vuelo'].astype(str) == fecha)
                    ]
                    if len(gdf_zm) > 0:
                        mapa_zm = crear_mapa_zonas_manejo(gdf_zm, indice, center_lat=center_lat, center_lon=center_lon, zoom=zoom_comun)
                        if mapa_zm:
                            st.plotly_chart(mapa_zm, use_container_width=True, key=f"mapa_zm_{i}")
                    else:
                        st.info("No hay zonas para este vuelo/cuartel")
            
            # Gráficos de zonas
            st.markdown("---")
            cols = st.columns(n_vuelos)
            for i, fecha in enumerate(fechas_unicas):
                with cols[i]:
                    gdf_zm = gdf_zonas_filtrado[
                        (gdf_zonas_filtrado['indice'] == indice) & 
                        (gdf_zonas_filtrado['fecha_vuelo'].astype(str) == fecha)
                    ]
                    fig = crear_grafico_zonas_manejo(gdf_zm, indice, f"Zonas - {fecha}")
                    if fig:
                        fig.update_layout(height=300)
                        st.plotly_chart(fig, use_container_width=True, key=f"graf_zm_{i}")
    
    else:
        # Vista de un solo vuelo
        mostrar_kpis(df, indice, info_superficie=info_sup)
        st.markdown("---")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.subheader(f"🗺️ Mapa de Puntos - {indice.upper()}")
            df_mapa = df.sample(n=min(10000, len(df)), random_state=42) if len(df) > 12000 else df
            mapa = crear_mapa_plotly_satelite(df_mapa, indice, radio_puntos, gdf_poligonos=gdf_poligonos)
            if mapa:
                st.plotly_chart(mapa, use_container_width=True, key="mapa_single")
        
        with col2:
            st.subheader("📊 Distribución")
            fig = crear_grafico_distribucion(df, indice)
            if fig:
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)
        
        # === SECCIÓN ZONAS DE MANEJO (Vista individual) ===
        if gdf_zonas_filtrado is not None and len(gdf_zonas_filtrado) > 0:
            st.markdown("---")
            st.subheader("📍 Zonas de Manejo")
            mostrar_explicacion_zonas_manejo()
            
            gdf_zm_filtrado = gdf_zonas_filtrado[gdf_zonas_filtrado['indice'] == indice].copy()
            
            if fechas_sel and len(fechas_sel) == 1 and 'fecha_vuelo' in gdf_zm_filtrado.columns:
                gdf_zm_filtrado = gdf_zm_filtrado[gdf_zm_filtrado['fecha_vuelo'].astype(str) == fechas_sel[0]]
            
            if len(gdf_zm_filtrado) > 0:
                mostrar_metricas_zonas_manejo(gdf_zm_filtrado, indice)
                
                st.markdown("---")
                
                col1, col2 = st.columns([3, 2])
                with col1:
                    st.markdown(f"**🗺️ Mapa Zonas de Manejo**")
                    mapa_zm = crear_mapa_zonas_manejo(gdf_zm_filtrado, indice)
                    if mapa_zm:
                        st.plotly_chart(mapa_zm, use_container_width=True, key="mapa_zm_single")
                
                with col2:
                    st.markdown("**📊 Distribución por Zona**")
                    fig_zm = crear_grafico_zonas_manejo(gdf_zm_filtrado, indice)
                    if fig_zm:
                        fig_zm.update_layout(height=500)
                        st.plotly_chart(fig_zm, use_container_width=True)
            else:
                st.info(f"No hay zonas de manejo disponibles para {indice.upper()} con los filtros seleccionados")


# =============================================================================
# OTROS TABS
# =============================================================================

def tab_analisis(df, indice, fechas_sel):
    """Tab Análisis con comparación de múltiples vuelos."""
    mostrar_descripcion_indice(indice)
    
    if indice not in df.columns:
        st.warning("Índice no disponible")
        return
    
    # Verificar si hay múltiples vuelos
    fechas_unicas = []
    if 'fecha_vuelo' in df.columns:
        fechas_unicas = sorted([str(f) for f in df['fecha_vuelo'].dropna().unique()])
    
    n_vuelos = len(fechas_unicas)
    mostrar_comparacion = n_vuelos >= 2
    
    if mostrar_comparacion:
        # === HISTOGRAMAS COMPARATIVOS ===
        st.subheader("📊 Histogramas por Vuelo")
        
        cols = st.columns(n_vuelos)
        for i, fecha in enumerate(fechas_unicas):
            df_vuelo = df[df['fecha_vuelo'].astype(str) == fecha]
            with cols[i]:
                st.markdown(f"**{fecha}**")
                fig = px.histogram(df_vuelo, x=indice, nbins=40, color_discrete_sequence=['#1a9641'])
                media = df_vuelo[indice].mean()
                fig.add_vline(x=media, line_dash="dash", line_color="red", annotation_text=f"μ={media:.3f}")
                fig.update_layout(height=300, margin=dict(l=40, r=20, t=30, b=40))
                st.plotly_chart(fig, use_container_width=True, key=f"hist_{i}")
        
        st.markdown("---")
        
        # === BOXPLOTS POR CUARTEL Y VUELO ===
        st.subheader("📦 Distribución por Cuartel")
        
        if 'Cuartel' in df.columns:
            cols = st.columns(n_vuelos)
            for i, fecha in enumerate(fechas_unicas):
                df_vuelo = df[df['fecha_vuelo'].astype(str) == fecha]
                with cols[i]:
                    st.markdown(f"**{fecha}**")
                    fig = px.box(df_vuelo, x='Cuartel', y=indice, color='Cuartel')
                    fig.update_layout(height=350, showlegend=False, margin=dict(l=40, r=20, t=30, b=60))
                    st.plotly_chart(fig, use_container_width=True, key=f"box_{i}")
        
        st.markdown("---")
        
        # === ESTADÍSTICAS DESCRIPTIVAS POR VUELO ===
        st.subheader("📈 Estadísticas Descriptivas por Vuelo")
        
        stats_list = []
        for fecha in fechas_unicas:
            df_vuelo = df[df['fecha_vuelo'].astype(str) == fecha]
            if len(df_vuelo) > 0 and indice in df_vuelo.columns:
                stats = df_vuelo[indice].describe()
                stats_dict = {
                    'Fecha': fecha,
                    'N': int(stats['count']),
                    'Media': round(stats['mean'], 3),
                    'Std': round(stats['std'], 3),
                    'Min': round(stats['min'], 3),
                    '25%': round(stats['25%'], 3),
                    '50%': round(stats['50%'], 3),
                    '75%': round(stats['75%'], 3),
                    'Max': round(stats['max'], 3)
                }
                stats_list.append(stats_dict)
        
        if stats_list:
            df_stats = pd.DataFrame(stats_list)
            st.dataframe(df_stats, use_container_width=True, hide_index=True)
        
        # === BOXPLOT COMPARATIVO GENERAL ===
        st.markdown("---")
        st.subheader("📊 Comparación General entre Vuelos")
        
        df_plot = df.copy()
        df_plot['fecha_str'] = df_plot['fecha_vuelo'].astype(str)
        
        fig = px.box(df_plot, x='fecha_str', y=indice, color='fecha_str',
                     labels={'fecha_str': 'Fecha de Vuelo', indice: indice.upper()})
        fig.update_layout(
            height=400, 
            showlegend=False,
            xaxis=dict(
                type='category',
                categoryorder='array',
                categoryarray=sorted(fechas_unicas)
            )
        )
        st.plotly_chart(fig, use_container_width=True)
    
    else:
        # Vista de un solo vuelo (comportamiento original)
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Histograma")
            fig = px.histogram(df, x=indice, nbins=40, color_discrete_sequence=['#1a9641'])
            media = df[indice].mean()
            fig.add_vline(x=media, line_dash="dash", line_color="red", annotation_text=f"μ={media:.3f}")
            fig.update_layout(height=350)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("📦 Por Cuartel")
            if 'Cuartel' in df.columns:
                fig = px.box(df, x='Cuartel', y=indice, color='Cuartel')
                fig.update_layout(height=350, showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        st.subheader("📈 Estadísticas Descriptivas")
        if indice in df.columns:
            stats = df[indice].describe().round(3)
            st.dataframe(stats, use_container_width=True)


def tab_comparacion(df, indice):
    """Tab Comparación con análisis temporal mejorado."""
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
    df_valid['clase_simple'] = df_valid[col_clase].apply(clasificar_punto)
    df_valid['fecha_str'] = df_valid['fecha_vuelo'].astype(str)
    
    # Crear pivot y ordenar por fecha
    pivot = df_valid.groupby(['fecha_str', 'clase_simple']).size().unstack(fill_value=0)
    pivot_pct = pivot.div(pivot.sum(axis=1), axis=0) * 100
    
    # Ordenar índice por fecha
    pivot_pct = pivot_pct.sort_index()
    
    fig = go.Figure()
    for clase in ORDEN_CLASES:
        if clase in pivot_pct.columns:
            fig.add_trace(go.Bar(
                name=clase, 
                x=pivot_pct.index.tolist(),  # Usar lista de strings
                y=pivot_pct[clase], 
                marker_color=COLORES_CLASE.get(clase, '#999')
            ))
    
    fig.update_layout(
        barmode='stack', 
        height=400, 
        xaxis_title="Fecha de Vuelo",
        yaxis_title="Porcentaje (%)",
        xaxis=dict(
            type='category',  # Forzar tipo categórico para fechas
            categoryorder='array',
            categoryarray=sorted(pivot_pct.index.tolist())  # Ordenar fechas
        )
    )
    st.plotly_chart(fig, use_container_width=True)
    
    # === ANÁLISIS COMPARATIVO ===
    st.markdown("---")
    st.subheader("📈 Análisis Comparativo por Vuelo")
    
    n_vuelos = len(fechas_unicas)
    
    # Estadísticas por vuelo
    cols = st.columns(n_vuelos)
    stats_vuelos = []
    
    for i, fecha in enumerate(fechas_unicas):
        df_vuelo = df_valid[df_valid['fecha_str'] == fecha]
        
        if len(df_vuelo) > 0 and indice in df_vuelo.columns:
            stats = {
                'fecha': fecha,
                'n_arboles': len(df_vuelo),
                'media': df_vuelo[indice].mean(),
                'std': df_vuelo[indice].std(),
                'min': df_vuelo[indice].min(),
                'max': df_vuelo[indice].max(),
                'pct_sanos': calcular_pct_sanos(df_vuelo, indice)
            }
            stats_vuelos.append(stats)
            
            with cols[i]:
                st.markdown(f"**📅 {fecha}**")
                st.metric(f"{indice.upper()} μ", f"{stats['media']:.3f}")
                st.metric("% Sanos", f"{stats['pct_sanos']:.1f}%")
                st.metric("N° Árboles", f"{stats['n_arboles']:,}")
    
    # Tabla comparativa
    if len(stats_vuelos) > 1:
        st.markdown("---")
        st.subheader("📋 Tabla Comparativa")
        
        df_stats = pd.DataFrame(stats_vuelos)
        df_stats.columns = ['Fecha', 'N° Árboles', f'{indice.upper()} Media', 'Desv. Std', 'Mínimo', 'Máximo', '% Sanos']
        df_stats[f'{indice.upper()} Media'] = df_stats[f'{indice.upper()} Media'].round(3)
        df_stats['Desv. Std'] = df_stats['Desv. Std'].round(3)
        df_stats['Mínimo'] = df_stats['Mínimo'].round(3)
        df_stats['Máximo'] = df_stats['Máximo'].round(3)
        df_stats['% Sanos'] = df_stats['% Sanos'].round(1)
        
        st.dataframe(df_stats, use_container_width=True, hide_index=True)
        
        # Gráfico de evolución temporal
        st.markdown("---")
        st.subheader("📈 Evolución Temporal")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Gráfico de media por fecha
            fig_evol = go.Figure()
            fig_evol.add_trace(go.Scatter(
                x=df_stats['Fecha'],
                y=df_stats[f'{indice.upper()} Media'],
                mode='lines+markers',
                name=f'{indice.upper()} Media',
                line=dict(color='#1a9641', width=3),
                marker=dict(size=10)
            ))
            fig_evol.update_layout(
                title=f"Evolución {indice.upper()} Promedio",
                xaxis_title="Fecha de Vuelo",
                yaxis_title=f"{indice.upper()}",
                height=300,
                xaxis=dict(type='category')
            )
            st.plotly_chart(fig_evol, use_container_width=True)
        
        with col2:
            # Gráfico de % sanos por fecha
            fig_sanos = go.Figure()
            fig_sanos.add_trace(go.Scatter(
                x=df_stats['Fecha'],
                y=df_stats['% Sanos'],
                mode='lines+markers',
                name='% Sanos',
                line=dict(color='#2166ac', width=3),
                marker=dict(size=10)
            ))
            fig_sanos.update_layout(
                title="Evolución % Árboles Sanos",
                xaxis_title="Fecha de Vuelo",
                yaxis_title="% Sanos",
                height=300,
                xaxis=dict(type='category')
            )
            st.plotly_chart(fig_sanos, use_container_width=True)


def tab_datos(df, indices_disponibles):
    """Tab Datos."""
    st.subheader("🔍 Explorador de Datos")
    
    cols_base = ['id', 'Cuartel', 'Especie', 'Variedad', 'lat', 'lon']
    cols_base = [c for c in cols_base if c in df.columns]
    
    if 'fecha_vuelo' in df.columns:
        cols_base.append('fecha_vuelo')
    
    cols_indices = []
    for idx in indices_disponibles[:2]:  # Solo primeros 2 índices
        if idx in df.columns:
            cols_indices.append(idx)
        col_clase = f"{idx}_clase"
        if col_clase in df.columns:
            cols_indices.append(col_clase)
    
    columnas = cols_base + cols_indices
    columnas = list(dict.fromkeys(columnas))
    
    df_mostrar = df[columnas].copy()
    st.dataframe(df_mostrar, use_container_width=True, height=500)
    
    st.markdown("---")
    csv = df_mostrar.to_csv(index=False)
    st.download_button(
        "📥 Descargar datos (CSV)",
        csv,
        f"datos_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        "text/csv"
    )


# =============================================================================
# SIDEBAR Y MAIN
# =============================================================================

def crear_sidebar(df):
    """Sidebar con filtros en cascada."""
    df_filtrado = df.copy()
    fechas_sel = []
    cultivo_sel = 'Todos'  # Valor por defecto
    
    with st.sidebar:
        mostrar_logo_sidebar()
        
        st.markdown("---")
        st.header("🔍 Filtros")
        
        # Filtro de cultivo
        if 'cultivo' in df.columns:
            cultivos = ['Todos'] + sorted(df['cultivo'].dropna().unique().tolist())
            cultivo_sel = st.selectbox("🌱 Cultivo", cultivos)
            if cultivo_sel != 'Todos':
                df_filtrado = df_filtrado[df_filtrado['cultivo'] == cultivo_sel]
        
        # Filtro de fecha
        if 'fecha_vuelo' in df_filtrado.columns:
            fechas_disponibles = sorted([str(f) for f in df_filtrado['fecha_vuelo'].dropna().unique()])
            
            modo_fecha = st.radio(
                "📅 Modo de visualización",
                ["Comparar todos", "Seleccionar vuelos"],
                horizontal=True,
                label_visibility="collapsed"
            )
            
            if modo_fecha == "Comparar todos":
                fechas_sel = fechas_disponibles
                st.info(f"📅 Comparando {len(fechas_disponibles)} vuelos")
            else:
                fechas_sel = st.multiselect(
                    "📅 Seleccionar Vuelos",
                    fechas_disponibles,
                    default=fechas_disponibles[:1] if fechas_disponibles else []
                )
                if not fechas_sel:
                    fechas_sel = fechas_disponibles
            
            if fechas_sel:
                df_filtrado = df_filtrado[df_filtrado['fecha_vuelo'].astype(str).isin(fechas_sel)]
        
        # Filtro de variedad
        if 'Variedad' in df_filtrado.columns:
            variedades = ['Todas'] + sorted(df_filtrado['Variedad'].dropna().unique().tolist())
            variedad_sel = st.selectbox("🍒 Variedad", variedades)
            if variedad_sel != 'Todas':
                df_filtrado = df_filtrado[df_filtrado['Variedad'] == variedad_sel]
        
        # Filtro de cuarteles
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
        
        INDICES_PERMITIDOS = ['ndvi', 'osavi', 'ndre', 'lci']
        indices = [k for k in INDICES_PERMITIDOS if k in df.columns and k in INDICES_INFO]
        
        indice_sel = st.selectbox(
            "Seleccionar", 
            indices, 
            format_func=lambda x: f"{INDICES_INFO[x]['nombre']} ({INDICES_INFO[x]['categoria']})"
        ) if indices else None
        
        st.markdown("---")
        st.header("⚙️ Visualización")
        radio_puntos = st.slider("Tamaño puntos", 1, 8, 1, 1)
        
        st.markdown("---")
        st.header("🎨 Leyenda Puntos (7 Clases)")
        for clase in ORDEN_CLASES:
            color = COLORES_CLASE.get(clase, '#999')
            st.markdown(f'<span style="background-color:{color}; padding: 2px 10px; border-radius: 3px;">&nbsp;</span> {clase}', unsafe_allow_html=True)
        
        st.markdown("---")
        st.header("🎨 Leyenda Zonas (3 Clases)")
        for clase in [1, 2, 3]:
            color = COLORES_ZONAS_MANEJO.get(clase, '#999')
            nombre = NOMBRES_ZONAS_MANEJO.get(clase, '')
            st.markdown(f'<span style="background-color:{color}; padding: 2px 10px; border-radius: 3px;">&nbsp;</span> {nombre}', unsafe_allow_html=True)
        
        st.markdown("---")
        st.caption(f"📊 {len(df_filtrado):,} árboles filtrados")
    
    return df_filtrado, indice_sel, radio_puntos, fechas_sel, indices, cultivo_sel


def main():
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
        st.sidebar.success(f"✅ Polígonos: {len(gdf_poligonos)} cuarteles")
    
    # Cargar zonas de manejo
    gdf_zonas_manejo = cargar_zonas_manejo(ZONAS_MANEJO_PATH)
    if gdf_zonas_manejo is not None:
        st.sidebar.success(f"✅ Zonas manejo: {len(gdf_zonas_manejo)} zonas")
    
    df_filtrado, indice_sel, radio_puntos, fechas_sel, indices_disponibles, cultivo_sel = crear_sidebar(df)
    
    if indice_sel is None:
        st.warning("No hay índices disponibles")
        return
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Resumen", "📈 Análisis", "📅 Comparación", "🔍 Datos"])
    
    with tab1:
        tab_resumen(df_filtrado, indice_sel, fechas_sel, radio_puntos, gdf_poligonos, gdf_zonas_manejo, cultivo_sel)
    
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
        <p><a href="https://www.temapeo.com" target="_blank">www.temapeo.com</a> | v9.3 - Análisis Comparativo Mejorado</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
