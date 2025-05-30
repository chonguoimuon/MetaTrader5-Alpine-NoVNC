from flasgger.utils import swag_from

# Swagger configuration
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec_1",
            "route": "/apispec_1.json",
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
    "title": "MT5 Trading Bot API",
    "description": "API for interacting with MetaTrader5 trading bot. Authorize with your API token in the Authorization header.",
    "version": "1.0.0",
    "securityDefinitions": {
        "ApiKeyAuth": {
            "type": "apiKey",
            "name": "Authorization",
            "in": "header",
            "description": "Enter your API token (e.g., '2010201119092012'). This will be sent as the Authorization header."
        }
    },
    "security": [
        {
            "ApiKeyAuth": []
        }
    ]
}

# Helper function to apply security to endpoints
def secure_endpoint(spec):
    """
    Decorator to apply API key security to an endpoint.
    Usage: @secure_endpoint(swag_from('path/to/spec.yml'))
    """
    if isinstance(spec, dict):
        spec["security"] = [{"ApiKeyAuth": []}]
        return swag_from(spec)
    elif isinstance(spec, str):
        def decorator(f):
            @swag_from(spec)
            def wrapped(*args, **kwargs):
                return f(*args, **kwargs)
            wrapped.__swagger_spec__ = {"security": [{"ApiKeyAuth": []}]}
            return wrapped
        return decorator
    else:
        raise ValueError("spec must be a dict or a string path to a YAML file")
