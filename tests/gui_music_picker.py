"""Exercise the actual file dialog and the empty-gap case reported in 0.1.1."""
from pathlib import Path
import hashlib
import tempfile
import time
import wave
import numpy as np
from PyQt5.QtCore import Qt, QTimer, QSettings
from PyQt5.QtWidgets import QApplication, QFileDialog, QMessageBox, QLineEdit, QDialogButtonBox
from PyQt5.QtTest import QTest
from compilando.core import RATE, Project
from compilando.ui import Studio

app = QApplication([])
errors = []
QMessageBox.warning = lambda parent, title, message: errors.append(message)
native_picker = QFileDialog.getOpenFileName
dialogs = []
responses = []

def automated_picker(parent, title, initial, filters):
    """Use the real Qt dialog, with a timer standing in for file selection."""
    assert responses, 'An unexpected file dialog opened'
    response = responses.pop(0)
    assert isinstance(parent, Studio)
    dialogs.append((title, initial, filters))
    def answer():
        dialog = app.activeModalWidget()
        assert isinstance(dialog, QFileDialog), 'The insert button did not open a file browser'
        if response is None:
            dialog.reject()
        else:
            dialog.setDirectory(str(response.parent))
            def select_and_open():
                dialog.findChild(QLineEdit, 'fileNameEdit').setText(response.name)
                dialog.findChild(QDialogButtonBox).button(QDialogButtonBox.Open).click()
            QTimer.singleShot(100, select_and_open)
    QTimer.singleShot(100, answer)
    return native_picker(parent, title, initial, filters, options=QFileDialog.DontUseNativeDialog)

QFileDialog.getOpenFileName = automated_picker

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    music_dir = root/'Músicas para el episodio'
    music_dir.mkdir()
    voice, music = root/'Voz.wav', music_dir/'Sintonía de prueba.wav'
    for path, hz in [(voice, 220), (music, 440)]:
        t = np.arange(40*RATE)/RATE
        signal = .2*np.sin(2*np.pi*hz*t)
        with wave.open(str(path), 'wb') as f:
            f.setnchannels(2);f.setsampwidth(2);f.setframerate(RATE)
            f.writeframes((np.column_stack([signal, signal])*32767).astype('<i2').tobytes())
    original_hash = hashlib.sha256(voice.read_bytes()).hexdigest()
    broken = music_dir/'Corrupto.wav';broken.write_text('This is not audio.')
    settings = QSettings(str(root/'preferences.ini'), QSettings.IniFormat)
    w = Studio(root/'episodio', root/'cache', settings)
    w.show();w.activateWindow();app.processEvents()

    def wait_job():
        deadline = time.monotonic()+10
        while (w.busy or w.jobs) and time.monotonic()<deadline:
            app.processEvents();QTest.qWait(10)
        assert not w.busy and not w.jobs, 'Import worker did not finish'
        app.processEvents()

    def insert(response):
        responses.append(response)
        QTest.mouseClick(w.insert_cue_button, Qt.LeftButton)
        wait_job()
        assert not responses

    w.import_voice(str(voice));wait_job()
    w.seek(round(16.3*RATE))
    before = w.project.state();history = list(w.project.undo_stack)
    assets = set(w.project.assets)
    # No music has been selected. The button must ask, without editing on Cancel.
    assert not w.music_path
    insert(None)
    assert len(dialogs)==1 and '*.flac' in dialogs[-1][2]
    assert w.project.state()==before and w.project.undo_stack==history
    assert set(w.project.assets)==assets
    # A decode error must not split voice, copy the broken file or leave a gap.
    insert(broken)
    assert len(errors)==1;errors.clear()
    assert w.project.state()==before and w.project.undo_stack==history
    assert set(w.project.assets)==assets
    assert not list((w.project.folder/'media').glob('*Corrupto.wav'))
    # Successful selection completes both operations; one Undo restores the voice.
    insert(music)
    assert w.project.frames==45*RATE and len(w.project.cues)==1
    assert w.cue_state.text()=='Colocada'
    assert 'Sintonía de prueba.wav' in w.cues.currentText()
    assert w.music_path==str(music) and w.music_folder==music_dir
    assert w.music_list.currentItem().data(Qt.UserRole)==str(music)
    assert settings.value('music_folder')==str(music_dir)
    assert w.project.render(19*RATE, RATE, track=1).any()
    inserted = w.project.state()
    w.undo();assert w.project.state()==before
    w.undo(True);assert w.project.state()==inserted
    w.undo()
    # Recreate and reopen a 0.1.1 empty P1: cursor 19.7 is INSIDE its 16.3–21.3 gap.
    q = w.project.add_cue(round(16.3*RATE), 5)
    w.project.save()
    w.project = Project.load(w.project.file, root/'reopened-cache')
    w.refresh();w.music_list.setCurrentRow(-1);w.music_path='';w.update_assignment()
    w.seek(round(19.7*RATE))
    empty = w.project.state();duration = w.project.frames
    assert w.assign_button.isEnabled() and 'Elegir música' in w.assign_button.text()
    insert(None);assert w.project.state()==empty
    insert(music)
    assert 'P1' in dialogs[-1][0]
    assert w.project.frames==duration and len(w.project.cues)==1
    assert w.project.cues[0].id==q.id
    assert [c for c in w.project.state()['clips'] if c['track']==0]==empty['clips']
    music_clip = next(c for c in w.project.clips if c.track==1)
    assert music_clip.start==round(16.3*RATE)
    copied = w.project.assets[music_clip.asset].path
    assert copied.is_relative_to(w.project.folder/'media')
    assert hashlib.sha256(copied.read_bytes()).hexdigest()==hashlib.sha256(music.read_bytes()).hexdigest()
    # The side button also offers the picker when no browser item is selected.
    w.undo();assert w.project.state()==empty
    w.music_list.setCurrentRow(-1);w.music_path='';w.update_assignment()
    responses.append(music)
    QTest.mouseClick(w.assign_button, Qt.LeftButton);wait_job()
    assert not responses and w.cue_state.text()=='Colocada'
    assert w.project.frames==duration and len(w.project.cues)==1
    # A list refresh must not silently forget the song selection.
    w.refresh_music();assert w.music_path==str(music)
    # Replacing music inside the gap must not open a second gap.
    insert(music)
    assert w.project.frames==duration and len([c for c in w.project.clips if c.track==1])==1
    # A failed drop uses the same transactional path, with no partial voice cut.
    state=w.project.state()
    w.drop_audio(str(broken), 30*RATE, 1);wait_job()
    assert len(errors)==1;errors.clear()
    assert w.project.state()==state
    w.drop_audio(str(music), round(19.7*RATE), 1);wait_job()
    assert w.project.frames==duration and len(w.project.cues)==1
    assert hashlib.sha256(voice.read_bytes()).hexdigest()==original_hash
    w.resize(1450,920);app.processEvents()
    w.grab().save('/tmp/compilando-studio-012.png')
    w.project.dirty=False;w.close();app.processEvents()
    reopened=Studio(root/'another-episode', root/'another-cache', settings)
    assert reopened.music_folder==music_dir
    reopened.close();app.processEvents()
    assert not errors, errors

print('PASS: actual file picker; cancel/decode failure leave voice intact; one-step undo/redo; reopened 0.1.1 gap at 19.7 s; side picker; replacement/drop without duplicate gap; music selection/folder retained; original files unchanged.')
