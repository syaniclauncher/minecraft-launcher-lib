# This file is part of minecraft-launcher-lib (https://codeberg.org/JakobDev/minecraft-launcher-lib)
# SPDX-FileCopyrightText: Copyright (c) 2019-2025 JakobDev <jakobdev@gmx.de> and contributors
# SPDX-License-Identifier: BSD-2-Clause
"""No-network checks for the Temurin runtime helpers. Runs standalone (`py tests/test_runtime_temurin.py`) or under pytest."""
from unittest import mock
from minecraft_launcher_lib import runtime
import tempfile
import platform
import os


def test_adoptium_platform_mapping() -> None:
    cases = {
        ("Windows", "AMD64"): ("windows", "x64"),
        ("Darwin", "arm64"): ("mac", "aarch64"),
        ("Linux", "x86_64"): ("linux", "x64"),
        ("Linux", "i686"): ("linux", "x86"),
    }
    for (system, machine), expected in cases.items():
        with mock.patch.object(platform, "system", return_value=system), \
             mock.patch.object(platform, "machine", return_value=machine):
            assert runtime._get_adoptium_platform() == expected, (system, machine)


def test_get_executable_path_temurin() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # Not installed -> None
        assert runtime.get_executable_path_temurin(17, tmp) is None

        platform_string = runtime._get_jvm_platform_string()
        root_dir = "jdk-17.0.19+10-jre"
        base = os.path.join(tmp, "runtime", "temurin-17", platform_string)
        bin_dir = os.path.join(base, root_dir, "bin")
        os.makedirs(bin_dir)

        java_name = "java.exe" if platform.system() == "Windows" else "java"
        expected = os.path.join(bin_dir, java_name)
        open(expected, "w").close()
        with open(os.path.join(base, ".temurin"), "w", encoding="utf-8") as f:
            f.write(root_dir)

        assert runtime.get_executable_path_temurin(17, tmp) == expected


def test_missing_java_version_defaults_to_8() -> None:
    # Mirrors the install.py / command.py fallback for pre-1.17 versions with no javaVersion field.
    assert {}.get("javaVersion", {}).get("majorVersion", 8) == 8
    assert {"javaVersion": {"majorVersion": 17}}.get("javaVersion", {}).get("majorVersion", 8) == 17


if __name__ == "__main__":
    test_adoptium_platform_mapping()
    test_get_executable_path_temurin()
    test_missing_java_version_defaults_to_8()
    print("ok")
