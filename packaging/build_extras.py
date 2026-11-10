#!/usr/bin/env python3
"""Build additional assets from the versioned source bundle and its manifest."""
import hashlib
import runpy
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
VERSION = runpy.run_path(str(ROOT/'compilando/__init__.py'))['__version__']
SOURCE = DIST / f'compilando-studio-{VERSION}-source.tar.gz'


def build():
    payload = SOURCE.read_bytes()
    manifest = dict(line.split(maxsplit=1)[::-1] for line in (DIST/'SHA256SUMS').read_text().splitlines())
    source_sha256 = manifest.get(SOURCE.name)
    if hashlib.sha256(payload).hexdigest() != source_sha256:
        raise SystemExit('El archivo de fuentes no coincide con SHA256SUMS. Ejecuta primero build.py.')
    runner = DIST / f'Compilando-Studio-{VERSION}-Linux.run'
    template = (ROOT / 'packaging/portable.sh.in').read_text()
    runner.write_bytes(template.replace('@VERSION@', VERSION).replace('@SHA256@', source_sha256).encode() + payload)
    runner.chmod(0o755)
    with tempfile.TemporaryDirectory(prefix='compilando-rpmbuild-') as tmp:
        top = Path(tmp)
        for name in ['BUILD', 'BUILDROOT', 'RPMS', 'SOURCES', 'SPECS', 'SRPMS', 'tmp', 'rpmdb']:
            (top / name).mkdir()
        shutil.copy2(SOURCE, top / 'SOURCES' / SOURCE.name)
        subprocess.run(['rpmbuild', '--define', f'_topdir {top}', '--define', f'_tmppath {top / "tmp"}', '--define', f'_dbpath {top / "rpmdb"}', '--define', '_buildhost compilando-studio', '-bb', str(ROOT / 'packaging/compilando-studio.spec')], check=True)
        rpm = DIST / f'compilando-studio-{VERSION}-1.noarch.rpm'
        shutil.copy2(top / 'RPMS/noarch' / rpm.name, rpm)
    extra_source = DIST / f'compilando-studio-{VERSION}-extras-source.tar.gz'
    with tarfile.open(extra_source, 'w:gz') as archive:
        for source in sorted((ROOT / 'packaging').iterdir()):
            if source.is_file():
                archive.add(source, arcname=f'compilando-studio-{VERSION}/packaging/{source.name}')
        archive.add(SOURCE, arcname=f'compilando-studio-{VERSION}/dist/{SOURCE.name}')
    artifacts = [rpm, runner, extra_source]
    checksums = DIST / 'SHA256SUMS-extras'
    checksums.write_text(''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n' for p in artifacts))
    for path in artifacts + [checksums]:
        print(path)


if __name__ == '__main__':
    build()
