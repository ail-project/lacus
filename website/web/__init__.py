#!/usr/bin/env python3

from importlib.metadata import version
from flask import Flask
from flask_restx import Api, Resource  # type: ignore

from project.projectname import ProjectName

from .helpers import get_secret_key
from .proxied import ReverseProxied

app: Flask = Flask(__name__)

app.wsgi_app = ReverseProxied(app.wsgi_app)  # type: ignore

app.config['SECRET_KEY'] = get_secret_key()

api = Api(app, title='Project API',
          description='API to query a the project.',
          version=version('project'))

project: ProjectName = ProjectName()


@api.route('/redis_up')
@api.doc(description='Check if redis is up and running')
class RedisUp(Resource):

    def get(self):
        return project.check_redis_up()
