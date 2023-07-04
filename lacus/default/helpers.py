import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, Union

from lacus.default import env_global_name
from lacus.default.exceptions import ConfigError, CreateDirectoryException, MissingEnv

configs: Dict[str, Dict[str, Any]] = {}
logger = logging.getLogger("Helpers")


@lru_cache(64)
def get_homedir() -> Path:
    """Get the home directory path.

    Returns
    -------
        Path: The path to the home directory.

    Raises
    ------
        MissingEnv: If the environment variable is missing.
    """
    if not os.environ.get(env_global_name):
        # Try to open a .env file in the home directory if it exists.
        if (Path(__file__).resolve().parent.parent.parent / ".env").exists():
            with (Path(__file__).resolve().parent.parent.parent / ".env").open() as f:
                for line in f:
                    key, value = line.strip().split("=", 1)
                    if value[0] in ['"', "'"]:
                        value = value[1:-1]
                    os.environ[key] = value

    if not os.environ.get(env_global_name):
        guessed_home = Path(__file__).resolve().parent.parent.parent
        raise MissingEnv(
            f"{env_global_name} is missing. \
Run the following command (assuming you run the code from the clonned repository):\
    export {env_global_name}='{guessed_home}'"
        )
    return Path(os.environ[env_global_name])


@lru_cache(64)
def load_configs(path_to_config_files: Optional[Union[str, Path]] = None):
    """Load the configuration files.

    Args:
        path_to_config_files (Union[str, Path], optional): Path to the configuration files. Defaults to None.

    Raises
    ------
        ConfigError: If the configuration directory is not found or is not a directory.
    """
    global configs
    if configs:
        return
    if path_to_config_files:
        if isinstance(path_to_config_files, str):
            config_path = Path(path_to_config_files)
        else:
            config_path = path_to_config_files
    else:
        config_path = get_homedir() / "config"
    if not config_path.exists():
        raise ConfigError(f"Configuration directory {config_path} does not exists.")
    elif not config_path.is_dir():
        raise ConfigError(f"Configuration directory {config_path} is not a directory.")

    configs = {}
    for path in config_path.glob("*.json"):
        with path.open() as _c:
            configs[path.stem] = json.load(_c)


@lru_cache(64)
def get_config(config_type: str, entry: Optional[str] = None, quiet: bool = False) -> Any:
    """Get a specific entry from the configuration file.

    Args:
        config_type (str): The type of configuration file.
        entry (str, optional): The specific entry to retrieve. Defaults to None.
        quiet (bool, optional): Whether to suppress warnings. Defaults to False.

    Returns
    -------
        Any: The value of the specified entry.

    Raises
    ------
        ConfigError: If the configuration file is not found.
    """
    global configs
    if not configs:
        load_configs()
    if config_type in configs:
        if entry:
            if entry in configs[config_type]:
                return configs[config_type][entry]
            else:
                if not quiet:
                    logger.warning(f"Unable to find {entry} in config file.")
        else:
            return configs[config_type]
    else:
        if not quiet:
            logger.warning(f"No {config_type} config file available.")
    if not quiet:
        logger.warning(
            f"Falling back on sample config, please initialize the {config_type} config file."
        )
    with (get_homedir() / "config" / f"{config_type}.json.sample").open() as _c:
        sample_config = json.load(_c)
    if entry:
        return sample_config[entry]
    return sample_config


def safe_create_dir(to_create: Path) -> None:
    """Safely create a directory.

    Args:
    to_create (Path): The path of the directory to create.

    Raises
    ------
    CreateDirectoryException: If the path already exists and is not a directory.
    """
    if to_create.exists() and not to_create.is_dir():
        raise CreateDirectoryException(
            f"The path {to_create} already exists and is not a directory"
        )
    to_create.mkdir(parents=True, exist_ok=True)


def get_socket_path(name: str) -> str:
    """Get the path to a specific socket.

    Args:
        name (str): The name of the socket.

    Returns
    -------
        str: The path to the socket.
    """
    mapping = {"cache": Path("cache", "cache.sock")}
    return str(get_homedir() / mapping[name])


def try_make_file(filename: Path):
    """Try to create a file if it doesn't exist.

    Args:
        filename (Path): The path to the file.

    Returns
    -------
        bool: True if the file is successfully created, False if it already exists.
    """
    try:
        filename.touch(exist_ok=False)
        return True
    except FileExistsError:
        return False
