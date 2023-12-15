import glob
import logging
import os
from typing import Any

import yaml

_log = logging.Logger(__name__)

# TODO: clean up, change to inherit from base config and to use gradcpt implementation

class _Config:
    def __init__(self) -> None:
        # Get the path to the project root directory by searching for the
        # "closest" parent directory that contains a .gitignore file
        root = os.path.dirname(os.path.abspath(__file__))
        target = ".gitignore"
        while len(glob.glob(target, root_dir=root)) == 0:
            # Check if the system root has been reached
            if len(os.path.basename(root)) == 0:
                raise Exception(
                    "Could not find project root directory on path "
                    + os.path.abspath(__file__)
                )
            else:
                root = os.path.dirname(root)
        self.__root = root
        
        # Specfiy the path to the default config, stored in the same directory
        # as this file
        dirPath = os.path.relpath(os.path.dirname(__file__), start=self.__root)
        self.__defaultConfig = os.path.join(dirPath, "default_config.yaml")
        
        # Read the list of config paths to check from the default config.
        # Values specified in config files later in the list will overwrite
        # corresponding values in config files earlier in the list. Changes to
        # this list in the default config file made after initializing this
        # object are not reflected.
        with open(os.path.join(self.__root, self.__defaultConfig), "r") as f:
            contents = yaml.load(f, Loader=yaml.FullLoader)
            self.PATH = contents["PATH"] if contents is not None else []
            if isinstance(self.PATH, str):
                self.PATH = [self.PATH]
    
    def __getConfig(self) -> dict[str: Any]:
        config = {}
        for k, configPath in enumerate((self.__defaultConfig, *self.PATH)):
            fullConfigPath = os.path.abspath(
                os.path.join(self.__root, configPath)
            )
            try:
                f = open(fullConfigPath, 'rt')
            except FileNotFoundError as E:
                if k == 0:
                    errmsg = (
                        "Could not read from default config file: " + 
                        f"{fullConfigPath}"
                    )
                    raise RuntimeError(errmsg) from E
                else:
                    _log.warn(
                        "Config file at following location could not be " +
                        "read, continuing execution: %s", fullConfigPath
                    )
            else:
                _log.debug("Loading config file: %s", fullConfigPath)
                contents = yaml.safe_load(f)
                if contents is not None:
                    config.update(contents)
            finally:
                f.close()
                
        config["root"] = self.__root
        return config

    def __getattr__(self, name):
        # PATH is both a attribute of this class and a value in the config.
        # Users must only interact with the attribute, so this method must not
        # be called with name="PATH". Calling `self.PATH` is the itended way of
        # accessing PATH and internally will not call this method. 
        if name == "PATH":
            raise ValueError(
                "`name` must not be 'PATH'. Use `self.PATH` instead."
            )
        
        try:
            val = self.__getConfig()[name]
        except KeyError as E:
            raise AttributeError(name) from E
        else:
            return val
    
    def attrNames(self) -> list[str]:
        c = self.__getConfig()
        c["PATH"] = self.PATH
        return list(c.keys())
    
    def __str__(self):
        c = self.__getConfig()
        c["PATH"] = self.PATH
        return str(c)
    
    def snapshot(self) -> dict[str, Any]:
        return self.__getConfig()
    
CONFIG = _Config()

# Temporarily adds the specified config file to CONFIG's path. Behaviour is
# undefined if CONFIG.PATH already contains the specified config file, or if it
# added/removed while in this context manager
class TempConfig:
    # TODO: make safe to add the same temp config multiple times
    def __init__(self, path):
        self._path = path
    
    def __enter__(self):
        CONFIG.PATH.append(self._path)
    
    def __exit__(self, exc_type, exc_value, exc_tb):
        CONFIG.PATH.remove(self._path)