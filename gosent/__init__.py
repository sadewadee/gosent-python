"""Gosent Send API client for Python 3.9+. Standard library only."""

from .client import FailureDetail, Gosent, SendResult
from .core import GosentError

__version__ = "0.1.0"

__all__ = ["Gosent", "GosentError", "SendResult", "FailureDetail", "__version__"]
