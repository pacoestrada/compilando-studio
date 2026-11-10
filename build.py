#!/usr/bin/env python3
"""Build a Debian package and a self-contained source/install bundle."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
import tarfile
import hashlib
ROOT=Path(__file__).resolve().parent
VERSION='0.1.4'
DIST=ROOT/'dist'
DIST.mkdir(exist_ok=True)
# Explicit source list: never ship repository metadata, recordings or caches.
sources=[ROOT/name for name in ['README.md','LICENSE','CHANGELOG.md','.gitignore','build.py','run.sh']]
for directory in ['compilando','assets','tests','docs','packaging','.github']:
    sources.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc')
sources=sorted(sources)
with tempfile.TemporaryDirectory(prefix='compilando-deb-') as tmp:
    tree=Path(tmp)/'root'
    app=tree/'usr/share/compilando-studio'
    app.mkdir(parents=True)
    shutil.copytree(ROOT/'compilando',app/'compilando',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(ROOT/'assets',app/'assets')
    shutil.copy2(ROOT/'README.md',app/'README.md')
    shutil.copy2(ROOT/'LICENSE',app/'LICENSE')
    shutil.copytree(ROOT/'docs',app/'docs')
    bin=tree/'usr/bin';bin.mkdir(parents=True)
    launcher=bin/'compilando-studio'
    launcher.write_text('#!/bin/sh\ncd /usr/share/compilando-studio || exit 1\nexec /usr/bin/python3 -m compilando "$@"\n')
    launcher.chmod(0o755)
    desktop=tree/'usr/share/applications';desktop.mkdir(parents=True)
    (desktop/'compilando-studio.desktop').write_text('[Desktop Entry]\nType=Application\nName=Compilando Studio\nComment=Edición y mezcla de podcast con estilo de radio\nExec=compilando-studio %f\nIcon=/usr/share/compilando-studio/assets/logo.jpg\nTerminal=false\nCategories=AudioVideo;Audio;AudioVideoEditing;\nMimeType=audio/x-wav;audio/wav;audio/flac;audio/x-flac;audio/mpeg;\nStartupNotify=true\n')
    control=tree/'DEBIAN';control.mkdir()
    (control/'control').write_text(f'Package: compilando-studio\nVersion: {VERSION}\nSection: sound\nPriority: optional\nArchitecture: all\nMaintainer: Compilando Podcast <compilando@localhost>\nDepends: python3 (>= 3.10), python3-numpy, python3-pyqt5, python3-pyqt5.qtmultimedia, libqt5multimedia5-plugins, ffmpeg\nRecommends: audacity\nDescription: Editor y mezclador de podcast Compilando Studio\n Interfaz de radio, importacion de voz, clips, musica automatica,\n proyectos y exportacion MP3, WAV y FLAC.\n')
    deb=DIST/f'compilando-studio_{VERSION}_all.deb'
    subprocess.run(['dpkg-deb','--root-owner-group','--build',str(tree),str(deb)],check=True)
bundle=DIST/f'Compilando-Studio-{VERSION}-Linux.zip'
with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
    z.write(deb,deb.name)
    z.writestr('LEEME.md',(ROOT/'README.md').read_text().replace('(docs/compilando-studio.png)','(codigo/docs/compilando-studio.png)'))
    for p in sources:
        z.write(p,Path('codigo')/p.relative_to(ROOT))
source_archive=DIST/f'compilando-studio-{VERSION}-source.tar.gz'
with tarfile.open(source_archive,'w:gz') as archive:
    for p in sources:
        archive.add(p,arcname=Path(f'compilando-studio-{VERSION}')/p.relative_to(ROOT))
checksums=DIST/'SHA256SUMS'
checksums.write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in [deb,bundle,source_archive]))
for p in [deb,bundle,source_archive,checksums]:print(p)
