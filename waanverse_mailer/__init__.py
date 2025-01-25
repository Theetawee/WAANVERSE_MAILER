# flake8: noqa
# Copyright 2025 Waanverse Labs Inc. All rights reserved.
import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Final

from .version import __version__

default_app_config = "waanverse_mailer.apps.WaanverseMailerConfig"

# Package metadata
__title__: Final = "waanverse_mailer"
__author__: Final = "Waanverse Labs Inc."
__copyright__: Final = f"Copyright 2025 {__author__}"
__email__: Final = "software@waanverse.com"
__license__: Final = "Proprietary and Confidential"
__description__: Final = (
    "A comprehensive Waanverse Labs Inc. internal package for sending emails"
)
__maintainer__: Final = "Khaotungkulmethee Pattawee Drake"
__maintainer_email__: Final = "tawee@waanverse.com"
__url__: Final = "https://github.com/waanverse/waanverse_mailer"
__status__: Final = "Production"

# ASCII art logo
__logo__: Final = r"""
| |  | |                                          | |         | |        
| |  | | __ _  __ _ _ ____   _____ _ __ ___  ___  | |     __ _| |__  ___ 
| |/\| |/ _` |/ _` | '_ \ \ / / _ \ '__/ __|/ _ \ | |    / _` | '_ \/ __|
\  /\  / (_| | (_| | | | \ V /  __/ |  \__ \  __/ | |___| (_| | |_) \__ \
 \/  \/ \__,_|\__,_|_| |_|\_/ \___|_|  |___/\___| \_____/\__,_|_.__/|___/
"""

# Package version
__version__ = __version__

# Public API exports

__all__ = []
