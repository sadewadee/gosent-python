"""Gosent Send API client for Python 3.9+. Standard library only."""

from .client import FailureDetail, Gosent, SendResult
from .core import VERSION as __version__
from .core import GosentError

__all__ = ["Gosent", "GosentError", "SendResult", "FailureDetail", "__version__"]
