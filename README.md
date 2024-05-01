# Lacus

A capturing system using playwright, as a web service.

# Install guide

## System dependencies

You need poetry installed, see the [install guide](https://python-poetry.org/docs/).

## Prerequisites

You need to have redis cloned and installed in the same directory you clone this template in:
this repoitory and `redis` must be in the same directory, and **not** `redis` cloned in the
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

It will launch the instance if you answer yes to the "restart" question.

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

# Maintenance

If you have recurring messages like the ones below you can remove the uuid from the queue as follows.

```
2023-11-17 08:00:59,936 LacusCore WARNING:[ef7f653d-4cfd-4e7b-9b91-58c9c2658868] Attempted to clear capture that is still being processed.
2023-11-17 08:01:00,939 LacusCore WARNING:[ef7f653d-4cfd-4e7b-9b91-58c9c2658868] Attempted to clear capture that is still being processed.
2023-11-17 08:01:01,941 LacusCore WARNING:[ef7f653d-4cfd-4e7b-9b91-58c9c2658868] Attempted to clear capture that is still being processed.
2023-11-17 08:01:02,944 LacusCore WARNING:[ef7f653d-4cfd-4e7b-9b91-58c9c2658868] Attempted to clear capture that is still being processed.
2023-11-17 08:01:03,947 LacusCore WARNING:[ef7f653d-4cfd-4e7b-9b91-58c9c2658868] Attempted to clear capture that is still being processed.
...
```


While redis is running connect to it via its socket and zrem then entry.

```
ail@ail-tokyo:~$ cd lacus/
ail@ail-tokyo:~/lacus$ ../redis/src/redis-cli -s cache/cache.sock
redis cache/cache.sock> zrem lacus:ongoing ef7f653d-4cfd-4e7b-9b91-58c9c2658868
(integer) 1
redis cache/cache.sock>
```

# Useful environment variables

There are env varibles you can pass to help making better captures, or avoir captures to fail when they shouldn't:

* `PW_TEST_SCREENSHOT_NO_FONTS_READY` avoids captures to get stuck on screenshot when the fonts don't load (https://github.com/microsoft/playwright/issues/28995)
* `PLAYWRIGHT_CHROMIUM_USE_HEADLESS_NEW` improves stealth for chromium by using the new headless mode (a little bit slower): https://github.com/Lookyloo/PlaywrightCapture/issues/55

To use them, you can run the capture manager this way:

```bash

PLAYWRIGHT_CHROMIUM_USE_HEADLESS_NEW=1 PW_TEST_SCREENSHOT_NO_FONTS_READY=1 capture_manager
```
