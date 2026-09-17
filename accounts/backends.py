"""Login by e-mail instead of username.

Django checks username by default. A customer has no reason to remember
one, so at registration the same e-mail is put into username, and here
the lookup is by email — case-insensitively.

One subtlety: if the e-mail somehow belongs to two records, nobody is let
in. Letting "the first one found" in would be a hole.
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
            # run the hashing anyway: otherwise the response time reveals
            # whether that e-mail exists in the database
            User().set_password(password)
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
