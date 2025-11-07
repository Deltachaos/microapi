import json
import os
from microapi import Container


class Translator:
    def __init__(self, messages, fallback_messages):
        self._messages = messages
        self._fallback_messages = fallback_messages

    def __call__(self, key: str, placeholders: dict = None) -> str:
        if placeholders is None:
            placeholders = {}
        
        message = self._messages.get(key)
        
        if message is None:
            message = self._fallback_messages.get(key)
        
        if message is None:
            return key
        
        try:
            return message.format(**placeholders)
        except (KeyError, ValueError):
            return message


class TranslatorMessageLoader:
    async def get(self, locale: str):
        return {}


class JsonFileTranslatorMessageLoader(TranslatorMessageLoader):
    def _directory(self):
        return "./locales/"

    async def get(self, locale: str):
        """
        Load translation messages from JSON file for the given locale.
        Supports locale fallback (e.g., de_DE -> de).
        """
        directory = self._directory()
        
        # Try the exact locale first
        file_path = os.path.join(directory, f"{locale}.json")
        
        if not os.path.exists(file_path):
            # Try locale fallback (e.g., de_DE -> de)
            if '_' in locale:
                fallback_locale = locale.split('_')[0]
                file_path = os.path.join(directory, f"{fallback_locale}.json")
        
        if not os.path.exists(file_path):
            return {}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError, OSError):
            return {}


class TranslatorFactory:
    def __init__(self, _: Container):
        self._ = _
        self._translator_message_loader = self._.tagged_generator('translator_message_loader')
        self._messages = {}

    async def default_locale(self):
        return "en"

    async def messages(self, locale: str = None):
        if locale is None:
            locale = await self.default_locale()

        if locale in self._messages:
            return self._messages[locale]

        self._messages[locale] = {}
        for loader_cls, get_loader in self._translator_message_loader():
            loader = await get_loader()
            _messages = await loader.get(locale)
            for key, value in _messages.items():
                self._messages[locale][key] = value

        return self._messages[locale]

    async def get(self, locale: str = None):
        return Translator(await self.messages(locale), await self.messages())