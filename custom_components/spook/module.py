"""Spook module helpers."""

from pathlib import Path


def python_module_path(module_file: Path) -> str:
    """Return the Python module path for a Spook module file.
    
    Converts a filesystem path to a Python module import path in a way that works
    correctly on all platforms (Windows, Linux, macOS). Special handling for 
    __init__.py files, which represent packages rather than modules.
    
    Examples:
        ectoplasms/alert/__init__.py -> ectoplasms.alert
        ectoplasms/foo/services/bar.py -> ectoplasms.foo.services.bar
    
    Args:
        module_file: The filesystem path to a module or package.
        
    Returns:
        The Python module path as a dotted string.
    """
    relative_path = module_file.relative_to(Path(__file__).parent)
    if relative_path.name == "__init__.py":
        relative_path = relative_path.parent
    else:
        relative_path = relative_path.with_suffix("")

    return ".".join(relative_path.parts)
