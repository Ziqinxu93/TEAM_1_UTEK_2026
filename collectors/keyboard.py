import statistics
import threading
import time
from collections import deque
from pynput import keyboard
window=60.0
pause=2.0
minkeys=20
maxhold=1.0
stale=3.0
def keyid(key):
    if isinstance(key,keyboard.Key):
        key=key.value
    return getattr(key,"vk",None) or key
class Keyboard:
    def __init__(self):
        self.lock=threading.Lock()
        self.presses=deque()
        self.holds=deque()
        self.down={}
        self.last_activity=time.perf_counter()
    def start(self):
        self.listener=keyboard.Listener(on_press=self.press,on_release=self.release)
        self.listener.daemon=True
        self.listener.start()
    def stop(self):
        self.listener.stop()
    def press(self,key):
        now=time.perf_counter()
        k=keyid(key)
        with self.lock:
            self.last_activity=now
            if now-self.down.get(k,0)<stale:
                return
            self.down[k]=now
            self.presses.append((now,key==keyboard.Key.backspace))
    def release(self,key):
        now=time.perf_counter()
        with self.lock:
            self.last_activity=now
            t=self.down.pop(keyid(key),None)
            if t and now-t<=maxhold:
                self.holds.append((now,now-t))
    def features(self):
        now=time.perf_counter()
        old=now-window
        with self.lock:
            while self.presses and self.presses[0][0]<old:
                self.presses.popleft()
            while self.holds and self.holds[0][0]<old:
                self.holds.popleft()
            presses=list(self.presses)
            holds=[h for t,h in self.holds]
        n=len(presses)
        times=[t for t,b in presses]
        gaps=[b-a for a,b in zip(times,times[1:]) if b-a<=pause]
        enough=n>=minkeys and len(gaps)>=2
        f={
            "keystrokes": n,
            "speed": n*60/window,
            "enough": enough,
            "mean": None,
            "std": None,
            "cv": None,
            "backspace": None,
            "hold": None,
        }
        if enough:
            m=statistics.fmean(gaps)
            s=statistics.stdev(gaps)
            f["mean"]=m
            f["std"]=s
            f["cv"]=s/m
            f["backspace"]=sum(b for t,b in presses)/n
            f["hold"]=statistics.fmean(holds) if holds else None
        return f
if __name__=="__main__":
    c=Keyboard()
    c.start()
    while 1:
        time.sleep(5)
        f=c.features()