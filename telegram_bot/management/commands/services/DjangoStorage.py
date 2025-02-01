from typing import Any, Dict, Optional
from aiogram.fsm.storage.base import BaseStorage, StorageKey
from aiogram.fsm.state import State
from django.db import transaction
from asgiref.sync import sync_to_async

from telegram_bot.models import FSMState, FSMData


class DjangoStorage(BaseStorage):
    @sync_to_async
    def set_state(self, key: StorageKey, state: Optional[State] = None) -> None:
        with transaction.atomic():
            fsm_state, created = FSMState.objects.get_or_create(
                bot_id=key.bot_id,
                chat_id=key.chat_id,
                user_id=key.user_id,
            )
            fsm_state.state = state.state if state is not None else None
            fsm_state.save()

    @sync_to_async
    def get_state(self, key: StorageKey) -> Optional[str]:
        try:
            fsm_state = FSMState.objects.get(
                bot_id=key.bot_id,
                chat_id=key.chat_id,
                user_id=key.user_id,
            )
            return fsm_state.state
        except FSMState.DoesNotExist:
            return None

    @sync_to_async
    def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        with transaction.atomic():
            fsm_data, created = FSMData.objects.get_or_create(
                bot_id=key.bot_id,
                chat_id=key.chat_id,
                user_id=key.user_id,
            )
            fsm_data.data = data
            fsm_data.save()

    @sync_to_async
    def get_data(self, key: StorageKey) -> Dict[str, Any]:
        try:
            fsm_data = FSMData.objects.get(
                bot_id=key.bot_id,
                chat_id=key.chat_id,
                user_id=key.user_id,
            )
            return fsm_data.data
        except FSMData.DoesNotExist:
            return {}

    async def update_data(self, key: StorageKey, data: Dict[str, Any]) -> Dict[str, Any]:
        current_data = await self.get_data(key=key)
        current_data.update(data)
        await self.set_data(key=key, data=current_data)
        return current_data

    async def close(self) -> None:
        pass
