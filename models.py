"""Pydantic data models for the B2B lead parser."""
from typing import Optional
from pydantic import BaseModel


class MapLead(BaseModel):
    """Lead collected from Yandex Maps."""
    source: str = "Яндекс Карты"
    name: str = ""
    category: str = ""
    city: str = ""
    address: str = ""
    phone_raw: str = ""
    phone_e164: str = ""        # +79991234567
    phone_digits: str = ""      # 79991234567
    phone_type: str = ""        # Мобильный / Городской / Неизвестно
    wa_link_website: str = ""   # wa.me link with website offer
    wa_link_bot: str = ""       # wa.me link with bot offer
    tg_link: str = ""           # t.me/+79991234567
    offer_text: str = ""        # plain text offer for copy-paste
    maps_url: str = ""


class FreelanceLead(BaseModel):
    """Lead collected from a freelance exchange."""
    source: str = ""
    date: Optional[str] = None
    title: str = ""
    description: str = ""
    budget: str = ""
    order_url: str = ""
    profile_url: str = ""
    contact: str = ""           # TG/WA found in description
    response_draft: str = ""
