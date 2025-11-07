from urllib.parse import urlencode, urlparse, parse_qs, urlunparse

from ...http import Request, ClientResponse, RedirectResponse, Response, ClientFactory
from ...security import JwtToken
from ...util import json_base64_decode, json_base64_encode


class JwtAccessToken(JwtToken):
    def __init__(self, data: dict):
        self.data = data
        self.access_token = data.get('access_token')
        self.scope = data.get('scope')

        super().__init__(data.get('id_token'))

    async def refreshed_access_token(self):
        return self.access_token

    def parse_scope(self):
        """Parse the scope string into a list of individual scopes."""
        return self.scope.split() if self.scope else []

    def to_dict(self):
        return {
            "id_token": self._raw,
            "access_token": self.access_token,
            "scope": self.scope
        }


class OAuthControllerConfig:
    def __init__(self, client_id, client_secret, authorization_url, token_url, redirect_uri, scope="openid"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_url = authorization_url
        self.token_url = token_url
        self.redirect_uri = redirect_uri
        self.scope = scope


class AbstractOAuthController:
    def __init__(self, client_factory: ClientFactory):
        self._client_factory = client_factory

    async def config(self, request: Request) -> OAuthControllerConfig:
        raise NotImplementedError()

    async def request(self, request: Request):
        state = request.query.get("state")
        if state is None:
            state = ""
        return state

    async def response(self,
                 request: Request,
                 result: ClientResponse,
                 token: JwtAccessToken,
                 state = None):
        return Response("", status_code=204)

    async def login(self, client_request: Request):
        config = await self.config(client_request)
        state = await self.request(client_request)

        if isinstance(state, Response):
            return state

        # Parse the authorization URL to extract existing query parameters
        parsed_url = urlparse(config.authorization_url)
        existing_params = parse_qs(parsed_url.query)
        
        # Flatten the existing parameters (parse_qs returns lists)
        flattened_existing = {}
        for key, value_list in existing_params.items():
            flattened_existing[key] = value_list[0] if value_list else ""
        
        # New parameters to add/override
        new_params = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": config.scope,
            "state": state
        }
        
        # Merge parameters, with new_params taking precedence
        merged_params = {**flattened_existing, **new_params}
        
        # Construct the final URL
        query_string = urlencode(merged_params)
        final_url = urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            query_string,
            parsed_url.fragment
        ))
        
        return RedirectResponse(final_url)

    async def callback(self, client_request: Request, code, state = None):
        config = await self.config(client_request)
        token_data = {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
        }
        result = await self._client_factory.create().post(config.token_url, data=token_data)
        token = None
        if result.status_code == 200:
            token_info = await result.json()
            token = JwtAccessToken(token_info)

        return await self.response(client_request, result, token, state)
