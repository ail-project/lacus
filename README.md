# Lacus

A capturing system using playwright, as a web service.

# Install guide

## System dependencies

You need poetry installed, see the [install guide](https://python-poetry.org/docs/).

## Prerequisites

You need to have redis cloned and installed in the same directory you clone this template in:
this repoitory and and `redis` must be in the same directory, and **not** `redis` cloned in the
this directory. See [this guide](https://www.lookyloo.eu/docs/main/install-lookyloo.html#_install_redis).

## Installation

Clone this repository:

```bash
git clone https://github.com/ail-project/lacus.git
```

From the directory you just cloned, run:

```bash
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
```
This will already launch a first instance.

## Configuration

Edit the config file `config/generic.json`, and configure it accordingly to your needs.

# Usage

Start the tool (as usual, from the directory):

```bash
poetry run start
```

You can stop it with

```bash
poetry run stop
```

With the default configuration, you can access the web interface on `http://0.0.0.0:7100`,
where you will find the API and can start playing with it.
