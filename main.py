"""
B2B Lead Parser — CLI entry point.

Usage examples:
    python main.py --source maps --city Москва --niche кафе
    python main.py --source freelance
    python main.py --source all --city Казань --niche ресторан --pages 5
    python main.py --source all --headless false --output my_leads.xlsx
"""
import argparse
import asyncio
import sys
from pathlib import Path

from config import CITIES, NICHES, EXCEL_FILENAME, OUTPUT_DIR
from exporters.excel import export_to_excel
from models import MapLead, FreelanceLead


# ─── Argument parser ──────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="b2b-parser",
        description="B2B Lead Parser — Яндекс.Карты + биржи фриланса",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--source",
        choices=["maps", "freelance", "habr", "fl", "kwork", "all"],
        default="all",
        help=(
            "Источник данных: maps (только Карты), freelance (все биржи), "
            "habr/fl/kwork (конкретная биржа), all (всё сразу). "
            "По умолчанию: all"
        ),
    )
    parser.add_argument(
        "--city",
        nargs="+",
        default=None,
        metavar="ГОРОД",
        help=(
            "Город(а) для поиска в Яндекс.Картах. "
            "Если не задан — берётся список из config.py."
        ),
    )
    parser.add_argument(
        "--niche",
        nargs="+",
        default=None,
        metavar="НИША",
        help=(
            "Ниша(и) для поиска в Яндекс.Картах. "
            "Если не задана — берётся список из config.py."
        ),
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=30,
        metavar="N",
        help="Максимум карточек на одну комбинацию (город × ниша). По умолчанию: 30",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=3,
        metavar="N",
        help="Количество страниц пагинации для каждой биржи фриланса. По умолчанию: 3",
    )
    parser.add_argument(
        "--headless",
        type=lambda v: v.lower() not in ("false", "0", "no"),
        default=True,
        metavar="BOOL",
        help=(
            "Запускать браузер в фоновом режиме (true/false). "
            "false — откроет видимое окно браузера. По умолчанию: true"
        ),
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="ФАЙЛ.xlsx",
        help=(
            "Путь к выходному .xlsx файлу. "
            f"По умолчанию: {EXCEL_FILENAME}"
        ),
    )

    return parser


# ─── Runner helpers ───────────────────────────────────────────────────────────

async def run_maps(
    cities: list,
    niches: list,
    max_results: int,
    headless: bool,
) -> list:
    from parsers.yandex_maps import scrape_yandex_maps
    return await scrape_yandex_maps(
        cities=cities,
        niches=niches,
        max_per_query=max_results,
        headless=headless,
    )


async def run_habr(pages: int) -> list:
    from parsers.habr_freelance import scrape_habr_freelance
    return await scrape_habr_freelance(pages=pages)


async def run_fl(pages: int) -> list:
    from parsers.fl_ru import scrape_fl_ru
    return await scrape_fl_ru(pages=pages)


async def run_kwork(pages: int) -> list:
    from parsers.kwork import scrape_kwork
    return await scrape_kwork(pages=pages)


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    cities = args.city or CITIES
    niches = args.niche or NICHES

    maps_leads: list[MapLead] = []
    freelance_leads: list[FreelanceLead] = []

    source = args.source

    # ── Yandex Maps ──────────────────────────────────────────────────────────
    if source in ("maps", "all"):
        print("\n=== Яндекс.Карты ===")
        maps_leads = await run_maps(
            cities=cities,
            niches=niches,
            max_results=args.max_results,
            headless=args.headless,
        )

    # ── Freelance exchanges ───────────────────────────────────────────────────
    if source in ("habr", "freelance", "all"):
        print("\n=== Хабр Фриланс ===")
        freelance_leads += await run_habr(pages=args.pages)

    if source in ("fl", "freelance", "all"):
        print("\n=== FL.ru ===")
        freelance_leads += await run_fl(pages=args.pages)

    if source in ("kwork", "freelance", "all"):
        print("\n=== Kwork ===")
        freelance_leads += await run_kwork(pages=args.pages)

    # ── Export ────────────────────────────────────────────────────────────────
    if not maps_leads and not freelance_leads:
        print("\n⚠️  Лиды не найдены. Проверьте настройки и доступность сайтов.")
        sys.exit(0)

    output_path = Path(args.output) if args.output else EXCEL_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\n=== Экспорт в Excel ===")
    saved_path = export_to_excel(
        maps_leads=maps_leads,
        freelance_leads=freelance_leads,
        output_path=output_path,
    )

    print(f"\n✅ Готово!")
    print(f"   📊 Яндекс.Карты:    {len(maps_leads)} лидов")
    print(f"   💼 Фриланс заказы:  {len(freelance_leads)} лидов")
    print(f"   📁 Файл сохранён:   {saved_path}")


if __name__ == "__main__":
    asyncio.run(main())
