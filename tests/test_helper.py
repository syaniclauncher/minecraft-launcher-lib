# This file is part of minecraft-launcher-lib (https://codeberg.org/JakobDev/minecraft-launcher-lib)
# SPDX-FileCopyrightText: Copyright (c) 2019-2025 JakobDev <jakobdev@gmx.de> and contributors
# SPDX-License-Identifier: BSD-2-Clause
import minecraft_launcher_lib._helper as helper
import requests_mock
import pathlib
import pytest


def test_download_file_falls_back_to_requests_inside_running_loop(monkeypatch: pytest.MonkeyPatch, requests_mock: requests_mock.Mocker, tmp_path: pathlib.Path) -> None:
    monkeypatch.delenv("MINECRAFT_LAUNCHER_LIB_DOWNLOAD_BACKEND", raising=False)
    monkeypatch.setattr(helper.asyncio, "get_running_loop", lambda: object())

    def fail_if_called(*args, **kwargs):
        pytest.fail("async downloader should not be used from a running loop")

    monkeypatch.setattr(helper, "_download_file_aiohttp", fail_if_called)
    requests_mock.get("minecraft-launcher-lib-test://text.txt", text="Hello World")

    target = tmp_path / "download.txt"
    assert helper.download_file("minecraft-launcher-lib-test://text.txt", str(target)) is True
    assert target.read_text(encoding="utf-8") == "Hello World"
