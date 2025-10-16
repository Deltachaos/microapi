import re
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

from ..di import tag
from ..http import Request
from ..util import jwt_decode, jwt_validate, logger


class User:
    def user_identifier(self):
        raise NotImplementedError()

    def roles(self):
        return ['IS_AUTHENTICATED']


class Token:
    def __init__(self):
        self._user = None

    def set_user(self, user: User | None):
        self._user = user

    def user(self) -> User | None:
        return self._user

    def user_identifier(self) -> Any:
        if self._user is None:
            return None
        return self._user.user_identifier()

    def roles(self):
        if self._user is None:
            return []
        return self._user.roles()


class UserResolver:
    async def resolve(self, token: Token) -> User|None:
        pass


class TokenResolver:
    async def resolve(self, request: Request) -> Token|None:
        pass


class JwtToken(Token):
    def __init__(self, raw: str):
        super().__init__()
        self._raw = raw
        payload, header, signature = jwt_decode(raw)
        self._payload = payload
        self._header = header
        self._signature = signature

        self.issued_at = None
        self.expires_at = None
        self.sub = None

        self.well_known = payload
        iat = self.well_known.get('iat')
        if iat:
            self.issued_at = datetime.fromtimestamp(iat, tz=timezone.utc)
        exp = self.well_known.get('exp')
        if exp:
            self.expires_at = datetime.fromtimestamp(exp, tz=timezone.utc)
        sub = self.well_known.get('sub')
        if sub:
            self.sub = sub

    @property
    def token(self) -> str:
        return self._raw

    def user_identifier(self) -> Any:
        if self._user is not None:
            return super().user_identifier()
        return self.sub

    @property
    def is_expired(self) -> bool:
        """Check if the access token is expired based on its expiration time."""
        if self.expires_at is None:
            return True
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def expires_in(self) -> timedelta:
        """Returns the remaining time until the token expires."""
        if self.expires_at is None:
            raise RuntimeError('no expires_at set')
        return datetime.now(timezone.utc) - self.expires_at

    def validate(self, secret):
        return not self.is_expired and jwt_validate(self._raw, secret)


class JwtUser(User):
    def __init__(self, uid: str, roles: list[str] = None):
        super().__init__()
        self._user_id = uid
        self._roles = roles or []

    def user_identifier(self):
        return self._user_id

    def set_roles(self, roles: list[str]):
        self._roles = roles

    def roles(self):
        return super().roles() + self._roles


class JwtUserResolver(UserResolver):
    def __init__(self, secret: str):
        if not secret:
            raise ValueError("secret cannot be empty")
        self._secret = secret

    async def resolve(self, token: Token) -> User|None:
        if isinstance(token, JwtToken):
            if token.validate(self._secret):
                return JwtUser(token.user_identifier())
            else:
                logger(__name__).warning('Token not valid')
        return None


@tag('security_token_resolver')
class JwtTokenResolver(TokenResolver):
    def __init__(self, secret: str = None):
        self._secret = secret

    async def resolve(self, request: Request) -> Token | None:
        headers = request.headers.as_lower_dict()
        if "authorization" in headers:
            auth_header = headers["authorization"]
            if auth_header.startswith("Bearer "):
                raw_token = auth_header[len("Bearer "):].strip()
                token = JwtToken(raw_token)
                if self._secret is not None:
                    return token
                if token.validate(self._secret):
                    return token


class TokenStore:
    async def set(self, request: Request, token: Token):
        request.attributes['_token'] = token

    async def get(self, request: Request) -> Token | None:
        if '_token' in request.attributes and isinstance(request.attributes['_token'], Token):
            return request.attributes['_token']
        return None


class VoterResult(Enum):
    ACCESS_GRANTED = 1
    ACCESS_ABSTAIN =0
    ACCESS_DENIED = -1


class Voter:
    async def supports(self, permission: str, subject: Any) -> bool:
        return False

    async def vote(self, token: Token | None, permission: str, subject: Any) -> VoterResult:
        return VoterResult.ACCESS_ABSTAIN


@tag('security_voter')
class DefaultVoter(Voter):
    async def supports(self, permission: str, subject: Any) -> bool:
        return True

    async def vote(self, token: Token | None, permission: str, subject: Any) -> VoterResult:
        if token is None:
            return VoterResult.ACCESS_DENIED

        roles = token.roles()
        if permission in roles:
            return VoterResult.ACCESS_GRANTED

        return VoterResult.ACCESS_DENIED


class Security:
    def __init__(self, token_store: TokenStore, voters = None):
        if voters is None:
            voters = lambda: []
        self.token_storage = token_store
        self.voters = voters

    async def user(self):
        return self.token_storage

    async def is_granted(self, request: Request, permission: str, subject: Any = None) -> bool:
        for _, service_get in self.voters():
            voter = await service_get()
            if await voter.supports(permission, subject):
                token = await self.token_storage.get(request)
                result = await voter.vote(token, permission, subject)
                if result == VoterResult.ACCESS_GRANTED:
                    return True
                elif result == VoterResult.ACCESS_DENIED:
                    return False

        return False


class Firewall:
    def __init__(self, security: Security, token_store: TokenStore, user_resolver: UserResolver = None, token_resolvers = None):
        if token_resolvers is None:
            token_resolvers = lambda: []
        self._security = security
        self._token_store = token_store
        self._token_resolvers = token_resolvers
        self._user_resolver = user_resolver
        self._list = {}

    async def add(self, path, role = None):
        self._list[path] = role

    async def list(self) -> dict:
        return self._list

    async def authenticate(self, request: Request):
        for _, service_get in self._token_resolvers():
            token_resolver = await service_get()
            token = await token_resolver.resolve(request)
            if token is not None:
                await self._token_store.set(request, token)

        token = await self._token_store.get(request)
        if self._user_resolver is not None and token is not None:
            user = await self._user_resolver.resolve(token)
            if user is not None:
                token.set_user(user)

    async def is_granted(self, request: Request):
        path = request.path
        items = await self.list()
        for pattern, role in items.items():
            if re.match(pattern, path):
                if role is None:
                    return True
                return await self._security.is_granted(request, role)

        return False
