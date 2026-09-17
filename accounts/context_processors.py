"""What every page needs from the account.

Favourite products are fetched in one query — otherwise every tile in the
grid would hit the database for its own heart (twelve queries per page).
Nothing is fetched for a guest.
"""

from __future__ import annotations

from accounts.models import Favorite


def cabinet(request) -> dict:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"favorite_ids": frozenset(), "favorites_count": 0}
    ids = frozenset(
        Favorite.objects.filter(user=user).values_list("product_id", flat=True)
    )
    return {"favorite_ids": ids, "favorites_count": len(ids)}
