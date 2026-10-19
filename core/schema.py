"""OpenAPI contracts for the authenticators that enforce verification."""
from drf_spectacular.authentication import SessionScheme
from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.plumbing import build_bearer_security_scheme_object


class VerifiedJWTScheme(SimpleJWTScheme):
    target_class = 'core.authentication.VerifiedJWTAuthentication'
    priority = 1


class VerifiedSessionScheme(SessionScheme):
    target_class = 'core.authentication.VerifiedSessionAuthentication'
    priority = 1


class APITokenScheme(OpenApiAuthenticationExtension):
    target_class = 'core.authentication.APITokenAuthentication'
    name = ['apiTokenHeader', 'apiTokenAuthorization']

    def get_security_requirement(self, auto_schema):
        return [{name: []} for name in self.name]

    def get_security_definition(self, auto_schema):
        return [
            {
                'type': 'apiKey', 'in': 'header', 'name': 'X-API-Token',
                'description': 'Scoped API token. Current account verification is required.',
            },
            build_bearer_security_scheme_object(
                header_name='Authorization', token_prefix='Token',
            ),
        ]
