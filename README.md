# Lacus

A capturing system using playwright, as a web service.

# Install guide

## System dependencies

You need poetry installed, see the [install guide](https://python-poetry.org/docs/).

## Prerequisites

> Lacus supports valkey or redis, but valkey is prefered now due to the change of license. So we will use valkey below, but as of now, redis also works.

### Installing valkey

System dependencies:

```bash
sudo apt-get update
sudo apt install build-essential
# To run the tests 
sudo apt install tcl
```

You need to have valkey cloned and installed in the same directory you clone the lacus repository in:
`lacus` and `valkey` must be in the same directory, and **not** `valkey` cloned in the `lacus` directory.

```bash
git clone https://github.com/valkey-io/valkey.git
```

Compile valkey:

```bash
cd valkey
git checkout 7.2
make
# Optionally, you can run the tests:
make test
cd ..
```

## Installation

Clone this repository if you haven't done it already:

```bash
git clone https://github.com/ail-project/lacus.git
```

The directory tree must look like that:

```
.
├── valkey  => cloned valkey
└── lacus => cloned lacus
```

From the `lacus` directory, run:

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


While valkey is running connect to it via its socket and zrem then entry.

```
ail@ail-tokyo:~$ cd lacus/
ail@ail-tokyo:~/lacus$ ../valkey/src/valkey-cli -s cache/cache.sock
valkey cache/cache.sock> zrem lacus:ongoing ef7f653d-4cfd-4e7b-9b91-58c9c2658868
(integer) 1
valkey cache/cache.sock>
```

# Useful environment variables

There are env varibles you can pass to help making better captures, or avoir captures to fail when they shouldn't:

* `PW_TEST_SCREENSHOT_NO_FONTS_READY` avoids captures to get stuck on screenshot when the fonts don't load (https://github.com/microsoft/playwright/issues/28995)
* `PLAYWRIGHT_CHROMIUM_USE_HEADLESS_NEW` improves stealth for chromium by using the new headless mode (a little bit slower): https://github.com/Lookyloo/PlaywrightCapture/issues/55

To use them, you can run the capture manager this way:

```bash

PLAYWRIGHT_CHROMIUM_USE_HEADLESS_NEW=1 PW_TEST_SCREENSHOT_NO_FONTS_READY=1 capture_manager
```
