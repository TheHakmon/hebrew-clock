"""Fetch the next major Jewish holiday from hebcal.com with nikud."""
import datetime
import httpx
from loguru import logger

_CACHE_TTL = 3600 * 6  # refresh every 6 hours

# Nikud mapping for major holidays
HOLIDAYS_NIKUD: dict[str, str] = {
    "Rosh Hashana":       "רֹאשׁ הַשָּׁנָה",
    "Rosh Hashana II":    "רֹאשׁ הַשָּׁנָה ב׳",
    "Yom Kippur":         "יוֹם כִּיפּוּר",
    "Sukkot":             "סֻכּוֹת",
    "Sukkot II":          "סֻכּוֹת ב׳",
    "Shmini Atzeret":     "שְׁמִינִי עֲצֶרֶת",
    "Simchat Torah":      "שִׂמְחַת תּוֹרָה",
    "Chanukah":           "חֲנֻכָּה",
    "Tu BiShvat":         "ט\"וּ בִּשְׁבָט",
    "Purim":              "פּוּרִים",
    "Shushan Purim":      "שׁוּשַׁן פּוּרִים",
    "Pesach":             "פֶּסַח",
    "Pesach II":          "פֶּסַח ב׳",
    "Pesach Sheni":       "פֶּסַח שֵׁנִי",
    "Lag BaOmer":         "לַ\"ג בָּעֹמֶר",
    "Shavuot":            "שָׁבוּעוֹת",
    "Shavuot II":         "שָׁבוּעוֹת ב׳",
    "Tish'a B'Av":        "תִּשְׁעָה בְּאָב",
    "Yom HaShoah":        "יוֹם הַשּׁוֹאָה",
    "Yom HaZikaron":      "יוֹם הַזִּכָּרוֹן",
    "Yom HaAtzmaut":      "יוֹם הָעַצְמָאוּת",
    "Yom Yerushalayim":   "יוֹם יְרוּשָׁלַיִם",
    "Rosh Chodesh":       "רֹאשׁ חֹדֶשׁ",
}

# Days-until text with nikud
def days_text(n: int) -> str:
    if n == 0:
        return "הַיּוֹם!"
    if n == 1:
        return "מָחָר"
    if n == 2:
        return "עוֹד יוֹמַיִם"
    return f"עוֹד {n} יָמִים"


_cache: dict[str, object] = {}


def _nikud_for(title: str) -> str | None:
    """Find nikud for a holiday title (handles prefix matches)."""
    for key, nikud in HOLIDAYS_NIKUD.items():
        if title == key or title.startswith(key + ":") or title.startswith(key + " "):
            return nikud
        if key == title.split(":")[0].strip():
            return nikud
    # Chanukah variations like "Chanukah: 1 Candle" → חֲנֻכָּה
    if "Chanukah" in title:
        return HOLIDAYS_NIKUD["Chanukah"]
    return None


async def get_next_holiday(client: httpx.AsyncClient) -> tuple[str, int] | None:
    """
    Return (holiday_name_with_nikud, days_until_as_int) for the next major holiday,
    or None if unavailable.
    """
    entry = _cache.get("next")
    if entry and isinstance(entry, dict):
        cached_at = entry.get("time")
        if cached_at and (datetime.datetime.utcnow() - cached_at).total_seconds() < _CACHE_TTL:
            return entry.get("data")

    today = datetime.date.today()
    all_items: list[dict] = []

    try:
        # Fetch current month + next 5 months to always find something upcoming
        for delta_months in range(6):
            ref = today + datetime.timedelta(days=delta_months * 30)
            url = (
                "https://www.hebcal.com/hebcal"
                f"?v=1&cfg=json&maj=on&min=off&nx=off&ss=off&mf=off&c=off"
                f"&geo=IL&i=on&year={ref.year}&month={ref.month}"
            )
            resp = await client.get(url, timeout=10)
            resp.raise_for_status()
            all_items.extend(resp.json().get("items", []))

        # Sort by date ascending, find first holiday >= today
        all_items.sort(key=lambda x: x.get("date", ""))
        seen: set[str] = set()  # deduplicate across month boundaries

        for item in all_items:
            if item.get("category") != "holiday":
                continue
            title = item.get("title", "")
            date_str = item.get("date", "")[:10]  # "YYYY-MM-DD"
            if not date_str or date_str in seen:
                continue
            try:
                holiday_date = datetime.date.fromisoformat(date_str)
            except ValueError:
                continue
            if holiday_date < today:
                continue

            nikud = _nikud_for(title)
            if nikud is None:
                continue  # skip holidays not in our list

            seen.add(date_str)
            n_days = (holiday_date - today).days
            result: tuple[str, int] = (nikud, n_days)
            _cache["next"] = {"data": result, "time": datetime.datetime.utcnow()}
            logger.info("next holiday: {} in {} days ({})", nikud, n_days, date_str)
            return result

        logger.warning("no upcoming holiday found in next 6 months")
        return None

    except Exception as exc:
        logger.warning("holiday fetch error: {}", exc)
        # Return stale cache if available
        if isinstance(entry, dict):
            return entry.get("data")
        return None
