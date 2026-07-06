from __future__ import annotations

import os
import pathlib

import minecraft_launcher_lib


def _create_callback() -> dict[str, object]:
    progress = {"value": 0, "maximum": 0}

    def set_status(text: str) -> None:
        print(text)

    def set_progress(value: int) -> None:
        progress["value"] = value
        maximum = progress["maximum"]
        if maximum:
            print(f"Progress: {value}/{maximum}")
        else:
            print(f"Progress: {value}")

    def set_max(value: int) -> None:
        progress["maximum"] = max(value, 0)
        print(f"Total steps: {progress['maximum']}")

    return {
        "setStatus": set_status,
        "setProgress": set_progress,
        "setMax": set_max,
    }


def _prompt_path(prompt: str, default: pathlib.Path | None = None, allow_empty: bool = False) -> pathlib.Path | None:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if not value:
            if default is not None:
                return default.resolve()
            if allow_empty:
                return None
            print("A value is required.")
            continue

        # Windows terminals often paste paths wrapped in quotes.
        value = value.strip("\"'")
        try:
            return pathlib.Path(value).expanduser().resolve()
        except OSError as exc:
            print(f"Invalid path: {exc}")


def _prompt_existing_file(prompt: str) -> pathlib.Path:
    while True:
        path = _prompt_path(prompt)
        assert path is not None
        if path.is_file():
            return path
        print("Please enter a path to an existing file.")


def main() -> None:
    print("mrpack installer")
    print("Run this as: py -m tests.test_mrpack_install")

    mrpack_path = _prompt_existing_file("Mrpack path")
    install_directory = _prompt_path("Install directory")

    assert mrpack_path is not None
    assert install_directory is not None

    os.makedirs(install_directory, exist_ok=True)

    minecraft_launcher_lib.mrpack.install_mrpack(
        mrpack_path,
        install_directory,
        modpack_directory=install_directory,
        callback=_create_callback(),
        mrpack_install_options={"skipDependenciesInstall": True},
    )

    print("Mrpack installation complete")
    print(f"Installed to: {install_directory}")
    print("Game dependency installation was skipped")


if __name__ == "__main__":
    main()
