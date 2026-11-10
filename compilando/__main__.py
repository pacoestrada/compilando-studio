import argparse
import sys
from pathlib import Path
from PyQt5.QtCore import Qt, QTimer, QTranslator, QLibraryInfo
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QIcon
from .ui import Studio

def main():
    parser=argparse.ArgumentParser(description='Compilando Studio · edición de podcast')
    parser.add_argument('file',nargs='?',help='Voz WAV/FLAC o proyecto .compilando.json')
    parser.add_argument('--episode',help='Carpeta del episodio')
    parser.add_argument('--voice',help='Audio de voz exportado por el teleprompter')
    args=parser.parse_args()
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
    app=QApplication(sys.argv[:1]);app.setApplicationName('Compilando Studio');app.setOrganizationName('Compilando Podcast')
    translator=QTranslator(app)
    if translator.load('qtbase_es',QLibraryInfo.location(QLibraryInfo.TranslationsPath)):app.installTranslator(translator)
    icon=QIcon(str(Path(__file__).resolve().parent.parent/'assets'/'logo.jpg'));app.setWindowIcon(icon)
    window=Studio(args.episode);window.setWindowIcon(icon);window.show()
    source=args.voice or args.file
    if window.project.file.exists() and not (source and source.endswith('.compilando.json')):
        QTimer.singleShot(150,lambda:window.guard(lambda:window.open_project(str(window.project.file),False,(lambda:window.import_voice(source)) if source else None)))
    elif source:
        fn=lambda:window.open_project(source,False) if source.endswith('.compilando.json') else window.import_voice(source)
        QTimer.singleShot(150,lambda:window.guard(fn))
    sys.exit(app.exec_())

if __name__=='__main__':main()
