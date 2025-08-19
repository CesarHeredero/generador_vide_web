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
            clips_imagenes = []
            frames_paths = []
            for i, ruta_foto in enumerate(rutas_fotos):
                imagen_procesada_pil = ajustar_y_procesar_imagen(ruta_foto, (1080, 1920), {
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
                imagen_procesada_pil.save(ruta_temporal_frame)
                frames_paths.append(ruta_temporal_frame)
                clip = ImageClip(ruta_temporal_frame, duration=duracion_foto)
                clips_imagenes.append(clip)
            video_con_transiciones = [clips_imagenes[0]]
            for i in range(len(clips_imagenes) - 1):
                clip_actual = clips_imagenes[i+1]
                video_con_transiciones.append(clip_actual)
            video_final = concatenate_videoclips(video_con_transiciones, method="compose")
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
                    "angle_sub": 0
                }
                for i in range(len(frames_paths))
            ]
            st.success("¡Vídeo generado! Ahora puedes ajustar los títulos antes de incrustarlos.")
# --- FUNCIÓN PARA SUPERPONER TÍTULOS EN UN FRAME (reemplazada para soportar rotación y escalado automático) ---
def superponer_titulos_en_frame(imagen_path, titulo, subtitulo, pos_y, tamano, color, pos_sub_y, tamano_sub, color_sub, angle=0, angle_sub=0):
	# Cargar imagen base
	img = Image.open(imagen_path).convert("RGBA")
	w_img, h_img = img.size

	# Crea capa transparente para el texto
	canvas = Image.new("RGBA", img.size, (0,0,0,0))

	# Función auxiliar para crear una capa con el texto y rotarla (ahora con auto-escalado)
	def _draw_rotated_text(text, font_size, x_center, y_top, fill, shadow_fill, angle_deg):
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
		rot_layer, pos = _draw_rotated_text(titulo, tamano, w_img//2, pos_y, color or "ffffff", "000000", angle)
		if rot_layer:
			canvas.alpha_composite(rot_layer, dest=pos)

	# Subtítulo
	if subtitulo:
		rot_layer_sub, pos_sub = _draw_rotated_text(subtitulo, tamano_sub, w_img//2, pos_sub_y, color_sub or "ffffff", "000000", angle_sub)
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
		t["pos_y"] = st.slider("Y título (px)", 0, 1800, value=int(t.get("pos_y",100)), step=5, key=f"posy_sel_{sel}")
		t["tamano"] = st.slider("Tamaño título", 6, 800, value=int(t.get("tamano",90)), step=1, key=f"tamano_sel_{sel}")
		t["angle"] = st.slider("Rotación título (grados)", -180, 180, value=int(t.get("angle",0)), step=1, key=f"angle_sel_{sel}")
		t["color"] = st.color_picker("Color título", "#" + t.get("color","000000"), key=f"color_sel_{sel}")[1:]
		# Subtitulo controls
		t["pos_sub_y"] = st.slider("Y subtítulo (px)", 0, 1800, value=int(t.get("pos_sub_y",1700)), step=5, key=f"possuby_sel_{sel}")
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
			current.get("angle_sub",0)
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
					t.get("angle_sub",0)
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
