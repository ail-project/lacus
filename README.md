# Project Template

This is a simple template used in all the web based tools in this repository, and a few others.

# Architecture

## `pyproject.toml` file

You must at least change the name of your project (variable `name`), the `description` and the `authors`.

The name of the project **must be the same** as the directory containing the main code.

## `project` directory

This directory contains the main code of the project. It must be renamed to the
same name value as the name defined in `pyproject.toml` and this name will be reused
all over the place, so pick a good one.

### `project/projectname.py` file

This file contains the main class of your project. You also want to rename this file **and** the
main class defined in it.

### `project/default` directory

This directory contains the default classes and methods used by the framework.

You must change the variable `env_global_name` defined in `project/default/__init__.py`.
It is the name of the global variable used in the framework to figure out the home directory of the project.

If you have more than one database, you will need to add it in `get_socket_path` file `project/default/helpers.py`.

You probably don't want to change anything else in it.
If you do so, it will also make updating the framework easier.
If you feel something should be added, you may want to do a PR on this repository.

## `config` directory

Contains the generic config file (`config/generic.json.sample`). All the config parameters used
by the project must be defined and commented (see `_notes`) in this file.

## `bin` directory

This directory contains the scripts that are used to run the app.

You must edit all of them and change all the imports starting with `from project.default` to the
new name of the `project` directory. Everything else should stay as-is.

## `cache` directory

Contains the redis config file and the start/stop script for the cache database in redis. No need to change anything.

## `etc` directory

Contains templates for systemd services, how to set them up is explained in the files themselves. You also need to rename the process file name to the name you use in `config/generic.json.sample`.

## `tools` directory

Contains standalone tools that are used for specific tasks.
For now the only one in there is a script that validates the config file, you will need to edit the
imports the same way you did in the `bin` directory.

## `website/web` directory

Contains the relevant files for the web interface.

### `website/web/helpers.py` file

You must change the imports the same way you did in the `bin` and `tools` directories.

### `website/web/__init__.py` file

* You must change the import to the main class (`from project.projectname import ProjectName`)
* You must change the name of the project in the call to `pkg_resources.get_distribution`.
  This name is the one defined in the `pyproject.toml`.
* You probably also want to change the description.

# Install guide

## System dependencies

You need poetry installed, see the [install guide](https://python-poetry.org/docs/).

## Prerequisites

You need to have redis cloned and installed in the same directory you clone this template in:
this repoitory and and `redis` must be in the same directory, and **not** `redis` cloned in the
this directory. See [this guide](https://www.lookyloo.eu/docs/main/install-lookyloo.html#_install_redis).

## Installation

From the directory you just cloned, run:

```bash
poetry install
```

Initialize the `.env` file:

```bash
echo PROJECT_HOME="`pwd`" >> .env
```

**Note**: `PROJECT_HOME` is the name you set in `project/default/__init__.py`

## Configuration

Copy the config file:

```bash
cp config/generic.json.sample config/generic.json
```

And configure it accordingly to your needs.

# Usage

Start the tool (as usual, from the directory):

```bash
poetry run start
```

You can stop it with

```bash
poetry run stop
```

With the default configuration, you can access the web interface on `http://0.0.0.0:9999`,
where you will find the API and can start playing with it.
