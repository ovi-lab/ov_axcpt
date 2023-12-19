import os
from typing import Callable

import neurokit2 as nk

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

def getSupportedMetrics() -> dict[str, Callable]:
    supportedMetrics = {
        "ApEn" : nk.entropy_approximate,
        "SampEn" : nk.entropy_sample,
        "FE" : nk.entropy_fuzzy,
        "MSE" : nk.entropy_multiscale,
        "MFE" : nk.complexity_fuzzymse
    }
    # Make sure that supported metrics matches those specified in config
    assert set(supportedMetrics) == set(CONFIG.protected["supported_metrics"])
    
    return supportedMetrics