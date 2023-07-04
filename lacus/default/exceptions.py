class LacusException(Exception):
    pass


class MissingEnv(LacusException):
    pass


class CreateDirectoryException(LacusException):
    pass


class ConfigError(LacusException):
    pass
