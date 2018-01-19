# Copyright (c) 2015-2018 Patricio Cubillos and contributors.
# MC3 is open-source software under the MIT license (see LICENSE).

__all__ = ["binrms", "prayer"]

import sys, os
import os

from .prayer import prayer

sys.path.append(os.path.dirname(os.path.realpath(__file__)) + "/../lib")
from timeavg import binrms

# Clean up top-level namespace--delete everything that isn't in __all__
# or is a magic attribute, and that isn't a submodule of this package
for varname in dir():
    if not ((varname.startswith('__') and varname.endswith('__')) or
            varname in __all__ ):
        del locals()[varname]
del(varname)
