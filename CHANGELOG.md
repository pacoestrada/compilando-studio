# Cambios

## 0.1.4 — 2026-11-10

- Edición directa sin siete botones de herramienta/selección: clic para seleccionar,
  onda arriba/abajo para volumen y cabecera para mover el clip.
- La línea azul no intercepta la selección ni el volumen de voz o música.
- Bajo la voz, arrastrar la música ajusta su fondo; en el tramo solo, su ganancia.
- Mayús permite afinar el volumen o mover toda la pista desde una cabecera.
- Regla/triángulo y barra de posición para avanzar; doble clic en la onda para situarse.
- Desplazamiento de la consola si falta altura; mínimos de los paneles recalculados
  al cambiar el zoom o las letras, evitando solapamientos con Guardar audio.
- Pruebas de gestos sin cambiar de modo, audio exportado, deshacer, selección,
  desplazamiento de clips/pistas y tamaños de ventana/fuente.

## 0.1.3 — 2026-11-10

- Curva musical editable: tirador de volumen y tirador de fondo/fundido.
- Modo Volumen (V); cursor de posición azul para distinguirlo de la curva amarilla.
- Deslizador de volumen del clip, valor en dB inmediato, restablecer a 0 dB y Alt+↑/↓.
- Onda y curva actualizadas al ajustar el volumen, incluso con la reproducción parada.
- Fondo y duración de bajada independientes por clip musical; sincronizados con el panel.
- «Seleccionar voz» y «Seleccionar música» indican su función y la selección activa.
- Se evita que la barra de posición se solape con la música al reducir la ventana.
- Un solo Deshacer por arrastre. Proyectos anteriores compatibles; guardado con esquema 2.
- Pruebas de ratón, teclado, selección, deshacer, audio exportado y reapertura de proyectos.

## 0.1.2 — 2026-11-10

Primera publicación del código y del instalador para GNU/Linux.

- «Insertar corte musical aquí» y la tecla M abren el selector de archivos.
- Al elegir una canción, se crea el corte de voz, el hueco musical y el fundido.
- Se reconoce todo el hueco de un punto existente para completarlo sin duplicarlo.
- Cancelar o elegir un archivo ilegible no modifica la voz.
- Un solo Deshacer revierte el corte nuevo y su música.
- El panel recuerda la carpeta de música y conserva la selección al refrescarse.
- Se incluyen pruebas del motor de mezcla, exportación y flujo de la interfaz.

## 0.1.1 — 2026-11-10

- Botón visible para insertar cortes musicales.
- Tiempos independientes de música sola y bajada bajo la voz (5 segundos por defecto).
- Curva de volumen visible que comparte el cálculo con la mezcla y la exportación.
- Barra de posición y cursor arrastrables, con avance y retroceso gráfico.

## 0.1.0 — 2026-11-10

- Primera versión de trabajo: editor nativo PyQt5 con aspecto de mesa de radio.
- Importación de voz, edición no destructiva, músicas, vúmetro y control máster.
- Tratamiento de voz y apertura de una copia en Audacity para usar sus plugins.
- Proyectos con recuperación, exportación MP3/WAV/FLAC y paquete de publicación.
