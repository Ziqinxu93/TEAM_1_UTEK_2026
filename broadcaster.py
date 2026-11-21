import json
import os
import time
from datetime import datetime
def write(data,name):
    tmp=name+'.tmp'
    with open(tmp,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=1)
    os.replace(tmp,name)
def run(name):
    t=time.monotonic()
    while 1:
        data={
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "score": 50,
            "status": "ok",
        }
        write(data,name)
        t+=5
        time.sleep(max(0,t-time.monotonic()))
if __name__=="__main__":
    run("output.json")
     
