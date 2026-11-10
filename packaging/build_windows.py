"""Build and smoke-test the Windows EXE on Windows; no cross-compilation."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT/'dist/windows'
VERSION = '0.1.2'
FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-9.0.2-essentials_build.zip'
FFMPEG_SHA = '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'


def build():
    if os.name != 'nt':
        raise SystemExit('Ejecuta esta receta en Windows x64 con Python 3.12.')
    DIST.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='compilando-win-build-') as tmp:
        work = Path(tmp)
        archive = work/'ffmpeg.zip'
        urllib.request.urlretrieve(FFMPEG_URL, archive)
        if hashlib.sha256(archive.read_bytes()).hexdigest() != FFMPEG_SHA:
            raise RuntimeError('SHA-256 incorrecto en la descarga de FFmpeg')
        with zipfile.ZipFile(archive) as z:
            members = [n for n in z.namelist() if n.endswith('/bin/ffmpeg.exe') or n.endswith('/LICENSE') or n.endswith('/README.txt')]
            for name in members:
                target = work / Path(name).name
                target.write_bytes(z.read(name))
        ffmpeg = work/'ffmpeg.exe'
        if not ffmpeg.is_file():
            raise RuntimeError('El paquete no contiene ffmpeg.exe')
        notices = work/'licenses'; notices.mkdir()
        for name in ['LICENSE', 'README.txt']:
            if (work/name).exists(): shutil.copy2(work/name, notices/('FFmpeg-'+name))
        shutil.copy2(ROOT/'LICENSE', notices/'Compilando-LICENSE.txt')
        versions = {name: importlib.metadata.version(name) for name in ['numpy','PyQt5','PyQt5-Qt5','PyQt5-sip','pyinstaller']}
        details = ('Compilando Studio '+VERSION+' — componentes de Windows\n\n'
                   'Compilando Studio: GPL-3.0-or-later. Código y recetas incluidos en este ZIP.\n'
                   'Python 3.12: PSF License; https://www.python.org/downloads/source/\n'
                   'NumPy: BSD-3-Clause; https://github.com/numpy/numpy/releases\n'
                   'PyQt5 y PyQt5-sip: GPLv3; https://pypi.org/project/PyQt5/#files ; https://pypi.org/project/PyQt5-sip/#files\n'
                   'Qt 5: LGPLv3/GPLv3; https://download.qt.io/archive/qt/5.15/\n'
                   'PyInstaller: GPLv2+ con excepción para el ejecutable; https://github.com/pyinstaller/pyinstaller/releases\n'
                   'FFmpeg 9.0.2, compilación estática Gyan (GPLv3): '+FFMPEG_URL+'\n'
                   'Fuentes FFmpeg de esta compilación: https://github.com/FFmpeg/FFmpeg/tree/946fcce07b\n'
                   'Configuración, bibliotecas y procedencia: https://www.gyan.dev/ffmpeg/builds/\n'
                   'FFmpeg se ejecuta como proceso separado. Se conserva su licencia y documentación.\n\n'
                   'Versiones exactas del entorno:\n'+json.dumps(versions,indent=2)+'\n')
        (notices/'THIRD-PARTY-Windows.txt').write_text(details,encoding='utf-8')
        for name in ['numpy', 'PyQt5', 'PyQt5-sip', 'pyinstaller']:
            distribution = importlib.metadata.distribution(name)
            for item in distribution.files or []:
                if any(part.lower().startswith(('license','copying')) for part in item.parts):
                    source = Path(distribution.locate_file(item))
                    if source.is_file():
                        destination = notices/name/str(item).replace('..','_')
                        destination.parent.mkdir(parents=True,exist_ok=True)
                        shutil.copy2(source,destination)
        name = f'Compilando-Studio-{VERSION}-Windows-x64'
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--name',name,
                        '--distpath',str(DIST),'--workpath',str(work/'build'),'--specpath',str(work),
                        '--paths',str(ROOT),'--paths',str(ROOT/'packaging'),
                        '--hidden-import','windows_smoke','--add-data',f'{ROOT / "assets"};assets',
                        '--add-data',f'{notices};licenses','--add-binary',f'{ffmpeg};.',str(ROOT/'packaging/windows_entry.py')],check=True)
        exe = DIST/(name+'.exe')
        report = DIST/'Windows-self-test.json'
        report.unlink(missing_ok=True)
        result = subprocess.run([str(exe),'--self-test',str(report)],timeout=180)
        if result.returncode or not report.exists() or not json.loads(report.read_text(encoding='utf-8')).get('ok'):
            raise RuntimeError('El EXE no supera la prueba: '+(report.read_text(encoding='utf-8') if report.exists() else str(result.returncode)))
        source_bundle = DIST/f'Compilando-Studio-{VERSION}-Windows-source-and-licenses.zip'
        with zipfile.ZipFile(source_bundle,'w',zipfile.ZIP_DEFLATED) as z:
            for directory in ['compilando','packaging','assets','tests','.github']:
                for file in (ROOT/directory).rglob('*'):
                    if file.is_file() and '__pycache__' not in file.parts and file.suffix!='.pyc':
                        z.write(file,Path('codigo')/file.relative_to(ROOT))
            for file in ['README.md','LICENSE','CHANGELOG.md']:
                z.write(ROOT/file,Path('codigo')/file)
            z.write(ROOT/'packaging/README-Windows.md','LEEME-Windows.md')
            for file in notices.rglob('*'):
                if file.is_file(): z.write(file,Path('licencias')/file.relative_to(notices))
        artifacts = [exe,source_bundle,report,report.with_suffix('.png')]
        (DIST/'SHA256SUMS-Windows').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in artifacts),encoding='utf-8')
        print(report.read_text(encoding='utf-8'))
        for file in artifacts: print(file.name,file.stat().st_size)


if __name__ == '__main__':
    build()
