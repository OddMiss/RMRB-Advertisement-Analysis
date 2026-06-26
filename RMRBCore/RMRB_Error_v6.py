import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)
from Config.Config import EXIT_ERRORS

def Exit_Error_Detector(Error: str):
    Error = str(Error)
    Error_Lower = Error.lower()
    for exit_error in EXIT_ERRORS:
        if exit_error in Error_Lower: return True
    return False