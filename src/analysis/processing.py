import datetime
import errno
import glob
import logging
import math
import os
import time
import warnings

from deepdiff import DeepDiff
import mne
import neurokit2 as nk
import numpy as np
import pandas as pd
import yaml

from src.config import CONFIG, TempConfig
from src.tools import helpers

_log = logging.getLogger(__name__)

class AXCPT:
    def __init__(self, **attrs):
        # TODO: change
        for k, v in attrs.items():
            self.__setattr__(k, v)
    
    @classmethod
    def readSession(
            cls, 
            sessionName: str,
            sessionConfigFile: str = "session_config.yaml",
            **kwargs
            ):
        
        # Find the session directory in the data directory
        _CONFIG_SS = CONFIG.snapshot()
        data_dir = os.path.join(_CONFIG_SS["root"], _CONFIG_SS["data_dir"])
        targetPath = data_dir + "/**/" + sessionName
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
        elif not os.path.isdir(matchingPaths[0]):
            raise RuntimeError(
                f"Must be existing directory: {matchingPaths[0]}"
            )
        else:
            sessionDir = matchingPaths[0]
            
        # Find the session config file
        fName, fType = os.path.splitext(sessionConfigFile)
        if fType != ".yaml":
            raise ValueError("'sessionConfigFile' must be a yaml file")
        targetPath = sessionDir + "/**/" + fName + ".yaml"
        matchingPaths = glob.glob(targetPath, recursive=True)
        if len(matchingPaths) > 1:
            raise RuntimeError(
                "Found multiple session config files matching " +
                f"'{sessionConfigFile}': {', '.join(matchingPaths)}"
            )
        elif len(matchingPaths) == 0:
            raise RuntimeError(
                f"Found no session config files matching '{sessionConfigFile}'"
            )
        else:
            configPath = matchingPaths[0]
            
        with TempConfig(configPath):
            # Load the data. If the config does not specify specific data to
            # use, search the session directory for data
            configDataPath = CONFIG.raw_data_path
            dataPath = sessionDir if configDataPath is None else configDataPath
            _kwargs = kwargs.copy()
            _kwargs.pop("path", None)
            raw, dataPath = cls.loadData(path=dataPath, **_kwargs)
                        
            # Get channel groups
            dataCH, nonDataCH, targetCH = cls.getChannelGroups(raw.ch_names)
            
            # Get events with meaningful names
            events, eventDict = cls.getEvents(raw)
            
            # Get the baseline
            noBaseline = not any(
                x.startswith("timing/baseline") for x in eventDict
            )
            blRaw = None if noBaseline else cls.extractBaseline(
                raw, events, eventDict, copy=True
            )
                
            # Apply any further processing to the raw data (+ baseline) here,
            # making sure not to modify the data in place. The raw data and
            # baseline must given to the AXCPT constructor unmodified.
            
            # Rename channels if necessary
            # TODO: implement
            
            # Apply necessary filtering to all data channels
            if CONFIG.apply_filters:
                rawFiltered = cls.applyFilters(raw, picks=dataCH, copy=True)
                blFiltered = None if noBaseline else cls.extractBaseline(
                    rawFiltered, events, eventDict, copy=True
                )
            else:
                rawFiltered = raw.copy()
                blFiltered = None if noBaseline else blRaw.copy()
            
            # Extract the metadata and corresponding events and event IDs
            metadata, events_md, eventDict_md = cls.getMetadata(
                events, eventDict, rawFiltered.info["sfreq"]
            )
            
            # Epoch the data using the metadata and corresponding
            # events/eventIDs
            epochs = mne.Epochs(
                rawFiltered,
                events_md,
                event_id=eventDict_md,
                tmin=CONFIG.epoch_tmin,
                tmax=CONFIG.epoch_tmax,
                metadata=metadata,
                preload=True,
                baseline=None
            )
            # Create fixed length epochs of the baseline data
            if noBaseline:
                blEpochs = None
            else:
                blEvents = mne.make_fixed_length_events(
                    blFiltered,
                    id=1,
                    duration=(CONFIG.epoch_tmax - CONFIG.epoch_tmin)
                )
                blMetadata, blEvents, blEventDict = mne.epochs.make_metadata(
                    blEvents,
                    {"epoch_start" : 1},
                    0,
                    (CONFIG.epoch_tmax - CONFIG.epoch_tmin),
                    blFiltered.info["sfreq"]
                )
                blEpochs = mne.Epochs(
                    blFiltered,
                    blEvents,
                    event_id=blEventDict,
                    tmin=0,
                    tmax=(CONFIG.epoch_tmax - CONFIG.epoch_tmin),
                    metadata=blMetadata,
                    preload=True,
                    baseline=None
                )
            
        # TODO: change dataChannels to always be read from config
        return cls(
            data={
                "raw" : raw,
                "rawProcessed" : rawFiltered,
                "epochs" : epochs
            },
            events={
                "raw" : events,
                "rawProcessed" : events,
                "epochs" : events_md
            },
            eventDict={
                "raw" : eventDict,
                "rawProcessed" : eventDict,
                "epochs" : eventDict_md
            },
            baseline={
                "raw" : blRaw,
                "rawProcessed" : blFiltered,
                "epochs" : blEpochs
            },
            sessionDir=sessionDir,
            sessionConfigPath=configPath,
            rawDataPath=dataPath
        )  
        
    @property
    def channelGroups(self):
        with TempConfig(self.sessionConfigPath):
            dataCH, nonDataCH, targetCH = self.getChannelGroups(
                self.data["raw"].ch_names
            )
            return {
                "dataCH" : dataCH,
                "nonDataCH" : nonDataCH,
                "targetCH" : targetCH
            }

    @classmethod
    def loadData(
            cls,
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
        
        # Determine the path to the raw data file to load, or the folder to
        # search for a data file
        if path is not None:
            # Use the file or folder passed to loadData
            _path = path
        elif _CONFIG_SS["raw_data_path"] is not None:
            # Use the path to the data raw data file/folder specified in config
            _path = _CONFIG_SS["raw_data_path"]
        elif _CONFIG_SS["session_name"] is not None:
            # Find and use the session folder in the data dir
            data_dir = os.path.join(_CONFIG_SS["root"], _CONFIG_SS["data_dir"])
            targetPath = data_dir + "/**/" + _CONFIG_SS["session_name"]
            matchingPaths = glob.glob(targetPath, recursive=True)
            if len(matchingPaths) > 1:
                raise RuntimeError(
                    "Found multiple directories with session_name " +
                    f"'{_CONFIG_SS['session_name']}' in data_dir " +
                    f"'{data_dir}': {matchingPaths}"
                )
            elif len(matchingPaths) == 0:
                raise RuntimeError(
                    "Found no directories with session_name " +
                    f"'{_CONFIG_SS['session_name']}' in data_dir '{data_dir}'"
                )
            else:
                _path = matchingPaths[0]
        else:
            # Use the entire data dir
            _path = os.path.abspath(
                os.path.join(_CONFIG_SS["root"], _CONFIG_SS["data_dir"])
            )
        
        def invalidFileTypeE(fileType):
            return RuntimeError(
                f"Unsupported file type `{fileType}`. Supported file types: " +
                f"{supportedFileTypes.keys()}"
            )
        
        if os.path.isfile(_path):
            # Use _path as the data file and extract its format directly
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
                    f"'{_path}'" +
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
    
    @classmethod
    def getChannelGroups(
            cls,
            chNames: list[str]
            ) -> (list[str], list[str], list[str]):
        # Get data and nondata channels, as well as which channels to analyze
        # (the target channels)
        # 
        # Requires: non_data_channels and target_channels in CONFIG are either
        # None or list[str]
        
        nonDataCH = CONFIG.non_data_channels
        if nonDataCH is None:
            nonDataCH = []
        
        dataCH = [x for x in chNames if x not in nonDataCH]
        
        targetCH = CONFIG.target_channels
        if targetCH is None:
            targetCH = dataCH    
            
        return dataCH, nonDataCH, targetCH
    
    @classmethod
    def extractBaseline(
            cls,
            raw: mne.io.BaseRaw,
            events,
            eventDict,
            copy: bool = True
            ) -> mne.io.BaseRaw:
        
        _raw = raw.copy() if copy else raw
        
        tRange = []
        for event in ("start", "stop"):
            eventNames = mne.event.match_event_names(
                eventDict, "timing/baseline/" + event
            )
            eventName = eventNames[0]
            tRange.append(events[events[:,2] == eventDict[eventName]][0,0])
            tRange[-1] = tRange[-1] / raw.info["sfreq"]
        
        return _raw.crop(tmin=tRange[0], tmax=tRange[1], include_tmax=True)
    
    @classmethod
    def applyFilters(
            cls,
            raw: mne.io.BaseRaw,
            picks: str|list[str]|None = None,
            copy: bool = True
            ) -> mne.io.BaseRaw:
        
        # Apply necessary filtering specified in config
        # Data must be loaded to apply filtering
        rawFiltered = raw.copy() if copy else raw
        rawFiltered.load_data()
        
        # Apply notch filter to remove noise spikes
        notch_freqs = CONFIG.notch_freqs
        if notch_freqs is not None:
            rawFiltered.notch_filter(freqs=notch_freqs, picks=picks)
            
        # Apply bandpass filter to isolate relevant frequencies
        l_freq = CONFIG.l_freq
        h_freq = CONFIG.h_freq
        if l_freq is not None or h_freq is not None:
            rawFiltered.filter(l_freq, h_freq, picks=picks)
            
        return rawFiltered

    @classmethod
    def getEvents(
            cls,
            raw: mne.io.BaseRaw
            ):
        # Extract events from annotations, and give them meaningful names
        # Assumes raw contains data recorded in a AXCPT session
        
        events, eventDict = mne.events_from_annotations(raw)
        
        # eventDict maps "OV stim id" -> "MNE event id". To insead use the
        # names of the OV stims as keys, use the inverse of the bijective
        # mapping returned by getOvStimCodes(), which maps "OV stim name" ->
        # "OV stim id"
        ovStimCodes = helpers.getOVStimCodes()
        ovStimCodesRev = {v : k for (k, v) in ovStimCodes.items()}
        assert len(ovStimCodes) == len(ovStimCodesRev)
        eventDict = {ovStimCodesRev[int(k)]: v for k, v in eventDict.items()}
        
        # Organize eventDict labels into appropriate groups
        # Load the stimulation groups
        stimGroupsFile = os.path.join(
            CONFIG.root, CONFIG.axcpt_stim_groups_path
        )
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
        for k in list(eventDict.keys()):
            if k in groupLabelsRev:
                eventDict[groupLabelsRev[k]] = eventDict.pop(k)
            
        return events, eventDict
    
    @classmethod
    def getMetadata(
            cls,
            events,
            eventDict,
            sfreq
            ):
        
        _events = events.copy()
        _eventDict = eventDict.copy()
        
        def getEventNames(x):
            y = mne.event.match_event_names(_eventDict, x, on_missing="raise")
            if len(y) == 1:
                y = y[0]
            return y
        
        # Define the target event for creating epochs around
        # add a new event to _eventDict to use as the target event
        targetEventName = "epochs_row_event"
        while targetEventName in _eventDict:
            targetEventName = targetEventName + "_"
        _eventDict[targetEventName] = max(_eventDict.values()) + 1
        # Add target event to _events array
        fixationCross = getEventNames(
            "visual/image_display/onset/fixation_cross"
        )
        targetEvents, _ = mne.event.define_target_events(
            _events,
            _eventDict[fixationCross],
            _eventDict[fixationCross],
            sfreq,
            0,
            (CONFIG.durations["ISI"] + CONFIG.durations["cue_stimulus"]) * 1.1,
            new_id=_eventDict[targetEventName],
            fill_na=_eventDict[fixationCross]
        )
        _events = np.concatenate([_events, targetEvents])
        _events = _events[_events[:,0].argsort()]
        
        # Extract the metadata and corresponding events and event IDs
        stimulusNameRoot = "visual/image_display/onset/stimulus"
        responseNameRoot = "keyboard/button_pressed/response"
        metadata, events_md, eventDict_md = mne.epochs.make_metadata(
            _events,
            _eventDict,
            None,
            None,
            sfreq,
            row_events=targetEventName,
            keep_first=responseNameRoot
        )
        
        stimulusNames = getEventNames(stimulusNameRoot)
        
        # Check that each epoch contains two stimuli (or one in the case of
        # duplicate stimuli)
        numStimuli = metadata[stimulusNames].notna().sum(axis=1)
        if not numStimuli.isin([1, 2]).all():
            raise RuntimeError(
                "Unexpected number of visual stimuli in epochs: " +
                ", ".join(metadata[~numStimuli.isin([1, 2])].index.tolist())
            )
            
        # Get the cue and probe stimuli, and whether they are a target sequence
        metadata["cue"] = metadata[stimulusNames].idxmin(axis=1)
        metadata["probe"] = metadata[stimulusNames].idxmax(axis=1)
        metadata["is_target_sequence"] = (
            metadata[["cue", "probe"]]
            .eq([getEventNames(f"{stimulusNameRoot}/{c}") for c in["A", "X"]])
            .all(axis=1)
        )
        
        # Determine the participant's response and response time
        metadata = metadata.rename(
            columns={
                f"first_{responseNameRoot}" : "given_response",
                responseNameRoot : "response_time"
            }
        )
        metadata["given_response"] = (
            responseNameRoot + "/" + metadata["given_response"]
        )
        
        # Determine whether the correct response was given
        metadata["response_correct"] = (
            metadata["given_response"].notna() &
            np.where(
                metadata["is_target_sequence"],
                metadata["given_response"].eq(
                    getEventNames(f"{responseNameRoot}/left")
                ),
                metadata["given_response"].eq(
                    getEventNames(f"{responseNameRoot}/right")
                )
            )
        )
        
        return metadata, events_md, eventDict_md
    
    def getClassifierData(
            self, 
            includeDropped: bool = False,
            baseline: bool = True
            ):
        labels, blLabels = self.getClassifierLabels(
            includeCRT=False,
            baseline=baseline
        )
        features, blFeatures = self.getClassifierFeatures(
            epochMask=labels["select"],
            baselineEpochMask=(blLabels["select"] if baseline else False),
            includeDropped=True,
            includeMask=False
            )
        
        if baseline:
            keys = ["task", "baseline"]
            labels = pd.concat([labels, blLabels], keys=keys)
            features = pd.concat([features, blFeatures], keys=keys)
        
        cData = features.unstack(level="channel")
        cData.columns = pd.MultiIndex.from_product(
            [["features"], ["/".join(s) for s in cData.columns.values]]
        )
        cData.insert(0, "label", labels["label"])
        
        if not includeDropped:
            for axis in (0, 1):
                cData = cData.dropna(axis=axis, how="all")
            
        return cData
    
    def getClassifierLabels(
            self,
            includeCRT: bool = False,
            baseline: bool = True
            ):
        with TempConfig(self.sessionConfigPath):
            alpha = CONFIG.alpha
            if not (alpha > 0 and alpha <= 0.5):
                raise RuntimeError(
                    "Config value `alpha` must be in range (0, 0.5], but " +
                    f"got {alpha}"
                )
            if self.baseline["epochs"] is None and baseline:
                raise ValueError(
                    "Received `baseline=True`, but no baseline data exists."
                )
                
            metadata = self.data["epochs"].metadata
            df = pd.DataFrame(index=metadata.index)
            df["epoch"] = df.index
            
            # Track which epochs to select or drop
            df["select"] = True
            
            # Get the average referenced (corrected) response times
            crt = "corrected_response_time"
            df[crt] = (
                metadata["response_time"] - metadata["response_time"].mean()
            )
            
            # Label the attention state
            quantiles = [0., alpha, 1. - alpha, 1.]
            labels = ["high", "medium", "low"]
            categories = ["baseline"] + [x for x in reversed(labels)]
            if alpha == 0.5:
                quantiles.pop(2)
                labels.pop(1)
            df["label"] = pd.qcut(
                df[crt],
                quantiles,
                labels=labels,
                precision=12
            )
            df["label"] = df["label"].cat.set_categories(categories)
            
            # Drop any epochs that are missing data
            df.loc[df.isna().any(axis=1), [("select")]] = False
            
            # Create labels for the baseline epochs
            blEpochs = self.baseline["epochs"]
            bl = None
            if baseline:
                bl = pd.DataFrame(index=blEpochs.metadata.index)
                bl["epoch"] = bl.index
                      
                # Drop any extra epochs from the start/end of the baseline      
                bl["select"] = False
                n = math.floor(
                    CONFIG.durations["baseline"] / blEpochs.times[-1]
                )
                start = max(0, math.ceil((len(bl) - n) / 2))
                bl.iloc[start:(start + n), bl.columns.get_loc("select")] = True
                
                # Set the label
                bl["label"] = pd.Categorical(
                    ["baseline"] * len(bl),
                    categories=categories,
                    ordered=False
                )
                
                bl.set_index("epoch", inplace=True)
            
            if not includeCRT:
                df = df.drop(crt, axis=1)
            df.set_index("epoch", inplace=True)
            
        return df, bl
    
    # for epochMask and baselineEpochMask:
    #   specify True to use all epochs, or provide a series (or dataframe with
    #   a column named "epochMask") with the same index as the data (and or
    #   baseline) epochs metadata to use as a mask of which epochs to use, or
    #   specify False so that no features are calculated and None is returned
    def getClassifierFeatures(
            self, 
            epochMask: pd.DataFrame|pd.Series|bool = True,
            baselineEpochMask: pd.DataFrame|pd.Series|bool = False,
            includeDropped: bool = True,
            includeMask: bool = False
            ):
        with TempConfig(self.sessionConfigPath):
            if self.baseline["epochs"] is None and baseline in [False, None]:
                raise ValueError(
                    "Received `baseline != False`, but no baseline data exists"
                )
                
            # Setup dataframe for both baseline and normal data
            masks = {"data" : epochMask, "baseline" : baselineEpochMask}
            dfs = {}
            for name, mask in masks.items():
                epochs = getattr(self, name)["epochs"]
                
                # Create a dataframe to store the features
                df = pd.DataFrame(index=epochs.metadata.index)
                df["type"] = name
                df["epoch"] = df.index
                df["channel"] = len(df) * [epochs.ch_names]
                
                # Specify which epochs to calculate features for
                if isinstance(mask, bool) or mask is None:
                    df["epoch_mask"] = bool(mask)
                elif not df.index.equals(mask.index):
                    a = {"data": "epochMask", "baseline": "baselineEpochMask"}
                    raise ValueError(
                        f"`{a[name]}` must have the same index as the " +
                        f"metadata of the {name} epochs"
                    )
                else:
                    _mask = mask 
                    if isinstance(mask, pd.DataFrame):
                        _mask = mask["epochMask"]
                    df.insert(len(df.columns), "epoch_mask", _mask)
                # Specify which channels to calculate features for
                channelMask = [
                    (x in self.channelGroups["targetCH"])
                    for x in epochs.ch_names
                ]
                df["channel_mask"] = len(df) * [channelMask]
                
                _log.info(
                    "Getting features for %i epochs and %i channels of %s",
                    df["epoch_mask"].sum(),
                    df.at[0, "channel_mask"].count(True),
                    name
                )
                # # Report the number of channels and epochs that features will be
                # # calculated for
                # numSelected = {
                #     "epochs" : df["epoch_mask"].sum(),
                #     "channels" : df.at[0, "channel_mask"].count(True)
                # }
                # _log.info(
                #     "Getting features for %s", 
                #     ", ".join([f"{v} {k}" for (k, v) in numSelected.items()])
                # )
                # for k, v in numSelected.items():
                #     if v == 0:
                #         warnings.warn(f"Getting features for 0 {k}")
                
                # Get the data
                # Use units="uV" to get units of "V" as there is an issue where
                # when loading data into mne, mne interprets data recorded by
                # openvibe (recorded with units of V) as having units of mV and
                # incorrectly scales it.
                df["data"] = [*epochs.get_data(units="uV")]
                
                # Explode and organise rows by epoch, then channel
                df = df.explode(["channel", "channel_mask", "data"])
                df = df.set_index(["type", "epoch", "channel"])
                df["mask"] = df[["epoch_mask", "channel_mask"]].all(axis=1)
                
                dfs[name] = df
                
            # Combine data and baseline dataframes into a single dataframe
            df = pd.concat(dfs.values(), axis="index", copy=False)
            for s in ["channel", "epoch"]:
                if not df[s + "_mask"].any():
                    warnings.warn(f"Getting features for 0 {s}s!")
            df = df.drop(["epoch_mask", "channel_mask"], axis=1)
            
            # Specify the metrics to calculate
            _metrics = {
                "ApEn" : nk.entropy_approximate,
                "SampEn" : nk.entropy_sample,
                "FE" : nk.entropy_fuzzy,
                "MSE" : nk.entropy_multiscale,
                "MFE" : nk.complexity_fuzzymse
            }
            metrics = CONFIG.metrics
            if metrics != "all":
                if isinstance(metrics, str):
                    _metrics = {metrics : _metrics[metrics]}
                else:
                    _metrics = {m : _metrics[m] for m in list(metrics)}
                    
            # Check whether any features have already been saved for the
            # current set of config values
            configSS = CONFIG.snapshot()
            excludedConfigVals = [
                "metrics", 
                "target_channels", 
                "non_data_channels", 
                "raw_data_path"
            ]
            for k in excludedConfigVals:
                configSS.pop(k, None)
            configSS["dataFilePath"] = self.rawDataPath
            cacheDir = os.path.join(
                self.sessionDir, "analysis", "feature_cache"
            )
            # Find the saved feature config that matches the current config
            n = 3
            maxID = 0
            targetPath = f"{cacheDir}/features_config_{'[0-9]' * n}.yaml"
            for featuresConfigPath in glob.iglob(targetPath):
                id = int(featuresConfigPath.rstrip(".yaml")[(-1 * n):])
                maxID = max(maxID, id)
                with open(featuresConfigPath, "r") as f:
                    if len(DeepDiff(configSS, yaml.safe_load(f))) == 0:
                        # Check if cached features dataframe has desired index
                        featuresPath = os.path.join(
                            cacheDir, (f"features_%0{n}i.csv") % id
                        )
                        cached = pd.read_csv(
                            featuresPath, 
                            usecols=(lambda x : x in df.index.names)
                        )
                        cached = cached.set_index(
                            [x for x in df.index.names if x in cached.columns]
                        )  
                        if cached.index.equals(df.index):
                            break        
            else:
                # Create new files for saving the features
                id = maxID + 1
                os.makedirs(cacheDir, exist_ok=True)
        
                # Save the modified copy of the config values. Assume these
                # values uniquely identify the epochs data and corresponding
                # features
                featuresConfigPath = os.path.join(
                    cacheDir, (f"features_config_%0{n}i.yaml") % id
                )
                with open(featuresConfigPath, "x") as f:
                    yaml.dump(configSS, f)
            
                # Save the empty features dataframe
                featuresPath = os.path.join(
                    cacheDir, (f"features_%0{n}i.csv") % id
                )
                pd.DataFrame(index=df.index).to_csv(featuresPath, mode="x")
            
            # Calculate the metrics, reading from the cached features as 
            # necessary.
            # Note: df and cachedFeatures are guaranteed to have the same index
            data = np.stack(df["data"].to_numpy())
            cachedFeatures = pd.read_csv(
                featuresPath, index_col=df.index.names
            )
            for name, f in _metrics.items():
                _log.info("Getting metric '%s'", name)
                t0 = time.monotonic()
                
                # Get cached values for this metric
                df[name] = np.nan
                if name in cachedFeatures.columns.values:
                    df.loc[df["mask"], name] = cachedFeatures.loc[
                        df["mask"], name
                    ]
                else:
                    cachedFeatures[name] = np.nan
                _log.debug(
                    "Loaded %i of %i items from cache for metric '%s'",
                    df[name].notna().sum(),
                    df["mask"].sum(),
                    name
                )
                
                # Calculate non-cached values for this metric
                if df[name].notna().sum() < df["mask"].sum():
                    mask = np.stack(
                        (df["mask"] & df[name].isna()).to_numpy()
                    )
                    metric = np.stack(df[name].to_numpy())
                    metric[mask] = np.apply_along_axis(
                        (lambda x : f(x)[0]), -1, data[mask]
                    )
                    df[name] = metric
                    _log.debug(
                        "Calculated %i of %i items for metric '%s'",
                        np.count_nonzero(mask),
                        df["mask"].sum(),
                        name
                    )
                    
                _log.debug(
                    "Done getting metric '%s'. Approximate time taken: %s",
                    name,
                    str(datetime.timedelta(seconds=(time.monotonic() - t0)))
                    )
                    
            # Update the saved cache if necessary
            # TODO: maybe do this more often, like after every metric calculated?
            names = [*_metrics]
            idx = cachedFeatures[names].isna() & df[names].notna() # TODO: make sure this actually updates vals correctly
            if idx.any(axis=None):
                cachedFeatures[idx] = df[idx]
                cachedFeatures.to_csv(featuresPath, mode="w")
              
            # Clean up the dataframe  
            df = df.drop("data", axis=1)
            if not includeMask:
                df = df.drop("mask", axis=1)
            if not includeDropped:
                for axis in (0, 1):
                    df = df.dropna(axis=axis, how="all")
            
        # Return features for the data and baseline seperately
        return df.loc["data"], df.loc["baseline"]
    
    def trainClassifier(self, features):
        pass
        
        
        