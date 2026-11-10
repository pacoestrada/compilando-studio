# Descargas adicionales de Compilando Studio 0.1.2

Mismo código de aplicación que la etiqueta pública v0.1.2. Estos archivos añaden
formatos de distribución; no sustituyen el DEB, ZIP ni fuentes ya publicados.

## RPM (Fedora)

Descarga `compilando-studio-0.1.2-1.noarch.rpm` y abre el instalador, o ejecuta:

```sh
sudo dnf install ./compilando-studio-0.1.2-1.noarch.rpm
```

Declara Python 3.10+, NumPy, PyQt5 completo (incluido QtMultimedia), Qt Multimedia,
FFmpeg y FFprobe como dependencias. Audacity es opcional. Para exportar MP3,
FFmpeg debe incluir `libmp3lame`; compruébalo con `ffmpeg -encoders`.
No añade repositorios ni instala códecs por su cuenta.

Orientado a Fedora con esas dependencias disponibles. El empaquetado y el código
extraído se verifican en el entorno de desarrollo, pero todavía no se ha probado
la instalación en una máquina Fedora. No se garantiza compatibilidad con todos
los sistemas RPM, como openSUSE o RHEL. El paquete no está firmado con GPG.

## Ejecutable .run (GNU/Linux)

Descarga `Compilando-Studio-0.1.2-Linux.run`. En Propiedades → Permisos, permite
ejecutarlo como programa y ábrelo. También puedes usar:

```sh
chmod +x Compilando-Studio-0.1.2-Linux.run
./Compilando-Studio-0.1.2-Linux.run
```

Es un lanzador autoextraíble: no instala la aplicación y limpia su directorio
temporal al cerrar. Necesita las dependencias del sistema; no es un binario
autónomo ni un ejecutable de Windows. No descarga ni instala nada automáticamente.
Los proyectos y grabaciones quedan en la carpeta del episodio, no en el temporal.

Requisitos en Linux Mint 22 / Ubuntu 24.04:

```sh
sudo apt install python3 python3-numpy python3-pyqt5 python3-pyqt5.qtmultimedia libqt5multimedia5-plugins ffmpeg
```

En Fedora: Python 3.10+, `python3-numpy`, `python3-qt5`, `qt5-qtmultimedia` y
FFmpeg/FFprobe con libmp3lame. La opción `--check` comprueba las dependencias.
La opción `--extract DIRECTORIO_VACÍO` permite obtener todo el código original.

## Reproducir los paquetes

El archivo `compilando-studio-0.1.2-extras-source.tar.gz` contiene estas recetas y
el archivo de fuentes original, fijado mediante SHA-256. Descomprímelo y ejecuta
`python3 packaging/build_extras.py` desde su raíz, con Python 3 y `rpmbuild`
disponibles. Los resultados aparecen en `dist/`.

Comprueba las nuevas descargas con `sha256sum -c SHA256SUMS-extras`.
El código y las recetas mantienen GPL-3.0-or-later; LICENSE está en las fuentes.
