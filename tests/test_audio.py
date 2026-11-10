import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path
import numpy as np
from compilando.core import Project, Clip, RATE

def wav(path, data):
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(RATE)
        f.writeframes((np.clip(data,-1,1)*32767).astype('<i2').tobytes())

class AudioTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.voice=self.root/'voice.wav';self.music=self.root/'music.wav'
        t=np.arange(RATE*12)/RATE
        signal=.2*np.sin(2*np.pi*220*t)
        wav(self.voice,np.column_stack([signal,signal]))
        wav(self.music,np.full((RATE*20,2),.1))
        self.hash=hashlib.sha256(self.voice.read_bytes()).hexdigest()
        self.p=Project(self.root/'episode',self.root/'cache')
        self.a=self.p.add_asset(self.voice);self.p.import_voice(self.a)

    def tearDown(self):self.temp.cleanup()

    def test_split_move_gap_undo_and_source_preservation(self):
        original=self.p.render(0,self.p.frames)
        c=self.p.clips[0]
        right=self.p.split(c.id,4*RATE)
        np.testing.assert_array_equal(self.p.render(0,self.p.frames),original)
        self.p.move(right.id,RATE)
        np.testing.assert_array_equal(self.p.render(4*RATE,RATE),np.zeros((RATE,2)))
        self.p.undo();np.testing.assert_array_equal(self.p.render(0,self.p.frames),original)
        cue=self.p.add_cue(4*RATE,5)
        self.assertEqual(self.p.frames,17*RATE)
        np.testing.assert_array_equal(self.p.render(4*RATE,5*RATE),np.zeros((5*RATE,2)))
        np.testing.assert_array_equal(self.p.render(9*RATE,8*RATE),original[4*RATE:])
        self.p.undo();self.assertEqual(self.p.frames,12*RATE)
        self.assertEqual(hashlib.sha256(self.voice.read_bytes()).hexdigest(),self.hash)

    def test_music_duck_master_stereo_and_clipping(self):
        self.p.duck_fade=1
        cue=self.p.add_cue(4*RATE,5);m=self.p.add_asset(self.music);self.p.assign(cue.id,m)
        full=np.mean(self.p.render(6*RATE,1000,track=1))
        bed=np.mean(self.p.render(11*RATE,1000,track=1))
        self.assertAlmostEqual(float(bed/full),10**(-24/20),places=5)
        self.p.master=-6
        quieter=np.mean(self.p.render(6*RATE,1000,track=1))
        self.assertAlmostEqual(float(quieter/full),10**(-6/20),places=5)
        self.p.master=-60;self.assertFalse(self.p.render(0,RATE).any())
        self.p.master=24
        result=self.p.export(self.root/'hot.wav')
        self.assertTrue(result['clipped'])

    def test_five_second_fade_curve_split_invariance_and_saved_setting(self):
        q=self.p.add_cue(4*RATE,5)
        c=self.p.assign(q.id,self.p.add_asset(self.music))
        # Music starts at 4 s; voice returns at 9 s; target level reached at 14 s.
        sample_times=np.array([6,9,11.5,14,14.5])*RATE
        curve=self.p.music_envelope(c,sample_times)
        bed=10**(-24/20)
        np.testing.assert_allclose(curve,[1,1,(1+bed)/2,bed,bed],atol=1e-7)
        music_level=float(self.p.assets[c.asset].data[0,0])
        for time,gain in zip(sample_times,curve):
            self.assertAlmostEqual(float(self.p.render(int(time),1,track=1)[0,0]),music_level*gain,places=7)
        # Cutting continuous speech must not restart the ducking curve.
        before=self.p.render(9*RATE,7*RATE,track=1)
        anchor=self.p.find(q.anchor);self.p.split(anchor.id,12*RATE)
        np.testing.assert_array_equal(before,self.p.render(9*RATE,7*RATE,track=1))
        self.p.duck_fade=3.5;self.p.save()
        loaded=Project.load(self.p.file,self.root/'fade-cache')
        self.assertEqual(loaded.duck_fade,3.5)
        legacy=json.loads(self.p.file.read_text());legacy.pop('duck_fade');self.p.file.write_text(json.dumps(legacy))
        self.assertEqual(Project.load(self.p.file,self.root/'legacy-cache').duck_fade,5)

    def test_repeat_insert_at_same_point_does_not_duplicate_gap(self):
        q=self.p.add_cue(4*RATE,5);frames=self.p.frames
        before=self.p.state();history=len(self.p.undo_stack)
        for position in [4*RATE,6*RATE,8*RATE,9*RATE]:
            self.assertEqual(self.p.add_cue(position,5).id,q.id)
            self.assertEqual(self.p.state(),before)
            self.assertEqual(len(self.p.undo_stack),history)
        self.assertEqual(self.p.frames,frames)
        self.assertEqual(len(self.p.cues),1)

    def test_insert_music_is_one_undo_step_and_completes_existing_gap(self):
        asset=self.p.add_asset(self.music);before=self.p.state()
        self.p.insert_music(4*RATE,asset)
        self.assertEqual(self.p.frames,17*RATE)
        self.assertEqual(len(self.p.cues),1)
        self.assertTrue(self.p.render(6*RATE,RATE,track=1).any())
        inserted=self.p.state()
        self.p.undo();self.assertEqual(self.p.state(),before)
        self.p.undo(True);self.assertEqual(self.p.state(),inserted)
        self.p.undo()
        cue=self.p.add_cue(4*RATE,5);empty=self.p.state()
        self.p.insert_music(7*RATE,asset)
        self.assertEqual(self.p.frames,17*RATE)
        self.assertEqual(len(self.p.cues),1)
        self.assertEqual(self.p.cues[0].id,cue.id)
        self.p.undo();self.assertEqual(self.p.state(),empty)

    def test_roundtrip_portable_project_and_exports(self):
        q=self.p.add_cue(4*RATE,2);self.p.assign(q.id,self.p.add_asset(self.music))
        self.p.save()
        moved=self.root/'moved';shutil.copytree(self.p.folder,moved)
        loaded=Project.load(moved/'episodio.compilando.json',self.root/'cache2')
        np.testing.assert_array_equal(loaded.render(0,loaded.frames),self.p.render(0,self.p.frames))
        for ext in ['wav','flac','mp3']:
            out=self.root/('out.'+ext);result=self.p.export(out)
            self.assertFalse(result['clipped']);self.assertTrue(out.is_file())
            probe=json.loads(subprocess.check_output(['ffprobe','-v','quiet','-show_format','-show_streams','-of','json',str(out)]))
            self.assertAlmostEqual(float(probe['format']['duration']),14,delta=.1)
            self.assertEqual(probe['streams'][0]['channels'],2)
            if ext!='mp3':
                decoded=loaded.add_asset(out,False)
                np.testing.assert_allclose(decoded.data[:self.p.frames],self.p.render(0,self.p.frames),atol=2e-7)
        with self.assertRaises(ValueError):self.p.export(self.a.path)

    def test_cue_assignment_independent_and_move_with_voice(self):
        q1=self.p.add_cue(2*RATE,2);q2=self.p.add_cue(8*RATE,2)
        music=self.p.add_asset(self.music);self.p.assign(q1.id,music)
        self.assertTrue(any(c.cue==q1.id for c in self.p.clips))
        self.assertFalse(any(c.cue==q2.id for c in self.p.clips))
        start=self.p.cue_position(q1);c=next(c for c in self.p.clips if c.cue==q1.id)
        self.p.move(q1.anchor,RATE,True)
        self.assertEqual(self.p.cue_position(q1),start+RATE);self.assertEqual(c.start,start+RATE)
        self.p.delete(q1.anchor)
        self.assertFalse(any(q.id==q1.id for q in self.p.cues))
        self.assertFalse(any(c.cue==q1.id for c in self.p.clips))
        self.p.undo();self.assertTrue(any(q.id==q1.id for q in self.p.cues))

    def test_publication_and_pcm_device(self):
        from PyQt5.QtCore import QCoreApplication,QIODevice
        from compilando.audio import MixerDevice
        app=QCoreApplication.instance() or QCoreApplication([])
        device=MixerDevice(self.p,0);device.open(QIODevice.ReadOnly)
        data=device.readData(4096);self.assertEqual(len(data),4096)
        samples=np.frombuffer(data,dtype='<i2').reshape(-1,2)/32767
        np.testing.assert_allclose(samples,self.p.render(0,1024),atol=1/32767)
        device.close()
        self.p.metadata['title']='Episodio <de prueba>'
        self.p.metadata['description']='Resumen & enlaces\nSegunda línea'
        bundle=self.root/'Publicacion';self.p.publication(bundle)
        self.assertTrue((bundle/'episodio.mp3').exists())
        self.assertIn('&lt;de prueba&gt;',(bundle/'entrada-web.html').read_text())
        self.assertTrue((bundle/'resumen.txt').exists())

if __name__=='__main__':unittest.main()
