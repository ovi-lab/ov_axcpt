import errno
import glob
import logging
import os

import mne

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