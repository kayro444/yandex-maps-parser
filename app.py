"""
Streamlit B2B Lead Parser — Полноценное веб-приложение.

Запуск:
    streamlit run app.py
"""
from __future__ import annotations

import asyncio
import concurrent.futures
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st

# ── Path fix so project modules are importable ────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from config import CITIES, NICHES
from models import MapLead, FreelanceLead

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="B2B Lead Parser",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "B2B Lead Parser v1.0 — Яндекс.Карты + биржи фриланса",
    },
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    /* Metrics cards */
    div[data-testid="stMetric"] {
        background: #1c2333;
        border-radius: 12px;
        padding: 18px 22px;
        border: 1px solid #2d3748;
        transition: border-color .2s;
    }
    div[data-testid="stMetric"]:hover { border-color: #00c4a7; }
    div[data-testid="stMetricValue"] { font-size: 2rem; font-weight: 700; }

    /* Tab styling */
    button[data-baseweb="tab"] { font-weight: 600; font-size: 0.95rem; }

    /* Sidebar header */
    .sidebar-logo {
        font-size: 1.6rem;
        font-weight: 800;
        background: linear-gradient(90deg, #00c4a7, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 4px;
    }

    /* Section headers */
    .section-header {
        font-size: 1.05rem;
        font-weight: 700;
        color: #00c4a7;
        margin: 16px 0 6px 0;
        padding-bottom: 4px;
        border-bottom: 1px solid #2d3748;
    }

    /* Offer preview card */
    .offer-card {
        background: #1c2333;
        border: 1px solid #2d3748;
        border-radius: 10px;
        padding: 16px 20px;
        margin: 8px 0;
        font-size: 0.9rem;
        line-height: 1.6;
    }

    /* Download button override */
    div[data-testid="stDownloadButton"] button {
        height: 56px;
        font-size: 1.1rem;
        font-weight: 700;
    }

    /* Expander */
    details summary { font-weight: 600; }

    /* Status badge emojis in dataframe */
    .stDataFrame { border-radius: 10px; overflow: hidden; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state init ────────────────────────────────────────────────────────
_DEFAULTS: dict = {
    "maps_leads": [],
    "freelance_leads": [],
    "last_run": None,
    "is_running": False,
    "run_log": [],
    "run_errors": [],
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v


# ── Async runner ──────────────────────────────────────────────────────────────
def run_async(coro) -> object:
    """
    Run an async coroutine in a fresh event loop in a worker thread.
    This avoids conflicts with Streamlit's own event loop on Windows.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


# ── DataFrame helpers ─────────────────────────────────────────────────────────
def maps_to_df(leads: List[MapLead]) -> pd.DataFrame:
    rows = []
    for ld in leads:
        rows.append(
            {
                " ": "🟢" if ld.phone_type == "Мобильный" else "⬜",
                "Название": ld.name,
                "Категория": ld.category,
                "Город": ld.city,
                "Адрес": ld.address,
                "Телефон": ld.phone_e164 or ld.phone_raw,
                "Тип": ld.phone_type,
                "WA Сайт": ld.wa_link_website,
                "WA Бот": ld.wa_link_bot,
                "Telegram": ld.tg_link,
                "Оффер (текст)": ld.offer_text,
                "На Карте": ld.maps_url,
            }
        )
    return pd.DataFrame(rows)


def freelance_to_df(leads: List[FreelanceLead]) -> pd.DataFrame:
    rows = []
    for ld in leads:
        desc = ld.description
        rows.append(
            {
                "Источник": ld.source,
                "Дата": ld.date or "",
                "Заголовок": ld.title,
                "Описание": desc[:130] + ("…" if len(desc) > 130 else ""),
                "Бюджет": ld.budget,
                "Заказ": ld.order_url,
                "Контакт": ld.contact,
                "Черновик отклика": ld.response_draft,
            }
        )
    return pd.DataFrame(rows)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown('<div class="sidebar-logo">🎯 B2B Parser</div>', unsafe_allow_html=True)
    st.caption("Лидогенерация из Яндекс.Карт и бирж фриланса")
    st.divider()

    # ── Sources ───────────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📡 Источники данных</div>', unsafe_allow_html=True)
    use_maps = st.checkbox("🗺️ Яндекс.Карты", value=True)
    use_habr = st.checkbox("Хабр Фриланс", value=True)
    use_fl   = st.checkbox("FL.ru", value=True)
    use_kwork = st.checkbox("Kwork", value=True)

    # ── Maps settings ─────────────────────────────────────────────────────────
    if use_maps:
        st.divider()
        st.markdown('<div class="section-header">🗺️ Настройки Карт</div>', unsafe_allow_html=True)
        cities_sel = st.multiselect(
            "Города", CITIES, default=CITIES[:2],
            help="Можно выбрать несколько городов одновременно",
        )
        niches_sel = st.multiselect(
            "Ниши / рубрики", NICHES, default=NICHES[:3],
            help="Парсер перебирает каждую комбинацию (город × ниша)",
        )
        max_results = st.slider(
            "Макс. карточек на запрос", 5, 100, 15, step=5,
            help="Ограничение числа карточек на одну комбинацию город+ниша",
        )
        headless_mode = st.toggle(
            "Скрытый браузер (headless)", value=True,
            help="Выключите чтобы видеть браузер — удобно для отладки",
        )
    else:
        cities_sel = CITIES[:1]
        niches_sel = NICHES[:2]
        max_results = 15
        headless_mode = True

    # ── Freelance settings ────────────────────────────────────────────────────
    if any([use_habr, use_fl, use_kwork]):
        st.divider()
        st.markdown('<div class="section-header">💼 Настройки бирж</div>', unsafe_allow_html=True)
        pages_cnt = st.slider(
            "Страниц пагинации", 1, 10, 2,
            help="Количество страниц листинга на каждой бирже",
        )
    else:
        pages_cnt = 2

    st.divider()

    nothing_selected = not any([use_maps, use_habr, use_fl, use_kwork])
    run_btn = st.button(
        "🚀 Запустить парсинг",
        use_container_width=True,
        type="primary",
        disabled=st.session_state.is_running or nothing_selected,
        help="Нажмите чтобы начать сбор лидов из выбранных источников",
    )
    if nothing_selected:
        st.caption("⚠️ Выберите хотя бы один источник")

    # ── Status strip ─────────────────────────────────────────────────────────
    total_now = len(st.session_state.maps_leads) + len(st.session_state.freelance_leads)
    if total_now:
        st.divider()
        st.success(f"В памяти: **{total_now}** лидов")
        if st.session_state.last_run:
            st.caption(f"Последний запуск: {st.session_state.last_run}")
        if st.button("🗑️ Очистить результаты", use_container_width=True):
            st.session_state.maps_leads = []
            st.session_state.freelance_leads = []
            st.session_state.run_log = []
            st.session_state.run_errors = []
            st.rerun()

    # ── Log ───────────────────────────────────────────────────────────────────
    if st.session_state.run_log:
        with st.expander("📄 Лог последнего запуска"):
            for line in st.session_state.run_log:
                st.code(line)
    if st.session_state.run_errors:
        with st.expander("❌ Ошибки"):
            for err in st.session_state.run_errors:
                st.error(err)


# ── Main header ───────────────────────────────────────────────────────────────
st.markdown("# 🎯 B2B Lead Parser")
st.markdown(
    "Автоматический поиск B2B-клиентов из **Яндекс.Карт** (компании без сайта) "
    "и бирж фриланса (**Хабр**, **FL.ru**, **Kwork**) с генерацией персонализированных "
    "WhatsApp/Telegram-офферов и экспортом в Excel."
)
st.divider()

# ── Metrics row ───────────────────────────────────────────────────────────────
maps_leads: List[MapLead] = st.session_state.maps_leads
freelance_leads: List[FreelanceLead] = st.session_state.freelance_leads

mobile_cnt   = sum(1 for ld in maps_leads if ld.phone_type == "Мобильный")
landline_cnt = sum(1 for ld in maps_leads if ld.phone_type == "Городской")
total_cnt    = len(maps_leads) + len(freelance_leads)

mc1, mc2, mc3, mc4, mc5 = st.columns(5)
mc1.metric("🗺️ Яндекс.Карты",      len(maps_leads),
           delta=None if not maps_leads else f"{mobile_cnt} мобильных")
mc2.metric("💼 Фриланс заказы",     len(freelance_leads))
mc3.metric("📱 Мобильных номеров",  mobile_cnt,
           delta="Приоритет WhatsApp", delta_color="off")
mc4.metric("☎️ Городских номеров",  landline_cnt)
mc5.metric("🏆 Всего лидов",        total_cnt)

st.divider()


# ── Run logic ─────────────────────────────────────────────────────────────────
if run_btn:
    st.session_state.is_running = True
    new_maps: List[MapLead] = []
    new_freelance: List[FreelanceLead] = []
    log: list = []
    errors: list = []

    sources_count = sum([use_maps, use_habr, use_fl, use_kwork])
    _step = [0]   # mutable container — avoids nonlocal inside if-block

    prog_bar   = st.progress(0, text="Инициализация...")
    status_box = st.empty()

    def _advance(label: str, n: int = 0) -> None:
        _step[0] += 1
        pct = int(_step[0] / sources_count * 90)
        prog_bar.progress(pct, text=label)
        if n:
            log.append(f"{label}: {n} лидов")
        status_box.info(f"⏳ {label}")

    try:
        if use_maps:
            _advance("Парсинг Яндекс.Карт…")
            from parsers.yandex_maps import scrape_yandex_maps
            new_maps = run_async(
                scrape_yandex_maps(
                    cities=cities_sel or CITIES[:1],
                    niches=niches_sel or NICHES[:2],
                    max_per_query=max_results,
                    headless=headless_mode,
                )
            )
            _advance(f"Яндекс.Карты готово", len(new_maps))

        if use_habr:
            _advance("Парсинг Хабр Фриланс…")
            from parsers.habr_freelance import scrape_habr_freelance
            habr_leads = run_async(scrape_habr_freelance(pages=pages_cnt))
            new_freelance.extend(habr_leads)
            _advance("Хабр Фриланс готово", len(habr_leads))

        if use_fl:
            _advance("Парсинг FL.ru…")
            from parsers.fl_ru import scrape_fl_ru
            fl_leads = run_async(scrape_fl_ru(pages=pages_cnt))
            new_freelance.extend(fl_leads)
            _advance("FL.ru готово", len(fl_leads))

        if use_kwork:
            _advance("Парсинг Kwork…")
            from parsers.kwork import scrape_kwork
            kwork_leads = run_async(scrape_kwork(pages=pages_cnt))
            new_freelance.extend(kwork_leads)
            _advance("Kwork готово", len(kwork_leads))

    except Exception as exc:
        errors.append(str(exc))
        status_box.error(f"Ошибка: {exc}")

    finally:
        st.session_state.maps_leads      = new_maps
        st.session_state.freelance_leads = new_freelance
        st.session_state.last_run        = datetime.now().strftime("%H:%M  %d.%m.%Y")
        st.session_state.run_log         = log
        st.session_state.run_errors      = errors
        st.session_state.is_running      = False

        prog_bar.progress(100, text="Готово!")
        found = len(new_maps) + len(new_freelance)
        if found:
            status_box.success(
                f"Парсинг завершён! Найдено **{found}** лидов. "
                + " | ".join(log)
            )
        else:
            status_box.warning(
                "Парсинг завершён, но лиды не найдены. "
                "Проверьте настройки и доступность сайтов."
            )
        st.rerun()


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_maps, tab_fl, tab_validator, tab_preview, tab_export = st.tabs([
    "🗺️  Яндекс.Карты",
    "💼  Фриланс",
    "📞  Валидатор номеров",
    "🛠️  Оффер-превью",
    "📥  Экспорт",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — Yandex Maps
# ════════════════════════════════════════════════════════════════════════════
with tab_maps:
    if not maps_leads:
        st.info(
            "Здесь появятся лиды из Яндекс.Карт после запуска парсинга. \n\n"
            "Убедитесь, что выбран источник **🗺️ Яндекс.Карты** в боковой панели."
        )
    else:
        # ── Filters ──────────────────────────────────────────────────────────
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            filt_type = st.selectbox(
                "Тип номера",
                ["Все", "Мобильный", "Городской", "Неизвестно"],
                key="m_ftype",
            )
        with fc2:
            city_opts = sorted({ld.city for ld in maps_leads if ld.city})
            filt_city = st.selectbox("Город", ["Все"] + city_opts, key="m_fcity")
        with fc3:
            cat_opts = sorted({ld.category for ld in maps_leads if ld.category})
            filt_cat = st.selectbox("Категория", ["Все"] + cat_opts, key="m_fcat")

        filtered_maps = maps_leads
        if filt_type != "Все":
            filtered_maps = [ld for ld in filtered_maps if ld.phone_type == filt_type]
        if filt_city != "Все":
            filtered_maps = [ld for ld in filtered_maps if ld.city == filt_city]
        if filt_cat != "Все":
            filtered_maps = [ld for ld in filtered_maps if ld.category == filt_cat]

        cnt_mob = sum(1 for ld in filtered_maps if ld.phone_type == "Мобильный")
        cnt_land = len(filtered_maps) - cnt_mob
        st.caption(
            f"Показано **{len(filtered_maps)}** из **{len(maps_leads)}** лидов  "
            f"| 🟢 Мобильных: {cnt_mob}  | ⬜ Остальных: {cnt_land}"
        )

        if filtered_maps:
            df_maps = maps_to_df(filtered_maps)
            st.dataframe(
                df_maps,
                column_config={
                    " ": st.column_config.TextColumn("", width=36),
                    "WA Сайт":      st.column_config.LinkColumn("📲 WA Сайт",  display_text="Открыть"),
                    "WA Бот":       st.column_config.LinkColumn("🤖 WA Бот",   display_text="Открыть"),
                    "Telegram":     st.column_config.LinkColumn("✈️ Telegram",  display_text="Открыть"),
                    "На Карте":     st.column_config.LinkColumn("🗺️ Карта",    display_text="Открыть"),
                    "Оффер (текст)": st.column_config.TextColumn("Текст оффера", width="large"),
                    "Название":     st.column_config.TextColumn("Название",   width="medium"),
                    "Адрес":        st.column_config.TextColumn("Адрес",      width="medium"),
                },
                use_container_width=True,
                hide_index=True,
                height=min(52 + len(filtered_maps) * 36, 600),
            )

            # ── Offer preview expander ────────────────────────────────────
            with st.expander(f"📋 Офферы первых {min(5, len(filtered_maps))} лидов"):
                for ld in filtered_maps[:5]:
                    col_a, col_b = st.columns([1, 2])
                    with col_a:
                        st.markdown(f"**{ld.name}**")
                        st.caption(f"{ld.city} · {ld.category}")
                        st.code(ld.phone_e164 or ld.phone_raw, language=None)
                        badge = "🟢 Мобильный" if ld.phone_type == "Мобильный" else "⬜ " + ld.phone_type
                        st.caption(badge)
                    with col_b:
                        st.markdown("**Оффер «Создание сайта»:**")
                        st.info(ld.offer_text)
                        if ld.wa_link_website:
                            st.markdown(f"[📲 Открыть в WhatsApp]({ld.wa_link_website})")
                    st.divider()
        else:
            st.warning("По выбранным фильтрам ничего не найдено.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — Freelance
# ════════════════════════════════════════════════════════════════════════════
with tab_fl:
    if not freelance_leads:
        st.info(
            "Здесь появятся заказы из бирж фриланса. \n\n"
            "Выберите **Хабр Фриланс**, **FL.ru** или **Kwork** в боковой панели и запустите парсинг."
        )
    else:
        sources_present = sorted({ld.source for ld in freelance_leads})
        filt_src = st.multiselect(
            "Источник", sources_present, default=sources_present, key="fl_fsrc"
        )
        filtered_fl = [ld for ld in freelance_leads if ld.source in filt_src]
        st.caption(f"Показано **{len(filtered_fl)}** из **{len(freelance_leads)}** заказов")

        if filtered_fl:
            df_fl = freelance_to_df(filtered_fl)
            st.dataframe(
                df_fl,
                column_config={
                    "Заказ":              st.column_config.LinkColumn("🔗 Заказ",       display_text="Смотреть"),
                    "Заголовок":          st.column_config.TextColumn("Заголовок",       width="large"),
                    "Черновик отклика":   st.column_config.TextColumn("Черновик отклика", width="large"),
                    "Описание":           st.column_config.TextColumn("Описание",        width="medium"),
                },
                use_container_width=True,
                hide_index=True,
                height=min(52 + len(filtered_fl) * 36, 600),
            )

            with st.expander(f"📋 Черновики откликов первых {min(5, len(filtered_fl))} заказов"):
                for ld in filtered_fl[:5]:
                    st.markdown(f"### {ld.title}")
                    info_cols = st.columns(3)
                    info_cols[0].caption(f"🏷️ Источник: **{ld.source}**")
                    info_cols[1].caption(f"💰 Бюджет: **{ld.budget or 'не указан'}**")
                    info_cols[2].caption(f"📅 Дата: **{ld.date or '—'}**")
                    if ld.contact:
                        st.markdown(f"📱 Найденный контакт: `{ld.contact}`")
                    st.success(ld.response_draft)
                    if ld.order_url:
                        st.markdown(f"[🔗 Открыть заказ]({ld.order_url})")
                    st.divider()
        else:
            st.warning("По выбранным фильтрам ничего не найдено.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — Phone Validator
# ════════════════════════════════════════════════════════════════════════════
with tab_validator:
    st.markdown("### 📞 Валидатор и нормализатор номеров")
    st.markdown(
        "Проверьте любой российский номер телефона: получите E.164-формат, "
        "тип линии и готовые WhatsApp/Telegram ссылки."
    )

    from utils.contacts import process_phone, classify_phone

    val_input = st.text_input(
        "Введите номер",
        placeholder="+7 (999) 123-45-67  или  8 (495) 555-11-22",
        key="val_phone_input",
    )

    if val_input:
        result = process_phone(val_input.strip())
        if result:
            v1, v2, v3 = st.columns(3)
            v1.metric("E.164 формат",    result["e164"])
            v2.metric("Только цифры",    result["digits"])
            v3.metric("Тип линии",       result["type"])

            st.success("✅ Номер валиден")

            from utils.templates import (
                build_wa_link,
                build_tg_link_by_phone,
                render_website_offer,
                render_bot_offer,
            )

            sample_company = st.text_input(
                "Название компании (для оффера)",
                value="Ваша компания",
                key="val_company",
            )
            sample_niche = st.text_input(
                "Ниша (для оффера)",
                value="услуги",
                key="val_niche",
            )

            offer_site = render_website_offer(sample_company, sample_niche)
            offer_bot  = render_bot_offer(sample_company, sample_niche)

            lc1, lc2, lc3 = st.columns(3)
            wa_site = build_wa_link(result["digits"], offer_site)
            wa_bot  = build_wa_link(result["digits"], offer_bot)
            tg_link = build_tg_link_by_phone(result["e164"])

            lc1.link_button("📲 WhatsApp (Сайт)", wa_site, use_container_width=True)
            lc2.link_button("🤖 WhatsApp (Бот)",  wa_bot,  use_container_width=True)
            lc3.link_button("✈️ Telegram",         tg_link, use_container_width=True)

            st.divider()
            st.markdown("**Сгенерированные ссылки:**")
            st.code(f"WhatsApp (Сайт) : {wa_site}", language=None)
            st.code(f"WhatsApp (Бот)  : {wa_bot}",  language=None)
            st.code(f"Telegram        : {tg_link}",  language=None)
        else:
            st.error(
                "❌ Номер не прошёл валидацию.\n\n"
                "Проверьте формат: +79991234567, 8 (999) 123-45-67, +7 495 555 11 22"
            )

    # ── Bulk validator ────────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 📋 Массовая проверка номеров")
    bulk_input = st.text_area(
        "Вставьте номера (каждый с новой строки)",
        placeholder="+79991234567\n+74951234567\n8-800-555-35-35",
        height=120,
        key="bulk_phones",
    )
    if bulk_input.strip():
        lines = [ln.strip() for ln in bulk_input.strip().splitlines() if ln.strip()]
        bulk_results = []
        for raw in lines:
            info = process_phone(raw)
            bulk_results.append({
                "Номер (исходный)": raw,
                "E.164":            info["e164"] if info else "❌ невалиден",
                "Цифры":            info["digits"] if info else "",
                "Тип":              info["type"] if info else "",
                "Валиден":          "✅" if info else "❌",
            })
        df_bulk = pd.DataFrame(bulk_results)
        valid_count = df_bulk["Валиден"].eq("✅").sum()
        st.caption(f"Валидных: **{valid_count}** из **{len(lines)}**")
        st.dataframe(df_bulk, use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — Offer Preview
# ════════════════════════════════════════════════════════════════════════════
with tab_preview:
    st.markdown("### 🛠️ Генератор и превью офферов")
    st.markdown(
        "Введите данные компании и получите персонализированный оффер с готовыми "
        "WhatsApp-ссылками — можно сразу скопировать или протестировать."
    )

    from utils.templates import (
        render_website_offer,
        render_bot_offer,
        render_freelance_response,
        build_wa_link,
        build_tg_link_by_phone,
    )
    from utils.contacts import process_phone as _proc_phone

    pr1, pr2 = st.columns(2)
    with pr1:
        p_company = st.text_input("Название компании", "Кофейня Арома", key="prev_company")
        p_niche   = st.text_input("Ниша / категория",  "кафе",          key="prev_niche")
    with pr2:
        p_phone   = st.text_input("Телефон",           "+79991234567",  key="prev_phone")
        p_info    = _proc_phone(p_phone.strip()) if p_phone.strip() else None
        if p_info:
            st.success(f"✅ {p_info['e164']} · {p_info['type']}")
        elif p_phone.strip():
            st.error("❌ Невалидный номер")

    if p_company and p_niche:
        offer_site = render_website_offer(p_company, p_niche)
        offer_bot  = render_bot_offer(p_company, p_niche)

        st.divider()
        oc1, oc2 = st.columns(2)

        with oc1:
            st.markdown("#### 🌐 Оффер «Создание сайта»")
            st.info(offer_site)
            if p_info:
                wa_s = build_wa_link(p_info["digits"], offer_site)
                st.link_button("📲 Открыть в WhatsApp", wa_s, use_container_width=True)

        with oc2:
            st.markdown("#### 🤖 Оффер «Telegram-бот»")
            st.info(offer_bot)
            if p_info:
                wa_b = build_wa_link(p_info["digits"], offer_bot)
                st.link_button("📲 Открыть в WhatsApp", wa_b, use_container_width=True)

        if p_info:
            tg = build_tg_link_by_phone(p_info["e164"])
            st.divider()
            st.markdown(f"**✈️ Telegram-ссылка:** [{tg}]({tg})")

    # ── Freelance draft ───────────────────────────────────────────────────────
    st.divider()
    st.markdown("#### 💼 Черновик отклика на биржевой заказ")
    p_title = st.text_input("Заголовок заказа", "Нужен сайт для кофейни", key="prev_title")
    if p_title:
        draft = render_freelance_response(p_title)
        st.success(draft)
        st.caption("Скопируйте текст и адаптируйте под конкретный заказ")


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — Export
# ════════════════════════════════════════════════════════════════════════════
with tab_export:
    st.markdown("### 📥 Экспорт результатов")

    if total_cnt == 0:
        st.info(
            "Нет данных для экспорта.\n\n"
            "Запустите парсинг с помощью кнопки **🚀 Запустить парсинг** в боковой панели."
        )
    else:
        # ── Summary cards ─────────────────────────────────────────────────
        ec1, ec2, ec3, ec4 = st.columns(4)
        ec1.metric("Строк в «Карты»",   len(maps_leads))
        ec2.metric("Строк в «Фриланс»", len(freelance_leads))
        ec3.metric("Из них мобильных",  mobile_cnt)
        ec4.metric("Итого лидов",       total_cnt)

        st.divider()

        # ── Download button ───────────────────────────────────────────────
        col_dl, col_save = st.columns([2, 1])
        with col_dl:
            try:
                from exporters.excel import export_to_bytes as _exp_bytes
                excel_bytes = _exp_bytes(maps_leads, freelance_leads)
                fname = f"b2b_leads_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
                st.download_button(
                    label="📥 Скачать Excel",
                    data=excel_bytes,
                    file_name=fname,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type="primary",
                    use_container_width=True,
                    help="Файл содержит 3 листа: Карты, Фриланс, Сводка",
                )
                st.caption(
                    f"Файл: **{fname}** · "
                    f"Размер: ~{len(excel_bytes) // 1024 + 1} КБ · "
                    f"Листов: 3"
                )
            except Exception as exc:
                st.error(f"Ошибка генерации Excel: {exc}")

        with col_save:
            if st.button("💾 Сохранить на диск", use_container_width=True,
                         help="Сохранить в папку output/ проекта"):
                try:
                    from exporters.excel import export_to_excel
                    saved = export_to_excel(maps_leads, freelance_leads)
                    st.success(f"Сохранено:\n`{saved}`")
                except Exception as exc:
                    st.error(str(exc))

        # ── Charts ────────────────────────────────────────────────────────
        st.divider()
        st.markdown("#### 📊 Статистика по лидам")

        chart1, chart2 = st.columns(2)

        with chart1:
            st.markdown("**Типы номеров (Яндекс.Карты)**")
            if maps_leads:
                phone_stats = pd.DataFrame(
                    {
                        "Тип": ["🟢 Мобильный", "⬜ Городской", "❔ Неизвестно"],
                        "Кол-во": [
                            sum(1 for ld in maps_leads if ld.phone_type == "Мобильный"),
                            sum(1 for ld in maps_leads if ld.phone_type == "Городской"),
                            sum(1 for ld in maps_leads if ld.phone_type == "Неизвестно"),
                        ],
                    }
                ).set_index("Тип")
                st.bar_chart(phone_stats)
            else:
                st.caption("Нет данных из Яндекс.Карт")

        with chart2:
            st.markdown("**Заказы по биржам (Фриланс)**")
            if freelance_leads:
                src_stats: dict = {}
                for ld in freelance_leads:
                    src_stats[ld.source] = src_stats.get(ld.source, 0) + 1
                df_src = pd.DataFrame.from_dict(
                    src_stats, orient="index", columns=["Заказов"]
                )
                st.bar_chart(df_src)
            else:
                st.caption("Нет данных из бирж фриланса")

        # ── City breakdown ────────────────────────────────────────────────
        if maps_leads:
            st.markdown("**Лиды из Яндекс.Карт по городам**")
            city_stats: dict = {}
            for ld in maps_leads:
                city_stats[ld.city or "—"] = city_stats.get(ld.city or "—", 0) + 1
            df_city = pd.DataFrame.from_dict(
                city_stats, orient="index", columns=["Компаний"]
            ).sort_values("Компаний", ascending=False)
            st.bar_chart(df_city)

        # ── Data preview ──────────────────────────────────────────────────
        st.divider()
        with st.expander("🔍 Предпросмотр данных для экспорта"):
            if maps_leads:
                st.markdown(f"**Яндекс.Карты** (первые 5 из {len(maps_leads)}):")
                st.dataframe(
                    maps_to_df(maps_leads[:5]),
                    use_container_width=True,
                    hide_index=True,
                )
            if freelance_leads:
                st.markdown(f"**Фриланс заказы** (первые 5 из {len(freelance_leads)}):")
                st.dataframe(
                    freelance_to_df(freelance_leads[:5]),
                    use_container_width=True,
                    hide_index=True,
                )
