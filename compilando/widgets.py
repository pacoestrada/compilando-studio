import math
from pathlib import Path
import numpy as np
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QMimeData, QUrl
from PyQt5.QtGui import QColor, QPainter, QPen, QLinearGradient, QFont, QDrag, QPolygonF
from PyQt5.QtWidgets import QWidget, QListWidget, QAbstractItemView, QSlider, QStyle, QStyleOptionSlider
from .core import RATE, FORMATS

def clock(frame):
    seconds = max(0, frame) / RATE
    return f'{int(seconds)//60:02d}:{int(seconds)%60:02d}.{int(seconds*10)%10}'

class PeakMeter(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.levels = [-60., -60.]
        self.peaks = [-60., -60.]
        self.clipped = False
        self.setMinimumSize(100, 230)
        self.setToolTip('Picos digitales de la mezcla, después del máster. Clic para borrar picos.')

    def set_levels(self, values):
        self.levels = [max(-60, 20 * math.log10(max(float(x), 1e-9))) for x in values]
        self.peaks = [max(a, b) for a, b in zip(self.peaks, self.levels)]
        self.clipped |= max(self.levels) > 0
        self.update()

    def mousePressEvent(self, event):
        self.peaks = [-60., -60.]
        self.clipped = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#171e20'))
        w, h = self.width(), self.height()
        top, bottom = 38, h - 30
        p.setFont(QFont('Monospace', 9))
        for channel in range(2):
            x, bw = 9 + channel * 27, 19
            p.setPen(QColor('#d9dfca'))
            peak = self.peaks[channel]
            label = '−∞' if peak <= -60 else f'{peak:.1f}'
            p.drawText(QRectF(x-6, 3, 34, 16), Qt.AlignCenter, label)
            p.drawText(QRectF(x, 18, bw, 16), Qt.AlignCenter, 'LR'[channel])
            for j in range(40):
                value = -60 + j * 1.5
                color = '#43da90' if value < -12 else '#ebc457' if value < -3 else '#f06c57'
                y = bottom - (j+1) / 40 * (bottom-top)
                p.fillRect(QRectF(x, y, bw, max(1, (bottom-top)/40 - 2)), QColor(color if self.levels[channel] > value else '#2b3537'))
            if peak > -60:
                y = bottom - min(60, peak+60) / 60 * (bottom-top)
                p.fillRect(QRectF(x, y, bw, 2), QColor('#fff3c6'))
        p.setPen(QColor('#b4c0ba'))
        for n in [0, -6, -12, -24, -36, -60]:
            y = bottom - (n+60)/60 * (bottom-top)
            p.drawText(QRectF(65, y-8, w-65, 16), Qt.AlignLeft, str(n))
        p.setPen(QColor('#ff846d' if self.clipped else '#bdc6bc'))
        p.drawText(QRectF(0, h-24, w, 20), Qt.AlignCenter, 'CLIP · clic' if self.clipped else 'dBFS · PICO')

class MusicList(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setWordWrap(True)

    def startDrag(self, actions):
        item = self.currentItem()
        if not item or not Path(item.data(Qt.UserRole)).is_file():
            return
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(item.data(Qt.UserRole))])
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec_(Qt.CopyAction)

class PositionSlider(QSlider):
    """Absolute click/drag seeking, independent of timeline zoom/scroll."""
    seekRequested = pyqtSignal(int)
    scrubStarted = pyqtSignal()
    scrubFinished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(Qt.Horizontal, parent)
        self.setObjectName('position')
        self.setMinimumHeight(25)
        self.setToolTip('Pincha o arrastra para avanzar y retroceder por todo el episodio.')

    def seek_at(self, x):
        option = QStyleOptionSlider();self.initStyleOption(option)
        groove = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderGroove, self)
        handle = self.style().subControlRect(QStyle.CC_Slider, option, QStyle.SC_SliderHandle, self)
        span = max(1, groove.width()-handle.width())
        position = max(0, min(span, int(x-groove.x()-handle.width()/2)))
        value = QStyle.sliderValueFromPosition(self.minimum(), self.maximum(), position, span, option.upsideDown)
        self.setValue(value);self.seekRequested.emit(value)

    def mousePressEvent(self, event):
        if event.button()==Qt.LeftButton:
            self.setFocus();self.scrubStarted.emit();self.setSliderDown(True);self.seek_at(event.x());event.accept()
        else:super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.isSliderDown():self.seek_at(event.x());event.accept()
        else:super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button()==Qt.LeftButton and self.isSliderDown():
            self.seek_at(event.x());self.setSliderDown(False);self.scrubFinished.emit();event.accept()
        else:super().mouseReleaseEvent(event)

class Timeline(QWidget):
    selected = pyqtSignal(str)
    seeked = pyqtSignal(int)
    changed = pyqtSignal()
    editStarted = pyqtSignal()
    dropped = pyqtSignal(str, int, int)
    cueRequested = pyqtSignal(int)
    scrubStarted = pyqtSignal()
    scrubFinished = pyqtSignal()

    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self.cursor = 0
        self.selected_id = ''
        self.track = 0
        self.mode = 'cursor'
        self.zoom = 1.0
        self.view = 0
        self.drag = None
        self.scrubbing = False
        self.setMinimumSize(400, 270)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)

    @property
    def span(self):
        if self.drag:
            return self.drag['span']
        return max(RATE, int(max(RATE*10, self.project.frames*1.08) / self.zoom))

    def x(self, frame):
        return 14 + (frame - self.view) / self.span * max(1, self.width()-28)

    def frame(self, x):
        return max(0, int(self.view + (x-14) / max(1, self.width()-28) * self.span))

    def rect_for(self, c):
        return QRectF(self.x(c.start), 40 + c.track*110, max(2, self.x(c.end)-self.x(c.start)), 88)

    def hit(self, point):
        return next((c for c in reversed(self.project.clips) if self.rect_for(c).contains(point)), None)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor('#1c2425'))
        p.setFont(QFont('Sans', 9))
        target = self.span / RATE / max(2, (self.width()-28)/95)
        step = next((x for x in [1,2,5,10,15,30,60,120,300,600,900,1800,3600,7200] if x >= target), max(7200, math.ceil(target))) * RATE
        for t in range(int(self.view//step*step), self.view+self.span+1, int(step)):
            x = self.x(t)
            if x < 0:
                continue
            p.setPen(QColor('#35403f'))
            p.drawLine(QPointF(x, 30), QPointF(x, 245))
            p.setPen(QColor('#bfc8bd'))
            p.drawText(QRectF(min(x+2, self.width()-70), 6, 70, 20), Qt.AlignLeft, clock(t).split('.')[0])
        for i, name in enumerate(['VOZ', 'MÚSICA']):
            p.setPen(QColor('#8e9b94'))
            p.drawText(16, 37 + i*110, name)
        for q in self.project.cues:
            x = self.x(self.project.cue_position(q))
            p.fillRect(QRectF(x, 40, self.x(self.project.cue_position(q)+q.gap)-x, 88), QColor('#665330'))
            p.setPen(QColor('#f0ce78'))
            p.drawLine(QPointF(x, 29), QPointF(x, 242))
            idx = self.project.cues.index(q) + 1
            p.drawText(QPointF(x+4, 137), 'P'+str(idx))
        regions = self.project.voice_regions()
        for c in self.project.clips:
            r = self.rect_for(c)
            if r.right() < 0 or r.left() > self.width():
                continue
            color = QColor('#365669' if c.track == 0 else '#59506b')
            p.setPen(QPen(QColor('#e9d8a5') if c.id == self.selected_id else color, 2 if c.id == self.selected_id else 1))
            p.setBrush(color)
            p.drawRoundedRect(r, 4, 4)
            p.fillRect(QRectF(r.x()+1,r.y()+1,max(0,r.width()-2),22), QColor('#283e4b' if c.track == 0 else '#40394f'))
            asset = self.project.assets[c.asset]
            p.save()
            p.setClipRect(r.adjusted(2, 1, -2, -1))
            p.setPen(QColor('#ede9d7'))
            title_width=r.width()-12-(170 if c.track==1 and r.width()>220 else 0)
            p.drawText(QRectF(r.x()+6,r.y()+2,title_width,20), Qt.AlignLeft|Qt.AlignVCenter, asset.path.name.split('_',1)[-1])
            p.setPen(QPen(QColor('#8fd0ed' if c.track == 0 else '#d0bbea'), 1))
            center = r.y()+57
            pixels = list(range(max(0,int(r.x()+2)), min(self.width(),int(r.right()-2)), 2))
            frames = np.array([self.frame(x) for x in pixels])
            envelope = self.project.music_envelope(c, frames, regions) if c.track == 1 else np.ones(len(pixels))
            for x, frame, gain in zip(pixels, frames, envelope):
                index = int((c.offset + frame - c.start) / 512)
                if 0 <= index < len(asset.peaks):
                    amp = min(1, float(asset.peaks[index]) * 10**(c.gain/20)*gain)*24
                    p.drawLine(QPointF(x,center-amp),QPointF(x,center+amp))
            if c.track == 1 and len(pixels)>1:
                p.setPen(QPen(QColor('#f2d179'), 2))
                p.drawPolyline(QPolygonF([QPointF(x,r.bottom()-8-float(gain)*46) for x,gain in zip(pixels,envelope)]))
                if r.width()>220:
                    p.setPen(QColor('#f2d179'))
                    p.drawText(QRectF(r.right()-170,r.y()+2,162,20), Qt.AlignRight|Qt.AlignVCenter, f'Bajada bajo voz · {self.project.duck_fade:g} s')
            p.restore()
        x = self.x(self.cursor)
        p.setPen(QPen(QColor('#f6db84'), 2))
        p.drawLine(QPointF(x, 26), QPointF(x, 248))
        p.setBrush(QColor('#f6db84'))
        p.drawPolygon(QPolygonF([QPointF(x-7,22),QPointF(x+7,22),QPointF(x,31)]))
        if not self.project.clips:
            p.setPen(QColor('#c5cbbd'))
            p.drawText(self.rect(), Qt.AlignCenter, 'Importa o arrastra la voz WAV / FLAC del teleprompter')

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        self.setFocus()
        # The ruler and the playhead always seek, even in clip/marker modes.
        line_hit = abs(event.x()-self.x(self.cursor)) <= 7
        c = self.hit(event.localPos())
        waveform_seek = self.mode=='cursor' and (not c or event.y()>=self.rect_for(c).top()+24)
        if event.y()<31 or line_hit or waveform_seek:
            if event.y()>=31 and not line_hit:
                self.track = 0 if event.y()<145 else 1
                if c:self.selected_id=c.id;self.selected.emit(c.id)
            self.scrubbing=True;self.scrubStarted.emit()
            self.cursor=min(self.project.frames,self.frame(event.x()));self.seeked.emit(self.cursor);self.update();return
        self.editStarted.emit()
        frame = self.frame(event.x())
        self.cursor = frame
        self.track = 0 if event.y() < 145 else 1
        self.seeked.emit(frame)
        if self.mode == 'mark' and self.track == 0:
            self.cueRequested.emit(frame)
            return
        if c:
            self.selected_id = c.id
            self.selected.emit(c.id)
            if self.mode in ('clip','track') or event.y() < self.rect_for(c).top()+24:
                self.drag = {'id':c.id,'x':event.x(),'state':self.project.state(),'moved':False,'span':self.span,'whole':self.mode=='track'}
        if not self.drag:
            self.scrubbing=True;self.scrubStarted.emit()
        self.update()

    def mouseMoveEvent(self, event):
        if self.scrubbing:
            self.cursor=min(self.project.frames,self.frame(event.x()));self.seeked.emit(self.cursor);self.update()
        elif self.drag:
            if not self.drag['moved'] and abs(event.x()-self.drag['x']) < 3:
                return
            self.project.restore(self.drag['state'])
            delta = int((event.x()-self.drag['x'])/max(1,self.width()-28)*self.drag['span'])
            self.project.move(self.drag['id'], delta, self.drag['whole'], False)
            self.drag['moved'] = True
            self.update()
        else:
            c = self.hit(event.localPos())
            if event.y()<31 or abs(event.x()-self.x(self.cursor))<=7:
                self.setCursor(Qt.SizeHorCursor);self.setToolTip('Arrastra el cursor para avanzar o retroceder.')
            else:
                self.setCursor(Qt.OpenHandCursor if c and (self.mode in ('clip','track') or event.y()<self.rect_for(c).top()+24) else Qt.CrossCursor)
            if c:
                self.setToolTip(f'{self.project.assets[c.asset].path.name}\n{clock(c.start)} — {clock(c.end)} · arrastra la cabecera')

    def mouseReleaseEvent(self, event):
        if self.scrubbing:
            self.cursor=min(self.project.frames,self.frame(event.x()));self.seeked.emit(self.cursor);self.scrubbing=False;self.scrubFinished.emit();self.update();return
        if self.drag and self.drag['moved']:
            self.project.undo_stack.append(self.drag['state'])
            self.project.undo_stack = self.project.undo_stack[-50:]
            self.project.redo_stack.clear()
            self.project.dirty = True
            self.changed.emit()
        self.drag = None

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls() and any(Path(u.toLocalFile()).suffix.lower() in FORMATS for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if Path(u.toLocalFile()).suffix.lower() in FORMATS]
        if paths:
            self.dropped.emit(paths[0], self.frame(event.pos().x()), 0 if event.pos().y()<145 else 1)
            event.acceptProposedAction()
