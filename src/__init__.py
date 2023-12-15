import logging as _logging

if not _logging.getLogger(__name__).hasHandlers():
    _logger = _logging.getLogger(__name__)
    _handler = _logging.StreamHandler()
    _formatter = _logging.Formatter(
        "%(levelname)-8s :: %(name)-16s :: %(message)-s"
        )
    
    _logger.setLevel(_logging.DEBUG)
    _handler.setLevel(_logging.DEBUG)
    _handler.setFormatter(_formatter)
    _logger.addHandler(_handler)
    