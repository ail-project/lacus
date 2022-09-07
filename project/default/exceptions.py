#!/usr/bin/env python3


class ProjectNameException(Exception):
    pass


class MissingEnv(ProjectNameException):
    pass


class CreateDirectoryException(ProjectNameException):
    pass


class ConfigError(ProjectNameException):
    pass
