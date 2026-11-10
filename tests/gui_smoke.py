"""Offscreen UI and keyboard integration checks; no audio device required."""
from pathlib import Path
import tempfile
import time
import wave
import numpy as np
from PyQt5.QtCore import Qt,QPoint,QPointF,QEvent,QSettings
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication,QMessageBox,QFileDialog
from PyQt5.QtTest import QTest
from compilando.ui import Studio
from compilando.core import RATE

app=QApplication([])
errors=[]
QMessageBox.warning=lambda parent,title,message:errors.append(message)
with tempfile.TemporaryDirectory() as tmp:
    root=Path(tmp)
    voice=root/'Voz-teleprompter.wav';music=root/'Musica-prueba.wav'
    for path,hz in [(voice,220),(music,440)]:
        t=np.arange(RATE*30)/RATE
        y=.2*np.sin(2*np.pi*hz*t)*(0.2+.8*np.abs(np.sin(t*3)))
        with wave.open(str(path),'wb') as f:
            f.setnchannels(2);f.setsampwidth(2);f.setframerate(RATE);f.writeframes((np.column_stack([y,y])*32767).astype('<i2').tobytes())
    w=Studio(root/'episodio',root/'cache',QSettings(str(root/'settings.ini'),QSettings.IniFormat));w.show();w.activateWindow();app.processEvents()
    assert w.file_model.filePath(w.files.rootIndex())==str(root/'episodio')
    def wait_job():
        end=time.monotonic()+10
        while w.busy and time.monotonic()<end:app.processEvents();QTest.qWait(10)
        assert not w.busy,'background job timed out'
        w.activateWindow();app.processEvents()
    w.import_voice(str(voice));wait_job()
    assert w.project.frames==30*RATE
    w.timeline.setFocus();QTest.keyClick(w.timeline,Qt.Key_Right)
    assert w.timeline.cursor==5*RATE,'advance key failed'
    QFileDialog.getOpenFileName=lambda *args,**kwargs:(str(music),'Audio')
    QTest.keyClick(w.timeline,Qt.Key_M);wait_job()
    assert len(w.project.cues)==1 and w.project.frames==35*RATE
    w.music_path=str(music);w.update_assignment();assert w.assign_button.isEnabled()
    w.assign_music();wait_job();assert w.cue_state.text()=='Colocada'
    # Single cue is assignable even when a second cue is empty.
    w.seek(20*RATE);w.add_cue(auto_assign=False);w.cue_id=w.project.cues[0].id;w.refresh();w.music_path=str(music);w.update_assignment();assert w.assign_button.isEnabled()
    w.seek(RATE);w.select_track(0);w.timeline.setFocus();QTest.keyClick(w.timeline,Qt.Key_I,Qt.ControlModifier)
    assert len([c for c in w.project.clips if c.track==0])==4
    c=w.project.find(w.timeline.selected_id);before=c.start
    r=w.timeline.rect_for(c);p=QPointF(r.x()+10,r.y()+8)
    app.sendEvent(w.timeline,QMouseEvent(QEvent.MouseButtonPress,p,Qt.LeftButton,Qt.LeftButton,Qt.NoModifier))
    app.sendEvent(w.timeline,QMouseEvent(QEvent.MouseMove,p+QPointF(30,0),Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
    app.sendEvent(w.timeline,QMouseEvent(QEvent.MouseButtonRelease,p+QPointF(30,0),Qt.LeftButton,Qt.NoButton,Qt.NoModifier))
    assert w.project.find(c.id).start>before,'drag failed'
    w.undo();assert w.project.find(c.id).start==before
    w.search.setFocus();QTest.keyClick(w.search,Qt.Key_M);assert w.search.text()=='m'
    w.master.setValue(-600);assert not w.project.render(0,1000).any();w.master.setValue(0)
    w.project.metadata['title']='Prueba de montaje · Compilando'
    w.save_project();assert w.project.file.exists()
    w.music_folder=root;w.search.clear();w.refresh_music();w.timeline.setFocus();w.resize(1450,920);app.processEvents()
    w.grab().save('/tmp/compilando-studio-funcional.png')
    assert w.assign_button.isEnabled() and w.cue_id
    w.project.dirty=False;w.close();app.processEvents()
    assert not errors,errors
print('PASS: real WAV import worker; keyboard navigation/cuts; cue assignment; mouse drag/undo; text fields; master mute; saving; episode-only browser.')
