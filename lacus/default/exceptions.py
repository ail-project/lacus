class LacusException(Exception):
    """Base exception class for Lacus project."""


class MissingEnv(LacusException):
    """Exception raised when a required environment variable is missing.

    This exception is raised when a required environment variable is not found
    or is not set to a valid value.
    """


class CreateDirectoryException(LacusException):
    """Exception raised when there is an error creating a directory.

    This exception is raised when there is a failure in creating a directory,
    such as permission issues or file system errors.
    """


class ConfigError(LacusException):
    """Exception raised when there is an error in the configuration.

    This exception is raised when there is an issue with the configuration
    settings or parameters.
    """
