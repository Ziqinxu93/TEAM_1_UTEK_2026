import time
from collections import deque
idlemin=60.0
breakmin=120.0
history=3600.0
class Activity:
    def __init__(self,sources):
        self.sources=sources
        self.last=self.latest()
        self.begin=time.perf_counter()
        self.breaks=deque()
    def latest(self):
        return max(s.last_activity for s in self.sources)
    def update(self):
        last=self.latest()
        now=time.perf_counter()
        if last-self.last>=breakmin:
            self.breaks.append((last,last-self.last))
            self.begin=last
        self.last=last
        while self.breaks and self.breaks[0][0]<now-history:
            self.breaks.popleft()
        return now,last
    def features(self):
        now,last=self.update()
        idle=now-last
        rest=idle>=breakmin
        b=self.breaks[-1] if self.breaks else None
        return {
            "idle": idle>=idlemin,
            "rest": rest,
            "idletime": idle,
            "session": 0.0 if rest else now-self.begin,
            "lastbreak": b[1] if b else None,
            "since": now-b[0] if b else None,
            "breaks": len(self.breaks),
        }
if __name__=="__main__":
    from collectors.keyboard import Keyboard
    from collectors.mouse import MouseCollector
    m=MouseCollector()
    k=Keyboard()
    m.start()
    k.start()
    a=Activity([m,k])
    while 1:
        time.sleep(5)
        f=a.features()