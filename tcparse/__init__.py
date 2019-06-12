from ._version import get_versions
from .parse import load_project, TWINCAT_TYPES

__version__ = get_versions()['version']
del get_versions

globals().update(TWINCAT_TYPES)

__all__ = ['__version__', 'load_project']
__all__ += list(TWINCAT_TYPES)
