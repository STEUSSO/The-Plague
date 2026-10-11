"""
Constants, mappings, and killer resolution logic for Dead by Daylight (Dennis Reep API).
"""
import re
import difflib
import unicodedata
from typing import Optional, Dict, Any, List

# Discord embed color palette (hex integers)
TIER_COLORS: Dict[str, int] = {
    "S": 0xBA55D3,  # Iridescent / Very Rare Purple
    "A": 0x2ECC71,  # Emerald Green
    "B": 0x3498DB,  # Rare Blue
    "C": 0xF1C40F,  # Uncommon Yellow / Gold
    "D": 0xE67E22,  # Common Orange
    "F": 0xE74C3C,  # Red
}

# Pillow RGB color palette
TIER_RGB: Dict[str, Dict[str, tuple]] = {
    "S": {"fill": (82, 23, 107, 255), "border": (235, 180, 50, 255)},   # Purple + Gold border
    "A": {"fill": (65, 20, 90, 255),  "border": (46, 204, 113, 255)},  # Purple + Green border
    "B": {"fill": (30, 55, 95, 255),  "border": (52, 152, 219, 255)},  # Dark Blue + Blue border
    "C": {"fill": (60, 50, 20, 255),  "border": (241, 196, 15, 255)},  # Dark Amber + Gold
    "D": {"fill": (60, 30, 20, 255),  "border": (230, 126, 34, 255)},  # Dark Orange
    "F": {"fill": (50, 20, 20, 255),  "border": (231, 76, 60, 255)},   # Dark Red
}

THEME_COLOR = 0x8A2BE2  # The Plague signature purple
TOPGG_VOTE_URL = "https://top.gg/bot/1124828126015393882/vote"

# Complete database of Killers supported by the Dennis Reep API v3
KILLERS_DB: List[Dict[str, Any]] = [
    {
        "api_name": "Plague",
        "display_name": "The Plague (Adiris)",
        "aliases": ["plague", "the plague", "adiris", "vommy mommy", "maladie"],
    },
    {
        "api_name": "Nurse",
        "display_name": "The Nurse (Sally Smithson)",
        "aliases": ["nurse", "the nurse", "sally", "sally smithson", "infirmiere", "infirmière"],
    },
    {
        "api_name": "Blight",
        "display_name": "The Blight (Talbot Grimes)",
        "aliases": ["blight", "the blight", "talbot", "talbot grimes", "fleau", "fléau"],
    },
    {
        "api_name": "Spirit",
        "display_name": "The Spirit (Rin Yamaoka)",
        "aliases": ["spirit", "the spirit", "rin", "rin yamaoka", "esprit"],
    },
    {
        "api_name": "Mastermind",
        "display_name": "The Mastermind (Albert Wesker)",
        "aliases": ["mastermind", "the mastermind", "wesker", "albert wesker", "resident evil"],
    },
    {
        "api_name": "Shape",
        "display_name": "The Shape (Michael Myers)",
        "aliases": ["shape", "the shape", "myers", "michael myers", "michael", "silhouette"],
    },
    {
        "api_name": "Good Guy",
        "display_name": "The Good Guy (Chucky)",
        "aliases": ["good guy", "the good guy", "chucky", "charles lee ray", "poupee"],
    },
    {
        "api_name": "Cannibal",
        "display_name": "The Cannibal (Leatherface / Bubba)",
        "aliases": ["cannibal", "the cannibal", "leatherface", "bubba", "bubba sawyer", "cannibale"],
    },
    {
        "api_name": "Cenobite",
        "display_name": "The Cenobite (Pinhead)",
        "aliases": ["cenobite", "the cenobite", "pinhead", "elliot spencer", "cenobite", "cénobite"],
    },
    {
        "api_name": "Executioner",
        "display_name": "The Executioner (Pyramid Head)",
        "aliases": ["executioner", "the executioner", "pyramid head", "pyramid", "bourreau", "silent hill"],
    },
    {
        "api_name": "Nightmare",
        "display_name": "The Nightmare (Freddy Krueger)",
        "aliases": ["nightmare", "the nightmare", "freddy", "freddy krueger", "cauchemar"],
    },
    {
        "api_name": "Lich",
        "display_name": "The Lich (Vecna)",
        "aliases": ["lich", "the lich", "vecna", "dnd", "dungeons and dragons"],
    },
    {
        "api_name": "Dark Lord",
        "display_name": "The Dark Lord (Dracula)",
        "aliases": ["dark lord", "the dark lord", "dracula", "vampire", "castlevania"],
    },
    {
        "api_name": "Onryo",
        "display_name": "The Onryo (Sadako Yamamura)",
        "aliases": ["onryo", "the onryo", "sadako", "sadako yamamura", "the ring", "ring"],
    },
    {
        "api_name": "Xenomorph",
        "display_name": "The Xenomorph (Alien)",
        "aliases": ["xenomorph", "the xenomorph", "alien", "xeno"],
    },
    {
        "api_name": "Ghost Face",
        "display_name": "The Ghost Face (Danny Johnson)",
        "aliases": ["ghost face", "ghostface", "the ghost face", "danny johnson", "jed olsen", "scream"],
    },
    {
        "api_name": "Nemesis",
        "display_name": "The Nemesis (Nemesis T-Type)",
        "aliases": ["nemesis", "the nemesis", "nemesis t-type", "tyrant"],
    },
    {
        "api_name": "Singularity",
        "display_name": "The Singularity (HUX-A7)",
        "aliases": ["singularity", "the singularity", "hux", "hux-a7", "robot"],
    },
    {
        "api_name": "Oni",
        "display_name": "The Oni (Kazan Yamaoka)",
        "aliases": ["oni", "the oni", "kazan", "kazan yamaoka"],
    },
    {
        "api_name": "Huntress",
        "display_name": "The Huntress (Anna)",
        "aliases": ["huntress", "the huntress", "anna", "chasseuse"],
    },
    {
        "api_name": "Hillbilly",
        "display_name": "The Hillbilly (Max Thompson Jr.)",
        "aliases": ["hillbilly", "the hillbilly", "billy", "max thompson", "montagnard"],
    },
    {
        "api_name": "Artist",
        "display_name": "The Artist (Carmina Mora)",
        "aliases": ["artist", "the artist", "carmina", "carmina mora", "artiste"],
    },
    {
        "api_name": "Deathslinger",
        "display_name": "The Deathslinger (Caleb Quinn)",
        "aliases": ["deathslinger", "the deathslinger", "slinger", "caleb", "caleb quinn", "lance-mort"],
    },
    {
        "api_name": "Doctor",
        "display_name": "The Doctor (Herman Carter)",
        "aliases": ["doctor", "the doctor", "herman", "herman carter", "docteur", "doc"],
    },
    {
        "api_name": "Clown",
        "display_name": "The Clown (Kenneth Chase / Jeffrey Hawk)",
        "aliases": ["clown", "the clown", "kenneth", "jeffrey hawk"],
    },
    {
        "api_name": "Dredge",
        "display_name": "The Dredge",
        "aliases": ["dredge", "the dredge", "drague"],
    },
    {
        "api_name": "Knight",
        "display_name": "The Knight (Tarhos Kovács)",
        "aliases": ["knight", "the knight", "tarhos", "tarhos kovacs", "chevalier"],
    },
    {
        "api_name": "Unknown",
        "display_name": "The Unknown",
        "aliases": ["unknown", "the unknown", "inconnu"],
    },
    {
        "api_name": "Houndmaster",
        "display_name": "The Houndmaster (Portia Maye)",
        "aliases": ["houndmaster", "the houndmaster", "portia", "portia maye", "chien"],
    },
    {
        "api_name": "Trapper",
        "display_name": "The Trapper (Evan MacMillan)",
        "aliases": ["trapper", "the trapper", "evan", "evan macmillan", "piegeur", "piégeur"],
    },
    {
        "api_name": "Wraith",
        "display_name": "The Wraith (Philip Ojomo)",
        "aliases": ["wraith", "the wraith", "philip", "philip ojomo", "spectre", "bing bong"],
    },
    {
        "api_name": "Pig",
        "display_name": "The Pig (Amanda Young)",
        "aliases": ["pig", "the pig", "amanda", "amanda young", "cochon", "saw"],
    },
    {
        "api_name": "Hag",
        "display_name": "The Hag (Lisa Sherwood)",
        "aliases": ["hag", "the hag", "lisa", "lisa sherwood", "harpie"],
    },
    {
        "api_name": "Legion",
        "display_name": "The Legion (Frank, Julie, Susie, Joey)",
        "aliases": ["legion", "the legion", "frank", "julie", "susie", "joey"],
    },
    {
        "api_name": "Demogorgon",
        "display_name": "The Demogorgon",
        "aliases": ["demogorgon", "the demogorgon", "demo", "stranger things"],
    },
    {
        "api_name": "Trickster",
        "display_name": "The Trickster (Ji-Woon Hak)",
        "aliases": ["trickster", "the trickster", "ji-woon", "ji-woon hak", "lanceur"],
    },
    {
        "api_name": "Twins",
        "display_name": "The Twins (Charlotte & Victor)",
        "aliases": ["twins", "the twins", "charlotte", "victor", "jumeaux"],
    },
    {
        "api_name": "Skull Merchant",
        "display_name": "The Skull Merchant (Adriana Imai)",
        "aliases": ["skull merchant", "the skull merchant", "adriana", "adriana imai", "marchande", "sm"],
    },
    {
        "api_name": "Animatronic",
        "display_name": "The Animatronic (Springtrap)",
        "aliases": ["animatronic", "the animatronic", "springtrap", "fnaf", "william afton"],
    },
    {
        "api_name": "Ghoul",
        "display_name": "The Ghoul",
        "aliases": ["ghoul", "the ghoul", "goule"],
    },
    {
        "api_name": "Krasue",
        "display_name": "The Krasue",
        "aliases": ["krasue", "the krasue"],
    },
    {
        "api_name": "First",
        "display_name": "The First",
        "aliases": ["first", "the first"],
    },
    {
        "api_name": "Slasher",
        "display_name": "The Slasher",
        "aliases": ["slasher", "the slasher"],
    },
]

# Fast lookup dict mapping normalized alias -> Killer DB item
_ALIAS_LOOKUP: Dict[str, Dict[str, Any]] = {}

def normalize_text(text: str) -> str:
    """Normalize text: strip accents, lowercase, remove punctuation and extra spaces."""
    if not text:
        return ""
    # Normalize unicode (decompose accents)
    nfkd = unicodedata.normalize('NFKD', text)
    clean = "".join([c for c in nfkd if not unicodedata.combining(c)])
    clean = clean.lower().strip()
    # Remove leading "the " or "le " or "la " or "l'"
    clean = re.sub(r"^(the\s+|le\s+|la\s+|l')", "", clean)
    # Remove special chars
    clean = re.sub(r"[^a-z0-9\s]", " ", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean

# Initialize lookup table
for killer in KILLERS_DB:
    # Add api_name
    _ALIAS_LOOKUP[normalize_text(killer["api_name"])] = killer
    # Add display_name
    _ALIAS_LOOKUP[normalize_text(killer["display_name"])] = killer
    # Add all aliases
    for alias in killer.get("aliases", []):
        norm_alias = normalize_text(alias)
        if norm_alias:
            _ALIAS_LOOKUP[norm_alias] = killer

def resolve_killer(query: str) -> Optional[Dict[str, Any]]:
    """
    Intelligently resolves a user query to a killer in Dennis Reep API.
    Supports exact alias matches, prefix/substring matches, and fuzzy Levenshtein matching.
    """
    if not query:
        return None
    
    norm = normalize_text(query)
    
    # 1. Exact match in aliases
    if norm in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[norm]
    
    # Also check without removing "the" just in case
    raw_lower = query.lower().strip()
    if raw_lower in _ALIAS_LOOKUP:
        return _ALIAS_LOOKUP[raw_lower]

    # 2. Substring match
    for alias, killer in _ALIAS_LOOKUP.items():
        if len(norm) >= 3 and (norm in alias or alias in norm):
            return killer

    # 3. Fuzzy matching via difflib
    all_keys = list(_ALIAS_LOOKUP.keys())
    matches = difflib.get_close_matches(norm, all_keys, n=1, cutoff=0.45)
    if matches:
        return _ALIAS_LOOKUP[matches[0]]

    # 4. Fallback check across display names
    display_names = [k["display_name"] for k in KILLERS_DB]
    disp_matches = difflib.get_close_matches(query, display_names, n=1, cutoff=0.4)
    if disp_matches:
        for k in KILLERS_DB:
            if k["display_name"] == disp_matches[0]:
                return k

    return None

def rating_bar(rating: float, max_rating: float = 5.0, length: int = 10) -> str:
    """Generate a clean visual rating bar e.g. ▰▰▰▰▰▰▰▱▱▱ (70%)."""
    ratio = max(0.0, min(1.0, rating / max_rating))
    filled = round(ratio * length)
    empty = length - filled
    return f"{'▰' * filled}{'▱' * empty}"
