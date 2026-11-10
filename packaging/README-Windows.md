# Compilando Studio 0.1.2 · Windows x64

Primera compilación para Windows 10/11 de 64 bits. Descarga
`Compilando-Studio-0.1.2-Windows-x64.exe` y ábrelo con doble clic.
No necesita instalar Python, Qt ni FFmpeg: se incluyen en el ejecutable.
Audacity sigue siendo una aplicación externa y opcional.

Los episodios se guardan inicialmente en Música → Compilando. Puedes cambiar
su carpeta en la app. Las grabaciones originales no se sobrescriben.
La primera apertura puede tardar unos segundos mientras se extrae la aplicación.
El ejecutable no tiene firma digital de editor; Windows puede identificarlo
como editor desconocido. No desactives las protecciones del sistema.

El código de edición coincide con la etiqueta v0.1.2. El lanzador de Windows
añade la ubicación de Música, el FFmpeg incluido, la ejecución sin consolas
auxiliares y el cierre de los archivos temporales de audio antes de limpiarlos.

## Construir y comprobar en Windows

Con Python 3.12 de 64 bits y el repositorio completo:

```powershell
python -m pip install -r packaging/requirements-windows.txt
python packaging/build_windows.py
```

El proceso descarga el paquete FFmpeg 9.0.2 de Gyan, comprueba su SHA-256,
genera el EXE con PyInstaller y ejecuta una prueba con audio sintético usando
el EXE terminado. Sólo produce las sumas de comprobación si la prueba pasa.
La prueba comprueba importación, cortes, fundidos, máster, proyecto, exportación
WAV/FLAC/MP3, reapertura y limpieza. No comprueba sonido por altavoces reales.

`Windows-self-test.json` contiene el resultado; `Windows-self-test.png`, una
captura real del ejecutable durante la prueba. Es una versión en desarrollo:
quedan pendientes las pruebas extensas en ordenadores de usuarios.

Código de Compilando Studio y de este lanzador: GPL-3.0-or-later, véase LICENSE.
Las dependencias y sus fuentes se documentan en THIRD-PARTY-Windows.txt, incluido
en el paquete complementario de fuentes y licencias.
