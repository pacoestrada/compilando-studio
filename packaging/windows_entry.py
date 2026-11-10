"""Windows launcher for the unchanged v0.1.2 editor (GPL-3.0-or-later)."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))


def ffmpeg(args):
    executable = ROOT / 'ffmpeg.exe'
    result = subprocess.run(
        [str(executable) if executable.exists() else 'ffmpeg', '-hide_banner',
         '-loglevel', 'error', '-nostdin', *map(str, args)],
        stdin=subprocess.DEVNULL, capture_output=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-2500:] or 'FFmpeg no pudo procesar el audio.')


def close_assets(project):
    # Windows does not allow deleting an open memory-mapped file.
    for asset in project.assets.values():
        mapping = getattr(asset.data, '_mmap', None)
        if mapping is not None and not mapping.closed:
            mapping.close()


def run():
    from PyQt5.QtCore import Qt, QTimer, QSettings, QStandardPaths, QTranslator, QLibraryInfo
    from PyQt5.QtGui import QIcon
    from PyQt5.QtWidgets import QApplication, QMessageBox
    from compilando import core, ui
    core.ffmpeg = ui.ffmpeg = ffmpeg

    class WindowsStudio(ui.Studio):
        def closeEvent(self, event):
            super().closeEvent(event)
            if event.isAccepted():
                close_assets(self.project)
                if self.cache_owner is not None:
                    self.cache_owner.cleanup()

    parser = argparse.ArgumentParser(description='Compilando Studio 0.1.2 · Windows')
    parser.add_argument('file', nargs='?')
    parser.add_argument('--episode')
    parser.add_argument('--voice')
    parser.add_argument('--self-test', metavar='REPORT', help='Prueba automatizada con audio sintético')
    args = parser.parse_args()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv[:1])
    app.setApplicationName('Compilando Studio')
    app.setOrganizationName('Compilando Podcast')
    app.setWindowIcon(QIcon(str(ROOT / 'assets/logo.jpg')))
    translator = QTranslator(app)
    if translator.load('qtbase_es', QLibraryInfo.location(QLibraryInfo.TranslationsPath)):
        app.installTranslator(translator)
    if args.self_test:
        from windows_smoke import smoke
        return smoke(app, WindowsStudio, Path(args.self_test).resolve(), close_assets)
    if not (ROOT / 'ffmpeg.exe').is_file():
        QMessageBox.critical(None, 'Compilando Studio', 'Falta FFmpeg en el ejecutable. Descarga de nuevo la versión de Windows de la release.')
        return 1
    for variable in ('ProgramFiles', 'ProgramFiles(x86)', 'LOCALAPPDATA'):
        base = os.environ.get(variable)
        if base:
            directory = Path(base) / 'Audacity'
            if (directory / 'Audacity.exe').is_file():
                os.environ['PATH'] = str(directory) + os.pathsep + os.environ.get('PATH', '')
    music = Path(QStandardPaths.writableLocation(QStandardPaths.MusicLocation) or str(Path.home()))
    settings = QSettings('Compilando', 'Studio')
    if not settings.contains('music_folder'):
        settings.setValue('music_folder', str(music))
    episode = args.episode or music / 'Compilando' / ('Episodio-' + datetime.now().strftime('%Y%m%d-%H%M%S'))
    window = WindowsStudio(episode, settings=settings)
    window.setWindowIcon(app.windowIcon())
    window.show()
    source = args.voice or args.file
    if window.project.file.exists() and not (source and source.lower().endswith('.compilando.json')):
        QTimer.singleShot(150, lambda: window.guard(lambda: window.open_project(str(window.project.file), False, (lambda: window.import_voice(source)) if source else None)))
    elif source:
        QTimer.singleShot(150, lambda: window.guard(lambda: window.open_project(source, False) if source.lower().endswith('.compilando.json') else window.import_voice(source)))
    return app.exec_()


if __name__ == '__main__':
    try:
        sys.exit(run())
    except Exception:
        error = traceback.format_exc()
        if '--self-test' in sys.argv:
            import json
            report = Path(sys.argv[sys.argv.index('--self-test') + 1])
            report.parent.mkdir(parents=True, exist_ok=True)
            report.write_text(json.dumps({'ok': False, 'error': error}, ensure_ascii=False, indent=2), encoding='utf-8')
        else:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None, error[-3000:], 'Compilando Studio · Error de inicio', 0x10)
        sys.exit(1)
