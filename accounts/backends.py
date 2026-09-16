"""Вход по почте вместо имени пользователя.

Django по умолчанию сверяет username. Покупателю помнить ещё и его
незачем, поэтому при регистрации мы кладём в username ту же почту,
а здесь ищем по email — без учёта регистра.

Отдельная тонкость: если почта почему-то досталась двум записям,
не пускаем никого. Пустить «первого попавшегося» — это дыра.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        login = username or kwargs.get("email") or ""
        if not login or password is None:
            return None
        try:
            user = User.objects.get(email__iexact=login.strip())
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            # прогоняем хеширование вхолостую: иначе по времени ответа
            # видно, есть такая почта в базе или нет
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
