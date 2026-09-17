"""Footer links — built from the pages table.

The footer is drawn on every page of the site, so nothing here may crash:
if the table does not exist yet (migrations not applied) or the database
is temporarily unavailable, empty lists are returned — the columns simply
do not show.
"""

from django.db import DatabaseError

from pages.models import InfoPage

# the page the consent checkbox under the order form links to
PRIVACY_SLUG = "politika-konfidentsialnosti"


def footer_links(request) -> dict:
    try:
        pages = list(InfoPage.objects.active())
    except DatabaseError:
        pages = []
    visible = [p for p in pages if p.group != InfoPage.Group.HIDDEN]
    return {
        "footer_buyer": [p for p in visible if p.group == InfoPage.Group.BUYER],
        "footer_partner": [p for p in visible if p.group == InfoPage.Group.PARTNER],
        # if the page does not exist yet, the link under the checkbox is
        # simply not shown — the form does not break
        "privacy_page": next((p for p in pages if p.slug == PRIVACY_SLUG), None),
    }
