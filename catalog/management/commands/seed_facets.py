"""Creates the "Filter panel" rows — one per reference model.

The values themselves live in the reference models; this command decides
which groups are shown to the customer by default. Run by start.bat and
safe to run again: settings changed by hand are not touched.

The Ukrainian label comes from the translations (locale/uk), not from a
dictionary in code: the same string "Цветы" is translated once in .po and
works both here and on the product page. Hence the order:
makelocales → translate → compilelocales → seed_facets.
If there is no translation yet, the label stays empty and the command
warns about it — the next run fills it in.
"""

from django.core.management.base import BaseCommand
from django.utils.translation import trans_real

from catalog.facets import FACETS
from catalog.models import FacetGroup


def ukrainian(label: str) -> str:
    """Label translation from .po; empty if there is none.

    Read straight from the catalog, not via gettext: "Тип" is also "Тип"
    in Ukrainian, and by string equality a translation cannot be told
    apart from its absence.
    """
    return trans_real.translation("uk")._catalog.get(label, "")


class Command(BaseCommand):
    help = "Creates filter panel groups from the reference model registry"

    def handle(self, *args, **options):
        created = kept = 0
        missing = []
        for spec in FACETS:
            name_uk = ukrainian(spec.label)
            if not name_uk:
                missing.append(spec.label)
            group, is_new = FacetGroup.objects.get_or_create(
                code=spec.code,
                defaults={
                    "name": spec.label,
                    "name_uk": name_uk,
                    "position": spec.position,
                    "is_active": spec.in_filter,
                    "has_search": spec.searchable,
                },
            )
            if is_new:
                created += 1
                mark = "in the filter panel" if spec.in_filter else "product page only"
                self.stdout.write(f"  {spec.label} — {mark}")
            else:
                kept += 1
                # the label appeared in the translations later — fill it in,
                # but do not touch what the owner typed by hand
                if not group.name_uk and name_uk:
                    group.name_uk = name_uk
                    group.save(update_fields=["name_uk", "updated_at"])
        self.stdout.write(self.style.SUCCESS(
            f"Filter panel: created {created}, already existed {kept}."
        ))
        if missing:
            self.stdout.write(self.style.WARNING(
                "No Ukrainian translation for labels: " + ", ".join(missing)
                + ". Run makelocales → translate → compilelocales first."
            ))
