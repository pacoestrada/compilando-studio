"""Regression for 0.1.1: visible insertion, five-second automation and seeking."""
from pathlib import Path
import tempfile,time,wave
import numpy as np
from PyQt5.QtCore import Qt,QPoint,QPointF,QEvent,QSettings
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication,QMessageBox,QFileDialog
from PyQt5.QtTest import QTest
from compilando.core import RATE
from compilando.ui import Studio

app=QApplication([])
errors=[]
QMessageBox.warning=lambda parent,title,message:errors.append(message)
with tempfile.TemporaryDirectory() as tmp:
    folder=Path(tmp)
    sources=[]
    for filename,hz in [('Voz-teleprompter.wav',220),('Musica.wav',440)]:
        p=folder/filename;t=np.arange(40*RATE)/RATE;y=.18*np.sin(2*np.pi*hz*t)
        with wave.open(str(p),'wb') as f:
            f.setnchannels(2);f.setsampwidth(2);f.setframerate(RATE);f.writeframes((np.column_stack([y,y])*32767).astype('<i2').tobytes())
        sources.append(p)
    w=Studio(folder/'episodio',folder/'cache',QSettings(str(folder/'settings.ini'),QSettings.IniFormat));w.show();w.activateWindow();app.processEvents()
    def wait_job():
        deadline=time.monotonic()+10
        while w.busy and time.monotonic()<deadline:app.processEvents();QTest.qWait(10)
        assert not w.busy,'worker did not finish'
        app.processEvents()
    w.import_voice(str(sources[0]));wait_job()
    assert w.project.duck_fade==w.duck_fade.value()==5
    assert w.gap.value()==5
    assert not w.view_row.isVisible(),'view-only scrollbar should not appear without zoom'
    # The visible button asks for a file, creates a cue and installs the music.
    QFileDialog.getOpenFileName=lambda *args,**kwargs:(str(sources[1]),'Audio')
    w.music_path=str(sources[1]);w.seek(4*RATE)
    QTest.mouseClick(w.insert_cue_button,Qt.LeftButton);wait_job()
    assert len(w.project.cues)==1
    assert len([c for c in w.project.clips if c.track==1])==1
    assert w.cue_state.text()=='Colocada'
    assert w.project.frames==45*RATE
    assert w.project.cue_position(w.project.cues[0])==4*RATE
    frozen=w.project.state()
    # A click in the position rail is absolute, not a page-step.
    s=w.position;h=s.height()//2
    QTest.mouseClick(s,Qt.LeftButton,pos=QPoint(int(s.width()*.8),h))
    assert .75*w.project.frames<w.timeline.cursor<.85*w.project.frames
    late=w.timeline.cursor
    QTest.mousePress(s,Qt.LeftButton,pos=QPoint(int(s.width()*.8),h))
    app.sendEvent(s,QMouseEvent(QEvent.MouseMove,QPointF(s.width()*.2,h),Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
    QTest.mouseRelease(s,Qt.LeftButton,pos=QPoint(int(s.width()*.2),h))
    assert .15*w.project.frames<w.timeline.cursor<.25*w.project.frames
    assert w.timeline.cursor<late
    assert w.position.value()==w.timeline.cursor
    # Ruler dragging works in mark mode without inserting or moving clips.
    w.mode('mark');timeline=w.timeline
    p1=QPoint(int(timeline.x(7*RATE)),15);p2=QPoint(int(timeline.x(27*RATE)),15)
    QTest.mousePress(timeline,Qt.LeftButton,pos=p1)
    app.sendEvent(timeline,QMouseEvent(QEvent.MouseMove,QPointF(p2),Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
    QTest.mouseRelease(timeline,Qt.LeftButton,pos=p2)
    assert abs(timeline.cursor-27*RATE)<RATE/5
    assert w.project.state()==frozen,'seeking must not edit the project'
    # Grab the line itself lower down, away from the ruler.
    p1=QPoint(int(timeline.x(timeline.cursor)),110);p2=QPoint(int(timeline.x(16*RATE)),110)
    QTest.mousePress(timeline,Qt.LeftButton,pos=p1)
    app.sendEvent(timeline,QMouseEvent(QEvent.MouseMove,QPointF(p2),Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
    QTest.mouseRelease(timeline,Qt.LeftButton,pos=p2)
    assert abs(timeline.cursor-16*RATE)<RATE/5
    assert w.project.state()==frozen
    # The global position bar still reaches the whole episode when zoomed.
    w.zoom(4);assert w.view_row.isVisible()
    QTest.mouseClick(s,Qt.LeftButton,pos=QPoint(int(s.width()*.9),h))
    assert w.timeline.cursor>38*RATE
    assert timeline.view<=timeline.cursor<=timeline.view+timeline.span
    # Check transport resume policy without using an unavailable audio device.
    real_play=w.play;calls=[]
    def fake_play():calls.append(timeline.cursor);w.playing=True
    w.play=fake_play;w.playing=True
    QTest.mousePress(s,Qt.LeftButton,pos=QPoint(int(s.width()*.25),h));assert not w.playing
    QTest.mouseRelease(s,Qt.LeftButton,pos=QPoint(int(s.width()*.3),h));assert w.playing and len(calls)==1
    w.playing=False;w.play=real_play
    w.duck_fade.setValue(3);assert w.project.music_duck_fade(w.music_target())==3
    w.undo();assert w.project.music_duck_fade(w.music_target())==5
    w.zoom(0);w.seek(10*RATE);w.mode('cursor')
    w.music_folder=folder;w.refresh_music();app.processEvents()
    w.grab().save('/tmp/compilando-studio-011.png')
    w.project.dirty=False;w.close();app.processEvents()
    assert not errors,errors
print('PASS: insert-and-assign button; five-second defaults; click/drag seeking both directions; ruler/playhead in mark mode; zoom-independent seeking; playback resumes once; editable/undoable fade.')
