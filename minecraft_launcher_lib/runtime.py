# This file is part of minecraft-launcher-lib (https://codeberg.org/JakobDev/minecraft-launcher-lib)
# SPDX-FileCopyrightText: Copyright (c) 2019-2025 JakobDev <jakobdev@gmx.de> and contributors
# SPDX-License-Identifier: BSD-2-Clause
"runtime allows to install the java runtime. This module is used by :func:`~minecraft_launcher_lib.install.install_minecraft_version`, so you don't need to use it in your code most of the time."
import asyncio
import aiohttp
from ._helper import get_user_agent, download_file, empty, get_sha1_hash, check_path_inside_minecraft_directory, get_client_json, create_download_session, _download_file_aiohttp, _should_use_async_download_backend
from ._internal_types.runtime_types import RuntimeListJson, PlatformManifestJson, _PlatformManifestJsonFile
from .types import CallbackDict, JvmRuntimeInformation, VersionRuntimeInformation
from .exceptions import VersionNotFound, PlatformNotSupported, InvalidChecksum
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import as_completed
import subprocess
import datetime
import requests
import platform
import hashlib
import tarfile
import zipfile
import os

_JVM_MANIFEST_URL = "https://launchermeta.mojang.com/v1/products/java-runtime/2ec0cc96c44e5a76b9c8b7c39df7210883d12871/all.json"
_ADOPTIUM_ASSETS_URL = "https://api.adoptium.net/v3/assets/latest/{major}/hotspot"


def _get_jvm_platform_string() -> str:
    """
    Get the name that is used the identify the platform
    """
    match platform.system():
        case "Windows":
            if platform.architecture()[0] == "32bit":
                return "windows-x86"
            else:
                return "windows-x64"
        case "Linux":
            if platform.architecture()[0] == "32bit":
                return "linux-i386"
            else:
                return "linux"
        case "Darwin":
            if platform.machine() == "arm64":
                return "mac-os-arm64"
            else:
                return "mac-os"
        case _:
            return "gamecore"


def get_jvm_runtimes() -> list[str]:
    """
    Returns a list of all jvm runtimes

    Example:

    .. code:: python

        for runtime in minecraft_launcher_lib.runtime.get_jvm_runtimes():
            print(runtime)
    """
    manifest_data: RuntimeListJson = requests.get(_JVM_MANIFEST_URL, headers={"user-agent": get_user_agent()}).json()
    jvm_list = []
    for key in manifest_data[_get_jvm_platform_string()].keys():
        jvm_list.append(key)
    return jvm_list


def get_installed_jvm_runtimes(minecraft_directory: str | os.PathLike) -> list[str]:
    """
    Returns a list of all installed jvm runtimes

    Example:

    .. code:: python

        for runtime in minecraft_launcher_lib.runtime.get_installed_jvm_runtimes():
            print(runtime)

    :param minecraft_directory: The path to your Minecraft directory
    """
    try:
        return os.listdir(os.path.join(minecraft_directory, "runtime"))
    except FileNotFoundError:
        return []


def _get_adoptium_platform() -> tuple[str, str]:
    """Return (os, architecture) as the Adoptium API identifies this machine."""
    match platform.system():
        case "Windows":
            os_name = "windows"
        case "Linux":
            os_name = "linux"
        case "Darwin":
            os_name = "mac"
        case _:
            os_name = "linux"

    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64", "x64"):
        arch = "x64"
    elif machine in ("aarch64", "arm64"):
        arch = "aarch64"
    elif machine in ("i386", "i686", "x86"):
        arch = "x86"
    elif machine.startswith("arm"):
        arch = "arm"
    else:
        arch = "x64"  # ponytail: sane default; add mapping if a new arch shows up
    return os_name, arch


def _sha256_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _extract_runtime_archive(archive_path: str, dest: str, minecraft_directory: str | os.PathLike, is_zip: bool) -> str:
    """Extract a Temurin archive into dest, guarding every member against path traversal. Returns the single top-level directory name."""
    tops: set[str] = set()
    if is_zip:
        with zipfile.ZipFile(archive_path) as zf:
            for name in zf.namelist():
                check_path_inside_minecraft_directory(minecraft_directory, os.path.join(dest, name))
                top = name.split("/", 1)[0]
                if top:
                    tops.add(top)
            zf.extractall(dest)
    else:
        with tarfile.open(archive_path, "r:gz") as tf:
            for member in tf.getmembers():
                check_path_inside_minecraft_directory(minecraft_directory, os.path.join(dest, member.name))
                top = member.name.split("/", 1)[0]
                if top:
                    tops.add(top)
            tf.extractall(dest)  # ponytail: manual per-member guard above covers <3.12 (no filter='data')

    # Temurin archives always have exactly one top-level dir (e.g. jdk-17.0.19+10-jre)
    assert len(tops) == 1, f"unexpected Temurin archive layout: {tops}"
    return tops.pop()


def install_jvm_runtime_temurin(
        major_version: int,
        minecraft_directory: str | os.PathLike,
        callback: CallbackDict | None = None) -> None:
    """
    Installs a Temurin (Eclipse Adoptium) JRE for the given Java major version.

    This is the Temurin equivalent of :func:`install_jvm_runtime` and is keyed by Java major
    version (e.g. ``17``) rather than by Mojang's runtime component name.

    Example:

    .. code:: python

        minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
        minecraft_launcher_lib.runtime.install_jvm_runtime_temurin(17, minecraft_directory)

    :param major_version: The Java major version (e.g. 8, 17, 21)
    :param minecraft_directory: The path to your Minecraft directory
    :param callback: the same dict as for :func:`~minecraft_launcher_lib.install.install_minecraft_version`
    :raises VersionNotFound: No Temurin JRE is available for this version/platform
    :raises FileOutsideMinecraftDirectory: A File should be placed outside the given Minecraft directory
    """
    if callback is None:
        callback = {}

    os_name, arch = _get_adoptium_platform()
    callback.get("setStatus", empty)(f"Fetching Temurin JRE {major_version}")
    response = requests.get(
        _ADOPTIUM_ASSETS_URL.format(major=major_version),
        params={"os": os_name, "architecture": arch, "image_type": "jre"},
        headers={"user-agent": get_user_agent()},
    )
    assets = response.json()
    if not assets:
        raise VersionNotFound(f"temurin-{major_version}")

    package = assets[0]["binary"]["package"]
    platform_string = _get_jvm_platform_string()
    base_path = os.path.join(minecraft_directory, "runtime", f"temurin-{major_version}", platform_string)
    is_zip = package["name"].endswith(".zip")
    archive_path = os.path.join(base_path, "_temurin.zip" if is_zip else "_temurin.tar.gz")
    check_path_inside_minecraft_directory(minecraft_directory, archive_path)

    # sha1=None + overwrite=True: always fetch fresh, then verify the SHA-256 Adoptium gives us
    download_file(package["link"], archive_path, callback=callback, minecraft_directory=minecraft_directory, overwrite=True)
    checksum = _sha256_hash(archive_path)
    if checksum != package["checksum"]:
        os.remove(archive_path)
        raise InvalidChecksum(package["link"], archive_path, package["checksum"], checksum)

    callback.get("setStatus", empty)(f"Extracting Temurin JRE {major_version}")
    root_dir = _extract_runtime_archive(archive_path, base_path, minecraft_directory, is_zip)
    os.remove(archive_path)

    marker_path = os.path.join(base_path, ".temurin")
    check_path_inside_minecraft_directory(minecraft_directory, marker_path)
    with open(marker_path, "w", encoding="utf-8") as f:
        f.write(root_dir)


def get_executable_path_temurin(major_version: int, minecraft_directory: str | os.PathLike) -> str | None:
    """
    Returns the path to the java executable of a Temurin JRE installed by :func:`install_jvm_runtime_temurin`. Returns None if none is found.

    :param major_version: The Java major version (e.g. 17)
    :param minecraft_directory: The path to your Minecraft directory
    """
    base_path = os.path.join(minecraft_directory, "runtime", f"temurin-{major_version}", _get_jvm_platform_string())
    try:
        with open(os.path.join(base_path, ".temurin"), encoding="utf-8") as f:
            root_dir = f.read().strip()
    except FileNotFoundError:
        return None

    for java_path in (
        os.path.join(base_path, root_dir, "bin", "java"),                          # Linux / Windows (+ .exe below)
        os.path.join(base_path, root_dir, "Contents", "Home", "bin", "java"),      # macOS
    ):
        if os.path.isfile(java_path):
            return java_path
        elif os.path.isfile(java_path + ".exe"):
            return java_path + ".exe"
    return None


''' 

replaced by Temurin (install_jvm_runtime_temurin / get_executable_path_temurin). Old Mojang runtime install kept for reference.

def install_jvm_runtime(
        jvm_version: str,
        minecraft_directory: str | os.PathLike,
        callback: CallbackDict | None = None,
        max_workers: int | None = None) -> None:
    """
    Installs the given jvm runtime. callback is the same dict as in the install module.

    Example:

    .. code:: python

        runtime_version = "java-runtime-gamma"
        minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
        minecraft_launcher_lib.runtime.install_jvm_runtime(runtime_version, minecraft_directory)

    :param jvm_version: The Name of the JVM version
    :param minecraft_directory: The path to your Minecraft directory
    :param callback: the same dict as for :func:`~minecraft_launcher_lib.install.install_minecraft_version`
    :param max_workers: number of workers for asynchronous downloads. If None, max_workers will be set automatically.
    :raises VersionNotFound: The given JVM Version was not found
    :raises FileOutsideMinecraftDirectory: A File should be placed outside the given Minecraft directory
    """
    if callback is None:
        callback = {}

    if _should_use_async_download_backend():
        asyncio.run(_install_jvm_runtime_async(jvm_version, minecraft_directory, callback, max_workers))
        return

    manifest_data: RuntimeListJson = requests.get(_JVM_MANIFEST_URL, headers={"user-agent": get_user_agent()}).json()
    platform_string = _get_jvm_platform_string()
    # Check if the jvm version exists
    if jvm_version not in manifest_data[platform_string]:
        raise VersionNotFound(jvm_version)
    # Check if there is a platform manifest
    if len(manifest_data[platform_string][jvm_version]) == 0:
        return
    platform_manifest: PlatformManifestJson = requests.get(manifest_data[platform_string][jvm_version][0]["manifest"]["url"], headers={"user-agent": get_user_agent()}).json()
    base_path = os.path.join(minecraft_directory, "runtime", jvm_version, platform_string, jvm_version)
    worker_count = max_workers if max_workers is not None else min(32, (os.cpu_count() or 1) + 4)
    session = create_download_session(worker_count)
    file_list: list[str] = []

    def install_runtime_file(key: str, value: _PlatformManifestJsonFile) -> None:
        """Install the single runtime file."""
        current_path = os.path.join(base_path, key)
        check_path_inside_minecraft_directory(minecraft_directory, current_path)

        if value["type"] == "file":
            # Prefer downloading the compresses file
            if "lzma" in value["downloads"]:
                download_file(value["downloads"]["lzma"]["url"], current_path, sha1=value["downloads"]["raw"]["sha1"], callback=callback, lzma_compressed=True, session=session)
            else:
                download_file(value["downloads"]["raw"]["url"], current_path, sha1=value["downloads"]["raw"]["sha1"], callback=callback, session=session)

            # Make files executable on unix systems
            if value["executable"]:
                try:
                    subprocess.run(["chmod", "+x", current_path])
                except FileNotFoundError:
                    pass
            file_list.append(key)

        elif value["type"] == "directory":
            try:
                os.makedirs(current_path)
            except Exception:
                pass

        elif value["type"] == "link":
            check_path_inside_minecraft_directory(minecraft_directory, os.path.join(base_path, value["target"]))
            os.makedirs(os.path.dirname(current_path), exist_ok=True)

            try:
                os.symlink(value["target"], current_path)
            except Exception:
                pass

    # Download all files of the runtime
    callback.get("setMax", empty)(len(platform_manifest["files"]) - 1)
    count = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(install_runtime_file, key, value)
            for key, value in platform_manifest["files"].items()
        ]
        for future in as_completed(futures):
            future.result()
            count += 1
            callback.get("setProgress", empty)(count)


async def _install_jvm_runtime_async(
        jvm_version: str,
        minecraft_directory: str | os.PathLike,
        callback: CallbackDict | None = None,
        max_workers: int | None = None) -> None:
    """
    Async runtime installer using aiohttp.
    """
    if callback is None:
        callback = {}

    manifest_data: RuntimeListJson = requests.get(_JVM_MANIFEST_URL, headers={"user-agent": get_user_agent()}).json()
    platform_string = _get_jvm_platform_string()
    if jvm_version not in manifest_data[platform_string]:
        raise VersionNotFound(jvm_version)
    if len(manifest_data[platform_string][jvm_version]) == 0:
        return

    platform_manifest: PlatformManifestJson = requests.get(manifest_data[platform_string][jvm_version][0]["manifest"]["url"], headers={"user-agent": get_user_agent()}).json()
    base_path = os.path.join(minecraft_directory, "runtime", jvm_version, platform_string, jvm_version)
    worker_count = max_workers if max_workers is not None else min(32, (os.cpu_count() or 1) + 4)
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=30, sock_read=30)
    connector = aiohttp.TCPConnector(limit=worker_count, limit_per_host=worker_count, ttl_dns_cache=300)
    session = aiohttp.ClientSession(headers={"user-agent": get_user_agent()}, timeout=timeout, connector=connector)
    file_list: list[str] = []

    async def install_runtime_file(key: str, value: _PlatformManifestJsonFile) -> None:
        current_path = os.path.join(base_path, key)
        check_path_inside_minecraft_directory(minecraft_directory, current_path)

        if value["type"] == "file":
            if "lzma" in value["downloads"]:
                await _download_file_aiohttp(value["downloads"]["lzma"]["url"], current_path, sha1=value["downloads"]["raw"]["sha1"], callback=callback, lzma_compressed=True, session=session)
            else:
                await _download_file_aiohttp(value["downloads"]["raw"]["url"], current_path, sha1=value["downloads"]["raw"]["sha1"], callback=callback, session=session)

            if value["executable"]:
                try:
                    subprocess.run(["chmod", "+x", current_path])
                except FileNotFoundError:
                    pass
            file_list.append(key)

        elif value["type"] == "directory":
            try:
                os.makedirs(current_path)
            except Exception:
                pass

        elif value["type"] == "link":
            check_path_inside_minecraft_directory(minecraft_directory, os.path.join(base_path, value["target"]))
            os.makedirs(os.path.dirname(current_path), exist_ok=True)
            try:
                os.symlink(value["target"], current_path)
            except Exception:
                pass

    callback.get("setMax", empty)(len(platform_manifest["files"]) - 1)
    count = 0
    try:
        tasks = [asyncio.create_task(install_runtime_file(key, value)) for key, value in platform_manifest["files"].items()]
        for future in asyncio.as_completed(tasks):
            await future
            count += 1
            callback.get("setProgress", empty)(count)
    finally:
        await session.close()

    version_path = os.path.join(minecraft_directory, "runtime", jvm_version, platform_string, ".version")
    check_path_inside_minecraft_directory(minecraft_directory, version_path)
    with open(version_path, "w", encoding="utf-8") as f:
        f.write(manifest_data[platform_string][jvm_version][0]["version"]["name"])

    sha1_path = os.path.join(minecraft_directory, "runtime", jvm_version, platform_string, f"{jvm_version}.sha1")
    check_path_inside_minecraft_directory(minecraft_directory, sha1_path)
    with open(sha1_path, "w", encoding="utf-8") as f:
        for current_file in file_list:
            current_path = os.path.join(base_path, current_file)
            ctime = os.stat(current_path).st_ctime_ns
            sha1 = get_sha1_hash(current_path)
            f.write(f"{current_file} /#// {sha1} {ctime}\n")


def get_executable_path(jvm_version: str, minecraft_directory: str | os.PathLike) -> str | None:
    """
    Returns the path to the executable. Returns None if none is found.

    Example:

    .. code:: python

        runtime_version = "java-runtime-gamma"
        minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
        executable_path = minecraft_launcher_lib.runtime.get_executable_path(runtime_version, minecraft_directory)
        if executable_path is not None:
            print(f"Executable path: {executable_path}")
        else:
            print("The executable path was not found")

    :param jvm_version: The Name of the JVM version
    :param minecraft_directory: The path to your Minecraft directory
    """
    java_path = os.path.join(minecraft_directory, "runtime", jvm_version, _get_jvm_platform_string(), jvm_version, "bin", "java")
    if os.path.isfile(java_path):
        return java_path
    elif os.path.isfile(java_path + ".exe"):
        return java_path + ".exe"
    java_path = java_path.replace(os.path.join("bin", "java"), os.path.join("jre.bundle", "Contents", "Home", "bin", "java"))
    if os.path.isfile(java_path):
        return java_path
    else:
        return None
'''  # end Mojang runtime reference block


def get_jvm_runtime_information(jvm_version: str) -> JvmRuntimeInformation:
    """
    Returns some Information about a JVM Version

    Example:

    .. code:: python

        runtime_version = "java-runtime-gamma"
        information = minecraft_launcher_lib.runtime.get_jvm_runtime_information(runtime_version)
        print("Java version: " + information["name"])
        print("Release date: " + information["released"].isoformat())

    :param jvm_version: A JVM Version
    :raises VersionNotFound: The given JVM Version was not found
    :raises VersionNotFound: The given JVM Version is not available on this Platform
    :return: A Dict with Information
    """
    manifest_data: RuntimeListJson = requests.get(_JVM_MANIFEST_URL, headers={"user-agent": get_user_agent()}).json()
    platform_string = _get_jvm_platform_string()

    # Check if the jvm version exists
    if jvm_version not in manifest_data[platform_string]:
        raise VersionNotFound(jvm_version)

    if len(manifest_data[platform_string][jvm_version]) == 0:
        raise PlatformNotSupported()

    return {
        "name": manifest_data[platform_string][jvm_version][0]["version"]["name"],
        "released": datetime.datetime.fromisoformat(manifest_data[platform_string][jvm_version][0]["version"]["released"])
    }


def get_version_runtime_information(version: str, minecraft_directory: str | os.PathLike) -> VersionRuntimeInformation | None:
    """
    Returns information about the runtime used by a version

    Example:

    .. code:: python

        minecraft_version = "1.20"
        minecraft_directory = minecraft_launcher_lib.utils.get_minecraft_directory()
        information = minecraft_launcher_lib.runtime.get_version_runtime_information(minecraft_version, minecraft_directory)
        print("Name: " + information["name"])
        print("Java version: " + str(information["javaMajorVersion"]))

    :param minecraft_directory: The path to your Minecraft directory
    :raises VersionNotFound: The Minecraft version was not found
    :return: A Dict with Information. None if the version has no runtime information.
    """
    data = get_client_json(version, minecraft_directory)

    if "javaVersion" not in data:
        return None

    return {
        "name": data["javaVersion"]["component"],
        "javaMajorVersion": data["javaVersion"]["majorVersion"]
    }
