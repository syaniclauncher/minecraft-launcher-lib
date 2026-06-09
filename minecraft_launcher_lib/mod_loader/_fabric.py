# This file is part of minecraft-launcher-lib (https://codeberg.org/JakobDev/minecraft-launcher-lib)
# SPDX-FileCopyrightText: Copyright (c) 2019-2025 JakobDev <jakobdev@gmx.de> and contributors
# SPDX-License-Identifier: BSD-2-Clause
from .._helper import get_requests_response_cache, check_path_inside_minecraft_directory, empty
from ._fabric_quilt_base import FabricQuiltBase
from ..types import CallbackDict
import json
import os


class Fabric(FabricQuiltBase):
    "Implements the mod loader class for Fabric"
    def __init__(self) -> None:
        super().__init__()

        self._maven_url = "https://maven.fabricmc.net/net/fabricmc/fabric-installer"
        self._game_url = "https://meta.fabricmc.net/v2/versions/game"
        self._loader_url = "https://meta.fabricmc.net/v2/versions/loader"
        self._loader_name = "fabric"

    def get_id(self) -> str:
        "Implements get_id() for Fabric"
        return "fabric"

    def get_name(self) -> str:
        "Implements get_name() for Fabric"
        return "Fabric"

    def install(self, minecraft_version: str, minecraft_directory: str, callback: CallbackDict, java: str, loader_version: str) -> None:
        "Implements install() for Fabric using the meta API"
        callback.get("setStatus", empty)("Install fabric")

        # The meta API serves the same version profile JSON that the installer would write
        data = get_requests_response_cache(self.get_profile_url(minecraft_version, loader_version)).json()

        installed_version = self.get_installed_version(minecraft_version, loader_version)
        data["id"] = installed_version

        version_path = os.path.join(minecraft_directory, "versions", installed_version, f"{installed_version}.json")
        check_path_inside_minecraft_directory(minecraft_directory, version_path)

        os.makedirs(os.path.dirname(version_path), exist_ok=True)
        with open(version_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
