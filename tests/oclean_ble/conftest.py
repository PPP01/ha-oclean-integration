"""Put the HA-free oclean_ble modules on sys.path for standalone unit tests.

The custom component's program_utils.py has zero Home Assistant imports, so it
can be imported and tested with plain pytest (this dev shell has no
`homeassistant` package). This conftest makes `import program_utils` resolve to
custom_components/oclean_ble/program_utils.py.

Some HA-free modules (e.g. parser.py) use *relative* imports (``from .const
import ...``) and therefore need a real parent package. Importing the actual
``custom_components/oclean_ble/__init__.py`` is not an option here because it
pulls in Home Assistant. Instead we register a *synthetic* ``oclean_ble``
package that points ``__path__`` at the component directory but skips the real
package ``__init__``. That lets ``from oclean_ble.parser import ...`` resolve
``from .const import ...`` to ``oclean_ble.const`` (both HA-free) without ever
executing the HA-importing package init.
"""

import pathlib
import sys
import types

_OCLEAN_DIR = pathlib.Path(__file__).resolve().parents[2] / "custom_components" / "oclean_ble"
sys.path.insert(0, str(_OCLEAN_DIR))

# Synthetic parent package for relative-import HA-free modules (parser.py, ...).
if "oclean_ble" not in sys.modules:
    _pkg = types.ModuleType("oclean_ble")
    _pkg.__path__ = [str(_OCLEAN_DIR)]  # namespace-style: only HA-free submodules
    sys.modules["oclean_ble"] = _pkg
