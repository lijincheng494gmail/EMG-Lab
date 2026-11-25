#!/usr/bin/env python3
"""EMG-Lab: local, read-only serial acquisition and offline signal analysis."""
import argparse
import csv
import io
import json
import math
import mimetypes
import re
import threading
import time
import uuid
import webbrowser
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

import numpy as np
from scipy import signal

ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
FIELDS = ['ch1_mean','ch1_adc','ch1_power','ch1_level','ch2_mean','ch2_adc','ch2_power','ch2_level']
HEADER = ['frame','host_elapsed_s'] + FIELDS + ['source_kind']
MAX_REPLAY = 200_000
MAX_BODY = 32 * 1024 * 1024
DEMO_FS = 300.0


def utc():
    return datetime.now(timezone.utc).isoformat()


def parse_frame(raw):
    parts = raw.strip().split(b',')
    if len(parts) != 8 or any(not re.fullmatch(rb'[+-]?\d{1,10}', p) for p in parts):
        raise ValueError('expected 8 integers')
    return tuple(int(p) for p in parts)


class Framer:
    def __init__(self):
        self.buf = b''
        self.synced = False
        self.bad = 0
        self.skipped = 0
    def feed(self, data):
        self.buf += data
        rows = []
        while b'\n' in self.buf:
            raw, self.buf = self.buf.split(b'\n', 1)
            if not self.synced:
                self.synced = True
                self.skipped += 1
                continue
            if not raw.strip():
                continue
            try:
                rows.append(parse_frame(raw))
            except ValueError:
                self.bad += 1
        if len(self.buf) > 4096:
            self.buf = b''
            self.synced = False
            self.bad += 1
        return rows


def demo_row(i, rng):
    t = i / DEMO_FS
    a = 18 + 230 * (0.5 + 0.5 * np.sin(2*np.pi*t/6))**5
    b = 18 + 170 * (0.5 + 0.5 * np.sin(2*np.pi*(t-.35)/6))**5
    def ch(amp, phase):
        x = amp*(.5*np.sin(2*np.pi*43*t+phase)+.3*np.sin(2*np.pi*81*t)+.2*rng.normal())
        return (2048, int(np.clip(round(2048+x),0,4095)), int(amp**2/10), int(amp/50))
    return ch(a,0) + ch(b,.7)


def fs_value(cfg, demo=False):
    if demo:
        return DEMO_FS, 'synthetic-known'
    v = cfg.get('fs')
    if v in (None, '', 0, '0'):
        return None, 'unknown'
    fs = float(v)
    if not math.isfinite(fs) or not 0.01 <= fs <= 100000:
        raise ValueError('Sampling rate must be between 0.01 and 100000 Hz')
    return fs, 'user-confirmed' if cfg.get('fs_confirmed') is True else 'user-assumed'


def preprocess(x, cfg, fs):
    x = np.asarray(x, dtype=float)
    y = x.copy()
    if cfg.get('center', True):
        y -= y.mean()
    kind = cfg.get('filter', 'none')
    if kind == 'none':
        return y
    if fs is None:
        raise ValueError('Enter a sampling rate before applying a filter in Hz')
    lo, hi = float(cfg.get('low',20)), float(cfg.get('high',100))
    ny = fs/2
    if kind == 'lowpass':
        if not 0 < hi < ny: raise ValueError('Low-pass cutoff must be below Nyquist')
        sos = signal.butter(4, hi, btype='lowpass', fs=fs, output='sos')
    elif kind == 'highpass':
        if not 0 < lo < ny: raise ValueError('High-pass cutoff must be below Nyquist')
        sos = signal.butter(4, lo, btype='highpass', fs=fs, output='sos')
    elif kind == 'bandpass':
        if not 0 < lo < hi < ny: raise ValueError('Require 0 < low < high < Nyquist')
        sos = signal.butter(4, [lo,hi], btype='bandpass', fs=fs, output='sos')
    elif kind == 'notch':
        f = float(cfg.get('notch',50))
        if not 0 < f < ny: raise ValueError('Notch frequency must be below Nyquist')
        b,a = signal.iirnotch(f,30,fs=fs)
        sos = signal.tf2sos(b,a)
    else:
        raise ValueError('Unknown filter')
    # The filter is explicitly an offline, zero-phase operation on the selected window.
    if len(y) < 40:
        raise ValueError('At least 40 frames are needed for this filter')
    return signal.sosfiltfilt(sos,y)


def rms_rolling(x,w):
    n = len(x)
    w = min(max(int(w),1),n)
    c = np.r_[0.,np.cumsum(np.square(x))]
    end = np.arange(1,n+1)
    beg = np.maximum(0,end-w)
    return np.sqrt(np.maximum(0,(c[end]-c[beg])/(end-beg)))


def metrics(raw, y):
    return dict(mean=float(raw.mean()), raw_sd=float(raw.std()), raw_min=float(raw.min()), raw_max=float(raw.max()),
                rms=float(np.sqrt(np.mean(y*y))), mav=float(np.mean(np.abs(y))), variance=float(y.var()),
                sd=float(y.std()), boundary=float(100*np.mean((raw==0)|(raw==4095))))


def spectral(y,fs):
    n=len(y)
    s=1.0 if fs is None else fs
    # One-sided amplitude of a Hann-windowed, demeaned record.
    win=signal.windows.hann(n,sym=False)
    a=np.abs(np.fft.rfft((y-y.mean())*win))/max(win.sum(),1e-15)
    if n%2==0: a[1:-1]*=2
    else: a[1:]*=2
    f=np.fft.rfftfreq(n,1/s)
    seg=min(256,n)
    pf,p=signal.welch(y,fs=s,nperseg=seg,noverlap=seg//2,detrend='constant',scaling='density')
    df=pf[1]-pf[0] if len(pf)>1 else 0
    total=float(p.sum()*df)
    med=None if total<=0 else float(pf[min(np.searchsorted(np.cumsum(p),p.sum()/2),len(pf)-1)])
    meanf=None if total<=0 else float(np.sum(pf*p)/p.sum())
    return dict(fft_f=f.tolist(),fft=a.tolist(),psd_f=pf.tolist(),psd=p.tolist(),total_power=total,median_freq=med,mean_freq=meanf)


def correlations(x,y,kmax):
    x=x-x.mean();y=y-y.mean();n=len(x)
    k=max(0,min(int(kmax),n//2,500))
    def ac(a):
        d=float(a@a)
        return None if d<=1e-20 else (signal.correlate(a,a,mode='full',method='fft')[n-1:n+k]/d).tolist()
    d=float(np.linalg.norm(x)*np.linalg.norm(y))
    cross=None if d<=1e-20 else (signal.correlate(y,x,mode='full',method='fft')[n-1-k:n+k]/d).tolist()
    lags=list(range(-k,k+1))
    peak=None if cross is None else int(lags[int(np.argmax(cross))])
    return dict(acf_lags=list(range(k+1)),acf1=ac(x),acf2=ac(y),lags=lags,ccf=cross,peak=peak,
                peak_r=None if peak is None else float(cross[peak+k]), pearson=None if cross is None else float(cross[k]))


def analyze(rows,cfg,demo=False):
    if len(rows)<8: raise ValueError('At least 8 valid frames are required')
    fs,basis=fs_value(cfg,demo)
    a=np.asarray([r[2] for r in rows],dtype=float)
    raw=[a[:,1],a[:,5]]
    y=[preprocess(v,cfg,fs) for v in raw]
    w=int(cfg.get('window',60)); k=int(cfg.get('lag',120))
    roll=[rms_rolling(v,w) for v in y]
    return dict(n=len(rows),frames=[r[0] for r in rows],fs=fs,fs_basis=basis,
                processed=[v.tolist() for v in y],rms=[v.tolist() for v in roll],
                metrics=[metrics(r,v) for r,v in zip(raw,y)],spectra=[spectral(v,fs) for v in y],
                correlation=correlations(*(roll if cfg.get('corr_rms') else y),k),window=min(max(w,1),len(rows)))


def load_csv(text):
    rd=csv.DictReader(io.StringIO(text.lstrip('\ufeff')))
    if not rd.fieldnames or not set(FIELDS).issubset(rd.fieldnames):
        raise ValueError('CSV must contain all eight device fields; see examples')
    rows=[]; targets=[]; trials=[]; kinds=[]
    has_target='target' in rd.fieldnames; has_trial='trial' in rd.fieldnames
    for j,r in enumerate(rd):
        if j>=MAX_REPLAY: raise ValueError('CSV exceeds 200,000 rows')
        try:
            a=tuple(int(r[f]) for f in FIELDS)
            stamp=float(r['host_elapsed_s']) if r.get('host_elapsed_s') else None
            if stamp is not None and not math.isfinite(stamp): stamp=None
            target=float(r['target']) if has_target and r.get('target','').strip() else None
            if target is not None and not math.isfinite(target): raise ValueError()
        except (ValueError,TypeError,KeyError,AttributeError):
            raise ValueError(f'Invalid value in CSV row {j+2}') from None
        rows.append((j,stamp,a));targets.append(target);kinds.append((r.get('source_kind') or '').strip());trials.append((r.get('trial') or '').strip() if has_trial else '')
    if not rows: raise ValueError('CSV has no data rows')
    return rows,targets,trials,bool(kinds) and all(k=='synthetic' for k in kinds)


def fit_regression(rows,targets,trials,cfg,demo=False):
    fs,basis=fs_value(cfg,demo)
    w=max(8,min(5000,int(cfg.get('window',60))))
    features=[]; labels=[]; groups=[]; starts=[]
    # Non-overlapping windows; never cross a trial boundary. Unlabeled windows are omitted.
    i=0
    while i<len(rows):
        end=i+1
        while end<len(rows) and trials[end]==trials[i]: end+=1
        for j in range(i,end-w+1,w):
            tar=targets[j:j+w]
            if any(v is None for v in tar): continue
            a=np.asarray([r[2] for r in rows[j:j+w]],float)
            v1=preprocess(a[:,1],cfg,fs);v2=preprocess(a[:,5],cfg,fs)
            features.append([float(np.sqrt(np.mean(v1*v1))),float(np.sqrt(np.mean(v2*v2)))])
            labels.append(float(np.mean(tar)));groups.append(trials[j]);starts.append(j)
        i=end
    if len(labels)<12: raise ValueError('Need at least 12 fully labeled non-overlapping windows')
    X=np.asarray(features); y=np.asarray(labels)
    unique=list(dict.fromkeys(groups))
    if any(groups):
        if '' in unique: raise ValueError('Fill trial labels for every labeled window, or omit trial column')
        if len(unique)<3: raise ValueError('Need at least 3 distinct trials for trial-held-out regression')
        held=set(unique[max(1,int(.75*len(unique))):]); test=np.array([g in held for g in groups]); split='held-out trials (last trials in first-seen order)'
    else:
        cut=int(.75*len(y));test=np.arange(len(y))>=cut;split='chronological non-overlapping windows (within-recording; no independent-trial guarantee)'
    if test.sum()<2 or (~test).sum()<5: raise ValueError('Too few training or test windows')
    D=np.column_stack([np.ones(len(X)),X]);beta,_,rank,_=np.linalg.lstsq(D[~test],y[~test],rcond=None)
    if rank<3: raise ValueError('Training features are rank deficient')
    p=D[test]@beta;actual=y[test];err=p-actual;den=np.sum((actual-actual.mean())**2)
    return dict(beta=beta.tolist(),train_n=int((~test).sum()),test_n=int(test.sum()),split=split,
                actual=actual.tolist(),predicted=p.tolist(),starts=np.asarray(starts)[test].tolist(),
                rmse=float(np.sqrt(np.mean(err*err))),mae=float(np.mean(abs(err))),r2=None if den<=1e-20 else float(1-np.sum(err*err)/den),fs_basis=basis)


class Lab:
    def __init__(self, data_dir):
        self.lock=threading.RLock();self.dir=Path(data_dir);self.dir.mkdir(parents=True,exist_ok=True)
        self.rows=deque(maxlen=12000);self.arrivals=deque();self.n=0;self.bad=0;self.skipped=0
        self.started=0.;self.last=None;self.mode='idle';self.stream_demo=False;self.status='Disconnected';self.port='';self.baud=115200
        self.worker=None;self.stop_event=None;self.rec=None;self.last_record=None
        self.replay=[];self.targets=[];self.trials=[];self.replay_name='';self.replay_demo=False;self.replay_known_fs=False
    def connect(self,mode,port='',baud=115200):
        if mode not in ('live','demo'): raise ValueError('Unknown source')
        with self.lock:
            if self.rec: raise ValueError('Stop recording first')
        self.disconnect()
        ser=None
        if mode=='live':
            if not port or len(port)>256: raise ValueError('Choose a serial port')
            try:
                import serial
            except ImportError: raise ValueError('Install pyserial in the Python environment') from None
            ser=serial.Serial(port,int(baud),timeout=.1)
            ser.reset_input_buffer()
        with self.lock:
            self.rows.clear();self.arrivals.clear();self.n=self.bad=self.skipped=0;self.last=None
            self.started=time.monotonic();self.mode=mode;self.stream_demo=mode=='demo';self.status='Streaming (synthetic)' if mode=='demo' else 'Waiting for frames';self.port=port;self.baud=int(baud)
            event=threading.Event();self.stop_event=event
            self.worker=threading.Thread(target=self.run,args=(mode,ser,event),daemon=True);self.worker.start()
    def disconnect(self):
        with self.lock:
            if self.stop_event: self.stop_event.set()
            worker=self.worker
        if worker: worker.join(timeout=3)
        if worker and worker.is_alive(): raise ValueError('Reader is still stopping; retry')
        with self.lock:
            self.stop_record('disconnect');self.worker=None;self.stop_event=None;self.mode='idle';self.status='Disconnected'
    def ingest(self,values,now):
        self.last=now
        for v in values:
            r=(self.n,now-self.started,v);self.rows.append(r);self.n+=1
            if self.rec:
                self.rec['writer'].writerow([r[0],f'{r[1]:.9f}',*v,self.rec['meta']['source']]);self.rec['count']+=1
        if values:
            self.arrivals.append((now,len(values)))
            while self.arrivals and self.arrivals[0][0]<now-5: self.arrivals.popleft()
            if self.rec:self.rec['file'].flush()
    def run(self,mode,ser,event):
        f=Framer();rng=np.random.default_rng(20261125);i=0
        try:
            while not event.is_set():
                if mode=='live':
                    values=f.feed(ser.read(ser.in_waiting or 1));now=time.monotonic()
                else:
                    now=time.monotonic();end=int((now-self.started)*DEMO_FS)
                    values=[demo_row(j,rng) for j in range(i,min(end,i+1500))];i+=len(values)
                with self.lock:
                    self.bad=f.bad;self.skipped=f.skipped
                    if values:
                        self.ingest(values,now)
                        self.status='Streaming (synthetic)' if mode=='demo' else 'Streaming'
                if mode=='demo': event.wait(.02)
        except Exception as e:
            with self.lock:
                self.status='Reader stopped: '+str(e);self.stop_record('reader error');self.mode='idle'
        finally:
            if ser: ser.close()
    def state(self,n=1000):
        with self.lock:
            now=time.monotonic();age=None if self.last is None else now-self.last
            rate=0.0
            if self.mode!='idle' and age is not None and age<3:
                rate=sum(c for t,c in self.arrivals if t>=now-5)/max(min(now-self.started,5),.001)
            status=self.status
            if self.mode!='idle' and (age is None or age>3):status='Waiting / no recent frames'
            return dict(mode=self.mode,stream_demo=self.stream_demo,status=status,port=self.port,baud=self.baud,received=self.n,invalid=self.bad,initial_discard=self.skipped,
                        rate=rate,last_age=age,rows=list(self.rows)[-n:],recording=None if self.rec is None else {'id':self.rec['id'],'count':self.rec['count'],'markers':self.rec['meta']['markers']},
                        last_record=self.last_record,replay_n=len(self.replay),replay_name=self.replay_name,replay_demo=self.replay_demo,replay_known_fs=self.replay_known_fs,
                        labeled=sum(v is not None for v in self.targets))
    def start_record(self,label,cfg):
        with self.lock:
            if self.mode=='idle': raise ValueError('Connect a source first')
            if self.rec: raise ValueError('Already recording')
            fs,basis=fs_value(cfg,self.mode=='demo')
            ident=datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6]
            file=(self.dir/(ident+'.csv')).open('x',newline='',encoding='utf-8')
            writer=csv.writer(file);writer.writerow(HEADER);file.flush()
            meta=dict(id=ident,label=str(label)[:100],source='synthetic' if self.mode=='demo' else 'device',port=self.port,baud=self.baud,
                      started_utc=utc(),sampling_rate_hz=fs,sampling_rate_basis=basis,clock='host batch receipt monotonic seconds since connection, not device sample time',
                      device_fields=FIELDS,adc_boundary_assumption=[0,4095],invalid_at_start=self.bad,markers=[])
            self.rec=dict(id=ident,file=file,writer=writer,meta=meta,count=0,start=time.monotonic())
            (self.dir/(ident+'.json')).write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
            return ident
    def mark(self,label):
        with self.lock:
            if not self.rec: raise ValueError('Start recording first')
            self.rec['meta']['markers'].append(dict(label=str(label)[:100],next_frame=self.n,host_elapsed_s=time.monotonic()-self.started,utc=utc()))
            (self.dir/(self.rec['id']+'.json')).write_text(json.dumps(self.rec['meta'],indent=2,ensure_ascii=False),encoding='utf-8')
    def stop_record(self,reason='user'):
        with self.lock:
            if not self.rec: return self.last_record
            r=self.rec;r['file'].close();m=r['meta'];m.update(ended_utc=utc(),duration_s=time.monotonic()-r['start'],valid_frames=r['count'],invalid_frames=self.bad-m['invalid_at_start'],stop_reason=reason)
            (self.dir/(r['id']+'.json')).write_text(json.dumps(m,indent=2,ensure_ascii=False),encoding='utf-8')
            self.last_record=r['id'];self.rec=None;return self.last_record
    def load_replay(self,text,name,demo=False):
        rows,targets,trials,is_synthetic=load_csv(text)
        with self.lock:
            self.replay=rows;self.targets=targets;self.trials=trials;self.replay_name=name[:150];self.replay_demo=demo or is_synthetic
            # A provenance label does not establish the generating sample clock.
            # Only the built-in example has the rate defined by this program.
            self.replay_known_fs=bool(demo)
        return len(rows)
    def selected(self,source,n,end=None):
        n=max(8,min(12000,int(n)))
        with self.lock:
            if source=='replay':
                end=len(self.replay) if end is None else max(0,min(len(self.replay),int(end)))
                return self.replay[max(0,end-n):end],self.replay_known_fs
            if source!='stream':raise ValueError('Unknown source')
            return list(self.rows)[-n:],self.stream_demo


def ports():
    try:
        from serial.tools import list_ports
        return [{'device':p.device,'description':p.description} for p in list_ports.comports()]
    except ImportError:return []


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send_bytes(self,data,ctype='application/json; charset=utf-8',status=200,filename=None):
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        if filename:self.send_header('Content-Disposition',f'attachment; filename="{filename}"')
        self.end_headers()
        try:self.wfile.write(data)
        except (BrokenPipeError,ConnectionResetError):pass
    def js(self,obj,status=200):self.send_bytes(json.dumps(obj,allow_nan=False,ensure_ascii=False).encode(),status=status)
    def allowed(self):
        host=self.headers.get('Host','');port=self.server.server_port
        if host not in (f'127.0.0.1:{port}',f'localhost:{port}'):
            self.js({'error':'Local host only'},403);return False
        origin=self.headers.get('Origin')
        if origin and origin not in (f'http://127.0.0.1:{port}',f'http://localhost:{port}'):
            self.js({'error':'Cross-origin requests are not allowed'},403);return False
        return True
    def do_GET(self):
        if not self.allowed():return
        p=urlparse(self.path);path=p.path;lab=self.server.lab
        try:
            if path=='/api/state':return self.js(lab.state(max(8,min(12000,int(parse_qs(p.query).get('n',[1000])[0])))))
            if path=='/api/ports':return self.js(ports())
            if path=='/api/records':
                with lab.lock:
                    files=sorted((f.stem for f in lab.dir.glob('*.csv') if re.fullmatch(r'\d{8}_\d{6}_[0-9a-f]{6}',f.stem)),reverse=True)
                return self.js(files)
            if path.startswith('/api/download/'):
                name=path.rsplit('/',1)[-1]
                if not re.fullmatch(r'\d{8}_\d{6}_[0-9a-f]{6}\.(csv|json)',name):raise ValueError('Invalid recording name')
                f=lab.dir/name
                if not f.is_file():return self.js({'error':'Recording not found'},404)
                with lab.lock:data=f.read_bytes()
                return self.send_bytes(data,'text/csv' if name.endswith('.csv') else 'application/json',filename=name)
            if path=='/example.csv':return self.send_bytes((ROOT/'examples'/'synthetic_labeled.csv').read_bytes(),'text/csv',filename='synthetic_labeled.csv')
            if path=='/notes':f=ROOT/'docs'/'index.html'
            else:f=WEB/({'/':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(path,'__missing__'))
            if f.is_file():return self.send_bytes(f.read_bytes(),(mimetypes.guess_type(f.name)[0] or 'text/plain')+'; charset=utf-8')
            self.js({'error':'Not found'},404)
        except Exception as e:self.js({'error':str(e)},400)
    def do_POST(self):
        if not self.allowed():return
        path=urlparse(self.path).path;lab=self.server.lab
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<=size<=MAX_BODY:raise ValueError('Request too large')
            body=self.rfile.read(size)
            if path=='/api/replay':
                if not self.headers.get('Content-Type','').startswith('text/csv'):raise ValueError('Expected text/csv')
                n=lab.load_replay(body.decode('utf-8-sig'),unquote(self.headers.get('X-Filename','import.csv')));return self.js({'n':n})
            if not self.headers.get('Content-Type','').startswith('application/json'):raise ValueError('Expected JSON')
            d=json.loads(body or b'{}')
            if not isinstance(d,dict):raise ValueError('Expected object')
            if path=='/api/connect':lab.connect(d['mode'],d.get('port',''),d.get('baud',115200))
            elif path=='/api/disconnect':lab.disconnect()
            elif path=='/api/record/start':return self.js({'id':lab.start_record(d.get('label',''),d.get('config',{}))})
            elif path=='/api/record/stop':return self.js({'id':lab.stop_record()})
            elif path=='/api/mark':lab.mark(d.get('label',''))
            elif path=='/api/example':return self.js({'n':lab.load_replay((ROOT/'examples'/'synthetic_labeled.csv').read_text(), 'Synthetic labeled example',True)})
            elif path=='/api/window':
                rows,demo=lab.selected(d.get('source','stream'),d.get('n',1000),d.get('end'));return self.js({'rows':rows,'demo':demo})
            elif path=='/api/analyze':
                rows,demo=lab.selected(d.get('source','stream'),d.get('n',1000),d.get('end'));return self.js(analyze(rows,d.get('config',{}),demo))
            elif path=='/api/regression':
                with lab.lock:rows=list(lab.replay);targets=list(lab.targets);trials=list(lab.trials);demo=lab.replay_known_fs
                return self.js(fit_regression(rows,targets,trials,d.get('config',{}),demo))
            else:return self.js({'error':'Not found'},404)
            self.js({'ok':True})
        except Exception as e:self.js({'error':str(e)},400)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--port',type=int,default=8765);p.add_argument('--data-dir',default=str(ROOT/'recordings'));p.add_argument('--no-browser',action='store_true');a=p.parse_args()
    lab=Lab(a.data_dir);srv=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);srv.lab=lab;srv.daemon_threads=True
    url=f'http://127.0.0.1:{srv.server_port}/';print(f'EMG-Lab v1.1 | {url}\nRecordings: {lab.dir}\nPress Ctrl+C to stop.',flush=True)
    if not a.no_browser:threading.Timer(.5,lambda:webbrowser.open(url)).start()
    try:srv.serve_forever()
    except KeyboardInterrupt:pass
    finally:lab.disconnect();srv.server_close()

if __name__=='__main__':main()
