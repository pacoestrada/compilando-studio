"""Regressions for the volume controls reported in Paco's 0.1.2 screenshot."""
from pathlib import Path
import tempfile
import wave
import numpy as np
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent, QSettings
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtTest import QTest
from compilando.core import RATE, Project
from compilando.ui import Studio

app = QApplication([])
errors = []
QMessageBox.warning = lambda parent, title, message: errors.append(message)
with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    w = Studio(root/'episodio-demo', root/'cache', QSettings(str(root/'settings.ini'), QSettings.IniFormat))
    for name in ('Voz-demo.wav', 'Sintonía-demo.wav'):
        t = np.arange(45*RATE)/RATE
        y = .35*np.sin(2*np.pi*220*t)*(.25+.75*np.abs(np.sin(3*t)))
        with wave.open(str(root/name), 'wb') as out:
            out.setnchannels(2);out.setsampwidth(2);out.setframerate(RATE)
            out.writeframes((np.column_stack([y,y])*32767).astype('<i2').tobytes())
    p = w.project
    p.import_voice(p.add_asset(root/'Voz-demo.wav'))
    music = p.add_asset(root/'Sintonía-demo.wav')
    c1 = p.insert_music(5*RATE, music)
    c2 = p.insert_music(30*RATE, music)
    first, second = c1.id, c2.id
    w.refresh();w.show();w.activateWindow();app.processEvents()
    w.seek(21*RATE);w.select_clip(first)
    timeline = w.timeline
    def music_rms(at, project=None):
        a = (project or w.project).render(int(at*RATE), 2000, track=1)
        return float(np.sqrt(np.mean(a*a)))
    def drag(a, b):
        QTest.mousePress(timeline, Qt.LeftButton, pos=QPoint(round(a.x()),round(a.y())))
        app.sendEvent(timeline, QMouseEvent(QEvent.MouseMove,b,Qt.NoButton,Qt.LeftButton,Qt.NoModifier))
        QTest.mouseRelease(timeline,Qt.LeftButton,pos=QPoint(round(b.x()),round(b.y())))
        app.processEvents()
    # The numeric control and fader update immediately, including the waveform.
    baseline = music_rms(7)
    image_before = timeline.grab().toImage()
    w.clip_gain.setValue(-6)
    assert p.find(first).gain == -6 and w.clip_gain_slider.value() == -60
    assert abs(music_rms(7)/baseline - 10**(-6/20)) < 1e-6
    assert image_before != timeline.grab().toImage()
    w.clip_gain_slider.setValue(-120)
    assert p.find(first).gain == w.clip_gain.value() == -12
    assert p.find(second).gain == 0
    w.timeline.setFocus();QTest.keyClick(timeline, Qt.Key_Up, Qt.AltModifier)
    assert p.find(first).gain == -11
    QTest.mouseClick(w.reset_clip_gain,Qt.LeftButton)
    assert p.find(first).gain == 0
    # Selecting a track changes only selection, never gain or the playhead.
    state = p.state();cursor = timeline.cursor
    QTest.mouseClick(w.track_buttons[0],Qt.LeftButton)
    assert timeline.track == 0 and p.state()==state and timeline.cursor==cursor
    QTest.mouseClick(w.track_buttons[1],Qt.LeftButton)
    assert timeline.selected_id==first and w.track_buttons[1].isChecked()
    # The former read-only curve can be dragged directly, with one Undo per gesture.
    before=p.state();undo=len(p.undo_stack)
    handle=dict(timeline.volume_handles(p.find(first)))['gain']
    drag(handle,handle+QPointF(0,8))
    assert p.find(first).gain<0 and timeline.cursor==cursor
    assert len(p.undo_stack)==undo+1 and p.find(second).gain==0
    edited=p.state();w.undo();assert p.state()==before
    w.undo(True);assert p.state()==edited
    w.undo()
    # Volume mode takes precedence over a coincident playhead; ruler still seeks.
    w.mode('volume');handle=dict(timeline.volume_handles(p.find(first)))['bed']
    w.seek(timeline.frame(handle.x()));cursor=timeline.cursor
    before=p.state();baseline_bed=music_rms(20)
    drag(handle,handle+QPointF(0,-9))
    assert p.find(first).bed > -24 and timeline.cursor==cursor
    assert p.find(second).bed is None and p.bed==-24
    assert music_rms(20)>baseline_bed*2 and w.bed.value()==round(p.find(first).bed*10)
    w.undo();assert p.state()==before
    # Horizontal movement of the low handle edits the actual fade duration.
    handle=dict(timeline.volume_handles(p.find(first)))['bed']
    fade_before=p.music_duck_fade(p.find(first))
    drag(handle,handle+QPointF(timeline.width()/20,0))
    assert p.music_duck_fade(p.find(first)) > fade_before
    assert p.find(first).bed==-24 and p.find(second).duck_fade is None
    assert w.duck_fade.value()==p.music_duck_fade(p.find(first))
    w.undo();assert p.state()==before
    # Side controls target the selected music only and repaint while stopped.
    image_before=timeline.grab().toImage();w.bed.setValue(-120)
    assert p.find(first).bed==-12 and p.bed==-24 and p.find(second).bed is None
    assert image_before!=timeline.grab().toImage()
    w.duck_fade.setValue(3)
    assert p.find(first).duck_fade==3 and p.find(second).duck_fade is None
    # Immediate changes must also survive save/load and lossless export.
    p.save();loaded=Project.load(p.file,root/'reopened')
    np.testing.assert_array_equal(p.render(0,p.frames),loaded.render(0,loaded.frames))
    out=root/'mix.wav';p.export(out);decoded=p.add_asset(out,False)
    np.testing.assert_allclose(decoded.data,p.render(0,p.frames),atol=2e-7)
    w.seek(20*RATE);state=p.state()
    QTest.mouseClick(timeline,Qt.LeftButton,pos=QPoint(round(timeline.x(12*RATE)),15))
    assert abs(timeline.cursor-12*RATE)<RATE/4 and p.state()==state
    # A long clip remains editable after zooming and horizontal scrolling.
    w.zoom(3);w.scroll.setValue(6*RATE);w.select_clip(first)
    point=QPointF(timeline.x(18*RATE),timeline.rect_for(p.find(first)).bottom()-20)
    cursor=timeline.cursor;drag(point,point+QPointF(0,-4))
    assert timeline.cursor==cursor and p.find(first).bed>-12
    # Slider drag creates one history entry even with multiple live updates.
    before=p.state();undo=len(p.undo_stack)
    w.clip_gain_slider.setSliderDown(True)
    for value in (-10,-20,-30):w.clip_gain_slider.setValue(value)
    w.clip_gain_slider.setSliderDown(False)
    assert len(p.undo_stack)==undo+1
    w.undo();assert p.state()==before
    w.zoom(0);w.zoom(2);w.scroll.setValue(0);w.seek(11*RATE);w.select_clip(first)
    w.bed.setValue(-240);w.duck_fade.setValue(5);w.clip_gain.setValue(-3)
    w.music_folder=root;w.refresh_music();w.output.setText('episodio-demo')
    w.resize(1450,960);app.processEvents()
    w.grab().save('/tmp/compilando-studio-013-volumen.png')
    for width,height in [(1050,720),(1450,920)]:
        w.resize(width,height);app.processEvents()
        assert w.clip_gain.isVisible() and w.timeline.width()>=400
        assert w.timeline.mapTo(w.centralWidget(),QPoint(0,w.timeline.height())).y() <= w.position.mapTo(w.centralWidget(),QPoint(0,0)).y(), 'Position control overlaps the music'
    w.project.dirty=False;w.close();app.processEvents()
    assert not errors,errors
print('PASS: immediate gain/fader/waveform; selectors; editable curve; per-clip bed/fade; cursor isolation; one-step undo; zoom; save/reload; exported samples.')
