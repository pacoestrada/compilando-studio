# Compilando Studio 0.1.2 · Radio Edition

Primera versión pública de un editor de podcast para GNU/Linux, nacido del flujo
de trabajo de Compilando Podcast y con una interfaz inspirada en las mesas de radio.

Importa tu voz, sitúa el cursor y pulsa **Insertar corte musical aquí** (o **M**).
Elige una canción: la aplicación abre 5 segundos de música sola y, cuando vuelve
la voz, baja la música durante otros 5 segundos hasta el nivel de fondo. Ambos
tiempos son configurables.

## Incluye

- Voz WAV/FLAC del teleprompter y otros formatos compatibles con FFmpeg.
- Clips que se pueden dividir y mover, pistas de voz y música y Deshacer/Rehacer.
- Cursor arrastrable y atajos de teclado para trabajar sin depender del ratón.
- Curva de fundido visible, medidor digital de picos y fader máster.
- Exportación MP3 por defecto, WAV y FLAC.
- Proyectos, recuperación y archivos del episodio a mano.
- Preparación del MP3, portada, resumen y HTML para su publicación manual.

## Correcciones de esta versión

El botón de corte abre el navegador de archivos. Si el cursor está dentro de un
hueco existente, completa ese mismo punto. Cancelar o seleccionar un archivo
ilegible deja el montaje intacto, y un solo Deshacer revierte el corte completo.

## Descargar e instalar

- **Linux Mint / Ubuntu / Debian compatibles:** descarga `compilando-studio_0.1.2_all.deb`.
- **Instalador y código juntos:** `Compilando-Studio-0.1.2-Linux.zip`.
- **Solo código:** `compilando-studio-0.1.2-source.tar.gz`.
- **Comprobación de descargas:** `SHA256SUMS`.

Para actualizar, guarda el proyecto, cierra la app e instala el nuevo DEB encima
del anterior. No es necesario desinstalar. Requiere Python 3.10+, NumPy, PyQt5,
Qt Multimedia y FFmpeg. Audacity es opcional.

## Estado del proyecto

Versión inicial en desarrollo, bajo **GPL-3.0-or-later**. Se han verificado la
mezcla, los fundidos, la exportación WAV/FLAC/MP3 y los flujos de edición mediante
pruebas automatizadas. Falta ampliar las pruebas con episodios largos y distintas
distribuciones y dispositivos de sonido.

Audacity se abre como aplicación externa. La subida a webs, iVoox y Spotify es
manual; no se envían archivos ni se modifican feeds desde esta versión.

Las incidencias y aportaciones son bienvenidas. Indica la versión, tu distribución
y los pasos para reproducir el problema.
