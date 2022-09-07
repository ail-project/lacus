#!/usr/bin/env python3


class LacusException(Exception):
    pass


class MissingEnv(LacusException):
    pass


class CreateDirectoryException(LacusException):
    pass


class ConfigError(LacusException):
    pass
