from typing import Any, Callable, MutableMapping


class ReverseProxied:
    """WSGI middleware for handling reverse proxy headers.

    This class is a WSGI middleware that adjusts the WSGI environment based on reverse proxy headers.
    It looks for the "HTTP_X_FORWARDED_PROTO" header or the "HTTP_X_SCHEME" header to determine the scheme
    (e.g., "http" or "https") used by the client when communicating with the reverse proxy.

    Args:
        app (callable): The WSGI application to be wrapped by this middleware.

    Returns
    -------
        callable: The wrapped WSGI application.

    Example:
        ```python
        from some_framework import SomeApp
        from reverse_proxy_middleware import ReverseProxied

        app = SomeApp()
        app = ReverseProxied(app)
        ```
    """

    def __init__(self, app: Callable[..., Any]) -> None:
        """Initialize the ReverseProxied middleware.

        Args:
            app (callable): The WSGI application to be wrapped by this middleware.
        """
        self.app = app

    def __call__(
        self, environ: MutableMapping[str, Any], start_response: Callable[..., Any]
    ) -> Any:
        """Adjust the WSGI environment and call the wrapped application.

        This method adjusts the WSGI environment based on the reverse proxy headers.
        It sets the "wsgi.url_scheme" environment variable to the detected scheme.

        Args:
            environ (MutableMapping[str, Any]): The WSGI environment.
            start_response (callable): The WSGI start_response function.

        Returns
        -------
            Any: The response from the wrapped WSGI application.
        """
        scheme = environ.get("HTTP_X_FORWARDED_PROTO")
        if not scheme:
            scheme = environ.get("HTTP_X_SCHEME")

        if scheme:
            environ["wsgi.url_scheme"] = scheme
        return self.app(environ, start_response)
