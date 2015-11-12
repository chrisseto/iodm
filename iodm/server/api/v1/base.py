import re

import tornado.web

from iodm import exceptions
from iodm.auth import Permissions
from iodm.server.api.base import BaseAPIHandler


class ResourceHandler(BaseAPIHandler):

    @property
    def page(self):
        raw = self.get_query_argument('page', default=1)
        try:
            page = int(raw)
        except (TypeError, ValueError):
            raise Exception()
        if page < 1:
            raise Exception()
        return page

    def initialize(self, resource):
        self.resource = resource()

    def prepare(self):
        super().prepare()
        resources = []
        resource = self.resource

        while resource:
            resources = [resource] + resources
            resource = resource.parent

        loaded = [
            r.load(self.path_kwargs[r.name + '_id'], self.request)
            for r in resources
            if self.path_kwargs.get(r.name + '_id')
        ]

        self.permissions = Permissions.get_permissions(self.current_user, *loaded)

        # TODO this is kinda hacky
        self.current_user.permissions = self.permissions

        required_permissions = self.resource.get_permissions(self.request)
        if required_permissions != Permissions.NONE and not required_permissions & self.permissions:
            if self.current_user.uid is None:
                raise exceptions.Unauthorized()
            raise exceptions.InsufficientPermissions()

    def parse_filter(self):
        filter_dict = {}
        matcher = re.compile(r'filter\[(.+)\]')
        for key in self.request.query_arguments:
            match = matcher.match(key)
            if match:
                filter_dict[match.groups()[-1]] = self.request.query_arguments[key][-1].decode()
        return filter_dict

    def get(self, **kwargs):
        # Get a specific resource
        if self.resource.resource is not None:
            return self.write({
                'data': self.resource.read(self.current_user)
            })

        # Resource listing
        selector = self.resource.list(self.current_user, page=self.page - 1, filter=self.parse_filter())
        return self.write({
            'data': [x.to_json_api() for x in selector],
            'meta': {
                'total': selector.count(),
                'perPage': self.resource.PAGE_SIZE
            },
            'links': {}
        })

    def post(self, **kwargs):
        assert self.resource.resource is None
        data = self.json['data']
        # assert data['type'] == self.resource.name
        self.set_status(201)
        self.write({
            'data': self.resource.create(data, self.current_user)
        })

    def put(self, **kwargs):
        assert self.resource.resource is not None
        data = self.json['data']
        assert data['id'] == self.path_kwargs[self.resource.name + '_id']
        # assert data['type'] == self.resource.name
        return self.write({
            'data': self.resource.replace(data, self.current_user)
        })

    def patch(self, **kwargs):
        assert self.resource.resource is not None
        data = self.json['data']
        assert data['id'] == self.path_kwargs[self.resource.name + '_id']
        assert data['type'] == self.resource.name
        return self.write({
            'data': self.resource.update(data, self.current_user)
        })

    def delete(self, **kwargs):
        self.set_status(204)
        self.resource.delete(self.current_user)


class APIResource:

    @classmethod
    def as_handler_entry(cls):
        inst = cls()
        return (inst.general_pattern, ResourceHandler, {'resource': cls})

    @property
    def general_pattern(self):
        if self.parent:
            url = self.parent.specific_pattern
        else:
            url = '/'
        return '{0}{1}(?:/(?P<{2}_id>(?:\w|-)+))?/?'.format(url, self.plural, self.name)

    @property
    def specific_pattern(self):
        if self.parent:
            url = self.parent.specific_pattern
        else:
            url = '/'
        return '{0}{1}/(?P<{2}_id>(?:\w|-)+)/'.format(url, self.plural, self.name)

    def __init__(self, resource_name, parent=None, plural=None):
        if parent:
            self.parent = parent()
        else:
            self.parent = None

        self.resource = None
        self.name = resource_name
        self.plural = plural or self.name + 's'

    def get_permissions(self, request):
        return Permissions.from_method(request.method)

    def load(self, resource):
        self.resource = resource
        return resource

    def list(self):
        raise tornado.web.HTTPError(405)

    def create(self):
        raise tornado.web.HTTPError(405)

    def read(self):
        raise tornado.web.HTTPError(405)

    def update(self):
        raise tornado.web.HTTPError(405)

    def replace(self):
        raise tornado.web.HTTPError(405)

    def delete(self):
        raise tornado.web.HTTPError(405)