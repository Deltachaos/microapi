from urllib.parse import urlencode

from microapi.http import Request, ClientResponse, RedirectResponse, Response, ClientFactory
from microapi.security import JwtToken
from microapi.util import json_base64_decode, json_base64_encode


class JwtAccessToken(JwtToken):
    def __init__(self, data: dict):
        self.data = data
        self.access_token = data.get('access_token')
        self.scope = data.get('scope')

        super().__init__(data.get('id_token'))

    def refreshed_access_token(self):
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
    client_id = None
    client_secret = None
    authorization_url = None
    token_url = None
    redirect_uri = None
    scope = None

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
        state = self.state_decode(state)
        return state

    async def response(self,
                 request: Request,
                 result: ClientResponse,
                 token: JwtAccessToken,
                 state = None):
        return Response("", status_code=204)

    # def authorize_path(self, state):
    #     encoded = self.state_encode(state)
    #     data = {
    #         "state": encoded
    #     }
    #     return self.path + f"?{urlencode(data)}"
    #
    # def callback_path(self):
    #     return self.path_callback

    async def login(self, client_request: Request):
        config = await self.config(client_request)
        state = await self.request(client_request)

        if isinstance(state, Response):
            return state

        state = self.state_encode(state)

        params = {
            "client_id": config.client_id,
            "redirect_uri": config.redirect_uri,
            "response_type": "code",
            "scope": config.scope,
            "state": state
        }
        auth_url = f"{config.authorization_url}?{urlencode(params)}"
        return RedirectResponse(auth_url)

    async def callback(self, client_request: Request, code, state = None):
        state = self.state_decode(state)
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

    def state_encode(self, state):
        # TODO: add encryption
        if not state:
            state = {}
        return json_base64_encode(state)

    def state_decode(self, state):
        # TODO: add encryption
        if state:
            return json_base64_decode(state)
        return {}
