#!/usr/bin/env python3

from importlib.metadata import version
from flask import Flask
from flask_restx import Api, Resource  # type: ignore

from redis import Redis

from lacus.default import get_config, get_socket_path
from lacus.lacus import LacusCore

from .helpers import get_secret_key
from .proxied import ReverseProxied

app: Flask = Flask(__name__)

app.wsgi_app = ReverseProxied(app.wsgi_app)  # type: ignore

app.config['SECRET_KEY'] = get_secret_key()

api = Api(app, title='Lacus API',
          description='API to query lacus.',
          version=version('lacus'))

redis: Redis = Redis(unix_socket_path=get_socket_path('cache'))

project: LacusCore = LacusCore(redis, get_config('generic', 'tor_proxy'), get_config('generic', 'only_global_lookups'))


@api.route('/redis_up')
@api.doc(description='Check if redis is up and running')
class RedisUp(Resource):

    def get(self):
        return project.check_redis_up()
