"""Direct editing: clip selection, volume, transport, undo and layout isolation."""
from pathlib import Path
import tempfile
import wave
import numpy as np
from PyQt5.QtCore import Qt, QPoint, QPointF, QEvent, QSettings
from PyQt5.QtGui import QMouseEvent, QFont
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtTest import QTest
from compilando.core import RATE, Project
from compilando.ui import Studio, STYLE

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
    def drag(a, b, modifiers=Qt.NoModifier):
        QTest.mousePress(timeline, Qt.LeftButton, modifiers, pos=QPoint(round(a.x()),round(a.y())))
        app.sendEvent(timeline, QMouseEvent(QEvent.MouseMove,b,Qt.NoButton,Qt.LeftButton,modifiers))
        QTest.mouseRelease(timeline,Qt.LeftButton,modifiers,pos=QPoint(round(b.x()),round(b.y())))
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
    # A single click anywhere on a clip selects without seeking, pausing or editing.
    state = p.state();cursor = timeline.cursor;history=len(p.undo_stack)
    seek_events=[];timeline.seeked.connect(seek_events.append)
    QTest.mouseClick(timeline,Qt.LeftButton,pos=QPoint(round(timeline.x(cursor)),90))
    assert timeline.track == 0 and p.state()==state and timeline.cursor==cursor
    QTest.mouseClick(timeline,Qt.LeftButton,pos=QPoint(round(timeline.x(cursor)),195))
    assert timeline.selected_id==first and p.state()==state and timeline.cursor==cursor
    assert not seek_events and len(p.undo_stack)==history
    QTest.keyClick(timeline,Qt.Key_Up);assert timeline.track==0
    QTest.keyClick(timeline,Qt.Key_Down);assert timeline.selected_id==first
    # The former read-only curve can be dragged directly, with one Undo per gesture.
    before=p.state();undo=len(p.undo_stack)
    handle=dict(timeline.volume_handles(p.find(first)))['gain']
    drag(handle,handle+QPointF(0,8))
    assert p.find(first).gain<0 and timeline.cursor==cursor
    assert len(p.undo_stack)==undo+1 and p.find(second).gain==0
    edited=p.state();w.undo();assert p.state()==before
    w.undo(True);assert p.state()==edited
    w.undo()
    # A coincident playhead never steals volume dragging, with no mode switch.
    handle=dict(timeline.volume_handles(p.find(first)))['bed']
    w.seek(timeline.frame(handle.x()));cursor=timeline.cursor
    before=p.state();baseline_bed=music_rms(20)
    drag(handle,handle+QPointF(0,-14))
    assert p.find(first).bed > -24 and timeline.cursor==cursor
    assert p.find(second).bed is None and p.bed==-24
    assert music_rms(20)>baseline_bed*2 and w.bed.value()==round(p.find(first).bed*10)
    w.undo();assert p.state()==before
    # Away from the thin curve, the entire music waveform edits the bed.
    w.seek(21*RATE);cursor=timeline.cursor
    point=QPointF(timeline.x(cursor),185)
    assert abs(point.y()-timeline.volume_y(p.find(first),-24))>10
    w.playing=True  # Selection/volume must not pause or seek an active transport.
    drag(point,point+QPointF(0,10))
    assert p.find(first).bed==-29 and timeline.cursor==cursor and w.playing
    assert p.find(second).bed is None
    w.undo();assert p.state()==before
    # Fine adjustment and voice volume share the same direct interaction.
    drag(point,point+QPointF(0,-10),Qt.ShiftModifier)
    assert p.find(first).bed==-23
    w.undo();assert p.state()==before
    voice_point=QPointF(timeline.x(21*RATE),90)
    voice_id=timeline.hit(voice_point).id
    drag(voice_point,voice_point+QPointF(0,8))
    assert p.find(voice_id).gain==-4 and timeline.cursor==cursor
    w.undo();assert p.state()==before
    # Header selection must not seek. Header drag moves one clip; Shift moves track.
    header=QPointF(timeline.x(7*RATE),160)
    original_starts={c.id:c.start for c in p.clips}
    drag(header,header+QPointF(22,0))
    assert p.find(first).start>original_starts[first]
    assert all(c.start==original_starts[c.id] for c in p.clips if c.id!=first)
    assert timeline.cursor==cursor
    w.undo();assert p.state()==before
    drag(header,header+QPointF(22,0),Qt.ShiftModifier)
    delta=p.find(first).start-original_starts[first]
    assert delta>0 and p.find(second).start-original_starts[second]==delta
    assert all(c.start==original_starts[c.id] for c in p.clips if c.track==0)
    w.undo();assert p.state()==before
    # Double click deliberately seeks; it never leaves a volume gesture active.
    QTest.mouseDClick(timeline,Qt.LeftButton,pos=QPoint(round(timeline.x(18*RATE)),190))
    QTest.mouseRelease(timeline,Qt.LeftButton,pos=QPoint(round(timeline.x(18*RATE)),190))
    assert abs(timeline.cursor-18*RATE)<RATE/4 and p.state()==before
    assert timeline.volume_drag is None and not timeline.scrubbing
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
    w.grab().save('/tmp/compilando-studio-014-edicion.png')
    def settle():
        for _ in range(8):app.processEvents()
    def check_layout():
        assert w.clip_gain.isVisible() and w.timeline.width()>=400
        console=w.console_scroll.widget()
        def top(widget):return widget.mapTo(console,QPoint(0,0)).y()
        def bottom(widget):return widget.mapTo(console,QPoint(0,widget.height())).y()
        assert bottom(timeline)<=top(w.position), 'Position control overlaps music'
        assert bottom(w.editor_panel)<=top(w.insert_cue_button), 'Editor overlaps insertion row'
        assert bottom(w.workspace)<=top(w.delivery), 'Editor/rack overlaps export'
        assert bottom(w.insert_cue_button)<bottom(w.editor_area), 'Cue escapes editor'
        assert bottom(w.fade)<bottom(w.rack), 'Music controls escape rack'
        assert bottom(w.output)<=top(w.files), 'Export overlaps files'
        assert bottom(w.files)<=bottom(w.delivery), 'Files escape delivery'
    for width,height in [(1050,720),(1450,920)]:
        w.resize(width,height);settle();check_layout()
        # Dragging the splitter cannot compress the rack or editor below its minimum.
        w.vertical_splitter.setSizes([200,900]);settle();check_layout()
        w.vertical_splitter.setSizes([900,100]);settle();check_layout()
        for zoom in (0,2):w.zoom(zoom);settle();check_layout()
    # Linux desktop text scaling is independent from Qt's pixel scaling.
    font=QFont(app.font());font.setPointSize(15);app.setFont(font)
    w.setStyleSheet(STYLE.replace('13px','18px'))
    w.resize(1450,920);settle();check_layout()
    assert w.console_scroll.verticalScrollBar().maximum()>0
    w.grab().save('/tmp/compilando-studio-014-letra-grande.png')
    w.project.dirty=False;w.close();app.processEvents()
    assert not errors,errors
print('PASS: direct selection and volume across playhead; fine adjustment; header/track movement; double-click/ruler seek; one-step undo; per-clip audio export; small/large fonts, zoom and splitter layout.')
