import errno
import glob
import logging
import os

import mne
import yaml

from src.config import CONFIG

_log = logging.getLogger(__name__)

def loadData(
        path: [None | str] = None, 
        checkSubdirs: bool = False,
        **kwargs
        ) -> (mne.io.Raw, str):
    
    # TODO: add logging
    
    # Use values from Config as defined at (approx) loadData call time -
    # prevents issues arising from Config values changes during execution
    _CONFIG_SS = CONFIG.snapshot()
    
    supportedFileTypes = {
        "gdf" : {}
    }
    
    # Determine the path to the raw data file to load, or the folder to search
    # for a data file
    if path is not None:
        # Use the file or folder passed to loadData
        _path = path
    elif _CONFIG_SS["raw_data_path"] is not None:
        # Use the path to the data raw data file or folder specified in config
        _path = _CONFIG_SS["raw_data_path"]
    elif _CONFIG_SS["session_name"] is not None:
        # Find and use the session folder in the data dir
        data_dir = os.path.join(_CONFIG_SS["root"], _CONFIG_SS["data_dir"])
        targetPath = data_dir + "/**/" + _CONFIG_SS["session_name"]
        matchingPaths = glob.glob(targetPath, recursive=True)
        if len(matchingPaths) > 1:
            raise RuntimeError(
                "Found multiple directories with session_name " +
                f"'{_CONFIG_SS['session_name']}' in data_dir '{data_dir}': " +
                f"{matchingPaths}"
            )
        elif len(matchingPaths) == 0:
            raise RuntimeError(
                "Found no directories with session_name " +
                f"'{_CONFIG_SS['session_name']}' in data_dir '{data_dir}': "
            )
        else:
            _path = matchingPaths[0]
    else:
        # Use the entire data dir
        _path = os.path.abspath(
            os.path.join(_CONFIG_SS["root"], _CONFIG_SS["data_dir"])
        )
        
    invalidFileTypeE = lambda fileType: RuntimeError(
        f"Unsupported file type `{fileType}`. Supported file types: " +
        f"{supportedFileTypes.keys()}"
    )
       
    if os.path.isfile(_path):
        # Use _path as the data file and extract its format directly from _path
        dataFormat = os.path.splitext(_path)[1].strip(".")
        if not dataFormat in supportedFileTypes:
            raise invalidFileTypeE(dataFormat)
        dataPath = _path
    elif os.path.isdir(_path):
        # Get the latest data recorded in _path (or subdirectories if
        # specified) of the format specified in the config
        dataFormat = _CONFIG_SS["data_format"]
        if not dataFormat in supportedFileTypes:
            raise invalidFileTypeE(datadataFormat_format)
        subdirTarget = "/**" if checkSubdirs else ""
        targetPaths = _path + subdirTarget + "/*." + dataFormat
        matchingPaths = glob.glob(targetPaths, recursive=checkSubdirs)
        
        if len(matchingPaths) == 0:
            raise RuntimeError(
                f"No data (filetype = {dataFormat}) found in directory " +
                f"'{data_dir}'" +
                (" or subdirectories" if checkSubdirs else "")
            )
        dataPath = max(matchingPaths, key=os.path.getctime)
    else:
        raise FileNotFoundError(
            errno.ENOENT, 
            "Specified data is not an existing file or directory", 
            _path
        )
        
    _log.debug("Loading data from file: %s", dataPath)
    _kwargs = {}
    _kwargs.update(supportedFileTypes[dataFormat])
    _kwargs.update(kwargs)
    raw = mne.io.read_raw(dataPath, **_kwargs)
    
    return raw, dataPath

def getEvents(
        raw: mne.io.BaseRaw
        ):
    # Extract events from annotations, and give them meaningful names
    
    events, eventDict = mne.events_from_annotations(raw)
    
    # eventDict maps "OV stim id" -> "MNE event id". To insead use the names of
    # the OV stims as keys, use the inverse of the bijective mapping returned
    # by getOvStimCodes(), which maps "OV stim name" -> "OV stim id"
    ovStimCodes = getOVStimCodes()
    ovStimCodesRev = {v : k for (k, v) in ovStimCodes.items()}
    assert len(ovStimCodes) == len(ovStimCodesRev)
    eventDict = {ovStimCodesRev[int(k)]: v for k, v in eventDict.items()}
    
    # Organize eventDict labels into appropriate groups
    # Load the stimulation groups
    stimGroupsFile = os.path.join(CONFIG.root, CONFIG.axcpt_stim_groups_path)
    with open(stimGroupsFile, "r") as f:
        stimGroups = yaml.safe_load(f)
    # Combine group names into a single "group label" (keys) for each label
    # (values)
    groupLabels = {}
    def combineGroupNames(d, prefix):
        _prefix = "" if prefix is None else prefix + "/"
        if isinstance(d, str):
            groupLabels[_prefix + d] = d
        else:
            for k,v in d.items():
                combineGroupNames(v, _prefix + k)
    combineGroupNames(stimGroups, None)
    # Rename the eventDict labels using the group labels
    groupLabelsRev = {v : k for (k, v) in groupLabels.items()}
    assert len(groupLabels) == len(groupLabelsRev)
    eventDict = {groupLabelsRev[k] : v for (k, v) in eventDict.items()}
        
    return events, eventDict

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