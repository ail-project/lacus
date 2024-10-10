#!/usr/bin/env python3

from __future__ import annotations

import datetime
import logging
import logging.config

from collections import defaultdict
from importlib.metadata import version
from typing import Dict, Optional, Union, Any, List, Tuple

from flask import Flask, request
from flask_restx import Api, Resource, fields  # type: ignore[import-untyped]

from lacuscore import CaptureStatus, CaptureResponse, CaptureSettingsError

from lacus.default import get_config
from lacus.lacus import Lacus

from .helpers import get_secret_key
from .proxied import ReverseProxied

logging.config.dictConfig(get_config('logging'))

logger = logging.getLogger(__name__)

app: Flask = Flask(__name__)

app.wsgi_app = ReverseProxied(app.wsgi_app)  # type: ignore[method-assign]

app.config['SECRET_KEY'] = get_secret_key()

api = Api(app, title='Lacus API',
          description='API to query lacus.',
          version=version('lacus'))

lacus: Lacus = Lacus()


@api.errorhandler(CaptureSettingsError)  # type: ignore[misc]
def handle_pydandic_validation_exception(error: CaptureSettingsError) -> tuple[dict[str, Any], int]:
    '''Return the validation error message and 400 status code'''
    if error.pydantic_validation_errors:
        logger.warning(f'Unable to validate capture settings: {error.pydantic_validation_errors}')
        return {'message': 'Unable to validate capture settings.',
                'details': error.pydantic_validation_errors.errors()}, 400
    logger.warning(f'Unable to validate capture settings: {error}')
    return {'message': str(error)}, 400


@api.route('/redis_up')
@api.doc(description='Check if redis is up and running')
class RedisUp(Resource):  # type: ignore[misc]

    def get(self) -> bool:
        return lacus.check_redis_up()


http_creds_model = api.model('HttpCredentialtModel', {
    'username': fields.String(example='admin'),
    'password': fields.String(example='password')
})

viewport_model = api.model('ViewportModel', {
    'width': fields.Integer(example=1024),
    'height': fields.Integer(example=768)
})

geolocation_model = api.model('GeolocalisationModel', {
    'longitude': fields.Float(example=12.453389),
    'latitude': fields.Float(example=41.902916)
})


submit_fields_post = api.model('SubmitFieldsPost', {
    'url': fields.Url(description="The URL to capture", example=''),
    'document': fields.String(description="A base64 encoded document, it can be anything a browser can display.", example=''),
    'document_name': fields.String(description="The name of the document.", example=''),
    'depth': fields.Integer(description="Depth of the capture, based on te URLs that can be found in the rendered page.", example=0),
    'rendered_hostname_only': fields.Boolean(description="If depth is >0, which URLs are we capturing (only the ones with the same hostname as the rendered page, or all of them.)", example=True),
    'browser': fields.String(description="Use this browser. Must be chromium, firefox or webkit.", example='webkit'),
    'device_name': fields.String(description="Use the pre-configured settings for this device. Get a list from /json/devices.", example='Nexus 6'),
    'user_agent': fields.String(description="User agent to use for the capture", example='Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/116.0'),
    'proxy': fields.Url(description="Proxy to use for the capture. Format: [scheme]://[username]:[password]@[hostname]:[port]", example=''),
    'general_timeout_in_sec': fields.Integer(description="General timeout for the capture. It will be killed regardless the status after that time.", example=300),
    'cookies': fields.String(description="JSON export of a list of cookies as exported from an other capture", example=''),
    'headers': fields.String(description="Headers to pass to the capture", example='Accept-Language: en-US;q=0.5, fr-FR;q=0.4'),
    'http_credentials': fields.Nested(http_creds_model, description="HTTP Authentication settings"),
    'geolocation': fields.Nested(geolocation_model, description="The geolocalisation of the browser"),
    'viewport': fields.Nested(viewport_model, description="The viewport of the capture"),
    'timezone_id': fields.String(description="The timezone ID of the browser", example='Europe/Paris'),
    'locale': fields.String(description="The locale of the browser", example='en-US'),
    'color_scheme': fields.String(description="The color scheme of the browser", example='dark'),
    'java_script_enabled': fields.Boolean(description="If False, javascript won't be executed when rendering the page", example=True),
    'referer': fields.String(description="Referer to pass to the capture", example='https://circl.lu'),
    'with_favicon': fields.Boolean(description="Attempts to get favicons related to the landing page of the capture", example=False),
    'allow_tracking': fields.Boolean(description="Attempt to let the website violate your privacy", example=False),
    'force': fields.Boolean(description="Force a capture, even if the same one was already done recently", example=False),
    'recapture_interval': fields.Integer(description="The minimal interval to re-trigger a capture, unless force is True", example=300),
    'priority': fields.Integer(description="Priority of the capture, the highest, the better", example=-5),
})


@api.route('/enqueue')
class Enqueue(Resource):  # type: ignore[misc]

    @api.doc(body=submit_fields_post)  # type: ignore[misc]
    @api.produces(['text/text'])  # type: ignore[misc]
    def post(self) -> str:
        to_query: Dict[str, Any] = request.get_json(force=True)
        perma_uuid = lacus.core.enqueue(
            url=to_query.get('url'),
            document_name=to_query.get('document_name'),
            document=to_query.get('document'),
            depth=to_query.get('depth', 0),
            browser=to_query.get('browser'),
            device_name=to_query.get('device_name'),
            user_agent=to_query.get('user_agent'),
            proxy=lacus.global_proxy if lacus.global_proxy else to_query.get('proxy'),
            general_timeout_in_sec=to_query.get('general_timeout_in_sec'),
            cookies=to_query.get('cookies'),
            headers=to_query.get('headers'),
            http_credentials=to_query.get('http_credentials'),
            viewport=to_query.get('viewport'),
            geolocation=to_query.get('geolocation'),
            timezone_id=to_query.get('timezone_id'),
            locale=to_query.get('locale'),
            color_scheme=to_query.get('color_scheme'),
            java_script_enabled=to_query.get('java_script_enabled', True),
            referer=to_query.get('referer'),
            with_favicon=to_query.get('with_favicon', False),
            allow_tracking=to_query.get('allow_tracking', False),
            rendered_hostname_only=to_query.get('rendered_hostname_only', True),
            force=to_query.get('force', False),
            recapture_interval=to_query.get('recapture_interval', 300),
            priority=to_query.get('priority', 0),
            uuid=to_query.get('uuid', None)
        )
        return perma_uuid


@api.route('/capture_status/<string:capture_uuid>')
@api.doc(description='Get the status of a capture.',
         params={'capture_uuid': 'The UUID of the capture'})
class CaptureStatusQuery(Resource):  # type: ignore[misc]

    def get(self, capture_uuid: str) -> CaptureStatus:
        return lacus.core.get_capture_status(capture_uuid)


@api.route('/capture_result/<string:capture_uuid>')
@api.doc(description='Get the result of a capture.',
         params={'capture_uuid': 'The UUID of the capture'})
class CaptureResult(Resource):  # type: ignore[misc]

    def get(self, capture_uuid: str) -> CaptureResponse:
        return lacus.core.get_capture(capture_uuid)


stats_model = api.model('StatsModel', {
    'captures': fields.Integer,
    'retry_success': fields.Integer,
    'retry_failed': fields.Integer,
    'errors': fields.List(fields.List(fields.String)),
})


@api.route('/daily_stats')
@api.route('/daily_stats/<string:date>')
@api.doc(description='Get the statistics for a day.',
         params={'date': 'The date in ISO format YYYY-MM-DD'})
class DailyStats(Resource):  # type: ignore[misc]

    @api.marshal_with(stats_model, skip_none=True)  # type: ignore[misc]
    def get(self, date: Optional[str]=None) -> Dict[str, Any]:
        if 'date' in request.args:
            date = request.args['date']
        if not date:
            date = datetime.date.today().isoformat()
        return lacus.monitoring.get_stats(date, cardinality_only=True)


stats_details_model = api.model('StatsDetailsModel', {
    'captures': fields.List(fields.String),
    'retry_success': fields.List(fields.String),
    'retry_failed': fields.List(fields.String),
    'errors': fields.List(fields.List(fields.String)),
})


@api.route('/daily_stats_details')
@api.route('/daily_stats_details/<string:date>')
@api.doc(description='Get the statistics for a day, with lists of successful/failed URLs.',
         params={'date': 'The date in ISO format YYYY-MM-DD'})
class DailyStatsDetails(Resource):  # type: ignore[misc]

    @api.marshal_with(stats_details_model, skip_none=True)  # type: ignore[misc]
    def get(self, date: Optional[str]=None) -> Dict[str, Any]:
        if 'date' in request.args:
            date = request.args['date']
        if not date:
            date = datetime.date.today().isoformat()
        return lacus.monitoring.get_stats(date, cardinality_only=False)


@api.route('/db_status')
@api.doc(description='Get a few infos about Redis usage.')
class DBSatus(Resource):  # type: ignore[misc]

    def get(self) -> Dict[str, Any]:
        return lacus.redis_status()


@api.route('/ongoing_captures')
@api.route('/ongoing_captures/<int:with_settings>')
@api.doc(description='Get all the ongoing captures.',
         params={'with_settings': 'If set, returns the settings.'})
class OngoingCaptures(Resource):  # type: ignore[misc]

    def get(self, with_settings: Optional[int]=None) -> Union[List[Tuple[str, str]], Dict[str, Any]]:
        ongoing = lacus.monitoring.get_ongoing_captures()
        _ongoing = [(uuid, d.isoformat()) for uuid, d in ongoing]
        if 'with_settings' in request.args:
            with_settings = True
        if not with_settings:
            return _ongoing
        to_return: Dict[str, Dict[str, Union[Dict[str, Any], str]]] = defaultdict(dict)
        for uuid, capture_time in _ongoing:
            to_return[uuid]['settings'] = lacus.monitoring.get_capture_settings(uuid)
            to_return[uuid]['capture_time'] = capture_time
        return to_return


@api.route('/enqueued_captures')
@api.route('/enqueued_captures/<int:with_settings>')
@api.doc(description='Get all the enqueued but not yet ongoing captures.',
         params={'with_settings': 'If set, returns the settings.'})
class EnqueuedCaptures(Resource):  # type: ignore[misc]

    def get(self, with_settings: Optional[int]=None) -> Union[List[Tuple[str, float]], Dict[str, Any]]:
        enqueued = lacus.monitoring.get_enqueued_captures()
        if 'with_settings' in request.args:
            with_settings = True
        if not with_settings:
            return enqueued
        to_return: Dict[str, Dict[str, Union[Dict[str, Any], str, float]]] = defaultdict(dict)
        for uuid, priority in enqueued:
            to_return[uuid]['settings'] = lacus.monitoring.get_capture_settings(uuid)
            to_return[uuid]['priority'] = priority
        return to_return


@api.route('/lacus_status')
@api.doc(description='Get the status of the Lacus instance.')
class LacusStatus(Resource):  # type: ignore[misc]

    def get(self) -> Dict[str, Any]:
        return lacus.status()


@api.route('/is_busy')
@api.doc(description='Check if Lacus is busy (ongoing captures >= max ongoing captures).')
class LacusIsBusy(Resource):  # type: ignore[misc]

    def get(self) -> bool:
        return lacus.is_busy
