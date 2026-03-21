import inspect
import os
import sys
from typing import get_type_hints


sys.path.insert(0, os.path.join(os.getcwd(), "src"))

from code_index_mcp.server import search_code_advanced


def test_search_code_advanced_regex_parameter_allows_none():
    signature = inspect.signature(search_code_advanced)
    regex_param = signature.parameters['regex']
    type_hints = get_type_hints(search_code_advanced)

    assert regex_param.default is None
    assert type_hints['regex'] == bool | None
