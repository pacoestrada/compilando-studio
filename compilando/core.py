"""Non-destructive, sample-aligned podcast editing and rendering."""
from __future__ import annotations
import copy
import hashlib
import html
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, asdict
import numpy as np

RATE = 44100
FORMATS = {'.wav', '.flac', '.mp3', '.ogg', '.opus', '.m4a', '.aac'}

def uid():
    return uuid.uuid4().hex[:12]

def db(value):
    return 0.0 if value <= -60 else 10 ** (value / 20)

def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

def ffmpeg(args):
    result = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-nostdin', *map(str, args)], capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace')[-2500:] or 'FFmpeg no pudo procesar el audio.')

@dataclass
class Clip:
    id: str
    asset: str
    track: int
    start: int
    offset: int
    length: int
    gain: float = 0.0
    cue: str = ''
    bed: float | None = None
    duck_fade: float | None = None

    @property
    def end(self):
        return self.start + self.length

@dataclass
class Cue:
    id: str
    anchor: str
    gap: int

class Asset:
    def __init__(self, id, path, pcm):
        self.id, self.path, self.pcm = id, Path(path), Path(pcm)
        size = self.pcm.stat().st_size
        if size < 8 or size % 8:
            raise ValueError('El archivo no contiene audio válido.')
        self.data = np.memmap(self.pcm, dtype='<f4', mode='r', shape=(size // 8, 2))
        self.frames = len(self.data)
        # One peak per 512 samples, generated in bounded memory chunks.
        chunks = []
        for pos in range(0, self.frames, 512 * 1024):
            a = np.max(np.abs(self.data[pos:pos + 512 * 1024]), axis=1)
            pad = (-len(a)) % 512
            if pad:
                a = np.pad(a, (0, pad))
            chunks.append(a.reshape(-1, 512).max(axis=1))
        self.peaks = np.concatenate(chunks)

class Project:
    def __init__(self, folder, cache=None):
        self.folder = Path(folder).resolve()
        self.cache = Path(cache) if cache else Path(tempfile.mkdtemp(prefix='compilando-audio-'))
        self.cache.mkdir(parents=True, exist_ok=True)
        self.assets = {}
        self.clips = []
        self.cues = []
        self.master = 0.0
        self.bed = -24.0
        self.fade = 1.0
        self.duck_fade = 5.0
        self.metadata = {'title': 'Compilando Podcast', 'artist': 'Paco Estrada', 'description': '', 'cover': ''}
        self.undo_stack, self.redo_stack = [], []
        self.dirty = False
        self.file = self.folder / 'episodio.compilando.json'

    @property
    def frames(self):
        return max((c.end for c in self.clips), default=0)

    def state(self):
        return {'clips': [asdict(c) for c in self.clips], 'cues': [asdict(c) for c in self.cues], 'master': self.master, 'bed': self.bed, 'fade': self.fade, 'duck_fade': self.duck_fade, 'metadata': copy.deepcopy(self.metadata)}

    def restore(self, state):
        self.clips = [Clip(**c) for c in state['clips']]
        self.cues = [Cue(**c) for c in state['cues']]
        self.master, self.bed, self.fade = state['master'], state['bed'], state['fade']
        self.duck_fade = state.get('duck_fade', 5.0)
        self.metadata = copy.deepcopy(state['metadata'])
        self.dirty = True

    def remember(self):
        self.undo_stack.append(self.state())
        self.undo_stack = self.undo_stack[-50:]
        self.redo_stack.clear()
        self.dirty = True

    def undo(self, redo=False):
        source, dest = (self.redo_stack, self.undo_stack) if redo else (self.undo_stack, self.redo_stack)
        if source:
            dest.append(self.state())
            self.restore(source.pop())

    def add_asset(self, filename, copy_source=True, asset_id=None):
        source = Path(filename).resolve()
        if not source.is_file() or source.suffix.lower() not in FORMATS:
            raise ValueError('Selecciona un archivo de audio compatible.')
        stat = source.stat()
        key = hashlib.sha256(f'{source}:{stat.st_size}:{stat.st_mtime_ns}'.encode()).hexdigest()
        pcm = self.cache / (key + '.f32')
        if not pcm.exists():
            tmp = pcm.with_suffix('.part')
            try:
                ffmpeg(['-y', '-i', source, '-map', '0:a:0', '-vn', '-ac', '2', '-ar', RATE, '-f', 'f32le', '-acodec', 'pcm_f32le', tmp])
                if tmp.stat().st_size < 8:
                    raise ValueError('Audio vacío.')
                os.replace(tmp, pcm)
            finally:
                tmp.unlink(missing_ok=True)
        if copy_source:
            media = self.folder / 'media'
            media.mkdir(parents=True, exist_ok=True)
            # Unique media names prevent overwriting an earlier take or music.
            destination = media / (uid() + '_' + source.name)
            shutil.copy2(source, destination)
            source = destination
        asset = Asset(asset_id or uid(), source, pcm)
        self.assets[asset.id] = asset
        return asset

    def import_voice(self, asset):
        self.remember()
        self.clips = [Clip(uid(), asset.id, 0, 0, 0, asset.frames)]
        self.cues = []

    def find(self, id):
        return next((c for c in self.clips if c.id == id), None)

    def cue_position(self, cue):
        anchor = self.find(cue.anchor)
        return max(0, anchor.start - cue.gap) if anchor else 0

    def split(self, id, position, remember=True):
        c = self.find(id)
        if c is None or not c.start < position < c.end:
            raise ValueError('Sitúa el cursor dentro del clip que quieres dividir.')
        if remember:
            self.remember()
        amount = position - c.start
        right = Clip(uid(), c.asset, c.track, position, c.offset + amount, c.length - amount,
                     c.gain, '', c.bed, c.duck_fade)
        c.length = amount
        self.clips.append(right)
        return right

    def cue_at(self, position):
        """A music cut occupies its whole gap, including the voice return."""
        for q in self.cues:
            anchor = self.find(q.anchor)
            if anchor and self.cue_position(q) <= position <= anchor.start:
                return q
        return next((q for q in self.cues if abs(self.cue_position(q) - position) < RATE // 10), None)

    def add_cue(self, position, gap_seconds=5):
        existing = self.cue_at(position)
        if existing:
            return existing
        voice = next((c for c in self.clips if c.track == 0 and c.start <= position < c.end), None)
        if voice is None:
            raise ValueError('Pon el cursor dentro de un clip de voz.')
        self.remember()
        right = self.split(voice.id, position, False) if position > voice.start else voice
        gap = round(max(.1, min(30, gap_seconds)) * RATE)
        for c in self.clips:
            if c.start >= position:
                c.start += gap
            elif c.track == 1 and c.end > position:
                c.length = position - c.start
        cue = Cue(uid(), right.id, gap)
        self.cues.append(cue)
        return cue

    def insert_music(self, position, asset, gap_seconds=5):
        """Create/complete a cut in one undo step, after audio has decoded."""
        existing = self.cue_at(position)
        cue = existing or self.add_cue(position, gap_seconds)
        return self.assign(cue.id, asset, remember=existing is not None)

    def assign(self, cue_id, asset, remember=True):
        q = next((q for q in self.cues if q.id == cue_id), None)
        if q is None:
            raise ValueError('Selecciona primero un punto musical.')
        if remember:
            self.remember()
        start = self.cue_position(q)
        end = min((self.cue_position(x) for x in self.cues if self.cue_position(x) > start), default=max((c.end for c in self.clips if c.track == 0), default=start + asset.frames))
        self.clips = [c for c in self.clips if c.cue != cue_id]
        c = Clip(uid(), asset.id, 1, start, 0, min(asset.frames, max(1, end - start)), cue=cue_id)
        self.clips.append(c)
        return c

    def move(self, id, delta, whole=False, remember=True):
        c = self.find(id)
        if not c:
            return
        if remember:
            self.remember()
        moving = [x for x in self.clips if x.track == c.track] if whole else [c]
        delta = max(int(delta), -min(x.start for x in moving))
        anchors = {x.id for x in moving if x.track == 0}
        attached = {q.id for q in self.cues if q.anchor in anchors}
        for x in self.clips:
            if x in moving or (x.track == 1 and x.cue in attached):
                x.start = max(0, x.start + delta)

    def delete(self, id):
        if not self.find(id):
            return
        self.remember()
        removed = {q.id for q in self.cues if q.anchor == id}
        self.clips = [c for c in self.clips if c.id != id and c.cue not in removed]
        self.cues = [q for q in self.cues if q.id not in removed]

    def voice_regions(self):
        """Adjacent cuts form one speech region; splitting must not pump music."""
        regions = []
        for c in sorted((c for c in self.clips if c.track == 0), key=lambda c:c.start):
            if regions and c.start <= regions[-1][1] + 1:
                regions[-1] = (regions[-1][0], max(regions[-1][1], c.end))
            else:
                regions.append((c.start, c.end))
        return regions

    def music_envelope(self, clip, times, regions=None):
        """One gain curve for both playback/export and the visible automation line."""
        times = np.asarray(times, dtype=np.float64)
        if not len(times):
            return np.zeros(0, dtype=np.float32)
        duck = np.zeros(len(times), dtype=np.float32)
        attack_frames = max(1, int(self.music_duck_fade(clip) * RATE))
        release_frames = max(1, int(self.fade * RATE))
        for start, end in self.voice_regions() if regions is None else regions:
            # A fresh music insert must not inherit the preceding voice's release.
            if end <= clip.start or end + release_frames < times[0] or start > times[-1]:
                continue
            attack = np.clip((times-start) / attack_frames, 0, 1)
            peak = min(1., (end-start) / attack_frames)
            release = peak * np.clip(1-(times-end) / release_frames, 0, 1)
            duck = np.maximum(duck, np.where(times < end, attack, release))
        edge = min(release_frames, max(1, clip.length // 2))
        edges = np.minimum(np.clip((times-clip.start) / edge, 0, 1), np.clip((clip.end-times) / edge, 0, 1))
        return ((1-(1-db(self.music_bed(clip)))*duck)*edges).astype(np.float32)

    def music_bed(self, clip):
        return self.bed if clip.bed is None else clip.bed

    def music_duck_fade(self, clip):
        return self.duck_fade if clip.duck_fade is None else clip.duck_fade

    def render(self, start, count, track=None, master=True):
        output = np.zeros((count, 2), dtype=np.float32)
        if count <= 0:
            return output
        times = np.arange(start, start + count)
        regions = self.voice_regions()
        for c in self.clips:
            if track is not None and c.track != track:
                continue
            lo, hi = max(start, c.start), min(start + count, c.end)
            if hi <= lo:
                continue
            asset = self.assets[c.asset]
            offset = c.offset + lo - c.start
            hi = min(hi, lo + asset.frames - offset)
            if hi <= lo:
                continue
            a, b = lo - start, hi - start
            gain = np.full(hi - lo, db(c.gain), dtype=np.float32)
            if c.track == 1:
                gain *= self.music_envelope(c, times[a:b], regions)
            output[a:b] += asset.data[offset:offset + hi - lo] * gain[:, None]
        if master:
            output *= db(self.master)
        return np.nan_to_num(output, copy=False)

    def save(self, filename=None, autosave=False):
        path = Path(filename) if filename else self.file
        payload = self.state()
        cover = payload['metadata'].get('cover')
        if cover:
            payload['metadata']['cover'] = os.path.relpath(cover, path.parent)
        # Retain imported sources for replacement and recovery.
        payload.update(schema=2, sample_rate=RATE, assets={k: os.path.relpath(a.path, path.parent) for k, a in self.assets.items()})
        atomic_json(path, payload)
        if not autosave:
            self.file = path
            self.dirty = False
        return path

    @classmethod
    def load(cls, filename, cache=None):
        path = Path(filename).resolve()
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema') not in (1, 2) or data.get('sample_rate') != RATE:
            raise ValueError('Versión de proyecto no compatible.')
        project = cls(path.parent, cache)
        for id, rel in data['assets'].items():
            source = (path.parent / rel).resolve()
            if not source.is_file():
                raise ValueError(f'Falta el audio {source}. Conserva la carpeta media junto al proyecto.')
            project.add_asset(source, False, id)
        project.restore(data)
        if project.metadata.get('cover'):
            project.metadata['cover'] = str((path.parent / project.metadata['cover']).resolve())
        for c in project.clips:
            if c.asset not in project.assets or c.start < 0 or c.offset < 0 or c.length <= 0 or c.offset + c.length > project.assets[c.asset].frames:
                raise ValueError('El proyecto contiene un clip no válido.')
        if any(not project.find(q.anchor) or q.gap < 0 for q in project.cues):
            raise ValueError('El proyecto contiene un punto musical no válido.')
        if not all(math.isfinite(v) for v in [project.master, project.bed, project.fade, project.duck_fade] + [c.gain for c in project.clips]):
            raise ValueError('El proyecto contiene un volumen no válido.')
        if not 0 <= project.duck_fade <= 30:
            raise ValueError('La duración del fundido no es válida.')
        for c in project.clips:
            if c.bed is not None and (not math.isfinite(c.bed) or not -60 <= c.bed <= 0):
                raise ValueError('El volumen de fondo de un clip no es válido.')
            if c.duck_fade is not None and (not math.isfinite(c.duck_fade) or not .1 <= c.duck_fade <= 30):
                raise ValueError('La duración del fundido de un clip no es válida.')
        project.file, project.dirty = path, False
        return project

    def export(self, filename, progress=None, track=None):
        if not self.frames:
            raise ValueError('Importa primero la voz.')
        destination = Path(filename).resolve()
        ext = destination.suffix.lower()
        codecs = {'.mp3': ['-c:a', 'libmp3lame', '-b:a', '192k'], '.wav': ['-c:a', 'pcm_s24le'], '.flac': ['-c:a', 'flac', '-sample_fmt', 's32']}
        if ext not in codecs:
            raise ValueError('Elige MP3, WAV o FLAC.')
        if any(destination == a.path.resolve() for a in self.assets.values()):
            raise ValueError('El audio de origen está protegido. Usa otro nombre para la mezcla.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='compilando-export-', dir=self.cache) as temp:
            raw, encoded = Path(temp) / 'mix.f32', Path(temp) / ('mix' + ext)
            peak = 0.0
            with raw.open('wb') as f:
                for start in range(0, self.frames, RATE * 5):
                    count = min(RATE * 5, self.frames - start)
                    audio = self.render(start, count, track)
                    peak = max(peak, float(np.max(np.abs(audio))))
                    f.write(audio.astype('<f4').tobytes())
                    if progress:
                        progress(int(80 * (start + count) / self.frames))
            args = ['-y', '-f', 'f32le', '-ar', RATE, '-ac', '2', '-i', raw]
            cover = self.metadata.get('cover', '')
            if ext == '.mp3' and cover and Path(cover).is_file():
                args += ['-i', cover, '-map', '0:a', '-map', '1:v:0', '-c:v', 'mjpeg', '-disposition:v', 'attached_pic', '-metadata:s:v', 'title=Portada', '-metadata:s:v', 'comment=Cover (front)']
            else:
                args += ['-map', '0:a']
            args += codecs[ext]
            if ext == '.mp3':
                args += ['-id3v2_version', '3']
            for field in ('title', 'artist', 'description'):
                args += ['-metadata', f'{field}={self.metadata.get(field, "")}']
            args += [encoded]
            ffmpeg(args)
            # Copy to same filesystem before atomic replace; never write over source media.
            staged = destination.with_name('.' + destination.name + '.' + uid() + '.tmp')
            try:
                shutil.copyfile(encoded, staged)
                os.replace(staged, destination)
            finally:
                staged.unlink(missing_ok=True)
            if progress:
                progress(100)
        return {'path': str(destination), 'peak': peak, 'clipped': peak > 1.0}

    def publication(self, folder, progress=None):
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=False)
        result = self.export(folder / 'episodio.mp3', progress)
        title, description = self.metadata['title'], self.metadata['description']
        (folder / 'resumen.txt').write_text(title + '\n\n' + description + '\n', encoding='utf-8')
        body = '\n'.join('<p>' + html.escape(p) + '</p>' for p in description.split('\n') if p.strip())
        (folder / 'entrada-web.html').write_text('<!doctype html><html lang="es"><meta charset="utf-8"><title>' + html.escape(title) + '</title><h1>' + html.escape(title) + '</h1>' + body + '<audio controls src="episodio.mp3"></audio></html>', encoding='utf-8')
        cover = self.metadata.get('cover')
        if cover and Path(cover).is_file():
            shutil.copy2(cover, folder / ('portada' + Path(cover).suffix.lower()))
        atomic_json(folder / 'datos-episodio.json', {**self.metadata, 'audio': 'episodio.mp3', 'duration_seconds': self.frames / RATE})
        (folder / 'LEEME.txt').write_text('Paquete para subida manual a tu web, iVoox y Spotify. No se ha publicado ni enviado ningún archivo.\n', encoding='utf-8')
        return result
