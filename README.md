![Lacus Logo](logos/1_horizontal/png/LACUS_horizontal-color.png?raw=true "Logo")

# Lacus

A capturing system using playwright, as a web service.

# Install guide with Docker or Podman
To run lacus using docker or podman you need docker installed or podman and podman-compose:

```
podman-compose build # or docker compose build
podman-compose up # or docker compose up
# go to http://localhost:7100/
```

# Install guide

## System dependencies

You need poetry installed, see the [install guide](https://python-poetry.org/docs/). The [poetry shell plugin](https://github.com/python-poetry/poetry-plugin-shell) is not strictly required, but will make your life easier. You can install it [this way](https://github.com/python-poetry/poetry-plugin-shell?tab=readme-ov-file#installation). 

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
git checkout 8.0
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
poetry run playwright install-deps
# for pydub:
sudo apt install ffmpeg libavcodec-extra
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

## Annoying repetitive log entries

If you have recurring messages like the ones below you can remove the uuid from the queue as follows. Note that it is probabli simply due to an unclean stop of lacus and they will be removed automatically after a while

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

## Error mentioning missing system dependencies 

On an initial install, we tell you to run `playwright install-deps`. After updating an existing lacus instance, you may have to do that again if new ones are required by playwright.

It that's the case, run the following command from the lacus directory:

``` bash
poetry run playwright install-deps
```

# Interactive sessions (xpra)

Lacus supports interactive capture sessions powered by [xpra](https://xpra.org). In an interactive session the browser is displayed inside a virtual X display managed by xpra. You can connect to it via a browser-based HTML5 client, interact with the page (log in, solve CAPTCHAs, etc.), and then trigger a normal capture once the page is in the desired state.

## Additional system dependencies

On Ubuntu 24.04, add the xpra.org repository and install the interactive
session dependencies:

```bash
curl -s https://xpra.org/gpg.asc | sudo apt-key add -
echo "deb https://xpra.org/ noble main" | sudo tee /etc/apt/sources.list.d/xpra.list
sudo apt update
sudo apt install xpra xvfb
```

> **Warning:** On desktop systems, installing xpra enables and starts a
> system-wide xpra service and socket. These are not needed by Lacus (which
> manages its own per-session xpra servers) and should be disabled:
>
> ```bash
> sudo systemctl disable --now xpra.service xpra.socket
> ```

## Running Tactus

Each interactive capture starts its own short-lived xpra server bound to a private unix socket. The Lacus API remains the control plane: it enqueues interactive captures, reports session state, and accepts the final `finish` signal. Tactus, the Lacus interactive sidecar, proxies `/interactive/<uuid>/view/` traffic to the matching xpra socket so you can view the HTML5 client in a browser.

This keeps the project boundaries:

- `LacusCore` owns interactive session lifecycle and xpra transport details.
- `lacus` exposes the control-plane API.
- Tactus handles end-user browser traffic for the HTML5 client.


By default, Tactus listens on `127.0.0.1:7101` and serves `/interactive/<uuid>/view/`, including the nested xpra transport under `/interactive/<uuid>/view/session/`.

The bundled wrapper assumes a same-origin deployment for its own UI assets and uses view-local convenience endpoints under `/interactive/<uuid>/view/` for status polling and `finish`. Those Tactus-local wrapper endpoints proxy to the Lacus API routes such as `GET /interactive/<uuid>` and `POST /interactive/<uuid>/finish`, so Flask remains the source of truth while the browser keeps a same-origin path for the panel controls.

## Configuration

If you want the Lacus API to return a browser-usable `view_url` in `GET /interactive/<uuid>`, set a public base URL template before starting lacus:

```bash
export LACUS_XPRA_PUBLIC_BASE_URL=http://127.0.0.1:8080/interactive/{uuid}/view/
```

For a deployment behind a third-party application or reverse proxy:

```bash
export LACUS_XPRA_PUBLIC_BASE_URL=https://thirdparty.example/interactive/{uuid}/view/
```

To enable interactive captures, set `allow_interactive` to `true` in `config/generic.json`. When this flag is set, `poetry run start` automatically launches Tactus alongside the main Lacus process.

Tactus itself can be configured with:

```json
"allow_interactive": true,
"tactus_listen_ip": "127.0.0.1",
"tactus_listen_port": 7101
```

These keys live in `config/generic.json`.

Sample reverse-proxy configurations are available in:

- `/etc/nginx/lacus.conf.sample`
- `/etc/apache2/lacus.conf.sample`

These examples route only `/interactive/<uuid>/view/` to Tactus and send the rest of the API traffic to the main Lacus application. The bundled wrapper uses Tactus-local helper endpoints under `/interactive/<uuid>/view/` for its panel controls, and those helpers proxy to the canonical Lacus API routes for session metadata and `finish`.

For systemd deployments, a sample Tactus unit is available in:

- `/etc/systemd/system/lacus-tactus.service.sample`

For supervisord deployments, a sample configuration that includes Tactus is available in:

- `/supervisord/supervisord-tactus.conf.sample`

The internal xpra unix sockets are not meant to be exposed directly to end-users. If you do not set `LACUS_XPRA_PUBLIC_BASE_URL`, the API will still report session state, but `view_url` may be absent.

## Usage

Enqueue an interactive capture:

```bash
UUID=$(curl -s -X POST http://localhost:7100/enqueue \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com", "interactive": true, "interactive_ttl": 600}')
echo "Session UUID: $UUID"
```

Poll until the session status is `ready`. Possible status values are
`starting`, `ready`, `capture_requested`, `stopped`, `expired`, and `error`.

```bash
curl -s http://localhost:7100/interactive/$UUID
# {"status": "ready", "view_url": "http://127.0.0.1:8080/interactive/<uuid>/view/", ...}
```

If `view_url` is present, open it in a browser to interact with the page. When ready, trigger the capture:

```bash
curl -s -X POST http://localhost:7100/interactive/$UUID/finish
```

Retrieve the result (poll until status is not `"unknown"`):

```bash
curl -s http://localhost:7100/capture_result/$UUID
```

## Architectural note

Tactus exists to make interactive sessions testable and deployable without turning the main Lacus web app into a full HTML5/WebSocket proxy. If you already have a third-party application (e.g. LookyLoo, AIL, Pandora) that fronts Lacus, that application can provide the same `/interactive/<uuid>/view/` route itself and proxy to the Lacus-managed unix socket instead of using Tactus.

## Third-party proxy contract

If a third-party application fronts Lacus, the clean contract is:

- `GET /interactive/<uuid>` on Lacus returns session state plus an optional deployment-facing `view_url`.
- The third-party app serves `/interactive/<uuid>/view/` to end-users.
- The wrapper page, if used, may expose same-origin helper routes under `/interactive/<uuid>/view/`, but those helpers should proxy to the canonical Lacus API routes (`GET /interactive/<uuid>` and `POST /interactive/<uuid>/finish`) rather than reimplementing the control plane.
- That route must proxy both HTTP and WebSocket traffic to the xpra server bound to the session's internal unix socket.
- The raw unix socket path should stay internal to trusted infrastructure. It should not be exposed to normal end-users.

The bundled `tactus` sidecar is only a reference implementation of that contract.

## Example deployment

One clean deployment model is:

- `lacus.service` runs the main Lacus control-plane service on `127.0.0.1:7100`
- `lacus-tactus.service` runs Tactus on `127.0.0.1:7101`
- nginx listens on the host-facing interface and routes:
  - `/interactive/<uuid>/view/` to `127.0.0.1:7101`
  - everything else to `127.0.0.1:7100`

In that setup, set:

```bash
export LACUS_XPRA_PUBLIC_BASE_URL=https://lacus.example.net/interactive/{uuid}/view/
```

Then enable and start both services:

```bash
sudo systemctl enable lacus.service lacus-tactus.service
sudo systemctl start lacus.service lacus-tactus.service
```

Finally, install the nginx sample and adjust `server_name`, TLS, and any access-control rules as needed for your environment.

---

# Useful environment variables

There are env varibles you can pass to help making better captures, or avoir captures to fail when they shouldn't:

* `PW_TEST_SCREENSHOT_NO_FONTS_READY` avoids captures to get stuck on screenshot when the fonts don't load (https://github.com/microsoft/playwright/issues/28995)
* `PLAYWRIGHT_CHROMIUM_USE_HEADLESS_NEW` improves stealth for chromium by using the new headless mode (a little bit slower): https://github.com/Lookyloo/PlaywrightCapture/issues/55

To use them, you can run the capture manager this way:

```bash

PLAYWRIGHT_CHROMIUM_USE_HEADLESS_NEW=1 PW_TEST_SCREENSHOT_NO_FONTS_READY=1 capture_manager
```
