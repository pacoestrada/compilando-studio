#!/usr/bin/env python3
"""Build additional release assets without replacing the existing v0.1.2 files."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / 'dist'
VERSION = '0.1.2'
SOURCE = DIST / f'compilando-studio-{VERSION}-source.tar.gz'
SOURCE_SHA256 = 'cc6e286566d5c6725698c2badc6a488fb834043e27698696e1a5d599ab4b7241'


def build():
    payload = SOURCE.read_bytes()
    if hashlib.sha256(payload).hexdigest() != SOURCE_SHA256:
        raise SystemExit('Use el archivo de fuentes publicado en v0.1.2; su SHA-256 no coincide.')
    runner = DIST / f'Compilando-Studio-{VERSION}-Linux.run'
    template = (ROOT / 'packaging/portable.sh.in').read_text()
    runner.write_bytes(template.replace('@VERSION@', VERSION).replace('@SHA256@', SOURCE_SHA256).encode() + payload)
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
