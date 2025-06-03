#!/bin/bash

set -e
set -x

/bin/bash -c 'cd /app/lacus/cache && ./run_redis.sh'
/usr/bin/supervisord -c /supervisord/supervisord.conf