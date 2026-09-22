"""
Standalone ingredient identity and HAVE/NEED matching engine.

This module deliberately has no Flask, web-search, UI, or ranking code.
It answers only two questions:

1. What is the actual ingredient identity in this recipe text?
2. Does that recipe ingredient match something the user has?

Recipe wording is not ingredient identity.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional


PANTRY_STAPLES = {
    "salt",
    "kosher salt",
    "sea salt",
    "table salt",
    "fine sea salt",
    "coarse salt",
    "fine salt",
    "coarse sea salt",
    "pepper",
    "black pepper",
    "white pepper",
    "ground pepper",
    "ground black pepper",
    "freshly ground pepper",
    "freshly ground black pepper",
    "cracked pepper",
    "cracked black pepper",
    "water",
}


# Canonical identities and their accepted source forms.
IDENTITY_ALIASES = {
    "flour": {
        "flour",
        "all purpose flour",
        "all-purpose flour",
        "plain flour",
    },
    "rice": {
        "rice",
    },
    "potato": {
        "potato",
        "potatoes",
        "small potatoes",
        "baby potatoes",
        "new potatoes",
        "red potatoes",
        "yukon gold potatoes",
        "russet potatoes",
    },
    "tomato": {
        "tomato",
        "tomatoes",
    },
    "garlic": {
        "garlic",
        "fresh garlic",
        "garlic clove",
        "garlic cloves",
    },
    "garlic powder": {
        "garlic powder",
    },
    "onion": {
        "onion",
        "onions",
        "yellow onion",
        "white onion",
        "red onion",
        "sweet onion",
        "green onion",
        "scallion",
        "spring onion",
    },
    "butter": {
        "butter",
        "salted butter",
        "unsalted butter",
        "stick butter",
    },
    "milk": {
        "milk",
        "whole milk",
        "skim milk",
        "2% milk",
        "low fat milk",
    },
    "egg": {
        "egg",
        "eggs",
        "large egg",
        "large eggs",
    },
    "olive oil": {
        "olive oil",
        "extra virgin olive oil",
        "extra-virgin olive oil",
        "virgin olive oil",
        "light olive oil",
    },
    "vegetable oil": {
        "vegetable oil",
    },
    "canola oil": {
        "canola oil",
    },
    "oil": {
        "oil",
        "cooking oil",
    },
    "mozzarella": {
        "mozzarella",
        "mozzarella cheese",
    },
    "ricotta": {
        "ricotta",
        "ricotta cheese",
    },
    "parmesan cheese": {
        "parmesan",
        "parmesan cheese",
    },
    "cheese": {
        "cheese",
    },
    "cream cheese": {
        "cream cheese",
    },
    "cheddar cheese": {
        "cheddar",
        "cheddar cheese",
    },
    "salmon": {
        "salmon",
        "salmon filet",
        "salmon filets",
        "salmon fillet",
        "salmon fillets",
        "salmon steak",
        "salmon steaks",
    },
    "cod": {
        "cod",
        "cod filet",
        "cod filets",
        "cod fillet",
        "cod fillets",
    },
    "haddock": {
        "haddock",
        "haddock filet",
        "haddock filets",
        "haddock fillet",
        "haddock fillets",
    },
    "tilapia": {
        "tilapia",
        "tilapia filet",
        "tilapia filets",
        "tilapia fillet",
        "tilapia fillets",
    },
    "tuna": {
        "tuna",
        "tuna filet",
        "tuna filets",
        "tuna fillet",
        "tuna fillets",
        "tuna steak",
        "tuna steaks",
    },
    "shrimp": {
        "shrimp",
    },
    "chicken": {
        "chicken",
        "boneless chicken",
    },
    "chicken breast": {
        "chicken breast",
        "chicken breasts",
        "boneless chicken breast",
        "boneless chicken breasts",
        "skinless chicken breast",
        "skinless chicken breasts",
        "boneless skinless chicken breast",
        "boneless skinless chicken breasts",
    },
    "chicken thigh": {
        "chicken thigh",
        "chicken thighs",
        "boneless chicken thigh",
        "boneless chicken thighs",
        "bone-in chicken thigh",
        "bone-in chicken thighs",
        "boneless skinless chicken thigh",
        "boneless skinless chicken thighs",
    },
    "chicken drumstick": {
        "chicken drumstick",
        "chicken drumsticks",
    },
    "chicken wing": {
        "chicken wing",
        "chicken wings",
    },
    "ground beef": {
        "ground beef",
        "lean ground beef",
    },
    "beef": {
        "beef",
    },
    "chuck roast": {
        "chuck roast",
        "beef chuck roast",
        "beef chuck",
    },
    "brisket": {
        "brisket",
        "beef brisket",
        "packer brisket",
        "whole packer brisket",
        "untrimmed brisket",
    },
}


# Generic families. The direction is always:
# generic pantry -> specific recipe = allowed.
GENERIC_TO_SPECIFIC = {
    "beef": {
        "beef",
        "ground beef",
        "chuck roast",
        "brisket",
    },
    "chicken": {
        "chicken",
        "chicken breast",
        "chicken thigh",
        "chicken drumstick",
        "chicken wing",
    },
    "rice": {
        "rice",
        "white rice",
        "brown rice",
        "basmati rice",
        "jasmine rice",
    },
    "oil": {
        "oil",
        "olive oil",
        "vegetable oil",
        "canola oil",
    },
    "cheese": {
        "cheese",
        "mozzarella",
        "ricotta",
        "parmesan cheese",
        "cream cheese",
        "cheddar cheese",
    },
    "tomato": {
        "tomato",
        "roma tomato",
        "plum tomato",
        "beefsteak tomato",
        "heirloom tomato",
        "vine tomato",
    },
    "salmon": {
        "salmon",
    },
    "cod": {
        "cod",
    },
    "haddock": {
        "haddock",
    },
    "tilapia": {
        "tilapia",
    },
    "tuna": {
        "tuna",
    },
}


TOMATO_SMALL_PATTERN = re.compile(
    r"\b(?:grape|cherry|currant|mini|baby|small|sungold|sun gold)\s+tomatoes?\b",
    re.IGNORECASE,
)


DESCRIPTOR_WORDS = {
    "a", "an", "the", "some", "each", "fresh", "freshly", "frozen",
    "raw", "cooked", "uncooked", "organic", "wild", "wild-caught",
    "boneless", "skinless", "peeled", "deveined", "seeded", "trimmed",
    "lean", "large", "medium", "small", "heaping", "scant",
    "roughly", "rough", "lightly", "heavily",
    "chopped", "chop", "diced", "dice", "sliced", "slice",
    "cubed", "cube", "minced", "mince", "crushed", "crush",
    "grated", "grate", "shredded", "shred", "juiced", "zested",
    "halved", "quartered", "trim", "optional",
    "divided", "reserved", "plus", "more", "extra", "additional",
    "bone-in", "bone in", "skin-on", "skin on",
}


UNIT_PATTERN = re.compile(
    r"^\s*"
    r"(?:"
    r"\d+(?:\s+\d+/\d+)?|\d+/\d+|[½⅓⅔¼¾⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞]"
    r")"
    r"(?:\s*(?:-|to)\s*(?:\d+(?:\s+\d+/\d+)?|\d+/\d+))?"
    r"(?:\s+(?:"
    r"tablespoons?|tbsp|tbs|teaspoons?|tsp|cups?|"
    r"ounces?|oz|pounds?|lbs?|grams?|g|kilograms?|kg|"
    r"milliliters?|ml|liters?|litres?|l|pinches?|dashes?|"
    r"handfuls?|cloves?|heads?|bunches?|pieces?|sticks?|"
    r"slices?|sprigs?|stalks?|servings?|portions?"
    r"))?\s*",
    re.IGNORECASE,
)


def _clean(text: str) -> str:
    text = text.strip().lower()
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("&", " and ")
    # Commas in recipe ingredient records usually separate descriptors.
    # They are not part of the ingredient identity.
    text = text.replace(",", " ")
    text = re.sub(r"[|;]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _singular(word: str) -> str:
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith("ves") and len(word) > 3:
        irregular = {
            "leaves": "leaf",
            "wives": "wife",
            "knives": "knife",
        }
        return irregular.get(word, word[:-1])
    if word.endswith("s") and not word.endswith("ss") and len(word) > 3:
        return word[:-1]
    return word


def _build_reverse_aliases():
    result = {}
    for canonical, aliases in IDENTITY_ALIASES.items():
        for alias in aliases:
            result[_clean(alias)] = canonical
    return result


_REVERSE_ALIASES = _build_reverse_aliases()


def _strip_quantity_and_units(text: str) -> str:
    previous = None
    while text != previous:
        previous = text
        text = UNIT_PATTERN.sub("", text, count=1).strip()

    text = re.sub(
        r"^\s*(?:lb|lbs|pound|pounds|oz|ounce|ounces|g|gram|grams|"
        r"kg|kilogram|kilograms|ml|milliliter|milliliters|"
        r"l|liter|liters|litre|litres)\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text.strip()


def _strip_descriptors(text: str) -> str:
    words = text.split()
    while words and words[0] in DESCRIPTOR_WORDS:
        words.pop(0)

    # Remove common trailing preparation words.
    while words and words[-1] in DESCRIPTOR_WORDS:
        words.pop()

    return " ".join(words).strip()


def _known_exact(text: str) -> Optional[str]:
    text = _clean(text)
    if text in _REVERSE_ALIASES:
        return _REVERSE_ALIASES[text]

    singular = " ".join(_singular(word) for word in text.split())
    if singular in _REVERSE_ALIASES:
        return _REVERSE_ALIASES[singular]

    return None


def _identity_without_animal_prefix(text: str) -> Optional[str]:
    text = _clean(text)
    animal_prefixes = (
        ("beef ", "beef"),
        ("chicken ", "chicken"),
        ("pork ", "pork"),
        ("turkey ", "turkey"),
        ("lamb ", "lamb"),
    )

    for prefix, _ in animal_prefixes:
        if text.startswith(prefix):
            remainder = text[len(prefix):].strip()
            if remainder == "chuck":
                return "chuck roast"
            if remainder == "chuck roast":
                return "chuck roast"
            if remainder == "brisket":
                return "brisket"
            if remainder:
                known = _known_exact(remainder)
                if known:
                    return known

    return None


def _identity_from_phrase(text: str) -> Optional[str]:
    text = _clean(text)

    # Special recipe wording: chicken quarters cut into thighs and drumsticks.
    cut_match = re.search(r"\bcut into\b(.+)$", text, re.IGNORECASE)
    if cut_match:
        base = text[:cut_match.start()].strip(" ,")
        pieces = cut_match.group(1).strip(" ,")
        if re.search(r"\bchicken\b", base, re.IGNORECASE):
            found = []
            for piece in re.split(r"\s+and\s+", pieces, flags=re.IGNORECASE):
                piece = _strip_descriptors(piece.strip(" ,"))
                if piece in {"thigh", "thighs"}:
                    found.append("chicken thigh")
                elif piece in {"drumstick", "drumsticks"}:
                    found.append("chicken drumstick")
            if len(found) >= 2:
                return " and/or ".join(dict.fromkeys(found))

    exact = _known_exact(text)
    if exact:
        return exact

    prefixed = _identity_without_animal_prefix(text)
    if prefixed:
        return prefixed

    # Remove a leading descriptor layer and retry.
    stripped = _strip_descriptors(text)
    if stripped != text:
        exact = _known_exact(stripped)
        if exact:
            return exact
        prefixed = _identity_without_animal_prefix(stripped)
        if prefixed:
            return prefixed

    # Search the longest established identity embedded in the cleaned phrase.
    padded = f" {stripped} "
    candidates = sorted(
        _REVERSE_ALIASES,
        key=lambda value: (len(value.split()), len(value)),
        reverse=True,
    )

    for alias in candidates:
        if f" {alias} " not in padded:
            continue

        canonical = _REVERSE_ALIASES[alias]

        # Generic animal names cannot steal a more specific identity.
        if canonical in {"beef", "chicken"} and stripped != alias:
            continue

        # "pepper" inside "red pepper flakes" is not the ingredient identity.
        if "pepper flakes" in stripped and canonical == "pepper":
            continue

        return canonical

    return None


def identify_ingredient(text: str) -> str:
    """
    Return one canonical ingredient identity, or "" for pantry staples.
    OR expressions remain combined as "x or y".
    """
    if not isinstance(text, str):
        return ""

    text = _clean(text)
    if not text:
        return ""

    if re.search(r"\s+or\s+", text):
        parts = [
            identify_ingredient(part)
            for part in re.split(r"\s+or\s+", text)
        ]
        parts = [part for part in parts if part]
        return " or ".join(dict.fromkeys(parts))

    # Recipe-specific multi-identity form.
    phrase_identity = _identity_from_phrase(text)
    if phrase_identity:
        if " and/or " in phrase_identity:
            return phrase_identity
        if phrase_identity in PANTRY_STAPLES:
            return ""
        return phrase_identity

    text = _strip_quantity_and_units(text)
    text = _strip_descriptors(text)

    phrase_identity = _identity_from_phrase(text)
    if phrase_identity:
        if " and/or " in phrase_identity:
            return phrase_identity
        if phrase_identity in PANTRY_STAPLES:
            return ""
        return phrase_identity

    # Pepper flakes remain real ingredients.
    pepper_flakes = re.fullmatch(
        r"(?:(?:crushed)\s+)?"
        r"(?:(?:red|green|yellow|orange|black|white)\s+)?"
        r"pepper\s+flakes?"
        r"(?:\s+(?:crushed|ground|freshly ground|coarsely ground|finely ground))?",
        text,
        re.IGNORECASE,
    )
    if pepper_flakes:
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        return normalized

    return ""


def ingredient_identities(text: str) -> List[str]:
    """
    Convert one recipe source line into one or more ingredient identities.
    Pantry staples are excluded.
    """
    if not isinstance(text, str):
        return []

    text = _clean(text)

    if " and/or " in text:
        parts = re.split(r"\s+and/or\s+", text, flags=re.IGNORECASE)
        result = []
        for part in parts:
            identity = identify_ingredient(part)
            if identity:
                result.append(identity)
        return list(dict.fromkeys(result))

    identity = identify_ingredient(text)

    if " or " in identity:
        return [
            part.strip()
            for part in identity.split(" or ")
            if part.strip()
        ]

    if " and/or " in identity:
        return [
            part.strip()
            for part in identity.split(" and/or ")
            if part.strip()
        ]

    return [identity] if identity else []


def _is_ground(identity: str) -> bool:
    return bool(re.search(r"\bground\s+(beef|chicken|pork|turkey|lamb)\b", identity))


def _meat_parent(identity: str) -> Optional[str]:
    identity = _clean(identity)

    if identity in {"beef", "ground beef", "chuck roast", "brisket"}:
        return "beef"
    if identity in {"chicken", "chicken breast", "chicken thigh",
                    "chicken drumstick", "chicken wing"}:
        return "chicken"
    if identity.startswith("ground pork") or identity == "pork":
        return "pork"
    if identity.startswith("ground turkey") or identity == "turkey":
        return "turkey"
    if identity.startswith("ground lamb") or identity == "lamb":
        return "lamb"

    return None


def _tomato_kind(identity: str) -> Optional[str]:
    identity = _clean(identity)

    if TOMATO_SMALL_PATTERN.fullmatch(identity):
        return "small"

    if identity in {
        "roma tomato",
        "plum tomato",
        "beefsteak tomato",
        "heirloom tomato",
        "vine tomato",
    }:
        return "standard"

    if identity == "tomato":
        return "generic"

    return None


def _oil_kind(identity: str) -> Optional[str]:
    identity = _clean(identity)
    if identity in {"oil", "cooking oil"}:
        return "generic"
    if identity.endswith(" oil"):
        return "specific"
    return None


def ingredients_match(recipe_ingredient: str, pantry_items: Iterable[str]) -> bool:
    """
    Return True only when the canonical recipe identity is satisfied
    by one of the canonical pantry identities.
    """
    recipe_identity = identify_ingredient(recipe_ingredient)
    if not recipe_identity:
        return False

    if " or " in recipe_identity:
        return any(
            ingredients_match(part, pantry_items)
            for part in recipe_identity.split(" or ")
        )

    if " and/or " in recipe_identity:
        return any(
            ingredients_match(part, pantry_items)
            for part in recipe_identity.split(" and/or ")
        )

    pantry_identities = {
        identify_ingredient(item)
        for item in pantry_items
    }
    pantry_identities.discard("")

    if recipe_identity in PANTRY_STAPLES:
        return False

    # Exact canonical identity.
    if recipe_identity in pantry_identities:
        return True

    # Cheese family: generic cheese may satisfy a specific cheese.
    if recipe_identity in GENERIC_TO_SPECIFIC["cheese"]:
        if "cheese" in pantry_identities:
            return True

    # Oil family.
    recipe_oil = _oil_kind(recipe_identity)
    if recipe_oil == "generic":
        return recipe_identity in pantry_identities
    if recipe_oil == "specific":
        if "oil" in pantry_identities:
            return True
        return recipe_identity in pantry_identities

    # Tomato family.
    recipe_tomato = _tomato_kind(recipe_identity)
    if recipe_tomato == "small":
        return any(_tomato_kind(item) == "small" for item in pantry_identities)
    if recipe_tomato == "standard":
        return "tomato" in pantry_identities
    if recipe_tomato == "generic":
        return recipe_identity in pantry_identities

    # Meat hierarchy.
    recipe_parent = _meat_parent(recipe_identity)
    if recipe_parent:
        recipe_ground = _is_ground(recipe_identity)

        for pantry_identity in pantry_identities:
            if _meat_parent(pantry_identity) != recipe_parent:
                continue

            pantry_ground = _is_ground(pantry_identity)

            if recipe_ground != pantry_ground:
                continue

            # Same specific cut/form.
            if recipe_identity == pantry_identity:
                return True

            # Generic animal meat can satisfy a specific cut.
            if recipe_identity != recipe_parent and pantry_identity == recipe_parent:
                return True

            # Generic ground meat can satisfy descriptive ground meat.
            if recipe_ground and pantry_identity == f"ground {recipe_parent}":
                return True

        return False

    # Fish species hierarchy.
    fish_identities = {
        "salmon": {"salmon", "salmon filet", "salmon filets",
                   "salmon fillet", "salmon fillets",
                   "salmon steak", "salmon steaks"},
        "cod": {"cod", "cod filet", "cod filets", "cod fillet", "cod fillets"},
        "haddock": {"haddock", "haddock filet", "haddock filets",
                    "haddock fillet", "haddock fillets"},
        "tilapia": {"tilapia", "tilapia filet", "tilapia filets",
                    "tilapia fillet", "tilapia fillets"},
        "tuna": {"tuna", "tuna filet", "tuna filets",
                 "tuna fillet", "tuna fillets",
                 "tuna steak", "tuna steaks"},
    }

    for species, variants in fish_identities.items():
        if recipe_identity not in variants:
            continue

        if recipe_identity == species:
            return recipe_identity in pantry_identities

        if species in pantry_identities:
            return True

        return recipe_identity in pantry_identities

    # Shrimp has no distinct product forms in this engine yet.
    if recipe_identity == "shrimp":
        return "shrimp" in pantry_identities

    return False


def match_recipe(recipe_ingredients: Iterable[str], pantry_items: Iterable[str]) -> dict:
    """
    Produce the simple HAVE/NEED result for a recipe.
    """
    requirements = []

    for source in recipe_ingredients:
        for identity in ingredient_identities(source):
            if identity and identity not in requirements:
                requirements.append(identity)

    have = []
    need = []

    for identity in requirements:
        if ingredients_match(identity, pantry_items):
            have.append(identity)
        else:
            need.append(identity)

    return {
        "have": have,
        "need": need,
        "total": len(requirements),
        "matched": len(have),
    }
