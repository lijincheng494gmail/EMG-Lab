import csv, io, tempfile, time, unittest
import numpy as np
import server as s

class TestLab(unittest.TestCase):
    def test_frame(self):
        self.assertEqual(s.parse_frame(b'2920,4095,2225,3,1516,1517,7,0\r'),(2920,4095,2225,3,1516,1517,7,0))
        with self.assertRaises(ValueError):s.parse_frame(b'1,2,3')
    def test_fragmented(self):
        f=s.Framer();self.assertEqual(f.feed(b'junk\r\n1,2,3'),[])
        self.assertEqual(f.feed(b',4,5,6,7,8\r\nbad\r\n'),[(1,2,3,4,5,6,7,8)])
        self.assertEqual(f.bad,1)
    def test_rms(self):
        a=np.array([-1,1,-3,3]);np.testing.assert_allclose(s.rms_rolling(a,2),[1,1,np.sqrt(5),3]);m=s.metrics(a,a);self.assertAlmostEqual(m['rms']**2,m['variance']+m['mean']**2)
    def test_spectral(self):
        t=np.arange(1000)/1000;y=np.sin(2*np.pi*50*t);d=s.spectral(y,1000)
        self.assertEqual(d['fft_f'][np.argmax(d['fft'])],50);self.assertAlmostEqual(max(d['fft']),1,places=5);self.assertAlmostEqual(d['total_power'],.5,delta=.02)
    def test_acf_ccf(self):
        rng=np.random.default_rng(1);x=np.r_[rng.normal(size=100),np.zeros(20)];y=np.r_[np.zeros(5),x[:-5]];d=s.correlations(x,y,20)
        self.assertEqual(d['peak'],5);self.assertAlmostEqual(d['acf1'][0],1);self.assertIsNone(s.correlations(np.ones(10),np.ones(10),2)['ccf'])
    def test_filter(self):
        fs=300;t=np.arange(3000)/fs;x=np.sin(2*np.pi*5*t)+np.sin(2*np.pi*90*t);y=s.preprocess(x,{'filter':'lowpass','high':20},fs)
        self.assertLess(np.std(y[100:-100]-np.sin(2*np.pi*5*t)[100:-100]),.005)
        with self.assertRaises(ValueError):s.preprocess(x,{'filter':'lowpass','high':20},None)
    def test_rate_basis(self):
        self.assertEqual(s.fs_value({}), (None,'unknown'));self.assertEqual(s.fs_value({'fs':300}),(300.,'user-assumed'));self.assertEqual(s.fs_value({},True),(300.,'synthetic-known'))
    def test_csv(self):
        r,tar,tri,d=s.load_csv(','.join(s.FIELDS)+'\n1,2,3,4,5,6,7,8\n');self.assertEqual(r[0][2],tuple(range(1,9)));self.assertEqual(tar,[None]);self.assertFalse(d)
        with self.assertRaises(ValueError):s.load_csv('bad\n1')
    def test_imported_synthetic_rate_is_unknown(self):
        text=(s.ROOT/'examples/synthetic_labeled.csv').read_text()
        with tempfile.TemporaryDirectory() as d:
            lab=s.Lab(d)
            lab.load_replay(text,'user_uploaded.csv')
            self.assertTrue(lab.state()['replay_demo'])
            rows,known_rate=lab.selected('replay',1000)
            result=s.analyze(rows,{},known_rate)
            self.assertIsNone(result['fs'])
            self.assertEqual(result['fs_basis'],'unknown')
            with self.assertRaises(ValueError):s.analyze(rows,{'filter':'lowpass','high':20},known_rate)
            result=s.analyze(rows,{'fs':500},known_rate)
            self.assertEqual(result['fs'],500)
            self.assertEqual(result['fs_basis'],'user-assumed')
            lab.load_replay(text,'Built-in example',demo=True)
            rows,known_rate=lab.selected('replay',1000)
            self.assertTrue(lab.state()['replay_known_fs'])
            result=s.analyze(rows,{},known_rate)
            self.assertEqual(result['fs'],300)
            self.assertEqual(result['fs_basis'],'synthetic-known')
    def test_regression(self):
        r,y,g,d=s.load_csv((s.ROOT/'examples/synthetic_labeled.csv').read_text());result=s.fit_regression(r,y,g,{'window':60},d)
        self.assertGreater(result['r2'],.9);self.assertEqual(result['train_n'],90);self.assertEqual(result['test_n'],30);self.assertTrue(d)
    def test_record(self):
        with tempfile.TemporaryDirectory() as d:
            lab=s.Lab(d);lab.connect('demo');time.sleep(.2);ident=lab.start_record('test',{});time.sleep(.2);lab.mark('event');lab.stop_record();lab.disconnect()
            data=(lab.dir/(ident+'.csv')).read_text();rows,_,_,demo=s.load_csv(data);self.assertGreater(len(rows),10);self.assertTrue(demo);self.assertTrue(lab.stream_demo)
    def test_analysis(self):
        rng=np.random.default_rng(1);rows=[(i,i/300,s.demo_row(i,rng)) for i in range(300)];d=s.analyze(rows,{'window':30,'corr_rms':True},True);self.assertEqual(d['n'],300);self.assertEqual(len(d['rms'][0]),300);self.assertEqual(d['fs_basis'],'synthetic-known')

if __name__=='__main__':unittest.main()
