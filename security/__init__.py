import re
from enum import Enum
from typing import Any

from microapi.di import tag
from microapi.http import Request


class Token:
    def user(self):
        return None

    def user_identifier(self):
        return None

    def roles(self):
        return []


class TokenResolver:
    async def resolve(self, request: Request):
        pass


class TokenStore:
    def __init__(self):
        self._token = None

    async def set(self, request: Request, token: Token):
        self._token = token

    async def get(self, request: Request) -> Token | None:
        return self._token


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
    def __init__(self, security: Security, token_store: TokenStore, token_resolvers = None):
        if token_resolvers is None:
            token_resolvers = lambda: []
        self._security = security
        self._token_store = token_store
        self._token_resolvers = token_resolvers
        self._list = {}

    async def add(self, path, role = None):
        self._list[path] = role

    async def list(self) -> dict:
        return self._list

    async def authenticate(self, request: Request):
        for _, service_get in self._token_resolvers():
            token_resolver = await service_get()
            token = token_resolver.resolve(request)
            if token is not None:
                await self._token_store.set(request, token)
                return

    async def is_granted(self, request: Request):
        path = request.path
        items = await self.list()
        for pattern, role in items.items():
            if re.match(pattern, path):
                if role is None:
                    return
                return await self._security.is_granted(request, role)

        return False