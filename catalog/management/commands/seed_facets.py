"""Заводит строки раздела «Панель подбора» — по одной на справочник.

Сами значения живут в справочниках, а эта команда решает, какие группы
показывать покупателю по умолчанию. Запускается из ЗАПУСТИТЬ-КОПИЮ.bat и
безопасна для повторного запуска: настройки, которые вы поменяли руками,
не трогает.

Украинская подпись берётся из переводов (locale/uk), а не из словаря
в коде: одна и та же строка «Цветы» переводится один раз в .po и
работает и здесь, и в карточке товара. Поэтому порядок такой:
makelocales → перевод → compilelocales → seed_facets (грабля 22).
Если перевода ещё нет, подпись остаётся пустой и команда об этом
предупреждает — следующий запуск её дозаполнит.
"""

from django.core.management.base import BaseCommand
from django.utils.translation import trans_real

from catalog.facets import FACETS
from catalog.models import FacetGroup


def ukrainian(label: str) -> str:
    """Перевод подписи из .po; пусто, если перевода нет.

    Смотрим прямо в каталог, а не через gettext: «Тип» по-украински
    тоже «Тип», и по совпадению строк не отличить перевод от его
    отсутствия.
    """
    return trans_real.translation("uk")._catalog.get(label, "")


class Command(BaseCommand):
    help = "Создаёт группы панели подбора по реестру справочников"

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
                mark = "в подборе" if spec.in_filter else "только в карточке товара"
                self.stdout.write(f"  {spec.label} — {mark}")
            else:
                kept += 1
                # подпись появилась в переводах позже — дозаполняем,
                # но то, что владелец вписал руками, не трогаем
                if not group.name_uk and name_uk:
                    group.name_uk = name_uk
                    group.save(update_fields=["name_uk", "updated_at"])
        self.stdout.write(self.style.SUCCESS(
            f"Панель подбора: создано {created}, уже было {kept}."
        ))
        if missing:
            self.stdout.write(self.style.WARNING(
                "Нет украинского перевода подписей: " + ", ".join(missing)
                + ". Сначала makelocales → перевод → compilelocales."
            ))
