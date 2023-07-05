import argparse
import json
import logging

from lacus.default import get_homedir

logger = logging.getLogger("Config validator")


def validate_generic_config_file() -> bool:
    """
    Validate the generic configuration file.

    This function checks if the user's generic configuration file is in line with the sample configuration file.
    It verifies the existence of all keys, their types, and the presence of documentation for each key.

    Returns
    -------
        bool: True if the validation is successful.

    Raises
    ------
        Exception: If a key is missing documentation or has an invalid type.
    """
    sample_config_path = get_homedir() / "config" / "generic.json.sample"
    with sample_config_path.open() as f:
        generic_config_sample = json.load(f)

    # Check documentation
    for key in generic_config_sample:
        if key == "_notes":
            continue
        if key not in generic_config_sample["_notes"]:
            raise Exception(f"###### - Documentation missing for {key}")

    user_config_path = get_homedir() / "config" / "generic.json"
    if not user_config_path.exists():
        # The config file was never created, copy the sample.
        with user_config_path.open("w") as fw:
            json.dump(generic_config_sample, fw)

    with user_config_path.open() as f:
        generic_config = json.load(f)

    # Check all entries in the sample files are in the user file, and they have the same type
    for key, value in generic_config_sample.items():
        if key == "_notes":
            continue
        if key not in generic_config:
            logger.warning(f"Entry missing in user config file: {key}. Will default to: {value}")
            continue
        if not isinstance(generic_config[key], type(value)):
            raise Exception(
                f"Invalid type for {key}. Got: {type(generic_config[key])} ({generic_config[key]}), expected: {type(value)} ({value})"
            )

        if isinstance(value, dict):
            # Check entries
            for sub_key, sub_value in value.items():
                if sub_key not in generic_config[key]:
                    raise Exception(
                        f"{sub_key} is missing in {key}. Default from sample file: {sub_value}"
                    )
                if not isinstance(generic_config[key][sub_key], type(sub_value)):
                    raise Exception(
                        f"Invalid type for {sub_key} in {key}. Got: {type(generic_config[key][sub_key])} ({generic_config[key][sub_key]}), expected: {type(sub_value)} ({sub_value})"
                    )

    # Make sure the user config file doesn't have entries missing in the sample config
    for key in generic_config:
        if key not in generic_config_sample:
            raise Exception(
                f"{key} is missing in the sample config file. You need to compare {user_config_path} with {sample_config_path}."
            )

    return True


def update_user_configs() -> bool:
    """
    Update the user configuration file with missing entries from the sample configuration file.

    This function checks for missing keys in the user's generic configuration file and adds them from the sample file.
    If the missing key is a dictionary, it also checks for missing sub-keys and adds them.

    Returns
    -------
        bool: True if new entries were added, False otherwise.
    """
    has_new_entry = False
    for file_name in ["generic"]:
        user_config_path = get_homedir() / "config" / f"{file_name}.json"
        with user_config_path.open() as f:
            try:
                generic_config = json.load(f)
            except Exception:
                generic_config = {}

        sample_config_path = get_homedir() / "config" / f"{file_name}.json.sample"
        with sample_config_path.open() as f:
            generic_config_sample = json.load(f)

        for key, value in generic_config_sample.items():
            if key == "_notes":
                continue
            if key not in generic_config:
                print(f"{key} was missing in {file_name}, adding it.")
                print(f"Description: {generic_config_sample['_notes'][key]}")
                generic_config[key] = value
                has_new_entry = True
            elif isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    if sub_key not in generic_config[key]:
                        print(f"{sub_key} was missing in {key} from {file_name}, adding it.")
                        generic_config[key][sub_key] = sub_value
                        has_new_entry = True

        if has_new_entry:
            with user_config_path.open("w") as fw:
                json.dump(generic_config, fw, indent=2, sort_keys=True)

    return has_new_entry


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check the config files.")
    parser.add_argument(
        "--check",
        default=False,
        action="store_true",
        help="Check if the sample config and the user config are in line",
    )
    parser.add_argument(
        "--update",
        default=False,
        action="store_true",
        help="Update the user config with the entries from the sample config if entries are missing",
    )
    args = parser.parse_args()

    if args.check and validate_generic_config_file():
        print(f"The entries in {get_homedir() / 'config' / 'generic.json'} are valid.")

    if args.update and not update_user_configs():
        print(f"No updates needed in {get_homedir() / 'config' / 'generic.json'}.")
