# Cambios

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
