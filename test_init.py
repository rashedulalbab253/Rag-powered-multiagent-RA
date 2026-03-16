import traceback
import sys

with open("clear_error.txt", "w") as f:
    try:
        from backend import ResearchAssistant
        a = ResearchAssistant()
        res, err = a.initialize()
        f.write(f"RES: {res}\n")
        f.write(f"ERR: {err}\n")
    except Exception as e:
        traceback.print_exc(file=f)
