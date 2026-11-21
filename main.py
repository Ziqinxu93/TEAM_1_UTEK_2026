import time
from datetime import datetime
import scorer
from broadcaster import write
from intervention import breakPopup
from collectors.keyboard import Keyboard
from collectors.mouse import MouseCollector
from collectors.activity import Activity
k=Keyboard()
m=MouseCollector()
k.start()
m.start()
a=Activity([m,k])
p=breakPopup()
t=time.monotonic()
while 1:
    f=a.features()
    s=scorer.get_score(f)
    write({
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "score": s,
        "status": "ok",
    },"output.json")
    p.update(s,f["rest"])
    t+=5
    time.sleep(max(0,t-time.monotonic()))
