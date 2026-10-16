"""Offline demo biometrics: log-Mel/MFCC voice classifier and optional LBPH face ID.
Not liveness detection or production-grade authentication; use password plus biometrics.
"""
import json
import math
from pathlib import Path
import numpy as np
from . import database as db

SAMPLE_RATE = 16000
VOICE_SECONDS = 3
PHRASE = 'My voice opens this smart bookstore'


def voice_features(samples, sr=SAMPLE_RATE):
    """Short-audio speaker feature: normalized MFCC means/std + low/high energy ratios."""
    from scipy.signal import stft, resample_poly
    from scipy.fft import dct
    x=np.asarray(samples,dtype=np.float64).ravel()
    if sr != SAMPLE_RATE:
        divisor=math.gcd(sr,SAMPLE_RATE)
        x=resample_poly(x,SAMPLE_RATE//divisor,sr//divisor)
    x=x-np.mean(x)
    rms=float(np.sqrt(np.mean(x*x))) if len(x) else 0
    if len(x) < SAMPLE_RATE or rms < 0.004:
        raise ValueError('No clear speech detected. Speak closer to your microphone.')
    x=x/(np.max(np.abs(x))+1e-8)
    f,t,z=stft(x,fs=SAMPLE_RATE,nperseg=400,noverlap=240,nfft=512,boundary=None)
    power=np.abs(z)**2
    # Voice-only frames via adaptive energy gating.
    e=np.sum(power,axis=0)
    voiced=e>max(float(np.max(e))*0.09,1e-12)
    if voiced.sum() < 12:
        raise ValueError('Speech is too short. Speak the complete phrase.')
    power=power[:,voiced]
    def mel(v): return 2595*np.log10(1+v/700)
    def unmel(v): return 700*(10**(v/2595)-1)
    borders=unmel(np.linspace(mel(80),mel(7600),28))
    bins=np.searchsorted(f,borders)
    filters=np.zeros((26,len(f)))
    for k in range(26):
        a,b,c=bins[k:k+3]
        if a<b: filters[k,a:b]=np.linspace(0,1,b-a,endpoint=False)
        if b<c: filters[k,b:c]=np.linspace(1,0,c-b,endpoint=False)
    logmel=np.log(np.maximum(filters@power,1e-10))
    cep=dct(logmel,type=2,axis=0,norm='ortho')[1:14]  # ignore overall energy
    mean=np.mean(cep,axis=1)
    std=np.std(cep,axis=1)
    spec=np.mean(power,axis=1)
    bands=[np.sum(spec[(f>=lo)&(f<hi)]) for lo,hi in [(80,400),(400,1200),(1200,3000),(3000,7600)]]
    bands=np.log(np.maximum(np.array(bands)/max(sum(bands),1e-9),1e-6))
    feat=np.r_[mean,std,bands].astype(float)
    return feat


def capture_voice():
    try:
        import sounddevice as sd
    except ImportError as e:
        raise RuntimeError('Microphone support missing. Run: pip install -r requirements.txt') from e
    try:
        recording=sd.rec(int(VOICE_SECONDS*SAMPLE_RATE), samplerate=SAMPLE_RATE,
                         channels=1,dtype='float32',blocking=True)
        return voice_features(recording[:,0],SAMPLE_RATE)
    except Exception as e:
        raise RuntimeError(f'Microphone recording failed: {e}. Check Windows microphone permission.') from e


def enroll_voice(user_id, feature_vectors):
    if len(feature_vectors)<3:
        raise ValueError('Record three voice samples to enroll.')
    for vec in feature_vectors:
        if len(vec)!=30 or not np.all(np.isfinite(vec)):
            raise ValueError('Invalid audio features.')
    with db.connect() as con:
        con.execute('DELETE FROM voice_templates WHERE user_id=?',(user_id,))
        con.executemany('INSERT INTO voice_templates(user_id,features_json) VALUES(?,?)',
                        [(user_id,json.dumps(np.asarray(v).tolist())) for v in feature_vectors])


def _voice_distance(a,b):
    a=np.asarray(a); b=np.asarray(b)
    scale=np.r_[np.full(13,5.0),np.full(13,3.0),np.full(4,0.8)]
    return float(np.sqrt(np.mean(((a-b)/scale)**2)))


def verify_voice(user_id, feature):
    templates=db.rows('SELECT user_id,features_json FROM voice_templates')
    own=[np.array(json.loads(t['features_json'])) for t in templates if t['user_id']==user_id]
    if len(own)<3:
        raise RuntimeError('No voice profile. Ask the administrator to help you enroll.')
    own_score=min(_voice_distance(feature,t) for t in own)
    others=[_voice_distance(feature,json.loads(t['features_json'])) for t in templates if t['user_id']!=user_id]
    competing=min(others, default=math.inf)
    # Practical demo threshold: combines enrolled voice resemblance and separation.
    ok=own_score<=2.6 and (competing==math.inf or own_score < competing*0.93)
    return ok,own_score


def face_dir():
    path=db.DATA_DIR/'faces'
    path.mkdir(parents=True,exist_ok=True)
    return path


def face_detector(cv2):
    cascade=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')
    if cascade.empty(): raise RuntimeError('OpenCV face cascade failed to load.')
    return cascade


def get_face(gray,cv2,cascade):
    faces=cascade.detectMultiScale(gray,scaleFactor=1.1,minNeighbors=5,minSize=(70,70))
    if len(faces)!=1: return None,None
    x,y,w,h=map(int,faces[0]); img=gray[y:y+h,x:x+w]
    img=cv2.equalizeHist(cv2.resize(img,(100,100)))
    return img,(x,y,w,h)


def capture_faces(user_id=None, enroll=False):
    try:
        import cv2
    except ImportError as e:
        raise RuntimeError('Face recognition is optional. Install: pip install -r requirements-face.txt') from e
    camera=cv2.VideoCapture(0,cv2.CAP_DSHOW if hasattr(cv2,'CAP_DSHOW') and __import__('sys').platform=='win32' else cv2.CAP_ANY)
    if not camera.isOpened():
        camera.release()
        camera=cv2.VideoCapture(0)  # fall back from DirectShow to default backend
    if not camera.isOpened():
        camera.release()
        raise RuntimeError('Cannot access camera. Check camera permissions or use voice recognition.')
    cascade=face_detector(cv2)
    images=[]
    goal=8 if enroll else 1
    try:
        while len(images)<goal:
            ok,frame=camera.read()
            if not ok: raise RuntimeError('Camera stopped delivering frames.')
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            crop,rect=get_face(gray,cv2,cascade)
            if rect:
                x,y,w,h=rect;cv2.rectangle(frame,(x,y),(x+w,y+h),(40,200,80),2)
            cv2.putText(frame,f'SPACE: capture ({len(images)}/{goal})  ESC: cancel',
                        (12,30),cv2.FONT_HERSHEY_SIMPLEX,0.55,(255,255,255),2)
            cv2.imshow('Bookstore Face Login (only one face visible)',frame)
            key=cv2.waitKey(30)&0xFF
            if key==27: raise RuntimeError('Face capture cancelled.')
            if key==32 and crop is not None: images.append(crop.copy())
        if enroll:
            np.savez_compressed(face_dir()/f'{user_id}.npz',*images)
        return images[0]
    finally:
        camera.release();cv2.destroyAllWindows()


def face_enrolled(user_id):
    return (face_dir()/f'{user_id}.npz').exists()


def verify_face(user_id, captured):
    try:
        import cv2
    except ImportError as e:
        raise RuntimeError('Face recognition requires opencv-contrib-python.') from e
    if not hasattr(cv2,'face') or not hasattr(cv2.face,'LBPHFaceRecognizer_create'):
        raise RuntimeError('Install opencv-contrib-python, not opencv-python, for LBPH.')
    x=[];y=[]
    for path in face_dir().glob('*.npz'):
        try:
            uid=int(path.stem)
            with np.load(path) as data:
                for key in data.files:
                    x.append(data[key].astype('uint8'));y.append(uid)
        except (ValueError,OSError): pass
    if user_id not in y: raise RuntimeError('No enrolled face profile for this account.')
    recog=cv2.face.LBPHFaceRecognizer_create(radius=1,neighbors=8,grid_x=8,grid_y=8)
    recog.train(x,np.array(y,dtype='int32'))
    guessed,conf=recog.predict(captured)
    return guessed==user_id and conf<=75.0,float(conf)
