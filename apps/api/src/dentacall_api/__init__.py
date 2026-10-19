"""DentaCall API - FastAPI service exposing tools and dashboard APIs."""

from dentacall_api.main import app, create_app
from dentacall_api.tools.definitions import get_tool_definitions

__version__ = "0.1.0"

__all__ = ["app", "create_app", "get_tool_definitions", "__version__"]
