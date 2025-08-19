# app.py
# -*- coding: utf-8 -*-

import streamlit as st
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip, CompositeVideoClip, vfx
import uuid # Para generar nombres de archivo únicos

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="Generador de Vídeos",
    page_icon="🎬",
    layout="centered"
)

# --- FUNCIONES NÚCLEO (ligeramente adaptadas) ---
def ajustar_y_procesar_imagen(ruta_imagen, tamano_salida, titulo_info, subtitulo_texto=None):
    """
    Abre una imagen, la redimensiona para que quepa en el formato vertical,
    crea un fondo desenfocado y añade los textos.
    """
    img = Image.open(ruta_imagen).convert("RGBA")
    fondo = img.resize(tamano_salida, Image.LANCZOS).filter(ImageFilter.GaussianBlur(radius=30))
    img.thumbnail(tamano_salida, Image.LANCZOS)
    
    lienzo = Image.new("RGBA", tamano_salida)
    lienzo.paste(fondo, (0, 0))
    pos_x = (tamano_salida[0] - img.width) // 2
    pos_y = (tamano_salida[1] - img.height) // 2
    lienzo.paste(img, (pos_x, pos_y), img)
    
    draw = ImageDraw.Draw(lienzo)

    # Añadir Título
    if titulo_info['texto']:
        try:
            fuente_titulo = ImageFont.truetype(titulo_info['fuente_path'], titulo_info['tamano'])
        except (IOError, TypeError):
            fuente_titulo = ImageFont.load_default() # Fuente por defecto si no se encuentra
        
        ancho_texto, alto_texto = draw.textsize(titulo_info['texto'], font=fuente_titulo)
        pos_titulo_x = (tamano_salida[0] - ancho_texto) // 2
        pos_titulo_y = 100
        
        draw.text((pos_titulo_x + 3, pos_titulo_y + 3), titulo_info['texto'], font=fuente_titulo, fill=titulo_info['color_sombra'])
        draw.text((pos_titulo_x, pos_titulo_y), titulo_info['texto'], font=fuente_titulo, fill=titulo_info['color'])

    # Añadir Subtítulo
    if subtitulo_texto:
        try:
            fuente_subtitulo = ImageFont.truetype(titulo_info['fuente_path'], titulo_info['tamano_sub'])
        except (IOError, TypeError):
            fuente_subtitulo = ImageFont.load_default()
            
        ancho_sub, alto_sub = draw.textsize(subtitulo_texto, font=fuente_subtitulo)
        pos_sub_x = (tamano_salida[0] - ancho_sub) // 2
        pos_sub_y = tamano_salida[1] - alto_sub - 150
        
        draw.text((pos_sub_x + 2, pos_sub_y + 2), subtitulo_texto, font=fuente_subtitulo, fill=titulo_info['color_sombra'])
        draw.text((pos_sub_x, pos_sub_y), subtitulo_texto, font=fuente_subtitulo, fill=titulo_info['color_sub'])

    return lienzo.convert("RGB")

# --- INTERFAZ DE STREAMLIT ---

st.title("🎬 Generador Automático de Vídeos Verticales")
st.markdown("Crea vídeos para Reels, Shorts o TikToks a partir de tus fotos y música en segundos.")

# --- FORMULARIO DE CONFIGURACIÓN ---
with st.sidebar:
    st.header("⚙️ Configuración del Vídeo")
    
    # 1. Entradas de archivos
    st.subheader("1. Sube tus Archivos")
    fotos_subidas = st.file_uploader(
        "Sube tus fotos (en orden)", 
        type=['jpg', 'jpeg', 'png'], 
        accept_multiple_files=True
    )
    audio_subido = st.file_uploader("Sube tu archivo de música", type=['mp3'])
    
    # 2. Textos
    st.subheader("2. Personaliza los Textos")
    texto_titulo = st.text_input("Título principal del vídeo", "Mis Vacaciones ☀️")
    mostrar_titulo_en = st.selectbox(
        "¿Dónde mostrar el título?",
        ('En todas las fotos', 'Solo en la primera foto'),
        index=0
    )
    subtitulos_texto = st.text_area(
        "Subtítulos (uno por línea, en el mismo orden que las fotos)",
        "Día 1: La llegada\nDía 2: Explorando\nDía 3: Atardecer en la playa\nDía 4: Despedida"
    )

    # 3. Ajustes de vídeo
    st.subheader("3. Ajustes de Duración")
    duracion_foto = st.slider("Duración de cada foto (segundos)", 1.0, 10.0, 3.0, 0.5)
    transicion_duracion = st.slider("Duración de la transición (segundos)", 0.1, 2.0, 0.5, 0.1)

# --- LÓGICA DE GENERACIÓN ---
if st.button("✨ ¡Generar Vídeo!"):
    if not fotos_subidas:
        st.warning("Por favor, sube al menos una foto.")
    elif not audio_subido:
        st.warning("Por favor, sube un archivo de audio.")
    else:
        with st.spinner('Procesando... El vídeo se está creando. ¡Esto puede tardar unos minutos!'):
            # Crear directorio temporal para los archivos
            temp_dir = "temp_files"
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            
            # Guardar archivos subidos
            rutas_fotos = []
            for foto in fotos_subidas:
                ruta = os.path.join(temp_dir, foto.name)
                with open(ruta, "wb") as f:
                    f.write(foto.getbuffer())
                rutas_fotos.append(ruta)

            ruta_audio = os.path.join(temp_dir, audio_subido.name)
            with open(ruta_audio, "wb") as f:
                f.write(audio_subido.getbuffer())

            subtitulos = [s.strip() for s in subtitulos_texto.split('\n') if s.strip()]
            if subtitulos and len(subtitulos) != len(rutas_fotos):
                st.warning("El número de subtítulos no coincide con el de fotos. Se omitirán.")
                subtitulos = []

            # Procesamiento de imágenes y creación de clips
            clips_imagenes = []
            primera_imagen_procesada = None
            for i, ruta_foto in enumerate(rutas_fotos):
                titulo_actual = texto_titulo if (mostrar_titulo_en == 'En todas las fotos' or i == 0) else ""
                subtitulo_actual = subtitulos[i] if i < len(subtitulos) else None
                
                titulo_info = {
                    'texto': titulo_actual, 'fuente_path': None, 'tamano': 90, 
                    'color': "white", 'color_sombra': "black", 'tamano_sub': 60, 'color_sub': "white"
                }

                imagen_procesada_pil = ajustar_y_procesar_imagen(ruta_foto, (1080, 1920), titulo_info, subtitulo_actual)
                
                if i == 0:
                    primera_imagen_procesada = imagen_procesada_pil
                
                # Usar nombres únicos para evitar colisiones
                ruta_temporal_frame = os.path.join(temp_dir, f"frame_{uuid.uuid4()}.png")
                imagen_procesada_pil.save(ruta_temporal_frame)
                clips_imagenes.append(ImageClip(ruta_temporal_frame).set_duration(duracion_foto))

            # Creación del vídeo
            video_con_transiciones = [clips_imagenes[0]]
            for i in range(len(clips_imagenes) - 1):
                clip_actual = clips_imagenes[i+1].crossfadein(transicion_duracion)
                video_con_transiciones[-1] = video_con_transiciones[-1].set_end(video_con_transiciones[-1].end - transicion_duracion)
                video_con_transiciones.append(clip_actual)

            video_final = concatenate_videoclips(video_con_transiciones, method="compose")
            
            # Añadir audio
            audio_clip = AudioFileClip(ruta_audio)
            audio_clip = audio_clip.fx(vfx.loop, duration=video_final.duration)
            video_final.audio = audio_clip.subclip(0, video_final.duration)

            # Exportar
            video_salida_path = os.path.join(temp_dir, "evento_final.mp4")
            miniatura_salida_path = os.path.join(temp_dir, "thumbnail.jpg")
            
            video_final.write_videofile(video_salida_path, codec='libx264', audio_codec='aac', fps=24)
            if primera_imagen_procesada:
                primera_imagen_procesada.save(miniatura_salida_path, "JPEG")

            st.success("¡Vídeo generado con éxito!")

            # Mostrar y permitir la descarga
            video_file = open(video_salida_path, 'rb')
            video_bytes = video_file.read()
            st.video(video_bytes)

            st.download_button(
                label="📥 Descargar Vídeo (MP4)",
                data=video_bytes,
                file_name="video_generado.mp4",
                mime="video/mp4"
            )

            with open(miniatura_salida_path, "rb") as file:
                st.download_button(
                     label="🖼️ Descargar Miniatura (JPG)",
                     data=file,
                     file_name="miniatura.jpg",
                     mime="image/jpeg"
                )