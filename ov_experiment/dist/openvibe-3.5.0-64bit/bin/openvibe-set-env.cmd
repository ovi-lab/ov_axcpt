@echo off


SET VRPNROOT=C:\Program Files\openvibe-3.5.0-64bit\dependencies\vrpn

SET PATH=C:\Program Files\openvibe-3.5.0-64bit\dependencies\gtk\bin;%PATH%
SET PATH=%VRPNROOT%\bin;%PATH%
SET PATH=C:\Program Files\openvibe-3.5.0-64bit\dependencies\pthread\lib;%PATH%
SET PATH=C:\Program Files\openvibe-3.5.0-64bit\dependencies\vcredist\;%PATH%

REM Apply user-provided Python2.7 paths if available
IF NOT !PYTHONHOME27!==!EMPTY!  IF NOT !PYTHONPATH27!==!EMPTY! SET REPLACE_PYTHON=true
IF NOT !REPLACE_PYTHON!==!EMPTY! (
  SET "PYTHONHOME=%PYTHONHOME27%"
  SET "PYTHONPATH=%PYTHONPATH27%"
)
