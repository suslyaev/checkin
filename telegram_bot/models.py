from django.db import models

class FSMState(models.Model):
    bot_id = models.BigIntegerField(null=False)
    chat_id = models.BigIntegerField(null=False)
    user_id = models.BigIntegerField(null=False)
    state = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        unique_together = ('bot_id', 'chat_id', 'user_id')
        verbose_name = 'Состояние пользователя в боте'


class FSMData(models.Model):
    bot_id = models.BigIntegerField(null=False)
    chat_id = models.BigIntegerField(null=False)
    user_id = models.BigIntegerField(null=False)
    data = models.JSONField(default=dict)

    class Meta:
        unique_together = ('bot_id', 'chat_id', 'user_id')
        verbose_name = 'Данные пользователя в боте'
