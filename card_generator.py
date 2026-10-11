"""
Dead by Daylight loadout card generator using Pillow.
Produces stylized, high-contrast HUD cards reminiscent of DBD's interface.
Features in-memory icon caching for ultra-fast rendering (<10ms).
"""
import io
import math
import urllib.parse
from typing import List, Dict, Any, Optional, Tuple
import aiohttp
from PIL import Image, ImageDraw, ImageFont
from constants import TIER_RGB

# In-memory image cache: url -> PIL.Image.Image (RGBA)
_ICON_CACHE: Dict[str, Image.Image] = {}

def get_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    """Finds system fonts (Segoe UI / Arial) with fallback."""
    font_candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
        r"/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else r"/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in font_candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except Exception:
            continue
    return ImageFont.load_default()

def draw_diamond(
    draw: ImageDraw.ImageDraw,
    center: Tuple[int, int],
    size: int,
    fill_color: tuple,
    outline_color: tuple,
    width: int = 3
):
    """Draws a diamond polygon (classic DBD perk shape)."""
    cx, cy = center
    r = size // 2
    points = [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)]
    draw.polygon(points, fill=fill_color, outline=outline_color, width=width)

def draw_star(draw: ImageDraw.ImageDraw, center: Tuple[int, int], radius: float, fill_color: tuple):
    """Draws a crisp 5-pointed vector star (eliminates missing character box bug)."""
    cx, cy = center
    points = []
    for i in range(10):
        r = radius if i % 2 == 0 else radius * 0.42
        angle = -math.pi / 2 + i * math.pi / 5
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        points.append((x, y))
    draw.polygon(points, fill=fill_color)

async def fetch_image(session: aiohttp.ClientSession, url: str) -> Optional[Image.Image]:
    """Fetch and decode an image into PIL, caching in memory."""
    if not url:
        return None
    url = url.strip()
    if url in _ICON_CACHE:
        return _ICON_CACHE[url]

    # Normalize url (spaces to %20)
    clean_url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=")
    try:
        async with session.get(clean_url) as resp:
            if resp.status == 200:
                raw_bytes = await resp.read()
                img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
                _ICON_CACHE[url] = img
                return img
    except Exception as e:
        print(f"[CardGenerator] Failed to fetch image {url}: {e}")
    return None

async def generate_killer_build_card(
    session: aiohttp.ClientSession,
    killer_name: str,
    killer_img_url: Optional[str],
    killer_tier: str,
    killer_rating: float,
    perks: List[Dict[str, Any]],
    page_num: int = 1,
    total_pages: int = 4
) -> io.BytesIO:
    """
    Generates an enlarged 1200x320 composite card showing the Killer and 4 perks.
    Uses crisp vector stars and high-DPI scaling.
    """
    width = 1200
    height = 320
    card = Image.new("RGBA", (width, height), (15, 16, 23, 255))
    draw = ImageDraw.Draw(card)

    # DBD stylized borders with purple plague glow
    draw.rounded_rectangle([3, 3, width - 4, height - 4], radius=24, outline=(186, 85, 211, 200), width=2)
    draw.rounded_rectangle([10, 10, width - 11, height - 11], radius=20, outline=(36, 40, 56, 255), width=1)

    # Killer Section (Left)
    k_x, k_y = 40, 35
    k_size = 180

    # Rounded frame for killer
    draw.rounded_rectangle([k_x - 4, k_y - 4, k_x + k_size + 4, k_y + k_size + 4], radius=16, fill=(10, 11, 15, 255), outline=(145, 50, 175, 255), width=2)

    if killer_img_url:
        k_img = await fetch_image(session, killer_img_url)
        if k_img:
            k_res = k_img.resize((k_size, k_size), Image.Resampling.LANCZOS)
            card.paste(k_res, (k_x, k_y), k_res)

    # Killer Typography
    f_killer = get_font(20, bold=True)
    f_pill = get_font(13, bold=True)

    k_disp = killer_name if len(killer_name) <= 17 else killer_name[:15] + ".."
    draw.text((k_x + k_size // 2, k_y + k_size + 18), k_disp, fill=(255, 255, 255, 255), font=f_killer, anchor="mm")

    # Pill badge: Tier X | ★ Rating/5
    pill_cx = k_x + k_size // 2
    pill_cy = k_y + k_size + 45
    pill_w, pill_h = 160, 26
    draw.rounded_rectangle([pill_cx - pill_w // 2, pill_cy - pill_h // 2, pill_cx + pill_w // 2, pill_cy + pill_h // 2], radius=10, fill=(40, 20, 55, 255), outline=(186, 85, 211, 220), width=1)

    draw.text((pill_cx - 45, pill_cy), f"Tier {killer_tier}", fill=(235, 195, 255, 255), font=f_pill, anchor="mm")
    draw.line([pill_cx - 15, pill_cy - 8, pill_cx - 15, pill_cy + 8], fill=(80, 50, 100, 255), width=1)
    draw_star(draw, (pill_cx + 2, pill_cy), 6.0, (255, 215, 0, 255))
    draw.text((pill_cx + 36, pill_cy), f"{killer_rating:.2f} / 5", fill=(255, 255, 255, 255), font=f_pill, anchor="mm")

    # Divider line
    draw.line([265, 30, 265, 290], fill=(45, 50, 68, 255), width=2)

    # Perks Section Header
    f_hdr = get_font(17, bold=True)
    f_page = get_font(13, bold=False)
    header_title = "RECOMMENDED META BUILD" if page_num == 1 else f"ALTERNATIVE PERKS (PAGE {page_num} OF {total_pages})"
    draw.text((295, 36), header_title, fill=(220, 225, 240, 255), font=f_hdr, anchor="ls")
    draw.text((width - 45, 36), f"Page {page_num} of {total_pages}", fill=(140, 145, 168, 255), font=f_page, anchor="rs")

    # Perks layout
    start_x = 290
    spacing = 225
    diamond_size = 140
    icon_size = 96

    f_pname = get_font(15, bold=True)
    f_pstat = get_font(13, bold=True)
    f_porig = get_font(12, bold=False)

    for i, p in enumerate(perks[:4]):
        center_x = start_x + i * spacing + 95
        center_y = 135

        tier = p.get("Tier", "B")
        colors = TIER_RGB.get(tier, TIER_RGB["B"])
        fill_c = colors["fill"]
        border_c = colors["border"]

        # Diamond perk frame
        draw_diamond(draw, (center_x, center_y), diamond_size, fill_c, border_c, width=3)

        # Icon scaled up to 96x96
        icon_url = p.get("PerkIcon") or p.get("Image")
        if icon_url:
            p_img = await fetch_image(session, icon_url)
            if p_img:
                p_res = p_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                card.paste(p_res, (center_x - icon_size // 2, center_y - icon_size // 2), p_res)

        # Name
        p_name = p.get("PerkName", "Unknown")
        if len(p_name) > 18:
            p_name = p_name[:16] + ".."

        draw.text((center_x, 226), p_name, fill=(255, 255, 255, 255), font=f_pname, anchor="mm")

        # Rating line with vector star
        stat_y = 250
        rating_val = p.get("Rating", 0)
        try:
            rating_str = f"{float(rating_val):.2f}"
        except Exception:
            rating_str = str(rating_val)

        draw.text((center_x - 30, stat_y), f"Tier {tier}  •", fill=border_c, font=f_pstat, anchor="rm")
        draw_star(draw, (center_x - 16, stat_y), 5.5, (255, 215, 0, 255))
        draw.text((center_x - 6, stat_y), f" {rating_str}/5", fill=border_c, font=f_pstat, anchor="lm")

        origin = p.get("PerkKiller") or p.get("Killer") or p.get("Survivor", "General")
        draw.text((center_x, 272), f"From: {origin}", fill=(160, 165, 185, 255), font=f_porig, anchor="mm")

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf

async def generate_randomizer_card(
    session: aiohttp.ClientSession,
    role: str,
    perks: List[Dict[str, Any]],
    killer_info: Optional[Dict[str, Any]] = None
) -> io.BytesIO:
    """
    Generates an enlarged roulette / randomizer card with 4 perks (and killer if applicable).
    """
    is_killer = "kill" in role.lower()
    width = 1200 if (is_killer and killer_info) else 1000
    height = 320
    card = Image.new("RGBA", (width, height), (16, 17, 24, 255))
    draw = ImageDraw.Draw(card)

    accent_border = (186, 85, 211, 200) if is_killer else (93, 226, 231, 200)
    draw.rounded_rectangle([3, 3, width - 4, height - 4], radius=24, outline=accent_border, width=2)
    draw.rounded_rectangle([10, 10, width - 11, height - 11], radius=20, outline=(36, 40, 56, 255), width=1)

    f_title = get_font(18, bold=True)
    f_sub = get_font(13, bold=False)

    title_text = "KILLER RANDOMIZER LOADOUT" if is_killer else "SURVIVOR RANDOMIZER LOADOUT"
    draw.text((40, 36), title_text, fill=(255, 255, 255, 255), font=f_title, anchor="ls")
    draw.text((width - 40, 36), "The Plague Roulette", fill=(140, 145, 170, 255), font=f_sub, anchor="rs")
    draw.line([40, 44, width - 40, 44], fill=(45, 52, 72, 255), width=1)

    start_x = 40
    if is_killer and killer_info:
        k_x, k_y = 40, 65
        k_size = 170
        draw.rounded_rectangle([k_x - 4, k_y - 4, k_x + k_size + 4, k_y + k_size + 4], radius=16, fill=(10, 11, 15, 255), outline=(145, 50, 175, 255), width=2)
        k_img = await fetch_image(session, killer_info.get("Image", ""))
        if k_img:
            k_res = k_img.resize((k_size, k_size), Image.Resampling.LANCZOS)
            card.paste(k_res, (k_x, k_y), k_res)

        k_name = killer_info.get("KillerName", "Killer")
        f_kname = get_font(16, bold=True)
        draw.text((k_x + k_size // 2, k_y + k_size + 18), k_name, fill=(255, 255, 255, 255), font=f_kname, anchor="mm")

        draw.line([250, 60, 250, 290], fill=(45, 52, 72, 255), width=2)
        start_x = 275

    spacing = 225 if (is_killer and killer_info) else 235
    diamond_size = 140
    icon_size = 96

    f_pname = get_font(15, bold=True)
    f_pstat = get_font(13, bold=True)
    f_porig = get_font(12, bold=False)

    for i, p in enumerate(perks[:4]):
        center_x = start_x + i * spacing + 95
        center_y = 145

        tier = p.get("Tier", "B")
        colors = TIER_RGB.get(tier, TIER_RGB["B"])
        fill_c = colors["fill"]
        border_c = colors["border"]

        draw_diamond(draw, (center_x, center_y), diamond_size, fill_c, border_c, width=3)

        icon_url = p.get("PerkIcon") or p.get("Image")
        if icon_url:
            p_img = await fetch_image(session, icon_url)
            if p_img:
                p_res = p_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
                card.paste(p_res, (center_x - icon_size // 2, center_y - icon_size // 2), p_res)

        p_name = p.get("PerkName", "Unknown")
        if len(p_name) > 18:
            p_name = p_name[:16] + ".."

        draw.text((center_x, 235), p_name, fill=(255, 255, 255, 255), font=f_pname, anchor="mm")

        stat_y = 258
        rating_val = p.get("Rating", 0)
        try:
            rating_str = f"{float(rating_val):.2f}"
        except Exception:
            rating_str = str(rating_val)

        draw.text((center_x - 30, stat_y), f"Tier {tier}  •", fill=border_c, font=f_pstat, anchor="rm")
        draw_star(draw, (center_x - 16, stat_y), 5.5, (255, 215, 0, 255))
        draw.text((center_x - 6, stat_y), f" {rating_str}/5", fill=border_c, font=f_pstat, anchor="lm")

        origin = p.get("PerkKiller") or p.get("Killer") or p.get("Survivor", "General")
        draw.text((center_x, 278), f"From: {origin}", fill=(160, 165, 185, 255), font=f_porig, anchor="mm")

    buf = io.BytesIO()
    card.save(buf, format="PNG")
    buf.seek(0)
    return buf
