from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from datetime import datetime
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal, QUrl, QIODevice, QDir, QEvent, QSettings
from PyQt5.QtGui import QPixmap, QKeySequence, QIcon
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSplitter, QFileDialog, QMessageBox, QLineEdit, QComboBox, QSlider, QDoubleSpinBox, QCheckBox,
    QListWidgetItem, QTreeView, QFileSystemModel, QScrollBar, QProgressDialog, QDialog, QFormLayout,
    QPlainTextEdit, QDialogButtonBox, QAbstractItemView, QAction, QApplication, QSpinBox)
from . import __version__
from .core import Project, RATE, FORMATS, ffmpeg, uid
from .widgets import Timeline, PeakMeter, MusicList, PositionSlider, clock

STYLE = '''
QMainWindow, QDialog {background:#30383a;color:#e8e4cf;font:13px "Sans";}
QWidget {color:#e8e4cf;} QFrame#console {border-left:9px solid #79543b;border-right:9px solid #79543b;background:#30383a;}
QFrame#panel {background:#394144;border:1px solid #68716b;border-radius:6px;}
QLabel#brand {font-size:22px;font-weight:bold;color:#efe6c4;} QLabel#muted {color:#b7c1b7;font-size:11px;}
QLabel#display {background:#172121;color:#e8c879;border:1px solid #5e685d;border-radius:4px;padding:7px;font:17px "Monospace";}
QPushButton {color:#252c2c;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #e7e1cb,stop:1 #b8b5a4);border:1px solid #1a2122;border-top:2px solid #f0ebd8;border-bottom:3px solid #202728;border-radius:4px;padding:7px 10px;min-height:18px;}
QPushButton:hover {background:#eee7cf;} QPushButton:pressed,QPushButton:checked {background:#92b5bd;border-top:3px solid #283538;border-bottom:1px solid #bcc9c3;}
QPushButton:disabled {background:#555f5e;color:#929b93;border-color:#3b4343;}
QPushButton[color="green"] {background:#6cbb8f;color:#122f23;} QPushButton[color="red"] {background:#ca7468;color:#2e1410;}
QPushButton[color="blue"] {background:#7bafce;color:#142937;} QPushButton[color="amber"] {background:#d7b75f;color:#342a0f;}
QPushButton[color="blue"]:disabled,QPushButton[color="green"]:disabled,QPushButton[color="red"]:disabled {background:#555f5e;color:#929b93;border-color:#3b4343;}
QLineEdit,QComboBox,QSpinBox,QDoubleSpinBox,QPlainTextEdit {background:#202a2b;border:1px solid #758074;border-radius:4px;padding:6px;color:#ede9d6;selection-background-color:#557b89;}
QComboBox QAbstractItemView {background:#263132;color:#ede9d6;selection-background-color:#557b89;}
QListWidget,QTreeView {background:#242e30;border:1px solid #58655f;border-radius:4px;alternate-background-color:#293537;selection-background-color:#615c75;selection-color:#fff0d4;}
QListWidget::item {padding:9px 6px;border-bottom:1px solid #3e4a48;} QHeaderView::section {background:#45504e;color:#e8e4cf;padding:5px;border:0;}
QSlider::groove:vertical {background:#141c1c;width:8px;border:1px solid #707970;} QSlider::handle:vertical {background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #dedccf,stop:.45 #757c78,stop:.5 #272f30,stop:1 #56605c);height:28px;margin:0 -10px;border:1px solid #111919;border-radius:3px;}
QSlider::groove:horizontal {background:#152020;height:6px;} QSlider::handle:horizontal {background:#d6d0b7;width:14px;margin:-6px 0;border:1px solid #182021;border-radius:3px;}
QSlider#position::groove:horizontal {background:#172121;height:8px;border:1px solid #748274;border-radius:4px;}
QSlider#position::sub-page:horizontal {background:#a68a43;border-radius:4px;}
QSlider#position::handle:horizontal {background:#efd58c;width:18px;margin:-5px 0;border:1px solid #55482c;border-radius:4px;}
QScrollBar:horizontal {background:#253334;height:13px;border:0;} QScrollBar::handle:horizontal {background:#73827a;min-width:28px;border-radius:3px;} QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal {width:0;} QScrollBar::add-page:horizontal,QScrollBar::sub-page:horizontal {background:#253334;}
QMenuBar,QMenu {background:#283233;color:#e6dfc4;} QMenu::item:selected {background:#526860;} QToolTip {background:#e9dfbc;color:#202829;border:1px solid #7b735d;padding:5px;}
QStatusBar {background:#232e2f;color:#d0d6c8;} QCheckBox {spacing:6px;} QSplitter::handle {background:#666454;}
'''

class Job(QThread):
    done = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(int)
    def __init__(self, function, parent=None):
        super().__init__(parent)
        self.function = function
    def run(self):
        try:
            self.done.emit(self.function(self.progress.emit))
        except Exception as ex:
            self.failed.emit(str(ex))

class Studio(QMainWindow):
    def __init__(self, episode=None, cache=None, settings=None):
        super().__init__()
        self.cache_owner = tempfile.TemporaryDirectory(prefix='compilando-session-') if cache is None else None
        self.cache = Path(cache or self.cache_owner.name)
        self.project = Project(episode or Path.home()/'Música'/'Compilando'/('Episodio-'+datetime.now().strftime('%Y%m%d-%H%M%S')), self.cache)
        self.project.folder.mkdir(parents=True, exist_ok=True)
        self.settings = settings if settings is not None else QSettings('Compilando', 'Studio')
        self.music_folder = Path(self.settings.value('music_folder', str(Path.home()/'Música')))
        if not self.music_folder.exists():
            self.music_folder = Path.home()
        self.music_path, self.cue_id = '', ''
        self.audio = None
        self.device = None
        self.play_start = 0
        self.stop_start = 0
        self.playing = False
        self.resume_after_scrub = False
        self.jobs = []
        self.busy = False
        self.setWindowTitle('Compilando Studio · Radio Edition ' + __version__)
        self.resize(1450, 920)
        self.setMinimumSize(1050, 720)
        self.setStyleSheet(STYLE)
        self.build_ui()
        self.build_menu()
        self.timer = QTimer(self)
        self.timer.setInterval(35)
        self.timer.timeout.connect(self.tick)
        self.autosave_timer = QTimer(self)
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(20000)
        self.refresh_music()
        self.refresh()
        QApplication.instance().installEventFilter(self)

    def button(self, text, function, color=None, check=False):
        b = QPushButton(text)
        if color:
            b.setProperty('color', color)
        b.setCheckable(check)
        b.clicked.connect(lambda checked=False: self.guard(function))
        return b

    def guard(self, fn):
        try:
            return fn()
        except Exception as ex:
            QMessageBox.warning(self, 'Compilando Studio', str(ex))

    def panel(self):
        f = QFrame();f.setObjectName('panel')
        return f

    def build_ui(self):
        central = QFrame();central.setObjectName('console');self.setCentralWidget(central)
        root = QVBoxLayout(central);root.setContentsMargins(14,12,14,10);root.setSpacing(9)
        head = QHBoxLayout()
        logo = QLabel();pix = QPixmap(str(Path(__file__).resolve().parent.parent/'assets'/'logo.jpg'))
        logo.setPixmap(pix.scaled(54,54,Qt.KeepAspectRatio,Qt.SmoothTransformation));head.addWidget(logo)
        brandbox = QVBoxLayout();brand = QLabel('COMPILANDO  /  STUDIO');brand.setObjectName('brand');brandbox.addWidget(brand)
        self.episode_label = QLabel();self.episode_label.setObjectName('muted');brandbox.addWidget(self.episode_label);head.addLayout(brandbox);head.addStretch()
        self.air = QLabel('  STOP  ');self.air.setObjectName('display');head.addWidget(self.air)
        head.addWidget(self.button('Carpeta del episodio', self.choose_episode));head.addWidget(self.button('Guardar proyecto', self.save_project));root.addLayout(head)
        vertical = QSplitter(Qt.Vertical);root.addWidget(vertical,1)
        workspace = QSplitter(Qt.Horizontal);vertical.addWidget(workspace)
        left = QWidget();lv = QVBoxLayout(left);lv.setContentsMargins(0,0,0,0);workspace.addWidget(left)
        imp = QHBoxLayout();imp.addWidget(self.button('Importar voz · Ctrl+O',self.import_voice,'blue'))
        self.voice_info = QLabel('WAV / FLAC del teleprompter · arrastra sobre la pista de voz');self.voice_info.setObjectName('muted');self.voice_info.setWordWrap(True);imp.addWidget(self.voice_info,1);lv.addLayout(imp)
        editor = self.panel();ev = QVBoxLayout(editor);ev.setContentsMargins(9,8,9,8);ev.setSpacing(7);lv.addWidget(editor,1)
        top = QHBoxLayout();top.addWidget(QLabel('EDICIÓN  ·  VOZ Y MÚSICA'));top.addStretch();top.addWidget(self.button('Tratar voz',self.effects));top.addWidget(self.button('Plugins en Audacity',self.open_audacity));ev.addLayout(top)
        transport = QHBoxLayout()
        for text, fn, col in [('Inicio',lambda:self.seek(0),None),('◀  −5 s',lambda:self.seek(self.timeline.cursor-5*RATE),None),('▶  Play',self.play,'green'),('Ⅱ  Pausa',self.pause,None),('■  Stop',self.stop,'red'),('+5 s  ▶',lambda:self.seek(self.timeline.cursor+5*RATE),None),('Final',lambda:self.seek(self.project.frames),None)]:
            transport.addWidget(self.button(text,fn,col))
        self.time_label = QLabel('00:00.0');self.time_label.setObjectName('display');transport.addWidget(self.time_label);ev.addLayout(transport)
        modes = QHBoxLayout();self.mode_buttons={}
        for mode,label in [('cursor','Cursor'),('clip','Mover clip'),('track','Mover pista')]:
            b=self.button(label,lambda m=mode:self.mode(m),check=True);self.mode_buttons[mode]=b;modes.addWidget(b)
        modes.addWidget(self.button('Dividir · Ctrl+I',self.split));modes.addWidget(self.button('Borrar',self.delete));modes.addWidget(self.button('↶',lambda:self.undo(False)));modes.addWidget(self.button('↷',lambda:self.undo(True)));modes.addStretch()
        modes.addWidget(self.button('−',lambda:self.zoom(.7)));modes.addWidget(self.button('Ajustar',lambda:self.zoom(0)));modes.addWidget(self.button('+',lambda:self.zoom(1.4)));ev.addLayout(modes)
        self.timeline = Timeline(self.project);self.timeline.editStarted.connect(self.pause);self.timeline.seeked.connect(self.seek);self.timeline.selected.connect(self.select_clip);self.timeline.changed.connect(self.refresh);self.timeline.cueRequested.connect(lambda pos:self.guard(lambda:self.add_cue(pos)));self.timeline.dropped.connect(self.drop_audio);ev.addWidget(self.timeline,1)
        self.timeline.scrubStarted.connect(self.begin_scrub);self.timeline.scrubFinished.connect(self.end_scrub)
        seekrow=QHBoxLayout();seekrow.addWidget(QLabel('POSICIÓN'))
        self.position=PositionSlider();self.position.seekRequested.connect(self.seek);self.position.scrubStarted.connect(self.begin_scrub);self.position.scrubFinished.connect(self.end_scrub);seekrow.addWidget(self.position,1)
        self.position_info=QLabel('00:00.0 / 00:00.0');self.position_info.setObjectName('muted');seekrow.addWidget(self.position_info);ev.addLayout(seekrow)
        self.view_row=QWidget();viewlayout=QHBoxLayout(self.view_row);viewlayout.setContentsMargins(0,0,0,0);viewlabel=QLabel('Vista ampliada');viewlabel.setObjectName('muted');viewlayout.addWidget(viewlabel)
        self.scroll = QScrollBar(Qt.Horizontal);self.scroll.valueChanged.connect(self.scroll_view);viewlayout.addWidget(self.scroll,1);ev.addWidget(self.view_row)
        properties = QHBoxLayout();self.selection = QLabel('Sin clip seleccionado');properties.addWidget(self.selection,1)
        properties.addWidget(QLabel('Ganancia clip'))
        self.clip_gain = QDoubleSpinBox();self.clip_gain.setRange(-60,24);self.clip_gain.setSuffix(' dB');self.clip_gain.setSingleStep(.5);self.clip_gain.editingFinished.connect(self.change_clip_gain);properties.addWidget(self.clip_gain)
        properties.addWidget(self.button('↑ Voz',lambda:self.select_track(0)));properties.addWidget(self.button('↓ Música',lambda:self.select_track(1)));ev.addLayout(properties)
        cues = QHBoxLayout();self.insert_cue_button=self.button('Insertar corte musical aquí… · M',self.add_cue,'amber');self.insert_cue_button.setToolTip('Abre el selector de música. Al elegir un archivo se crea el corte y su fundido. Dentro de un hueco existente, completa ese corte.');cues.addWidget(self.insert_cue_button)
        self.cues = QComboBox();self.cues.currentIndexChanged.connect(self.select_cue);cues.addWidget(self.cues,1)
        self.cue_state = QLabel('Sin puntos');cues.addWidget(self.cue_state);lv.addLayout(cues)
        hint = QLabel('← / → 5 s    Mayús 15 s    Ctrl 1 s    Espacio Play/Pausa    M elegir música e insertar    , / . mover    Ctrl+Z deshacer');hint.setObjectName('muted');hint.setWordWrap(True);lv.addWidget(hint)
        rack = self.panel();rl=QHBoxLayout(rack);rl.setContentsMargins(10,10,10,10);workspace.addWidget(rack)
        music = QVBoxLayout();rl.addLayout(music,1)
        musichead=QHBoxLayout();musichead.addWidget(QLabel('MÚSICAS'));musichead.addStretch();musichead.addWidget(self.button('↑',self.music_up));musichead.addWidget(self.button('Carpeta…',self.choose_music));music.addLayout(musichead)
        self.music_folder_label=QLabel();self.music_folder_label.setObjectName('muted');self.music_folder_label.setWordWrap(True);music.addWidget(self.music_folder_label)
        self.search=QLineEdit();self.search.setPlaceholderText('Buscar música');self.search.textChanged.connect(self.refresh_music);music.addWidget(self.search)
        self.music_list=MusicList();self.music_list.currentItemChanged.connect(self.choose_music_item);self.music_list.itemDoubleClicked.connect(self.music_double);music.addWidget(self.music_list,1)
        self.mark=self.button('Elegir corte con clic',lambda:self.mode('mark'),'amber',True);music.addWidget(self.mark)
        gapline=QHBoxLayout();gapline.addWidget(QLabel('Música sola'));self.gap=QDoubleSpinBox();self.gap.setRange(.1,30);self.gap.setValue(5);self.gap.setSuffix(' s');self.gap.setToolTip('Hueco de voz que abre cada nuevo corte musical.');gapline.addWidget(self.gap);music.addLayout(gapline)
        duckline=QHBoxLayout();duckline.addWidget(QLabel('Bajar bajo voz'));self.duck_fade=QDoubleSpinBox();self.duck_fade.setRange(.1,30);self.duck_fade.setValue(5);self.duck_fade.setSuffix(' s');self.duck_fade.setToolTip('Duración de la bajada al entrar la voz. Se aplica a todas las músicas.');self.duck_fade.editingFinished.connect(self.change_duck_fade);duckline.addWidget(self.duck_fade);music.addLayout(duckline)
        self.assign_button=self.button('Colocar música',self.assign_music,'blue');music.addWidget(self.assign_button)
        music.addWidget(QLabel('Música bajo la voz'))
        self.bed=QSlider(Qt.Horizontal);self.bed.setRange(-600,0);self.bed.setValue(-240);self.bed.sliderPressed.connect(self.begin_volume);self.bed.valueChanged.connect(self.change_bed);music.addWidget(self.bed)
        self.bed_label=QLabel('−24.0 dB');music.addWidget(self.bed_label)
        self.fade=QCheckBox('Suavizar inicio/final · 1 s');self.fade.setChecked(True);self.fade.toggled.connect(self.change_fade);music.addWidget(self.fade)
        master=QVBoxLayout();rl.addLayout(master);master.addWidget(QLabel('MÁSTER'))
        meterrow=QHBoxLayout();self.meter=PeakMeter();meterrow.addWidget(self.meter)
        self.master=QSlider(Qt.Vertical);self.master.setRange(-600,60);self.master.setValue(0);self.master.setTickPosition(QSlider.TicksBothSides);self.master.setTickInterval(60);self.master.sliderPressed.connect(self.begin_volume);self.master.valueChanged.connect(self.change_master);meterrow.addWidget(self.master);master.addLayout(meterrow,1)
        self.master_label=QLabel('0.0 dB');self.master_label.setObjectName('display');master.addWidget(self.master_label)
        master.addWidget(self.button('0 dB',lambda:self.master.setValue(0)));master.addWidget(QLabel('Picos reales\nClic para borrar'))
        rack.setMinimumWidth(365);workspace.setSizes([1000,390]);workspace.setStretchFactor(0,1)
        delivery=self.panel();dv=QVBoxLayout(delivery);vertical.addWidget(delivery)
        out=QHBoxLayout();out.addWidget(QLabel('GUARDAR AUDIO'))
        self.output=QLineEdit('podcast73');out.addWidget(self.output,1);self.format=QComboBox();self.format.addItems(['MP3','WAV','FLAC']);out.addWidget(self.format)
        out.addWidget(self.button('Guardar audio · Ctrl+S',self.export_audio,'green'));out.addWidget(self.button('Preparar publicación',self.publish,'amber'));dv.addLayout(out)
        ephead=QHBoxLayout();ephead.addWidget(QLabel('ARCHIVOS DEL EPISODIO'));ephead.addStretch();ephead.addWidget(self.button('Abrir carpeta',lambda:self.open_path(self.project.folder)));dv.addLayout(ephead)
        self.file_model=QFileSystemModel(self);self.file_model.setFilter(QDir.AllEntries|QDir.NoDotAndDotDot)
        self.files=QTreeView();self.files.setModel(self.file_model);self.files.setDragEnabled(True);self.files.setAlternatingRowColors(True);self.files.setSelectionMode(QAbstractItemView.SingleSelection);self.files.doubleClicked.connect(self.open_episode_item);self.files.setMinimumHeight(85);self.files.setRootIsDecorated(True);self.files.setColumnWidth(0,480);dv.addWidget(self.files)
        vertical.setSizes([640,190]);vertical.setStretchFactor(0,1)
        self.mode('cursor')

    def build_menu(self):
        menu=self.menuBar().addMenu('Proyecto')
        for title,shortcut,fn in [('Nueva carpeta de episodio','Ctrl+N',self.choose_episode),('Abrir proyecto','Ctrl+Shift+O',self.open_project),('Guardar proyecto','Ctrl+Shift+S',self.save_project),('Importar voz','Ctrl+O',self.import_voice),('Exportar audio','Ctrl+S',self.export_audio)]:
            a=QAction(title,self);a.setShortcut(QKeySequence(shortcut));a.triggered.connect(lambda checked=False,f=fn:self.guard(f));menu.addAction(a)
        helpmenu=self.menuBar().addMenu('Ayuda');a=helpmenu.addAction('Atajos y funcionamiento');a.triggered.connect(self.help)

    def work(self, title, fn, callback):
        if self.busy:
            return
        self.pause();self.busy=True
        self.centralWidget().setEnabled(False);self.menuBar().setEnabled(False)
        dialog=QProgressDialog(title,'',0,100,self);dialog.setCancelButton(None);dialog.setWindowModality(Qt.WindowModal);dialog.setRange(0,0);dialog.show()
        job=Job(fn,self);self.jobs.append(job)
        job.progress.connect(lambda n:(dialog.setRange(0,100),dialog.setValue(n)))
        def finish(result=None,error=None):
            dialog.close();self.busy=False;self.centralWidget().setEnabled(True);self.menuBar().setEnabled(True)
            if error:
                QMessageBox.warning(self,'Compilando Studio',error)
            else:
                self.guard(lambda:callback(result))
            self.refresh()
        job.done.connect(lambda result:finish(result));job.failed.connect(lambda err:finish(error=err));job.finished.connect(lambda:self.jobs.remove(job) if job in self.jobs else None);job.finished.connect(job.deleteLater);job.start()

    def refresh(self):
        self.timeline.project=self.project
        self.timeline.cursor=min(self.timeline.cursor,self.project.frames)
        self.timeline.update()
        self.episode_label.setText(str(self.project.folder))
        self.cues.blockSignals(True);self.cues.clear()
        for i,q in enumerate(self.project.cues):
            c=next((c for c in self.project.clips if c.cue==q.id),None)
            name=self.project.assets[c.asset].path.name.split('_',1)[-1] if c else 'Sin música'
            self.cues.addItem(f'P{i+1} · {clock(self.project.cue_position(q))} · {name}',q.id)
        idx=self.cues.findData(self.cue_id)
        self.cues.setCurrentIndex(idx if idx>=0 else (0 if self.cues.count() else -1));self.cues.blockSignals(False)
        self.cue_id=self.cues.currentData() or ''
        self.update_assignment()
        for widget,value in [(self.master,round(self.project.master*10)),(self.bed,round(self.project.bed*10))]:
            widget.blockSignals(True);widget.setValue(value);widget.blockSignals(False)
        self.fade.blockSignals(True);self.fade.setChecked(self.project.fade>=.9);self.fade.blockSignals(False)
        self.duck_fade.blockSignals(True);self.duck_fade.setValue(self.project.duck_fade);self.duck_fade.blockSignals(False)
        self.master_label.setText('−∞ dB' if self.project.master<=-60 else f'{self.project.master:+.1f} dB')
        self.bed_label.setText(f'{self.project.bed:.1f} dB')
        self.scroll.blockSignals(True);self.scroll.setRange(0,max(0,int(max(RATE*10,self.project.frames*1.08))-self.timeline.span));self.scroll.setPageStep(self.timeline.span);self.scroll.setValue(self.timeline.view);self.timeline.view=self.scroll.value();self.scroll.blockSignals(False);self.view_row.setVisible(self.scroll.maximum()>0)
        self.file_model.setRootPath(str(self.project.folder));self.files.setRootIndex(self.file_model.index(str(self.project.folder)))
        voice=next((c for c in self.project.clips if c.track==0),None)
        self.voice_info.setText(self.project.assets[voice.asset].path.name.split('_',1)[-1]+' · '+clock(self.project.frames) if voice else 'WAV / FLAC del teleprompter · arrastra sobre la pista de voz')
        self.select_clip(self.timeline.selected_id,False)
        self.update_position()
        self.insert_cue_button.setEnabled(any(c.track==0 for c in self.project.clips))
        self.setWindowTitle(('● ' if self.project.dirty else '')+'Compilando Studio · Radio Edition '+__version__)

    def update_assignment(self):
        i=next((i+1 for i,q in enumerate(self.project.cues) if q.id==self.cue_id),None)
        c=next((c for c in self.project.clips if c.cue==self.cue_id),None)
        self.assign_button.setEnabled(i is not None)
        selected=bool(self.music_path and Path(self.music_path).is_file())
        action='Cambiar música' if c else 'Colocar música' if selected else 'Elegir música'
        self.assign_button.setText(f'{action} en P{i}' + ('' if selected else '…') if i else 'Colocar música')
        self.assign_button.setToolTip('Usa la música seleccionada en el panel o abre el selector de archivos para este punto.')
        self.cue_state.setText('Colocada' if c else 'Elige una música' if i else 'Sin puntos')

    def mode(self, mode):
        self.pause();self.timeline.mode=mode
        for key,b in self.mode_buttons.items():b.setChecked(key==mode)
        self.mark.setChecked(mode=='mark');self.timeline.setFocus()

    def select_clip(self, id, choose_cue=True):
        c=self.project.find(id);self.timeline.selected_id=id if c else ''
        self.clip_gain.blockSignals(True);self.clip_gain.setEnabled(bool(c));self.clip_gain.setValue(c.gain if c else 0);self.clip_gain.blockSignals(False)
        self.selection.setText(('Voz' if c.track==0 else 'Música')+' · '+clock(c.length) if c else 'Sin clip seleccionado')
        if c:
            self.timeline.track=c.track
            if choose_cue and c.cue:
                self.cue_id=c.cue;self.cues.setCurrentIndex(self.cues.findData(c.cue))
        self.timeline.update()

    def select_track(self, track):
        self.timeline.track=track
        c=next((c for c in self.project.clips if c.track==track and c.start<=self.timeline.cursor<c.end),next((c for c in self.project.clips if c.track==track),None))
        self.select_clip(c.id if c else '')

    def select_cue(self, index):
        self.cue_id=self.cues.currentData() or '';self.update_assignment()

    def import_voice(self, filename=None):
        if filename is None:
            filename,_=QFileDialog.getOpenFileName(self,'Voz del teleprompter',str(self.project.folder.parent),'Audio (*.wav *.flac *.mp3 *.ogg *.m4a)')
        if not filename:return
        if self.project.clips and QMessageBox.question(self,'Cambiar la voz','Se iniciará un montaje nuevo. Puedes deshacerlo con Ctrl+Z. ¿Usar esta grabación?',QMessageBox.Yes|QMessageBox.No)!=QMessageBox.Yes:return
        def done(asset):
            self.project.import_voice(asset);self.timeline.cursor=0;self.timeline.zoom=1;self.timeline.view=0;self.timeline.selected_id=self.project.clips[0].id;self.statusBar().showMessage('Voz importada. El original se conserva; la copia está en media.',10000)
        self.work('Importando y dibujando la voz…',lambda progress:self.project.add_asset(filename),done)

    def drop_audio(self, filename, position, track):
        if track==0 or not self.project.clips:self.guard(lambda:self.import_voice(filename));return
        def go():
            q=self.project.cue_at(position) or min(self.project.cues,key=lambda q:abs(self.project.cue_position(q)-position),default=None)
            if not q or abs(self.project.cue_position(q)-position)>RATE:
                self.place_music(filename,position=position)
            else:
                self.place_music(filename,cue_id=q.id)
        self.guard(go)

    def add_cue(self, position=None, auto_assign=True):
        self.pause()
        position=self.timeline.cursor if position is None else position
        q=self.project.cue_at(position)
        if not q and not any(c.track==0 and c.start<=position<c.end for c in self.project.clips):
            raise ValueError('Sitúa el cursor sobre la voz o dentro de un corte musical existente.')
        if not auto_assign:
            q=self.project.add_cue(position,self.gap.value());self.cue_id=q.id;self.refresh();return
        title='Elegir música para el corte'
        if q:
            number=next(i+1 for i,item in enumerate(self.project.cues) if item.id==q.id)
            title=f'Elegir música para P{number} · {clock(self.project.cue_position(q))}'
        path=self.choose_music_file(title)
        if path:self.place_music(path,position=position)

    def choose_music_file(self, title):
        initial=self.music_path if self.music_path and Path(self.music_path).is_file() else str(self.music_folder)
        formats=' '.join('*'+suffix for suffix in sorted(FORMATS))
        path,_=QFileDialog.getOpenFileName(self,title,initial,f'Audio ({formats});;Todos los archivos (*)')
        return path

    def assign_music(self):
        if not self.cue_id:return
        path=self.music_path if self.music_path and Path(self.music_path).is_file() else self.choose_music_file('Elegir música para el punto seleccionado')
        if path:self.place_music(path,cue_id=self.cue_id)

    def place_music(self, path, position=None, cue_id=None):
        # Decode first: cancel/errors must never leave a new silent gap.
        project,gap=self.project,self.gap.value()
        def done(asset):
            c=project.assign(cue_id,asset) if cue_id else project.insert_music(position,asset,gap)
            self.cue_id=c.cue;self.timeline.selected_id=c.id
            self.music_folder=Path(path).resolve().parent
            self.search.blockSignals(True);self.search.clear();self.search.blockSignals(False)
            self.music_path=str(Path(path).resolve());self.refresh_music()
            self.mode('cursor')
            self.files.expand(self.file_model.index(str(asset.path.parent)))
            self.statusBar().showMessage(f'{Path(path).name} colocada. Bajada bajo la voz en {project.duck_fade:g} segundos; la línea dorada muestra el volumen.',12000)
        self.work('Preparando música…',lambda progress:project.add_asset(path),done)

    def split(self):
        self.pause();c=self.project.find(self.timeline.selected_id)
        if not c or not c.start<self.timeline.cursor<c.end:
            c=next((c for c in self.project.clips if c.track==self.timeline.track and c.start<self.timeline.cursor<c.end),None)
        if not c:raise ValueError('Selecciona un clip y sitúa el cursor dentro.')
        right=self.project.split(c.id,self.timeline.cursor);self.timeline.selected_id=right.id;self.refresh()

    def delete(self):
        self.pause();self.project.delete(self.timeline.selected_id);self.timeline.selected_id='';self.refresh()

    def undo(self, redo=False):
        self.pause();self.project.undo(redo);self.refresh()

    def nudge(self, seconds):
        self.pause();self.project.move(self.timeline.selected_id,round(seconds*RATE),self.timeline.mode=='track');self.refresh()

    def zoom(self, multiplier):
        self.timeline.zoom=1 if multiplier==0 else max(1,min(10000,self.timeline.zoom*multiplier));self.refresh()

    def scroll_view(self, value):
        self.timeline.view=value;self.timeline.update()

    def begin_volume(self):
        self.project.remember()

    def change_master(self, value):
        if not self.master.isSliderDown():self.project.remember()
        self.project.master=value/10;self.project.dirty=True;self.master_label.setText('−∞ dB' if value<=-600 else f'{value/10:+.1f} dB')

    def change_bed(self, value):
        if not self.bed.isSliderDown():self.project.remember()
        self.project.bed=value/10;self.project.dirty=True;self.bed_label.setText(f'{value/10:.1f} dB')

    def change_fade(self, checked):
        self.project.remember();self.project.fade=1 if checked else .01;self.refresh()

    def change_duck_fade(self):
        if self.project.duck_fade!=self.duck_fade.value():
            self.pause();self.project.remember();self.project.duck_fade=self.duck_fade.value();self.refresh()

    def change_clip_gain(self):
        c=self.project.find(self.timeline.selected_id)
        if c and c.gain!=self.clip_gain.value():self.pause();self.project.remember();c.gain=self.clip_gain.value();self.refresh()

    def seek(self, frame):
        resume=self.playing
        if resume:self.pause()
        self.timeline.cursor=max(0,min(self.project.frames,int(frame)));self.update_position()
        if self.timeline.cursor<self.timeline.view or self.timeline.cursor>self.timeline.view+self.timeline.span:
            self.scroll.setValue(max(0,self.timeline.cursor-int(self.timeline.span*.5)))
        self.timeline.update()
        if resume:self.guard(self.play)

    def update_position(self):
        self.position.blockSignals(True);self.position.setRange(0,self.project.frames);self.position.setValue(self.timeline.cursor);self.position.blockSignals(False)
        self.position.setEnabled(self.project.frames>0)
        self.time_label.setText(clock(self.timeline.cursor));self.position_info.setText(clock(self.timeline.cursor)+' / '+clock(self.project.frames))

    def begin_scrub(self):
        self.resume_after_scrub=self.playing;self.pause()

    def end_scrub(self):
        resume=self.resume_after_scrub;self.resume_after_scrub=False
        if resume and self.timeline.cursor<self.project.frames:self.guard(self.play)

    def play(self):
        if self.playing:return
        if not self.project.frames:raise ValueError('Importa primero la voz.')
        from PyQt5.QtMultimedia import QAudioOutput,QAudioFormat,QAudioDeviceInfo
        from .audio import MixerDevice
        if self.timeline.cursor>=self.project.frames:self.timeline.cursor=0
        fmt=QAudioFormat();fmt.setSampleRate(RATE);fmt.setChannelCount(2);fmt.setSampleSize(16);fmt.setCodec('audio/pcm');fmt.setByteOrder(QAudioFormat.LittleEndian);fmt.setSampleType(QAudioFormat.SignedInt)
        device=QAudioDeviceInfo.defaultOutputDevice()
        if device.isNull():raise RuntimeError('No hay dispositivo de salida de audio disponible.')
        if not device.isFormatSupported(fmt):raise RuntimeError('La salida actual no admite estéreo a 44,1 kHz. Selecciona otra salida en los ajustes de sonido de Linux.')
        self.audio=QAudioOutput(device,fmt,self);self.audio.setBufferSize(16384)
        self.play_start=self.timeline.cursor;self.stop_start=self.timeline.cursor
        self.device=MixerDevice(self.project,self.play_start,self);self.device.open(QIODevice.ReadOnly)
        self.audio.start(self.device);self.playing=True;self.timer.start();self.air.setText('  PLAY  ');self.air.setStyleSheet('color:#88e7a6;')

    def pause(self):
        if self.playing and self.audio:
            self.timeline.cursor=min(self.project.frames,self.play_start+int(self.audio.processedUSecs()*RATE/1000000))
        self.playing=False;self.timer.stop() if hasattr(self,'timer') else None
        if self.audio:self.audio.stop();self.audio.deleteLater();self.audio=None
        if self.device:self.device.close();self.device.deleteLater();self.device=None
        if hasattr(self,'meter'):self.meter.set_levels([0,0]);self.air.setText('  STOP  ');self.air.setStyleSheet('')

    def stop(self):
        self.pause();self.seek(self.stop_start)

    def tick(self):
        if not self.audio:return
        from PyQt5.QtMultimedia import QAudio
        if self.audio.error()!=QAudio.NoError:
            self.pause();self.statusBar().showMessage('La salida de audio no está disponible. Revisa los ajustes de sonido de Linux.',15000);return
        frame=min(self.project.frames,self.play_start+int(self.audio.processedUSecs()*RATE/1000000));self.timeline.cursor=frame
        a=self.project.render(frame,min(1536,max(0,self.project.frames-frame)))
        self.meter.set_levels(np.max(np.abs(a),axis=0) if len(a) else [0,0]);self.update_position()
        if frame>self.timeline.view+self.timeline.span*.92:self.scroll.setValue(max(0,frame-int(self.timeline.span*.15)))
        self.timeline.update()
        if frame>=self.project.frames or self.audio.state()==QAudio.IdleState:self.pause()

    def choose_music(self):
        directory=QFileDialog.getExistingDirectory(self,'Carpeta de músicas',str(self.music_folder))
        if directory:self.music_folder=Path(directory);self.refresh_music()

    def music_up(self):
        self.music_folder=self.music_folder.parent;self.refresh_music()

    def refresh_music(self):
        previous=self.music_path
        self.music_list.blockSignals(True);self.music_list.clear();self.music_path='';self.music_folder_label.setText(str(self.music_folder));term=self.search.text().casefold()
        try:entries=sorted(self.music_folder.iterdir(),key=lambda p:(not p.is_dir(),p.name.casefold()))
        except OSError:entries=[]
        for p in entries:
            if not p.name.startswith('.') and (p.is_dir() or (p.suffix.lower() in FORMATS and term in p.name.casefold())):
                item=QListWidgetItem(('▸ ' if p.is_dir() else '♪ ')+p.name);item.setData(Qt.UserRole,str(p));item.setToolTip(str(p));self.music_list.addItem(item)
                if str(p)==previous and p.is_file():self.music_list.setCurrentItem(item);self.music_path=previous
        self.music_list.blockSignals(False)
        self.settings.setValue('music_folder',str(self.music_folder))
        self.update_assignment()

    def choose_music_item(self,current,previous):
        p=Path(current.data(Qt.UserRole)) if current else None;self.music_path=str(p) if p and p.is_file() else '';self.update_assignment()

    def music_double(self,item):
        p=Path(item.data(Qt.UserRole))
        if p.is_dir():self.music_folder=p;self.refresh_music()
        else:self.guard(self.assign_music)

    def save_project(self):
        self.project.save();self.refresh();self.statusBar().showMessage('Proyecto guardado · '+str(self.project.file),8000)

    def autosave(self):
        if not self.busy and self.project.dirty and self.project.clips:
            try:self.project.save(self.project.folder/'recuperacion.compilando.json',autosave=True)
            except OSError as ex:self.statusBar().showMessage('No se pudo guardar la recuperación: '+str(ex),10000)

    def abandon(self):
        if not self.project.dirty:return True
        answer=QMessageBox.question(self,'Guardar proyecto','Hay cambios sin guardar. ¿Guardarlos antes de continuar?',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Save)
        if answer==QMessageBox.Cancel:return False
        if answer==QMessageBox.Save:
            try:self.save_project()
            except Exception as ex:QMessageBox.warning(self,'No se ha guardado',str(ex));return False
        return True

    def choose_episode(self):
        if not self.abandon():return
        directory=QFileDialog.getExistingDirectory(self,'Carpeta del episodio',str(self.project.folder.parent))
        if not directory:return
        path=Path(directory)/'episodio.compilando.json'
        if path.exists():self.open_project(str(path),False);return
        self.pause();self.project=Project(directory,self.cache);self.timeline.selected_id='';self.timeline.cursor=0;self.timeline.view=0;self.cue_id='';self.refresh()

    def open_project(self, filename=None, ask=True, after=None):
        if ask and not self.abandon():return
        if not filename:filename,_=QFileDialog.getOpenFileName(self,'Abrir proyecto',str(self.project.folder.parent),'Proyecto Compilando (*.compilando.json)')
        if not filename:return
        def done(project):
            self.project=project;self.timeline.selected_id='';self.timeline.cursor=0;self.timeline.view=0;self.timeline.zoom=1;self.cue_id=''
            if after:QTimer.singleShot(0,after)
        self.work('Abriendo proyecto…',lambda progress:Project.load(filename,self.cache),done)

    def export_audio(self):
        if not self.project.frames:raise ValueError('Importa primero la voz.')
        name=Path(self.output.text().strip() or 'episodio').name
        name=Path(name).stem+'.'+self.format.currentText().lower()
        path,_=QFileDialog.getSaveFileName(self,'Guardar mezcla',str(self.project.folder/name),'Audio (*.'+self.format.currentText().lower()+')')
        if not path:return
        if not Path(path).suffix:path+='.'+self.format.currentText().lower()
        self.work('Mezclando y exportando audio…',lambda progress:self.project.export(path,progress),self.export_done)

    def export_done(self,result):
        message='Audio guardado en '+result['path']
        if result['clipped']:message+='\nLa mezcla supera 0 dBFS. Baja el máster y vuelve a exportar para evitar saturación.'
        QMessageBox.information(self,'Exportación terminada',message)

    def metadata_dialog(self):
        dialog=QDialog(self);dialog.setWindowTitle('Datos del episodio');dialog.resize(620,430);form=QFormLayout(dialog)
        title=QLineEdit(self.project.metadata['title']);author=QLineEdit(self.project.metadata['artist']);description=QPlainTextEdit(self.project.metadata['description']);description.setPlaceholderText('Resumen del episodio para la web, iVoox y Spotify')
        cover=QLineEdit(self.project.metadata.get('cover',''));coverrow=QHBoxLayout();coverrow.addWidget(cover)
        def select_cover():
            filename,_=QFileDialog.getOpenFileName(dialog,'Portada',str(self.project.folder),'Imagen (*.jpg *.jpeg *.png)')
            if filename:cover.setText(filename)
        coverrow.addWidget(self.button('Elegir…',select_cover));form.addRow('Título',title);form.addRow('Autor',author);form.addRow('Resumen',description);form.addRow('Portada',coverrow)
        note=QLabel('Genera MP3, portada, resumen y entrada HTML. La subida a tus webs, iVoox y Spotify es manual.');note.setWordWrap(True);form.addRow(note)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);form.addRow(buttons)
        if dialog.exec_()!=QDialog.Accepted:return False
        if not title.text().strip():raise ValueError('Escribe el título del episodio.')
        image=cover.text().strip()
        if image:
            source=Path(image)
            if not source.is_file():raise ValueError('No se encuentra la portada.')
            media=self.project.folder/'media';media.mkdir(parents=True,exist_ok=True);dest=media/(uid()+'_portada'+source.suffix.lower());shutil.copy2(source,dest);image=str(dest)
        self.project.remember();self.project.metadata={'title':title.text().strip(),'artist':author.text().strip(),'description':description.toPlainText(),'cover':image};return True

    def publish(self):
        if not self.project.frames:raise ValueError('Importa primero la voz.')
        if not self.metadata_dialog():return
        self.save_project();folder=self.project.folder/('Publicacion-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
        def done(result):
            self.export_done(result);self.open_path(folder)
        self.work('Preparando archivos para publicar…',lambda progress:self.project.publication(folder,progress),done)

    def effects(self):
        voices={c.asset for c in self.project.clips if c.track==0}
        if not voices:raise ValueError('Importa primero la voz.')
        dialog=QDialog(self);dialog.setWindowTitle('Tratamiento de voz');layout=QVBoxLayout(dialog)
        text=QLabel('Se crea una voz corregida y se conservan los cortes del montaje. Puedes deshacer el tratamiento.');text.setWordWrap(True);layout.addWidget(text)
        hp=QCheckBox('Filtro de graves a 80 Hz');hp.setChecked(True);comp=QCheckBox('Compresión suave');comp.setChecked(True);norm=QCheckBox('Normalizar voz a −16 LUFS');norm.setChecked(True)
        for w in [hp,comp,norm]:layout.addWidget(w)
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
        if dialog.exec_()!=QDialog.Accepted:return
        filters=[]
        if hp.isChecked():filters.append('highpass=f=80')
        if comp.isChecked():filters.append('acompressor=threshold=0.125:ratio=3:attack=10:release=150:makeup=1.5')
        if norm.isChecked():filters.append('loudnorm=I=-16:TP=-1.5:LRA=11')
        if not filters:return
        def process(progress):
            mapping={};media=self.project.folder/'media';media.mkdir(parents=True,exist_ok=True)
            for i,id in enumerate(voices):
                out=media/(uid()+'_voz-corregida.wav');ffmpeg(['-y','-i',self.project.assets[id].path,'-af',','.join(filters),'-ar',RATE,'-c:a','pcm_s24le',out]);mapping[id]=self.project.add_asset(out,False);progress(int((i+1)/len(voices)*100))
            return mapping
        def done(mapping):
            for c in self.project.clips:
                if c.asset in mapping and c.offset+c.length>mapping[c.asset].frames+1:raise ValueError('La duración del tratamiento ha cambiado; se conserva la voz anterior.')
            self.project.remember()
            for c in self.project.clips:
                if c.asset in mapping:c.asset=mapping[c.asset].id;c.length=min(c.length,self.project.assets[c.asset].frames-c.offset)
            self.statusBar().showMessage('Voz tratada. El original sigue en la carpeta media.',9000)
        self.work('Tratando la voz…',process,done)

    def open_audacity(self):
        executable=shutil.which('audacity')
        if not executable:raise ValueError('Instala Audacity para usar sus plugins.')
        if not self.project.frames:raise ValueError('Importa primero la voz.')
        dest=self.project.folder/('Audacity-voz-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.wav')
        def done(result):
            subprocess.Popen([executable,str(dest)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            QMessageBox.information(self,'Edición externa','Se ha abierto una copia de la voz montada en Audacity. Aplica tus plugins y exporta otro WAV/FLAC. Al importarlo como voz se inicia un montaje nuevo; el proyecto anterior se conserva si lo guardas.')
        self.work('Preparando voz para Audacity…',lambda progress:self.project.export(dest,progress,track=0),done)

    def open_path(self, path):
        from PyQt5.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def open_episode_item(self,index):
        path=Path(self.file_model.filePath(index))
        if path.is_file():self.open_path(path)

    def help(self):
        QMessageBox.information(self,'Compilando Studio '+__version__,
            'Ctrl+O · importar voz\nCtrl+S · exportar audio\nCtrl+Mayús+S · guardar proyecto\nCtrl+Mayús+O · abrir proyecto\nEspacio · Play/Pausa\nS · Stop\n← / → · 5 s; Mayús · 15 s; Ctrl · 1 s\n↑ / ↓ · voz / música\nInicio / Fin · principio / final\nM · elegir música e insertar/completar corte en el cursor\nCtrl+Intro · colocar música\nCtrl+I · dividir clip\nSupr · borrar clip (deja hueco)\n, / . · mover 0,5 s; Mayús · 5 s\nCtrl+Z / Ctrl+Mayús+Z · deshacer / rehacer\n\nInsertar corte musical abre el selector de archivos. Si cancelas, no se cambia la voz. Dentro de un hueco existente se completa ese corte, sin crear otro. Ctrl+Z deshace el corte nuevo y su música juntos. Pincha o arrastra POSICIÓN, la regla o la línea dorada para avanzar y retroceder. Música sola y Bajar bajo voz son dos tiempos independientes (5 s cada uno por defecto). Arrastra la cabecera para mover un clip. «Mover pista» desplaza toda la pista. Los originales no se alteran. Guarda y mueve siempre el proyecto junto a su carpeta media. La subida a plataformas es manual.')

    def dispatch_key(self,event):
        if self.busy:return False
        focus=QApplication.focusWidget()
        if isinstance(focus,(QLineEdit,QPlainTextEdit,QDoubleSpinBox,QSpinBox,QComboBox)):
            return False
        key=event.key();ctrl=bool(event.modifiers()&Qt.ControlModifier);shift=bool(event.modifiers()&Qt.ShiftModifier)
        action=None
        if key in (Qt.Key_Left,Qt.Key_Right):action=lambda:self.seek(self.timeline.cursor+(1 if key==Qt.Key_Right else -1)*(1 if ctrl else 15 if shift else 5)*RATE)
        elif key==Qt.Key_Space:action=self.pause if self.playing else self.play
        elif key==Qt.Key_S and not ctrl:action=self.stop
        elif key==Qt.Key_M and not ctrl:action=self.add_cue
        elif key==Qt.Key_I and ctrl:action=self.split
        elif key==Qt.Key_Z and ctrl:action=lambda:self.undo(shift)
        elif key in (Qt.Key_Return,Qt.Key_Enter) and ctrl:action=self.assign_music
        elif key==Qt.Key_Delete:action=self.delete
        elif key==Qt.Key_Up:action=lambda:self.select_track(0)
        elif key==Qt.Key_Down:action=lambda:self.select_track(1)
        elif key==Qt.Key_Home:action=lambda:self.seek(0)
        elif key==Qt.Key_End:action=lambda:self.seek(self.project.frames)
        elif key in (Qt.Key_Comma,Qt.Key_Less):action=lambda:self.nudge(-5 if shift else -.5)
        elif key in (Qt.Key_Period,Qt.Key_Greater):action=lambda:self.nudge(5 if shift else .5)
        elif key==Qt.Key_Escape:action=lambda:self.mode('cursor')
        if action:
            if not event.isAutoRepeat() or key in (Qt.Key_Left,Qt.Key_Right):self.guard(action)
            event.accept()
            return True
        return False

    def eventFilter(self,watched,event):
        if event.type()==QEvent.KeyPress and QApplication.activeWindow() is self:
            return self.dispatch_key(event)
        return super().eventFilter(watched,event)

    def keyPressEvent(self,event):
        if not self.dispatch_key(event):super().keyPressEvent(event)

    def closeEvent(self,event):
        if self.busy:
            QMessageBox.information(self,'Proceso en marcha','Espera a que termine la importación o exportación antes de cerrar.');event.ignore();return
        if not self.abandon():event.ignore();return
        self.pause();event.accept()
