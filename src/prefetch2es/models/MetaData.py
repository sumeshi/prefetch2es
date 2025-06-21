# coding: utf-8
from importlib.metadata import version, PackageNotFoundError


def get_version(name: str = "prefetch2es") -> str:
    """Get package version.

    Args:
        name (str): Package name. Defaults to "prefetch2es".

    Returns:
        str: Package version or empty string if not found.
    """
    try:
        return version(name)
    except PackageNotFoundError:
        return ""
