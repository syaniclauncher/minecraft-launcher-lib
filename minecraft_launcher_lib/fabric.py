# This file is part of minecraft-launcher-lib (https://codeberg.org/JakobDev/minecraft-launcher-lib)
# SPDX-FileCopyrightText: Copyright (c) 2019-2025 JakobDev <jakobdev@gmx.de> and contributors
# SPDX-License-Identifier: BSD-2-Clause
"""
.. warning::
    This module is deprecated and has been replaced by :mod:`~minecraft_launcher_lib.mod_loader`.
    It will no longer receive updates or bug fixes and may be removed in a future release.

fabric contains functions for dealing with the `Fabric modloader <https://fabricmc.net/>`_.
"""
from ._helper import get_requests_response_cache, parse_maven_metadata, check_path_inside_minecraft_directory, empty
from .exceptions import VersionNotFound, UnsupportedVersion
from .types import FabricMinecraftVersion, FabricLoader, CallbackDict
from .install import install_minecraft_version
from .utils import is_version_valid
import warnings
import json
import os


def get_all_minecraft_versions() -> list[FabricMinecraftVersion]:
    """
    Returns all available Minecraft Versions for Fabric

    Example:

    .. code:: python

        for version in minecraft_launcher_lib.fabric.get_all_minecraft_versions():
            print(version["version"])
    """
    warnings.warn("This module is deprecated and has been replaced by mod_loader", DeprecationWarning)
    FABRIC_MINECARFT_VERSIONS_URL = "https://meta.fabricmc.net/v2/versions/game"
    return get_requests_response_cache(FABRIC_MINECARFT_VERSIONS_URL).json()


def get_stable_minecraft_versions() -> list[str]:
    """
    Returns a list which only contains the stable Minecraft versions that supports Fabric

    Example:

    .. code:: python

        for version in minecraft_launcher_lib.fabric.get_stable_minecraft_versions():
            print(version)
    """
    warnings.warn("This module is deprecated and has been replaced by mod_loader", DeprecationWarning)
    minecraft_versions = get_all_minecraft_versions()
    stable_versions = []
    for i in minecraft_versions:
        if i["stable"] is True:
            stable_versions.append(i["version"])
    return stable_versions


def get_latest_minecraft_version() -> str:
    """
    Returns the latest unstable Minecraft versions that supports Fabric. This could be a snapshot.

    Example:

    .. code:: python

        print("Latest Minecraft version: " + minecraft_launcher_lib.fabric.get_latest_minecraft_version())
    """
    warnings.warn("This module is deprecated and has been replaced by mod_loader", DeprecationWarning)
    minecraft_versions = get_all_minecraft_versions()
    return minecraft_versions[0]["version"]


def get_latest_stable_minecraft_version() -> str:
    """
    Returns the latest stable Minecraft version that supports Fabric

    Example:

    .. code:: python

        print("Latest stable Minecraft version: " + minecraft_launcher_lib.fabric.get_latest_stable_minecraft_version())
    """
    warnings.warn("This module is deprecated and has been replaced by mod_loader", DeprecationWarning)
    stable_versions = get_stable_minecraft_versions()
    return stable_versions[0]


def is_minecraft_version_supported(version: str) -> bool:
    """
    Checks if a Minecraft version supported by Fabric

    Example:

    .. code:: python

        version = "1.20"
        if minecraft_launcher_lib.fabric.is_minecraft_version_supported(version):
            print(f"{version} is supported by fabric")
        else:
            print(f"{version} is not supported by fabric")

    :param version: A vanilla version
    """
    warnings.warn("This module is deprecated and has been replaced by mod_loader", DeprecationWarning)
    minecraft_versions = get_all_minecraft_versions()
    for i in minecraft_versions:
        if i["version"] == version:
            return True
    return False


def get_all_loader_versions() -> list[FabricLoader]:
    """
    Returns all loader versions

    Example:

    .. code:: python

        for version in minecraft_launcher_lib.fabric.get_all_loader_versions():
            print(version["version"])
    """
    warnings.warn("This module is deprecated and has been replaced by mod_loader", DeprecationWarning)
    FABRIC_LOADER_VERSIONS_URL = "https://meta.fabricmc.net/v2/versions/loader"
    return get_requests_response_cache(FABRIC_LOADER_VERSIONS_URL).json()


def get_latest_loader_version() -> str:
    """
    Get the latest loader version

    Example:

    .. code:: python

        print("Latest loader version: " + minecraft_launcher_lib.fabric.get_latest_loader_version())
    """
    warnings.warn("This module is deprecated and has been replaced by mod_loader", DeprecationWarning)
    loader_versions = get_all_loader_versions()
    return loader_versions[0]["version"]


def get_latest_installer_version() -> str:
    """
    Returns the latest installer version

    Example:

    .. code:: python

        print("Latest installer version: " + minecraft_launcher_lib.fabric.get_latest_installer_version())
    """
    warnings.warn("This module is deprecated and has been replaced by mod_loader", DeprecationWarning)
    FABRIC_INSTALLER_MAVEN_URL = "https://maven.fabricmc.net/net/fabricmc/fabric-installer/maven-metadata.xml"
    return parse_maven_metadata(FABRIC_INSTALLER_MAVEN_URL)["latest"]


def install_fabric(minecraft_version: str, minecraft_directory: str | os.PathLike, loader_version: str | None = None, callback: CallbackDict | None = None, java: str | os.PathLike | None = None) -> None:
    """
    Installs the Fabric modloader.

    Example:

    .. code:: python

        minecraft_version = "1.20"
        minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
        minecraft_launcher_lib.fabric.install_fabric(minecraft_version, minecraft_directory)

    :param minecraft_version: A vanilla version that is supported by Fabric
    :param minecraft_directory: The path to your Minecraft directory
    :param loader_version: The fabric loader version. If not given it will use the latest
    :param callback: The same dict as for :func:`~minecraft_launcher_lib.install.install_minecraft_version`
    :param java: A Path to a custom Java executable
    :raises VersionNotFound: The given Minecraft does not exists
    :raises UnsupportedVersion: The given Minecraft version is not supported by Fabric
    """
    warnings.warn("This module is deprecated and has been replaced by mod_loader", DeprecationWarning)

    path = str(minecraft_directory)
    if not callback:
        callback = {}

    # Check if the given version exists
    if not is_version_valid(minecraft_version, minecraft_directory):
        raise VersionNotFound(minecraft_version)

    # Check if the given Minecraft version supported
    if not is_minecraft_version_supported(minecraft_version):
        raise UnsupportedVersion(minecraft_version)

    # Get latest loader version if not given
    if not loader_version:
        loader_version = get_latest_loader_version()

    # Make sure the Minecraft version is installed
    install_minecraft_version(minecraft_version, path, callback=callback)

    # Fetch the version profile JSON directly from the meta API
    callback.get("setStatus", empty)("Install fabric")
    fabric_minecraft_version = f"fabric-loader-{loader_version}-{minecraft_version}"
    profile_url = f"https://meta.fabricmc.net/v2/versions/loader/{minecraft_version}/{loader_version}/profile/json"
    data = get_requests_response_cache(profile_url).json()
    data["id"] = fabric_minecraft_version

    version_path = os.path.join(path, "versions", fabric_minecraft_version, f"{fabric_minecraft_version}.json")
    check_path_inside_minecraft_directory(path, version_path)
    os.makedirs(os.path.dirname(version_path), exist_ok=True)
    with open(version_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    # Install all libs of fabric
    install_minecraft_version(fabric_minecraft_version, path, callback=callback)
