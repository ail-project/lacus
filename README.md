# Lacus

A capturing system using playwright, as a web service.

## Install Guide

### System dependencies

You need poetry installed, see the [install guide](https://python-poetry.org/docs/).

### Prerequisites

You need to have redis cloned and installed in the same directory you clone this template in:
this repository and `redis` must be in the same directory, and **not** `redis` cloned in this directory. See [this guide](https://www.lookyloo.eu/docs/main/install-lookyloo.html#_install_redis).

### Installation

Clone this repository:

```bash
git clone https://github.com/ail-project/lacus.git
```

From the directory you just cloned, run:

```bash
cd lacus
poetry install
```

Install the system dependencies required by playwright (will call sudo):

```bash
poetry shell 
playwright install-deps
```

Initialize the `.env` file:

```bash
echo LACUS_HOME="`pwd`" >> .env
```

Initialize the config and install playwright browsers:

```bash
poetry run update --init

* Restarting
Continue? (y/N) <-- N
Okay, quitting.
```

**Clone the Redis server:**

1. Navigate to the parent directory:

```bash
pushd ..
```

2. Clone the Redis repository:

```bash
git clone https://github.com/antirez/redis.git
```

3. Enter the Redis directory:

```bash
pushd redis
```

4. Checkout the version "7.0" of Redis:

```bash
git checkout 7.0
```

5. Compile Redis:

```bash
make
```

6. Return to the previous directory:

```bash
popd
```

7. Return to the initial directory:

```bash
popd
```

### Lacus CLI(Command line Interface)
## start
- `poetry run start`: This command is used to start a Lacus service
```bash
poetry run start 
```
## stop
- `poetry run stop`: This command is used to stop a Lacus service
```bash
poetry run stop
```

## update
- `poetry run update`: This command is used to update the project dependencies according to the configurations defined in the `pyproject.toml` file.
```bash
poetry run update
```

## shutdown
- `poetry run shutdown`: This command is used to completely shut down a  Lacus service
```bash
poetry run shutdown 
```

## run_backend
- `poetry run run_backend`: This command is used to manager the backend redis 
```bash
poetry run run_backend --help 
  -h, --help  show this help message and exit
  --start     Start all
  --stop      Stop all
  --status    Show status
```
## start_website
- `poetry run start_website`: This command is used to start the web server 
```bash
poetry run start_website
```
## capture_manager
- `poetry run capture_manager`: This command is used to start the capture manager for data.
```bash
poetry run capture_manager
```

## stop_capture_manager
- `poetry run stop_capture_manager`: This command is used to stop the running capture manager.
```bash
poetry run stop_capture_manager
```


@Terrtia @SteveClement @adulau @Rafiot @gallypette 