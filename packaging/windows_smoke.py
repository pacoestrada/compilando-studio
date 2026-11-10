"""Exercise the actual packaged EXE without any user recordings or audio device."""
import hashlib
import json
from pathlib import Path
import tempfile
import time
import wave
import numpy as np
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from compilando.core import Project, RATE
from compilando import __version__


def smoke(app, Studio, report, close_assets):
    report.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    QMessageBox.warning = lambda parent, title, message: errors.append(str(message))
    windows = []
    projects = []
    with tempfile.TemporaryDirectory(prefix='compilando-windows-test-') as tmp:
        root = Path(tmp)
        voice, music = root/'Voz con ñ.wav', root/'Música con tilde.wav'
        for file, hz, seconds in [(voice, 220, 15), (music, 440, 30)]:
            t = np.arange(RATE * seconds) / RATE
            y = .15 * np.sin(2 * np.pi * hz * t)
            with wave.open(str(file), 'wb') as stream:
                stream.setnchannels(2); stream.setsampwidth(2); stream.setframerate(RATE)
                stream.writeframes((np.column_stack([y, y]) * 32767).astype('<i2').tobytes())
        original_hash = hashlib.sha256(voice.read_bytes()).hexdigest()
        window = Studio(root/'Episodio de prueba', root/'cache', QSettings(str(root/'settings.ini'), QSettings.IniFormat))
        windows.append(window)
        window.show(); app.processEvents()

        def wait():
            until = time.monotonic() + 30
            while window.busy and time.monotonic() < until:
                app.processEvents(); time.sleep(.01)
            assert not window.busy, 'El proceso de audio excede 30 s'
            app.processEvents()
            assert not errors, errors

        try:
            window.import_voice(str(voice)); wait()
            assert window.project.frames == 15 * RATE
            window.seek(4 * RATE)
            QFileDialog.getOpenFileName = lambda *a, **k: (str(music), 'Audio')
            window.add_cue(); wait()
            project = window.project
            projects.append(project)
            assert len(project.cues) == 1 and project.frames == 20 * RATE
            clip = next(c for c in project.clips if c.track == 1)
            np.testing.assert_allclose(project.music_envelope(clip, np.array([6, 9, 11.5, 14])*RATE), [1, 1, (1+10**(-24/20))/2, 10**(-24/20)], atol=1e-7)
            window.seek(11 * RATE); assert window.timeline.cursor == 11 * RATE
            project.master = -60; assert not project.render(0, RATE).any()
            project.master = 0
            project.save()
            reopened = Project.load(project.file, root/'reopened-cache')
            projects.append(reopened)
            np.testing.assert_array_equal(project.render(0, project.frames), reopened.render(0, reopened.frames))
            for extension in ['wav', 'flac', 'mp3']:
                output = root / ('Mezcla con ñ.' + extension)
                project.export(output)
                asset = reopened.add_asset(output, False)
                assert abs(asset.frames - project.frames) < RATE // 5
                assert output.stat().st_size > 1000
            project.publication(root/'Publicación')
            assert (root/'Publicación/episodio.mp3').is_file()
            assert hashlib.sha256(voice.read_bytes()).hexdigest() == original_hash
            window.resize(1450, 920); app.processEvents()
            assert window.grab().save(str(report.with_suffix('.png')))
        finally:
            for window in windows:
                window.project.dirty = False
                window.close()
            for project in projects:
                close_assets(project)
            app.processEvents()
    report.write_text(json.dumps({'ok': True, 'version': __version__, 'platform': 'Windows x64', 'checks': ['GUI startup and close', 'WAV import with Unicode paths', 'music insertion and 5-second ducking', 'cursor seek', 'master mute', 'project save and reopen', 'WAV/FLAC/MP3 export and decode', 'publication files', 'original unchanged', 'temporary audio cleanup'], 'physical_audio': 'not tested'}, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0
