# app.py
# -*- coding: utf-8 -*-

import streamlit as st
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from moviepy.video.VideoClip import ImageClip
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
from moviepy.audio.io.AudioFileClip import AudioFileClip
from moviepy import concatenate_videoclips
import uuid
import tempfile
import re

# --- NUEVO: intento de importar OpenCV / numpy ---
try:
	import cv2
	import numpy as np
	cv2_available = True
	_haarcascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
	if not os.path.exists(_haarcascade_path):
		_haarcascade_path = None
except Exception:
	cv2 = None
	np = None
	cv2_available = False
	_haarcascade_path = None

# --- nueva: detección simple de emoji ---
_emoji_re = re.compile(
	"[" 
	"\U0001F300-\U0001F5FF"
	"\U0001F600-\U0001F64F"
	"\U0001F680-\U0001F6FF"
	"\U0001F700-\U0001F77F"
	"\U0001F780-\U0001F7FF"
	"\U0001F800-\U0001F8FF"
	"\U0001F900-\U0001F9FF"
	"\U0001FA00-\U0001FA6F"
	"\U0001FA70-\U0001FAFF"
	"]", flags=re.UNICODE)

def contiene_emoji(s):
	if not s:
		return False
	return bool(_emoji_re.search(s))

# --- NUEVO: utilidades de detección y difuminado usando OpenCV ---
def detectar_caras_pil(img_pil):
	"""
	Devuelve lista de boxes (x,y,w,h) usando Haarcascade sobre imagen PIL.
	Si OpenCV no está disponible devuelve [].
	"""
	if not cv2_available or _haarcascade_path is None:
		return []
	arr = np.array(img_pil.convert("RGB"))
	gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
	cascade = cv2.CascadeClassifier(_haarcascade_path)
	faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
	return faces.tolist() if len(faces) else []

def es_menor_por_tamano(face_box, img_size, threshold_ratio):
	"""
	Heurística: si la altura de la cara < threshold_ratio * altura_imagen => considerar menor.
	"""
	x, y, w, h = face_box
	_, h_img = img_size
	return (h / float(h_img)) < float(threshold_ratio)

def difuminar_caras_en_pil(img_pil, boxes, blur_radius=15, expand_factor=0.25):
	"""
	Aplica GaussianBlur sobre cada box (con margen expand_factor).
	"""
	if not boxes:
		return img_pil
	img = img_pil.convert("RGBA")
	for (x, y, w, h) in boxes:
		exp_w = int(w * expand_factor)
		exp_h = int(h * expand_factor)
		x0 = max(0, x - exp_w)
		y0 = max(0, y - exp_h)
		x1 = min(img.width, x + w + exp_w)
		y1 = min(img.height, y + h + exp_h)
		region = img.crop((x0, y0, x1, y1))
		region = region.filter(ImageFilter.GaussianBlur(radius=blur_radius))
		img.paste(region, (x0, y0), region)
	return img

# --- nueva: carga de fuente escalable ---
def cargar_fuente(tamano, fuente_path=None, prefer_emoji=False):
	"""
	Intentar cargar una fuente TrueType escalable.
	Si prefer_emoji True, prueba fuentes emoji antes de las estándar.
	"""
	tamano = int(tamano) if tamano else 20
	posibles = []
	if prefer_emoji:
		# rutas comunes de fuentes emoji (macOS / Linux)
		posibles += [
			"/System/Library/Fonts/Apple Color Emoji.ttf",
			"/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
			"/usr/share/fonts/truetype/seguiemj.ttf",
			"/usr/share/fonts/truetype/ancient-scripts/Symbola.ttf"
		]
	if fuente_path:
		posibles.append(fuente_path)
	# rutas comunes en Linux / macOS / Windows (no-emoji)
	posibles += [
		"/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
		"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
		"/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
		"/usr/share/fonts/truetype/freefont/FreeSans.ttf",
		"/usr/share/fonts/truetype/msttcorefonts/Arial.ttf",
		"/Library/Fonts/Arial.ttf",
		"C:\\Windows\\Fonts\\Arial.ttf",
		"arial.ttf",
	]
	for p in posibles:
		try:
			if p and os.path.exists(p):
				# intenta cargar con tamaño
				return ImageFont.truetype(p, tamano)
		except Exception:
			continue
	# Intentar por nombre (Pillow puede resolver algunos nombres instalados)
	for name_try in ("DejaVuSans.ttf", "Arial.ttf", "LiberationSans-Regular.ttf"):
		try:
			return ImageFont.truetype(name_try, tamano)
		except Exception:
			continue
	# último recurso
	return ImageFont.load_default()

# --- NUEVO: estilo por prompt y funciones de efecto (a nivel de módulo) ---
def apply_style_effects(img_pil, prompt):
	"""
	Aplica efectos simples basados en palabras clave del prompt.
	Efectos: sepia/vintage, noir/black&white, warm/cool, grain, vignette, soft/blur, glow, contrast, brighten, desaturate.
	"""
	if not prompt:
		return img_pil
	p = str(prompt).lower()

	img = img_pil.convert("RGBA")
	# brillo/contraste/color enhancers
	from PIL import ImageEnhance, ImageOps, ImageChops, ImageFilter, Image
	# b&w / noir
	if any(k in p for k in ("noir", "black and white", "black&white", "b&w", "bw", "monochrome")):
		img = ImageOps.grayscale(img).convert("RGBA")
		# aumentar contraste
		img = ImageEnhance.Contrast(img).enhance(1.3)
	# sepia / vintage
	if any(k in p for k in ("sepia", "vintage", "retro")):
		rgb = img.convert("RGB")
		sep = rgb.copy()
		sep = sep.convert("L")
		sep = sep.convert("RGB")
		overlay = Image.new("RGB", sep.size, (230, 180, 120))
		sep = Image.blend(sep, overlay, 0.35).convert("RGBA")
		sep.putalpha(img.split()[-1])
		img = sep
	# warm / sunny
	if any(k in p for k in ("warm", "sunny", "sun")):
		rgb = img.convert("RGB")
		r_enh = ImageEnhance.Color(rgb).enhance(1.1)
		r_enh = ImageEnhance.Brightness(r_enh).enhance(1.05)
		w, h = rgb.size
		overlay = Image.new("RGB", (w,h), (255,140,50))
		img = Image.blend(r_enh, overlay, 0.08).convert("RGBA")
	# cool / blue
	if any(k in p for k in ("cool", "blue", "cold")):
		rgb = img.convert("RGB")
		overlay = Image.new("RGB", rgb.size, (40,120,200))
		img = Image.blend(rgb, overlay, 0.08).convert("RGBA")
	# soft / blur
	if any(k in p for k in ("soft", "blur", "gentle")):
		img = img.filter(ImageFilter.GaussianBlur(radius=2))
	# glow
	if "glow" in p:
		blur = img.filter(ImageFilter.GaussianBlur(radius=8))
		img = ImageChops.screen(img.convert("RGB"), blur.convert("RGB")).convert("RGBA")
	# grain
	if any(k in p for k in ("grain", "film", "noise")):
		w, h = img.size
		try:
			noise = Image.effect_noise((w, h), 64).convert("L")
			noise = ImageEnhance.Brightness(noise).enhance(0.8)
			noise_rgba = Image.merge("RGBA", (noise, noise, noise, noise)).convert("RGBA")
			img = Image.blend(img, noise_rgba, 0.08)
		except Exception:
			pass
	# vignette
	if "vignette" in p:
		w, h = img.size
		mask = Image.new("L", (w, h), 0)
		mdraw = ImageDraw.Draw(mask)
		n = 8
		for i in range(n):
			bbox = [int(w* (-0.1 + i*(1.2/n))), int(h*(-0.1 + i*(1.2/n))), int(w*(1.1 - i*(1.2/n))), int(h*(1.1 - i*(1.2/n)))]
			alpha = int(255 * (i/(n-1))**1.5)
			mdraw.ellipse(bbox, fill=alpha)
		mask = ImageOps.invert(mask)
		black = Image.new("RGBA", (w,h), (0,0,0,180))
		img = Image.composite(img, Image.composite(img, black, mask), mask).convert("RGBA")
	# contrast/bright/desaturate shortcuts
	if "contrast" in p:
		img = ImageEnhance.Contrast(img).enhance(1.15)
	if "bright" in p or "brillo" in p or "brighten" in p:
		img = ImageEnhance.Brightness(img).enhance(1.08)
	if "desaturate" in p or "desaturado" in p:
		img = ImageEnhance.Color(img).enhance(0.5)
	return img

# --- NUEVA SECCIÓN: Ajuste de títulos tras la generación del vídeo ---
# (Movida aquí para estar definida antes de su uso)
def superponer_titulos_en_video(video_path, output_path, titulos, pos_y, tamano, color, pos_sub_y, tamano_sub, color_sub):
    # Importar submódulos concretos (evita dependencias de moviepy.editor)
    from moviepy.video.io.VideoFileClip import VideoFileClip
    from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
    try:
        from moviepy.video.VideoClip import TextClip
    except Exception:
        TextClip = None

    video = VideoFileClip(video_path)
    clips = [video]

    # Si TextClip no está disponible, no añadimos clips de texto (se puede usar la ruta de frames/PIL)
    if TextClip is not None:
        for i, (titulo, subtitulo) in enumerate(titulos):
            if titulo:
                txt_clip = TextClip(
                    titulo,
                    fontsize=tamano,
                    color=color,
                    font="Arial",
                    method="caption",
                    size=(video.w - 100, None)
                ).set_position(("center", pos_y)).set_duration(video.duration)
                clips.append(txt_clip)
            if subtitulo:
                sub_clip = TextClip(
                    subtitulo,
                    fontsize=tamano_sub,
                    color=color_sub,
                    font="Arial",
                    method="caption",
                    size=(video.w - 100, None)
                ).set_position(("center", pos_sub_y)).set_duration(video.duration)
                clips.append(sub_clip)

    final = CompositeVideoClip(clips)
    final.write_videofile(output_path, codec='libx264', audio_codec='aac', fps=24)
    video.close()
    final.close()


# --- FUNCIONES NÚCLEO (ligeramente adaptadas) ---
# --- nueva: normaliza especificadores de color a '#RRGGBB' o devuelve nombre válido ---
def normalizar_color(c):
	"""
	Devuelve un color válido para PIL: acepta '#RRGGBB', 'RRGGBB' o nombres como 'white'.
	"""
	if not c:
		return "#000000"
	cs = str(c).strip()
	if cs.startswith("#"):
		return cs
	# si es hex sin '#'
	if len(cs) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in cs):
		return "#" + cs
	# fallback: devuelve tal cual (permite nombres como 'white')
	return cs

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
        prefer_emoji = contiene_emoji(titulo_info['texto'])
        fuente_titulo = cargar_fuente(titulo_info.get('tamano', 90), titulo_info.get('fuente_path'), prefer_emoji=prefer_emoji)
        bbox_titulo = draw.textbbox((0, 0), titulo_info['texto'], font=fuente_titulo)
        ancho_texto = bbox_titulo[2] - bbox_titulo[0]
        alto_texto = bbox_titulo[3] - bbox_titulo[1]
        pos_titulo_x = (tamano_salida[0] - ancho_texto) // 2
        pos_titulo_y = titulo_info.get('pos_y', 100)  # Usa el valor configurable
        
        # normalizar colores antes de dibujar
        _color_sombra = normalizar_color(titulo_info.get('color_sombra', '000000'))
        _color_texto = normalizar_color(titulo_info.get('color', 'ffffff'))
        
        draw.text((pos_titulo_x + 3, pos_titulo_y + 3), titulo_info['texto'], font=fuente_titulo, fill=_color_sombra)
        draw.text((pos_titulo_x, pos_titulo_y), titulo_info['texto'], font=fuente_titulo, fill=_color_texto)

    # Añadir Subtítulo
    if subtitulo_texto:
        prefer_emoji_sub = contiene_emoji(subtitulo_texto)
        fuente_subtitulo = cargar_fuente(titulo_info.get('tamano_sub', 60), titulo_info.get('fuente_path'), prefer_emoji=prefer_emoji_sub)
        bbox_sub = draw.textbbox((0, 0), subtitulo_texto, font=fuente_subtitulo)
        ancho_sub = bbox_sub[2] - bbox_sub[0]
        alto_sub = bbox_sub[3] - bbox_sub[1]
        pos_sub_x = (tamano_salida[0] - ancho_sub) // 2
        pos_sub_y = titulo_info.get('pos_sub_y', tamano_salida[1] - alto_sub - 150)  # Usa el valor configurable
        
        _color_sombra_sub = normalizar_color(titulo_info.get('color_sombra', '000000'))
        _color_sub = normalizar_color(titulo_info.get('color_sub', 'ffffff'))
        
        draw.text((pos_sub_x + 2, pos_sub_y + 2), subtitulo_texto, font=fuente_subtitulo, fill=_color_sombra_sub)
        draw.text((pos_sub_x, pos_sub_y), subtitulo_texto, font=fuente_subtitulo, fill=_color_sub)

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

    # 4. Ajustes de título (nuevo)
    st.subheader("4. Ajustes de Título")
    pos_titulo_y = st.slider("Posición vertical del título (px desde arriba)", 0, 1800, 100, 10)
    tamano_titulo = st.slider("Tamaño del título", 20, 2000, 300, 2)
    pos_sub_y = st.slider("Posición vertical del subtítulo (px desde arriba)", 0, 1800, 1770, 10)
    tamano_subtitulo = st.slider("Tamaño del subtítulo", 10, 1500, 200, 2)

    # 4. Ajustes globales de difuminado
    st.subheader("🔒 Privacidad / Difuminado")
    if not cv2_available:
        st.info("OpenCV no está disponible: la detección de caras no funcionará. Instala 'opencv-python' para habilitarla.")
    global_blur = st.checkbox("Difuminar caras en todo el vídeo (global)", value=False)
    global_blur_minors = st.checkbox("Si activo: difuminar solo menores (heurística por tamaño)", value=False)
    global_blur_strength = st.slider("Intensidad difuminado (radio)", 1, 60, 15)
    global_minors_threshold = st.slider("Umbral menores (ratio altura cara / altura imagen)", 0.02, 0.25, 0.12, step=0.01)

    # --- NUEVO: controles globales de estilo (prompt) ---
    st.subheader("🎨 Estilo del Vídeo (prompt)")
    global_style_prompt = st.text_input("Prompt de estilo (ej: 'vintage sepia grain vignette')", value=st.session_state.get("global_style_prompt",""))
    global_style_apply = st.checkbox("Aplicar estilo global por defecto", value=st.session_state.get("global_style_apply", False))

    # guardar en session
    st.session_state["global_blur"] = global_blur
    st.session_state["global_blur_minors"] = global_blur_minors
    st.session_state["global_blur_strength"] = global_blur_strength
    st.session_state["global_minors_threshold"] = global_minors_threshold
    st.session_state["global_style_prompt"] = global_style_prompt
    st.session_state["global_style_apply"] = global_style_apply

# --- LÓGICA DE GENERACIÓN ---
if "video_generado_path" not in st.session_state:
	st.session_state["video_generado_path"] = None
if "frames_paths" not in st.session_state:
	st.session_state["frames_paths"] = []
if "titulos_state" not in st.session_state:
	st.session_state["titulos_state"] = []
# nuevo: frame seleccionado
if "selected_frame" not in st.session_state:
	st.session_state["selected_frame"] = 0

if st.button("✨ ¡Generar Vídeo!"):
    if not fotos_subidas:
        st.warning("Por favor, sube al menos una foto.")
    else:
        with st.spinner('Procesando... El vídeo se está creando. ¡Esto puede tardar unos minutos!'):
            temp_dir = "temp_files"
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)
            rutas_fotos = []
            for foto in fotos_subidas:
                ruta = os.path.join(temp_dir, foto.name)
                with open(ruta, "wb") as f:
                    f.write(foto.getbuffer())
                rutas_fotos.append(ruta)
            ruta_audio = None
            if audio_subido:
                ruta_audio = os.path.join(temp_dir, audio_subido.name)
                with open(ruta_audio, "wb") as f:
                    f.write(audio_subido.getbuffer())
            subtitulos = [s.strip() for s in subtitulos_texto.split('\n') if s.strip()]
            if subtitulos and len(subtitulos) != len(rutas_fotos):
                st.warning("El número de subtítulos no coincide con el de fotos. Se omitirán.")
                subtitulos = []
            
            # Determinar settings a partir del prompt de estilo global (puede ajustarse por imagen luego)
            style_prompt_global = st.session_state.get("global_style_prompt", "") or ""
            sp = style_prompt_global.lower()
            montage_mode = "normal"
            if "collage" in sp or "grid" in sp:
                montage_mode = "collage"
            elif "overlay" in sp or "superpos" in sp:
                montage_mode = "overlay"
            # velocidad
            speed_factor = 1.0
            if "fast" in sp or "rápido" in sp:
                speed_factor = 0.6
            if "slow" in sp or "lento" in sp:
                speed_factor = 1.5
            # transición
            use_crossfade = any(k in sp for k in ("crossfade", "fade", "dissolve"))
            # construir frames/clips aplicando montaje
            clips_imagenes = []
            frames_paths = []
            i = 0
            N = len(rutas_fotos)
            while i < N:
                # seleccionar imágenes según montage_mode
                if montage_mode == "collage":
                    # tomar hasta 3 imágenes para collage
                    group = rutas_fotos[i:i+3]
                    # crear imagen procesada (usar ajustar_y_procesar_imagen en cada subimagen y luego combinar)
                    temp_imgs = []
                    for p in group:
                        improc = ajustar_y_procesar_imagen(p, (1080,1920), {
                            'texto': '',
                            'fuente_path': None,
                            'tamano': 1,
                            'color': "white",
                            'color_sombra': "black",
                            'tamano_sub': 1,
                            'color_sub': "white",
                            'pos_y': 0,
                            'pos_sub_y': 0
                        }, None)
                        # guardar temporal para crear collage
                        tmpn = os.path.join(temp_dir, f"sub_{uuid.uuid4()}.png")
                        improc.save(tmpn)
                        temp_imgs.append(tmpn)
                    collage_img = crear_collage(temp_imgs, tamaño=(1080,1920), modo="grid")
                    # aplicar estilo global si activo
                    if st.session_state.get("global_style_apply", False) and style_prompt_global:
                        try:
                            collage_img = apply_style_effects(collage_img, style_prompt_global)
                        except Exception:
                            pass
                    ruta_temporal_frame = os.path.join(temp_dir, f"frame_{uuid.uuid4()}.png")
                    collage_img.save(ruta_temporal_frame)
                    frames_paths.append(ruta_temporal_frame)
                    dur = max(0.5, duracion_foto * speed_factor)
                    clips_imagenes.append(ImageClip(ruta_temporal_frame, duration=dur))
                    i += len(group)
                elif montage_mode == "overlay":
                    # overlay current + next (or fallback single)
                    a = rutas_fotos[i]
                    b = rutas_fotos[i+1] if i+1 < N else None
                    if b:
                        # procesar y overlay
                        a_proc = ajustar_y_procesar_imagen(a, (1080,1920), {
                            'texto': '',
                            'fuente_path': None,
                            'tamano': 1,
                            'color': "white",
                            'color_sombra': "black",
                            'tamano_sub': 1,
                            'color_sub': "white",
                            'pos_y': 0,
                            'pos_sub_y': 0
                        }, None)
                        b_proc = ajustar_y_procesar_imagen(b, (1080,1920), {
                            'texto': '',
                            'fuente_path': None,
                            'tamano': 1,
                            'color': "white",
                            'color_sombra': "black",
                            'tamano_sub': 1,
                            'color_sub': "white",
                            'pos_y': 0,
                            'pos_sub_y': 0
                        }, None)
                        # guardar y overlay
                        ta = os.path.join(temp_dir, f"sub_{uuid.uuid4()}.png")
                        tb = os.path.join(temp_dir, f"sub_{uuid.uuid4()}.png")
                        a_proc.save(ta); b_proc.save(tb)
                        over = overlay_two_images(ta, tb, tamaño=(1080,1920), alpha=0.35)
                        # aplicar estilo global si procede
                        if st.session_state.get("global_style_apply", False) and style_prompt_global:
                            try:
                                over = apply_style_effects(over, style_prompt_global)
                            except Exception:
                                pass
                        ruta_temporal_frame = os.path.join(temp_dir, f"frame_{uuid.uuid4()}.png")
                        over.save(ruta_temporal_frame)
                        frames_paths.append(ruta_temporal_frame)
                        dur = max(0.5, duracion_foto * speed_factor)
                        clips_imagenes.append(ImageClip(ruta_temporal_frame, duration=dur))
                        i += 2
                    else:
                        # último sin par
                        single = ajustar_y_procesar_imagen(a, (1080,1920), {
                            'texto': '',
                            'fuente_path': None,
                            'tamano': 1,
                            'color': "white",
                            'color_sombra': "black",
                            'tamano_sub': 1,
                            'color_sub': "white",
                            'pos_y': 0,
                            'pos_sub_y': 0
                        }, None)
                        ruta_temporal_frame = os.path.join(temp_dir, f"frame_{uuid.uuid4()}.png")
                        single.save(ruta_temporal_frame)
                        frames_paths.append(ruta_temporal_frame)
                        dur = max(0.5, duracion_foto * speed_factor)
                        clips_imagenes.append(ImageClip(ruta_temporal_frame, duration=dur))
                        i += 1
                else:
                    # modo normal: cada foto -> frame
                    p = rutas_fotos[i]
                    imagen_procesada_pil = ajustar_y_procesar_imagen(p, (1080,1920), {
                        'texto': '',
                        'fuente_path': None,
                        'tamano': 1,
                        'color': "white",
                        'color_sombra': "black",
                        'tamano_sub': 1,
                        'color_sub': "white",
                        'pos_y': 0,
                        'pos_sub_y': 0
                    }, None)
                    # aplicar estilo global si procede
                    if st.session_state.get("global_style_apply", False) and style_prompt_global:
                        try:
                            imagen_procesada_pil = apply_style_effects(imagen_procesada_pil, style_prompt_global)
                        except Exception:
                            pass
                    ruta_temporal_frame = os.path.join(temp_dir, f"frame_{uuid.uuid4()}.png")
                    imagen_procesada_pil.save(ruta_temporal_frame)
                    frames_paths.append(ruta_temporal_frame)
                    dur = max(0.5, duracion_foto * speed_factor)
                    clips_imagenes.append(ImageClip(ruta_temporal_frame, duration=dur))
                    i += 1

            # Concatenar con o sin crossfade (usamos padding negativo para solapar si use_crossfade)
            padding_val = -transicion_duracion if use_crossfade else 0
            video_final = concatenate_videoclips(clips_imagenes, method="compose", padding=padding_val)

            video_salida_path = os.path.join(temp_dir, "evento_final.mp4")
            if ruta_audio:
                audio_clip = AudioFileClip(ruta_audio)
                audio_clip = audio_clip.fx(lambda c: c.loop(duration=video_final.duration))
                video_final.audio = audio_clip.subclip(0, video_final.duration)
            else:
                video_final = video_final.without_audio()
            video_final.write_videofile(video_salida_path, codec='libx264', audio_codec='aac', fps=24)
            
            # --- NUEVO: calcula tamaños por defecto basados en el primer frame ---
            if frames_paths:
                try:
                    with Image.open(frames_paths[0]) as _img:
                        w_first, h_first = _img.size
                except Exception:
                    h_first = 1920
            else:
                h_first = 1920

            default_title_size = max(18, int(h_first * 0.08))   # ~8% de la altura
            default_sub_size = max(12, int(h_first * 0.045))    # ~4.5% de la altura

            st.session_state["video_generado_path"] = video_salida_path
            st.session_state["frames_paths"] = frames_paths
            st.session_state["titulos_state"] = [
                {
                    "titulo": texto_titulo if (mostrar_titulo_en == 'En todas las fotos' or i == 0) else "",
                    "subtitulo": subtitulos[i] if i < len(subtitulos) else "",
                    "pos_y": int(h_first * 0.06),
                    "tamano": default_title_size,
                    "color": "000000",
                    "pos_sub_y": int(h_first * 0.88),
                    "tamano_sub": default_sub_size,
                    "color_sub": "000000",
                    "angle": 0,
                    "angle_sub": 0,
                    # nuevos campos para difuminado (por imagen)
                    "blur": st.session_state.get("global_blur", False),
                    "blur_minors": st.session_state.get("global_blur_minors", False),
                    "blur_strength": st.session_state.get("global_blur_strength", 15),
                    "minors_threshold": st.session_state.get("global_minors_threshold", 0.12),
                    # campos de estilo por imagen
                    "use_style": st.session_state.get("global_style_apply", False),
                    "style_prompt": st.session_state.get("global_style_prompt", "")
                }
                for i in range(len(frames_paths))
            ]
            st.success("¡Vídeo generado! Ahora puedes ajustar los títulos antes de incrustarlos.")
# --- FUNCIÓN PARA SUPERPONER TÍTULOS EN UN FRAME ---
# Modificar llamadas para aceptar flags blur y aplicarlo antes de dibujar texto
def superponer_titulos_en_frame(imagen_path, titulo, subtitulo, pos_y, tamano, color, pos_sub_y, tamano_sub, color_sub, angle=0, angle_sub=0, blur=False, blur_minors=False, blur_strength=15, minors_threshold=0.12, style_apply=False, style_prompt=""):
	# Cargar imagen base
	img = Image.open(imagen_path).convert("RGBA")
	# Si se solicita difuminado, detectar caras y aplicar según opciones
	if blur and cv2_available:
		boxes = detectar_caras_pil(img)
		if boxes:
			if blur_minors:
				# filtrar boxes por heurística de tamaño
				boxes = [b for b in boxes if es_menor_por_tamano(b, img.size, minors_threshold)]
			# aplicar difuminado
			img = difuminar_caras_en_pil(img, boxes, blur_radius=blur_strength)
	# aplicar estilo (si está activo y hay prompt)
	if style_apply and style_prompt:
		try:
			img = apply_style_effects(img, style_prompt)
		except Exception:
			# no bloquear si falla el efecto
			pass
	# continuar con el proceso (resto de la implementación igual)
	w_img, h_img = img.size
	canvas = Image.new("RGBA", img.size, (0,0,0,0))

	# Función auxiliar para crear una capa con el texto y rotarla (ahora con auto-escalado)
	def _draw_rotated_text_inner(base_img, text, font_size, x_center, y_top, fill, shadow_fill, angle_deg):
		if not text:
			return (None, None)
		# normalizar colores
		fill_color = normalizar_color(fill)
		shadow_color = normalizar_color(shadow_fill)

		# preferencia por emoji si corresponde
		prefer_emoji = contiene_emoji(text)
		requested_size = int(max(6, font_size))
		font = cargar_fuente(requested_size, None, prefer_emoji=prefer_emoji)

		# medir texto con la fuente actual
		temp_draw = ImageDraw.Draw(Image.new("RGBA", (10,10)))
		bbox = temp_draw.textbbox((0,0), text, font=font)
		tw = bbox[2] - bbox[0]
		th = bbox[3] - bbox[1]

		# ancho máximo permitido para el texto (margen lateral)
		max_width = max(20, w_img - 40)

		# si excede, escalar fuente proporcionalmente (mismo comportamiento)
		if tw > max_width:
			scale = max_width / float(tw)
			new_size = max(8, int(requested_size * scale))
			font = cargar_fuente(new_size, None, prefer_emoji=prefer_emoji)
			bbox = temp_draw.textbbox((0,0), text, font=font)
			tw = bbox[2] - bbox[0]
			th = bbox[3] - bbox[1]
			loop_guard = 0
			while tw > max_width and loop_guard < 12 and new_size > 8:
				new_size = max(8, int(new_size * 0.9))
				font = cargar_fuente(new_size, None, prefer_emoji=prefer_emoji)
				bbox = temp_draw.textbbox((0,0), text, font=font)
				tw = bbox[2] - bbox[0]
				th = bbox[3] - bbox[1]
				loop_guard += 1

		# utilizar métricas para margen inferior (evita corte)
		try:
			ascent, descent = font.getmetrics()
		except Exception:
			ascent, descent = th, int(th*0.2)
		margin_top = 10
		margin_bottom = max(10, descent + 6)

		layer_w, layer_h = tw + margin_top + margin_bottom + 20, th + margin_top + margin_bottom + 20
		layer = Image.new("RGBA", (layer_w, layer_h), (0,0,0,0))
		layer_draw = ImageDraw.Draw(layer)
		# dibujar sombra y texto en la capa con colores normalizados
		shadow_offset = 3
		layer_draw.text((10+shadow_offset, margin_top+shadow_offset), text, font=font, fill=shadow_color)
		layer_draw.text((10, margin_top), text, font=font, fill=fill_color)
		# rotar capa
		rot = layer.rotate(angle_deg, resample=Image.BICUBIC, expand=True)
		# calcular paste position
		paste_x = int(x_center - rot.width // 2)
		paste_y = int(y_top)
		# clamp vertical/horizontal
		if paste_y < 0:
			paste_y = 0
		if paste_y + rot.height > h_img:
			paste_y = max(0, h_img - rot.height)
		if paste_x < 0:
			paste_x = 0
		if paste_x + rot.width > w_img:
			paste_x = max(0, w_img - rot.width)
		return rot, (paste_x, paste_y)

	# Título: centrado en ancho, posición vertical pos_y
	if titulo:
		rot_layer, pos = _draw_rotated_text_inner(img, titulo, tamano, w_img//2, pos_y, color or "ffffff", "000000", angle)
		if rot_layer:
			canvas.alpha_composite(rot_layer, dest=pos)

	# Subtítulo
	if subtitulo:
		rot_layer_sub, pos_sub = _draw_rotated_text_inner(img, subtitulo, tamano_sub, w_img//2, pos_sub_y, color_sub or "ffffff", "000000", angle_sub)
		if rot_layer_sub:
			canvas.alpha_composite(rot_layer_sub, dest=pos_sub)

	# Combinar sobre la imagen original
	result = Image.alpha_composite(img, canvas).convert("RGB")
	return result

# --- Nueva UI: configuración a la izquierda, vista previa a la derecha ---
if st.session_state["video_generado_path"]:
	st.header("🎨 Editor de títulos (configuración a la izquierda, vista previa a la derecha)")
	frames_paths = st.session_state["frames_paths"]
	titulos_state = st.session_state["titulos_state"]

	# columnas: izquierda controles, derecha vista previa
	col_cfg, col_preview = st.columns([1, 2])

	# Selector de frame en la columna de configuración
	with col_cfg:
		st.subheader("Configuración del frame")
		sel = st.selectbox("Elige foto", options=list(range(len(frames_paths))), format_func=lambda x: f"Foto {x+1}", index=st.session_state.get("selected_frame", 0))
		st.session_state["selected_frame"] = sel
		t = titulos_state[sel]
		# Edición
		t["titulo"] = st.text_input("Título", value=t.get("titulo",""), key=f"titulo_sel_{sel}")
		t["subtitulo"] = st.text_input("Subtítulo", value=t.get("subtitulo",""), key=f"sub_sel_{sel}")
		# Estilo por imagen (override)
		t["use_style"] = st.checkbox("Aplicar estilo a esta foto", value=t.get("use_style", False), key=f"use_style_{sel}")
		t["style_prompt"] = st.text_input("Prompt estilo (vacío = usar global)", value=t.get("style_prompt",""), key=f"style_prompt_{sel}")
		# Opciones de difuminado por imagen
		if cv2_available:
			t["blur"] = st.checkbox("Difuminar caras en esta foto", value=t.get("blur", False), key=f"blur_sel_{sel}")
			t["blur_minors"] = st.checkbox("  → Solo menores (heurística)", value=t.get("blur_minors", False), key=f"blurmin_sel_{sel}")
			t["blur_strength"] = st.slider("Intensidad difuminado (radio)", 1, 60, value=int(t.get("blur_strength", 15)), key=f"blurstr_sel_{sel}")
			t["minors_threshold"] = st.slider("Umbral menores (ratio altura cara / altura imagen)", 0.02, 0.25, value=float(t.get("minors_threshold", 0.12)), step=0.01, key=f"minorst_sel_{sel}")
		else:
			st.caption("Instala 'opencv-python' para habilitar difuminado de caras.")
		t["pos_y"] = st.slider("Y título (px)", 0, 1800, value=int(t.get("pos_y",100)), step=5, key=f"posy_sel_{sel}")
		t["tamano"] = st.slider("Tamaño título", 6, 800, value=int(t.get("tamano",90)), step=1, key=f"tamano_sel_{sel}")
		t["angle"] = st.slider("Rotación título (grados)", -180, 180, value=int(t.get("angle",0)), step=1, key=f"angle_sel_{sel}")
		t["color"] = st.color_picker("Color título", "#" + t.get("color","000000"), key=f"color_sel_{sel}")[1:]
		# Subtitulo controls
		t["pos_sub_y"] = st.slider("Y subtítulo (px)", 0, 1800, value=int(t.get("pos_sub_y",1700)), step=5, key=f'possuby_sel_{sel}')
		t["tamano_sub"] = st.slider("Tamaño subtítulo", 6, 400, value=int(t.get("tamano_sub",60)), step=1, key=f"tamano_sub_sel_{sel}")
		t["angle_sub"] = st.slider("Rotación subtítulo (grados)", -180, 180, value=int(t.get("angle_sub",0)), step=1, key=f"angle_sub_sel_{sel}")
		t["color_sub"] = st.color_picker("Color subtítulo", "#" + t.get("color_sub","000000"), key=f"colorsub_sel_{sel}")[1:]
		# Guardar cambios (actualiza session_state)
		if st.button("Guardar cambios", key=f"guardar_{sel}"):
			st.session_state["titulos_state"][sel] = t
			st.success("Guardado para la foto " + str(sel+1))

	# Vista previa a la derecha
	with col_preview:
		st.subheader("Vista previa")
		frame_path = frames_paths[st.session_state["selected_frame"]]
		current = st.session_state["titulos_state"][st.session_state["selected_frame"]]
		img_preview = superponer_titulos_en_frame(
			frame_path,
			current["titulo"],
			current["subtitulo"],
			current["pos_y"],
			current["tamano"],
			current["color"],
			current["pos_sub_y"],
			current["tamano_sub"],
			current["color_sub"],
			current.get("angle",0),
			current.get("angle_sub",0),
			blur=current.get("blur", False),
			blur_minors=current.get("blur_minors", False),
			blur_strength=current.get("blur_strength", 15),
			minors_threshold=current.get("minors_threshold", 0.12),
			style_apply = current.get("use_style", False),
			style_prompt = current.get("style_prompt", "") or st.session_state.get("global_style_prompt","")
		)
		tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
		img_preview.save(tmp.name)
		st.image(tmp.name, caption=f"Preview foto {st.session_state['selected_frame']+1}", use_container_width=True)

	# Botón para incrustar títulos en todo el vídeo
	if st.button("🎬 Incrustar títulos en el vídeo final"):
		with st.spinner("Incrustando títulos en el vídeo..."):
			from moviepy.video.io.VideoFileClip import VideoFileClip
			from moviepy.video.VideoClip import ImageClip as MPImageClip
			video = VideoFileClip(st.session_state["video_generado_path"])
			clips = []
			duracion_foto = video.duration / len(frames_paths)
			for i, frame_path in enumerate(frames_paths):
				t = titulos_state[i]
				img_con_titulo = superponer_titulos_en_frame(
					frame_path,
					t["titulo"],
					t["subtitulo"],
					t["pos_y"],
					t["tamano"],
					t["color"],
					t["pos_sub_y"],
					t["tamano_sub"],
					t["color_sub"],
					t.get("angle",0),
					t.get("angle_sub",0),
					blur=t.get("blur",False),
					blur_minors=t.get("blur_minors",False),
					blur_strength=t.get("blur_strength",15),
					minors_threshold=t.get("minors_threshold",0.12),
					style_apply = t.get("use_style", False),
					style_prompt = t.get("style_prompt","") or st.session_state.get("global_style_prompt","")
				)
				temp_img_path = os.path.join("temp_files", f"final_frame_{i}_{uuid.uuid4()}.png")
				img_con_titulo.save(temp_img_path)
				clips.append(MPImageClip(temp_img_path, duration=duracion_foto))
			video_final_con_titulos = concatenate_videoclips(clips, method="compose")
			# Mantener audio original si existe
			if video.audio:
				video_final_con_titulos.audio = video.audio
			video_con_titulos_path = os.path.join("temp_files", "video_con_titulos.mp4")
			video_final_con_titulos.write_videofile(video_con_titulos_path, codec='libx264', audio_codec='aac', fps=24)
			with open(video_con_titulos_path, "rb") as f:
				st.video(f.read())
			st.download_button(
				label="📥 Descargar Vídeo con Títulos (MP4)",
				data=open(video_con_titulos_path, "rb").read(),
				file_name="video_con_titulos.mp4",
				mime="video/mp4"
			)