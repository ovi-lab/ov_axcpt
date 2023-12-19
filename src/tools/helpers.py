import os

from src.config import CONFIG

def getOVStimCodes() -> dict[str, int]:
    ovStimListPath = os.path.join(CONFIG.root, CONFIG.ov_stim_list_path)
    with open(ovStimListPath, "r") as f:
        lines = f.readlines()
        
    ovStimCodes = {}
    for line in lines:
        entries = line.split()
        ovStimCodes[entries[0]] = int(entries[2], base=16)
        
    if not len(ovStimCodes) == len(lines):
        raise RuntimeError(
            "The number of stimulation codes read from the stimulations " +
            "file is not equal to the number of lines in that file."
        )
        
    return ovStimCodes

def getChannelNamesEEGO() -> list[str]:
    path = os.path.join(CONFIG.root, CONFIG.eego_electrode_map_path)
    with open(path, "r") as f:
        channelNames = [line.strip() for line in f]
    return channelNames