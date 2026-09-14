from flask import Flask, request, render_template_string
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import os
import json
import html as html_lib
from dotenv import load_dotenv
import posthog

load_dotenv()

posthog_client = posthog.Posthog(
    project_api_key=os.getenv("POSTHOG_API_KEY"),
    host=os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
)

app = Flask(__name__)

THEMEALDB_URL = "https://www.themealdb.com/api/json/v1/1"

RECIPE_API_KEY = os.getenv("RECIPE_API_KEY")

BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

RECIPE_CACHE = {}
# ---------------------------------------------------------
# PANTRY STAPLES
# These don't count as ingredients the user needs to buy.
# ---------------------------------------------------------

PANTRY_STAPLES = {
    "salt and pepper",
    "salt & pepper",
    "water",
    "salt",
    "pepper",
    "black pepper",
    "kosher salt",
    "sea salt",
}



# ---------------------------------------------------------
# CORE INGREDIENT MATCHING
# ---------------------------------------------------------
# This is the single source of truth for ingredient variants.
#
# A generic pantry ingredient can satisfy an accepted variant
# of that ingredient, but a specific ingredient does NOT
# automatically satisfy a different specific ingredient.
#
# Examples:
#   beef -> ground beef                 YES
#   beef -> beef broth                  NO
#   pasta -> spaghetti                  YES
#   pasta -> fettuccine                 YES
#   beans -> butter beans               NO
#   butter beans -> beans               NO
#   garlic -> garlic powder             NO
#   butter -> stick butter              YES
# ---------------------------------------------------------

_FIND_CORE_CACHE = {}

CORE_INGREDIENTS = {

    "chicken": {
        "chicken",
        "ground chicken",
        "chicken breast",
        "chicken breasts",
        "skinless chicken breast",
        "skinless chicken breasts",
        "boneless chicken breast",
        "boneless chicken breasts",
        "chicken thigh",
        "chicken thighs",
        "chicken leg",
        "chicken legs",
        "chicken wing",
        "chicken wings",
        "chicken drumstick",
        "chicken drumsticks",
        "boneless skinless chicken breast",
        "boneless skinless chicken thighs",
    },

    "beef": {
        "beef",
        "ground beef",
        "lean ground beef",
        "beef chuck",
        "beef chuck roast", "beef brisket",
        "beef shank",
        "beef steak",
        "beef roast",
        "beef stew meat",
        "beef short ribs",
        "beef tenderloin",
        "beef sirloin",
    },

    "pork": {
        "pork",
        "ground pork",
        "pork chop",
        "pork chops",
        "pork loin",
        "pork shoulder",
        "pork tenderloin",
    },

    "turkey": {
        "turkey",
        "ground turkey",
        "turkey breast",
        "turkey thigh",
    },

    "lamb": {
        "lamb",
        "ground lamb",
        "lamb shoulder",
        "lamb leg",
        "lamb chops",
    },

    "pepper": {
        "pepper",
        "bell pepper",
        "green pepper",
        "green bell pepper",
        "red pepper",
        "red bell pepper",
        "yellow pepper",
        "yellow bell pepper",
        "orange pepper",
        "orange bell pepper",
        "sweet pepper",
    },
    "rice": {
        "rice",
        "white rice",
        "brown rice",
        "basmati rice",
        "jasmine rice",
        "long grain rice",
        "long grain white rice",
        "extra long grain white rice",
        "microwave brown rice",
    },

    "pasta": {
        "pasta",
        "spaghetti",
        "fettuccine",
        "linguine",
        "penne",
        "penne pasta",
        "penne rigate",
        "rigatoni",
        "rigatoni pasta",
        "macaroni",
        "macaroni pasta",
        "elbow macaroni",
        "elbow pasta",
        "cavatappi",
        "cavatappi pasta",
        "rotini",
        "rotini pasta",
        "ziti",
        "ziti pasta",
        "farfalle",
        "bow tie pasta",
        "dry pasta",
        "vermicelli",
        "noodles",
        "egg noodles",
    },

    "butter": {
        "butter",
        "stick butter",
        "unsalted butter",
        "salted butter",
        "unsalted butter chilled",
    },

    "egg": {
        "egg",
        "eggs",
        "large egg",
        "large eggs",
        "beaten egg",
        "beaten eggs",
        "eggs beaten well",
    },

    "garlic": {
        "garlic",
        "fresh garlic",
        "garlic clove",
        "garlic cloves",
        "grated garlic",
        "finely grated garlic",
    },

    "onion": {
        "onion",
        "onions",
        "yellow onion",
        "white onion",
        "red onion",
        "sweet onion",
        "green onion",
        "green onions",
        "scallion",
        "scallions",
        "spring onion",
        "spring onions",
    },

    "broccoli": {
        "broccoli",
        "broccoli florets",
        "fresh broccoli",
        "frozen broccoli",
        "large head broccoli",
    },

    "carrot": {
        "carrot",
        "carrots",
        "baby carrots",
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

    "oil": {
        "oil",
        "olive oil",
        "extra virgin olive oil",
    },

    # Generic cheese does NOT satisfy a specific cheese type.
    # Specific cheeses are kept in their own families so:
    #
    #   cheese -> parmesan       NO
    #   cheese -> cheddar        NO
    #   parmesan -> grated parmesan YES
    #   cheddar -> cheddar cheese YES
    #
    "thyme": {
        "thyme",
        "fresh thyme",
        "dried thyme",
    },
    "cheese": {
        "cheese",
    },

    "cheddar cheese": {
        "cheddar cheese",
        "cheddar",
    },

    "mozzarella": {
        "mozzarella",
        "mozzarella cheese",
    },

    "parmesan": {
        "parmesan",
        "parmesan cheese",
    },

    # Beans are intentionally different.
    # Generic beans do NOT satisfy a specific bean type.
    "beans": {
        "beans",
        "bean",
    },

    "black beans": {
        "black beans",
        "black bean",
    },

    "kidney beans": {
        "kidney beans",
        "kidney bean",
    },

    "pinto beans": {
        "pinto beans",
        "pinto bean",
    },

    "cannellini beans": {
        "cannellini beans",
        "cannellini bean",
    },

    "butter beans": {
        "butter beans",
        "butter bean",
        "lima beans",
        "lima bean",
    },

    "navy beans": {
        "navy beans",
        "navy bean",
    },

    "great northern beans": {
        "great northern beans",
        "great northern bean",
    },

    "chickpeas": {
        "chickpeas",
        "chickpea",
        "garbanzo beans",
        "garbanzo bean",
    },
}

SUBSTITUTIONS = {
    "milk": [
        "unsweetened almond milk",
        "oat milk",
        "soy milk"
    ],

    "butter": [
        "margarine",
        "olive oil"
    ],

    "olive oil": [
        "vegetable oil",
        "canola oil"
    ],

    "vegetable oil": [
        "canola oil",
        "olive oil"
    ],

    "flour": [
        "all-purpose flour",
        "gluten-free flour"
    ],

    "sugar": [
        "honey",
        "maple syrup"
    ],

    "sour cream": [
        "Greek yogurt",
        "plain yogurt"
    ],

    "cream": [
        "half-and-half",
        "milk"
    ],

    "parmesan": [
        "pecorino romano",
        "asiago"
    ],

    "tomato sauce": [
        "crushed tomatoes",
        "diced tomatoes"
    ],

    "onion": [
        "shallots",
        "onion powder"
    ],

    "garlic": [
        "garlic powder",
        "jarred minced garlic"
    ]
}
SUBSTITUTION_NOTES = {

    "milk": {
        "rating": "🟢 Good",
        "note": "Usually little flavor difference."
    },

    "butter": {
        "margarine": {
            "rating": "🟢 Very close",
            "note": "Similar flavor and texture in most recipes."
        },
        "olive oil": {
            "rating": "🟠 Noticeable difference",
            "note": "Changes the flavor and can change the texture."
        }
     },
    "olive oil": {
        "vegetable oil": {
            "rating": "🟢 Very close",
            "note": "Very similar for most cooking, with a more neutral flavor."
        },
        "canola oil": {
            "rating": "🟢 Very close",
            "note": "Works well for cooking and has a mild flavor."
        }
    },
    "vegetable oil": {
        "canola oil": {
            "rating": "🟢 Very close",
            "note": "Very similar cooking properties and a mild flavor."
        },
        "olive oil": {
            "rating": "🟡 Good",
            "note": "Works well for cooking, but can add a noticeable olive oil flavor."
        }
     },
    "flour": {
        "rating": "🟡 Good",
        "note": "Works in many recipes, but texture may vary."
    },

    "sugar": {
        "rating": "🟠 Noticeable difference",
        "note": "Changes sweetness, flavor and moisture."
    },

    "sour cream": {
        "rating": "🟢 Good",
        "note": "Usually a close substitute with a similar texture."
    },

    "cream": {
        "rating": "🟡 Good",
        "note": "May change richness and texture."
    },

    "parmesan": {
        "rating": "🟢 Good",
        "note": "Similar savory flavor, but can be saltier or sharper."
    },

    "tomato sauce": {
        "rating": "🟡 Good",
        "note": "May change texture and tomato intensity."
    },

    "onion": {
    "shallots": {
        "rating": "🟢 Very close",
        "note": "Similar flavor and texture, though slightly milder."
    },
    "onion powder": {
        "rating": "🟡 Some difference",
        "note": "Provides onion flavor but not the texture of fresh onion."
    }
},
    "garlic": {
        "garlic powder": {
            "rating": "🟡 Some difference",
            "note": "Provides garlic flavor but not the texture of fresh garlic."
        },
        "jarred minced garlic": {
            "rating": "🟢 Very close",
            "note": "Similar flavor and texture, though fresh garlic may taste stronger."
        }
    }
}

COMMON_INGREDIENTS = {
    "Meat & Seafood": [
        "chicken breast",
        "chicken thigh",
        "chicken drumstick",
        "chicken wing",
        "chicken tenders",
        "ground chicken",
        "whole chicken",
        "ground beef",
        "beef chuck",
        "beef brisket",
        "beef steak",
        "beef roast",
        "beef stew meat",
        "ground pork",
        "pork chop",
        "pork loin",
        "pork shoulder",
        "pork tenderloin",
        "pork sausage",
        "italian sausage",
        "bacon",
        "ham",
        "ground lamb",
        "lamb shoulder",
        "lamb leg",
        "lamb chops",
        "ground turkey",
        "turkey breast",
        "turkey thigh",
        "salmon",
        "cod",
        "haddock",
        "tilapia",
        "tuna",
        "shrimp",
    ],

    "Dairy & Eggs": [
        "eggs",
        "milk",
        "cheese",
        "butter",
    ],

    "Produce": [
        "potatoes",
        "onion",
        "garlic",
        "tomato",
        "grape / cherry tomatoes",
        "broccoli",
        "carrots",
        "bell pepper",
    ],

    "Pantry": [
        "flour",
        "rice",
        "beans",
        "bread",
        "tomato sauce",
        "olive oil",
        "vegetable oil",
    ],
    "Plant-Based": [
        "tofu",
        "tempeh",
        "seitan",
        "plant-based chicken",
        "plant-based beef",
        "plant-based sausage",
        "vegan cheese",
        "vegan butter",
    ],

}

PASTA_GROUP = {
    "Pasta": [
        "spaghetti",
        "penne",
        "rotini",
        "rigatoni",
        "ziti",
        "elbow macaroni",
        "fettuccine",
        "linguine",
        "angel hair",
        "lasagna noodles",
        "bow tie pasta",
    ],
}


MEAT_GROUPS = {

    "Beef": [
        "ground beef",
        "beef chuck",
        "beef brisket",
        "beef steak",
        "beef roast",
        "beef stew meat",
    ],

    "Chicken": [
        "chicken breast",
        "chicken thigh",
        "chicken drumstick",
        "chicken wing",
        "whole chicken",
    ],

    "Pork": [
        "ground pork",
        "pork chop",
        "pork loin",
        "pork shoulder",
        "pork tenderloin",
        "bacon",
        "ham",
    ],

    "Lamb": [
        "ground lamb",
        "lamb shoulder",
        "lamb leg",
        "lamb chops",
    ],

    "Turkey": [
        "ground turkey",
        "turkey breast",
        "turkey thigh",
    ],

    "Fish": [
        "salmon",
        "cod",
        "haddock",
        "tilapia",
        "tuna",
    ],

    "Shellfish": [
        "shrimp",
    ],
}

# ---------------------------------------------------------
# CLEAN INGREDIENT WORDS
# ---------------------------------------------------------

def clean_word(text):
    if not text:
        return ""

    text = text.lower().strip()
    
    text = re.sub(r"\([^)]*\)", "", text)

    text = text.replace("-", " ")
    text = text.replace("/", " ")

    text = re.sub(
        r"\b\d+([./]\d+)?\b",
        "",
        text
    )

    text = re.sub(
        r"\b(tablespoon|tablespoons|tbsp|tbs|"
        r"teaspoon|teaspoons|tsp|"
        r"cup|cups|ounce|ounces|oz|"
        r"gram|grams|g|kg|ml|liter|litre|"
        r"pinch|handful|clove|cloves|head|heads|"
        r"bunch|piece|pieces)\b",
        "",
        text
    )

    # Universal animal-raising descriptor. "Free range" describes
    # the source/raising method, not the ingredient identity.
    text = re.sub(r"\bfree\s+range\b", "", text)

    text = re.sub(r"[^a-zA-Z\s]", "", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text


# ---------------------------------------------------------
# UNIVERSAL CANONICAL INGREDIENT IDENTITY
# ---------------------------------------------------------
# InThePantry only needs the ingredient identity itself.
#
# Remove:
#   - quantities
#   - preparation instructions
#   - source/editorial wording
#   - non-identity quality/raising descriptors
#   - non-identity size wording
#   - dietary/source qualifiers
#
# Keep:
#   - meaningful ingredient/flavor distinctions
#   - actual ingredient varieties where they matter
#
# Pantry staples:
#   - all salt forms -> removed
#   - seasoning pepper -> removed
#   - water -> removed
#
# Examples:
#   grass fed ground beef -> ground beef
#   lean ground beef -> ground beef
#   garlic roughly -> garlic
#   corn cut off the cob -> corn
#   purple potatoes -> potato
#   extra virgin olive oil -> olive oil
#   red bell pepper -> red bell pepper
#   jasmine rice -> jasmine rice
# ---------------------------------------------------------

def canonical_ingredient_identity(text):
    if not isinstance(text, str):
        return ""

    text = clean_word(text)
    if not text:
        return ""

    # "bone-in" becomes "bone in" inside clean_word().
    # Treat that phrase as a non-identity descriptor so:
    #   bone-in chicken breast -> chicken breast
    #   bone-in chicken        -> chicken
    text = re.sub(
        r"\bbone\s+in\s+",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return ""

    # Handle explicit OR alternatives independently.
    if " or " in text:
        parts = []
        for part in re.split(
            r"\s+or\s+",
            text,
            flags=re.IGNORECASE
        ):
            canonical = canonical_ingredient_identity(part)
            if canonical and canonical not in parts:
                parts.append(canonical)
        return " or ".join(parts)

    # Salt + pepper seasoning is entirely a pantry staple.
    # Do not remove real pepper vegetables such as bell/red/green pepper.
    if (
        re.search(r"\bsalt\b", text)
        and re.search(r"\bpepper\b", text)
        and not re.search(
            r"\b(?:bell|red|green|yellow|orange)\s+pepper\b",
            text
        )
    ):
        return ""

    # Remove salt in every seasoning/product form.
    salt_seasoning = re.compile(
        r"\b(?:(?:un)?salt(?:ed)?|"
        r"(?:kosher|sea|table|fine|coarse|pink|himalayan|"
        r"seasoned|garlic|onion|celery)\s+salt)\b"
    )

    if salt_seasoning.search(text):
        # Salted/unsalted butter is still butter.
        if re.fullmatch(
            r"(?:un)?salted\s+butter",
            text
        ):
            return "butter"

        # Salt-cured ingredients keep the underlying ingredient identity.
        text = salt_seasoning.sub(" ", text).strip()

        if not text:
            return ""

    # Water is a pantry staple.
    if re.fullmatch(
        r"(?:hot|warm|cold|boiling|boiled|room\s+temperature|"
        r"filtered|distilled)?\s*water",
        text,
    ):
        return ""

    # Seasoning pepper is a pantry staple.
    # Pepper vegetables and pepper-flake products remain ingredients.
    if (
        re.fullmatch(
            r"(?:(?:freshly|fresh)\s+)?"
            r"(?:ground|cracked)\s+(?:black|white)?\s*pepper",
            text,
        )
        or re.fullmatch(r"(?:black|white)\s+pepper", text)
        or text == "pepper"
    ):
        return ""

    # Remove non-identity quality / raising descriptors.
    text = re.sub(
        r"\b(?:grass\s+fed|grassfed|grain\s+fed|pasture\s+raised|"
        r"free\s+range|organic|all\s+natural|natural|lean|"
        r"extra\s+lean|premium|boneless|skinless)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # Remove non-identity size wording.
    text = re.sub(
        r"\b(?:extra\s+large|large|medium|small|baby|little|"
        r"bunches?)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # Remove universal product/state descriptors that do not define
    # ingredient identity.
    #
    # Examples:
    #   canned corn undrained -> corn
    #   granulated garlic powder -> garlic powder
    #   reduced fat cheese -> cheese
    #   low sodium soy sauce -> soy sauce
    text = re.sub(
        r"\b(?:canned|jarred|packaged|prepackaged|"
        r"undrained|granulated|reduced\s+fat|low\s+fat|"
        r"fat\s+free|nonfat|low\s+sodium|"
        r"no\s+salt\s+added|unsweetened|"
        r"sugar\s+free)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # Remove wording such as "various colors".
    text = re.sub(
        r"\b(?:various|different|assorted)\s+colors?\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\b(?:various|different|assorted)\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # Preparation/instruction wording starts the non-identity tail.
    text = re.sub(
        r"\s+\b(?:roughly|rough|lightly|heavily|"
        r"chopped|chop|diced|dice|sliced|slice|cubed|cube|"
        r"minced|mince|mashed|mash|crushed|crush|"
        r"smashed|smash|grated|grate|shredded|shred|"
        r"julienned|cut|cutting|quartered|halved|"
        r"peeled|peel|trimmed|trim|browned|cooked|uncooked|"
        r"drained|rinsed|washed|roasted|baked|boiled|"
        r"sauteed|saute|sautéed|sauté|fried|grilled|"
        r"seared|steamed|thawed|softened|melted|reserved|"
        r"divided|for\s+garnish|for\s+serving|as\s+needed|"
        r"to\s+taste)\b.*$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    # Remove connector/prose tails left after preparation cleanup.
    # Do not treat the "in" from hyphenated ingredient wording such as
    # "bone-in chicken breast" as a connector.
    text = re.sub(
        r"(?<!-)\s+\b(?:off|from|into|on|in|with|and)\b.*$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return ""

    # A compound seasoning may become just a pepper phrase after salt removal.
    if (
        re.fullmatch(r"pepper", text)
        or re.fullmatch(r"(?:black|white)\s+pepper", text)
        or re.fullmatch(
            r"(?:(?:freshly|fresh)\s+)?"
            r"(?:ground|cracked)\s+pepper",
            text,
        )
        or re.fullmatch(
            r"(?:(?:freshly|fresh)\s+)?"
            r"(?:ground|cracked)\s+"
            r"(?:black|white)\s+pepper",
            text,
        )
    ):
        return ""

    # Olive oil is one ingredient regardless of olive-oil style.
    text = re.sub(
        r"\b(?:extra\s+virgin|virgin|light|pure|"
        r"cold\s+pressed|first\s+press)\s+olive\s+oil\b",
        "olive oil",
        text,
        flags=re.IGNORECASE,
    )

    # Preserve meaningful pepper and onion flavor distinctions.
    text = re.sub(
        r"\b(red|green|yellow|orange)\s+bell\s+peppers\b",
        r"\1 bell pepper",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bbell\s+peppers\b",
        "bell pepper",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\bgreen\s+onions\b",
        "green onion",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bspring\s+onions?\b",
        "green onion",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bscallions?\b",
        "green onion",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bonions\b",
        "onion",
        text,
        flags=re.IGNORECASE,
    )

    # Universal potato identity cleanup for singular and plural varieties.
    # Sweet potato is handled separately above and remains distinct.
    potato_varieties = {
        "red potato",
        "purple potato",
        "white potato",
        "yellow potato",
        "gold potato",
        "yukon gold potato",
        "russet potato",
        "baby potato",
        "new potato",
        "small potato",
    }

    if text in potato_varieties:
        return "potato"

    # Potato color/variety is not ingredient identity for this app.
    # Sweet potato remains distinct.
    if re.fullmatch(
        r"sweet\s+potatoes?",
        text,
        flags=re.IGNORECASE,
    ):
        return "sweet potato"

    if re.fullmatch(
        r"(?:red|purple|white|yellow|gold|yukon\s+gold|russet|baby|new|small)?\s*potatoes?",
        text,
        flags=re.IGNORECASE,
    ):
        return "potato"

    # Retain flavor-specific rice varieties but remove non-identity wording.
    text = re.sub(
        r"\bextra\s+long\s+grain\s+white\s+rice\b",
        "white rice",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\blong\s+grain\s+white\s+rice\b",
        "white rice",
        text,
        flags=re.IGNORECASE,
    )

    # Remove dietary/source qualifiers while keeping the ingredient.
    text = re.sub(
        r"\bgluten\s+free\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"\bnon\s+gmo\b",
        " ",
        text,
        flags=re.IGNORECASE,
    )

    # Known harmless plural forms.
    singulars = {
        "tomatoes": "tomato",
        "carrots": "carrot",
        "potatoes": "potato",
        "mushrooms": "mushroom",
        "bell peppers": "bell pepper",
        "green onions": "green onion",
        "red onions": "red onion",
        "yellow onions": "yellow onion",
        "white onions": "white onion",
        "sweet onions": "sweet onion",
    }

    text = singulars.get(text, text)

    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------
# INGREDIENT ALIAS PERFORMANCE CACHE
# ---------------------------------------------------------

_INGREDIENT_ALIAS_CACHE = {}
_INGREDIENT_ALIAS_CANDIDATES = None


def _get_ingredient_alias_candidates():
    global _INGREDIENT_ALIAS_CANDIDATES

    if _INGREDIENT_ALIAS_CANDIDATES is not None:
        return _INGREDIENT_ALIAS_CANDIDATES

    known_ingredients = set()

    for family_values in CORE_INGREDIENTS.values():
        known_ingredients.update(family_values)

    for category_values in COMMON_INGREDIENTS.values():
        known_ingredients.update(category_values)

    typo_candidates = set(known_ingredients)

    typo_candidates.update([
        "olive oil",
        "vegetable oil",
        "ground nut oil",
        "groundnut oil",
        "soy sauce",
        "tomato sauce",
        "tomato paste",
        "parmesan",
        "breadcrumbs",
    ])

    _INGREDIENT_ALIAS_CANDIDATES = frozenset(typo_candidates)

    return _INGREDIENT_ALIAS_CANDIDATES


# ---------------------------------------------------------
# INGREDIENT ALIASES
# ---------------------------------------------------------

def ingredient_alias(text):
    if not isinstance(text, str):
        return ""

    raw_text = text.strip().lower()
    if not raw_text:
        return ""

    cached = _INGREDIENT_ALIAS_CACHE.get(raw_text)
    if cached is not None:
        return cached

    text = clean_word(raw_text)

    if not text:
        return ""

    if cached is not None:
        return cached

    if text == 'lean ground beef':
        result = 'ground beef'
        _INGREDIENT_ALIAS_CACHE[raw_text] = result
        return result

    # Correct obvious misspellings before applying aliases.
    # Only very close matches to known ingredients are corrected.
    from difflib import get_close_matches

    typo_candidates = _get_ingredient_alias_candidates()

    if text not in typo_candidates and text and text != "cracked pepper":
        close = get_close_matches(
            text,
            typo_candidates,
            n=1,
            cutoff=0.82
        )
        if close:
            text = close[0]
        else:
            # Handle a common typo where two adjacent letters
            # were accidentally typed in the wrong order.
            words = text.split()
            corrected_words = []

            for word in words:
                corrected = None
                for candidate in typo_candidates:
                    if ' ' in candidate:
                        continue
                    if len(candidate) != len(word):
                        continue
                    differences = [
                        i for i in range(len(word))
                        if word[i] != candidate[i]
                    ]
                    if len(differences) == 2:
                        i, j = differences
                        if j == i + 1 and word[i] == candidate[j] and word[j] == candidate[i]:
                            corrected = candidate
                            break
                corrected_words.append(corrected or word)

            text = ' '.join(corrected_words)

            # Final fallback: allow one small edit anywhere in a
            # single-word ingredient when the result is clearly
            # closer to a known ingredient than the original.
            if text == ' '.join(words):
                best = None
                best_distance = None
                for candidate in typo_candidates:
                    if ' ' in candidate or len(candidate) < 4:
                        continue
                    if len(candidate) - len(text) > 1 or len(text) - len(candidate) > 1:
                        continue
                    import difflib
                    distance = 1 - difflib.SequenceMatcher(None, text, candidate).ratio()
                    if best_distance is None or distance < best_distance:
                        best_distance = distance
                        best = candidate
                if best is not None and best_distance <= 0.18:
                    text = best

    aliases = {
        "spring onions": "green onion",
        "spring onion": "green onion",
        "green onions": "green onion",
        "green onion": "green onion",
        "scallions": "green onion",
        "scallion": "green onion",
        "onions": "onion",

        "plain flour": "flour",
        "all purpose flour": "flour",
        "all-purpose flour": "flour",

        "eggs": "egg",
        "large eggs": "egg",
        "large egg": "egg",

        "potatoes": "potato",

        "beef mince": "ground beef",
        "minced beef": "ground beef",

        "fresh garlic": "garlic",

        "caster sugar": "sugar",
        "granulated sugar": "sugar",

        "tomato purée": "tomato puree",

        "plain breadcrumbs": "breadcrumbs",
        "bread crumbs": "breadcrumbs",

        "whole milk": "milk",
        "skim milk": "milk",
        "2% milk": "milk",
        "low fat milk": "milk",

        "parmesan cheese": "parmesan",

        "tomatoes": "tomato",

        "carrot": "carrots",

        "garlic clove": "garlic",
        "garlic cloves": "garlic",

        "olive oil": "olive oil",
        "vegetable oil": "vegetable oil",
        "ground nut oil": "ground nut oil",
        "groundnut oil": "groundnut oil",

        "chicken breasts": "chicken breast",
        "boneless skinless chicken breast": "chicken breast",
        "boneless skinless chicken breasts": "chicken breast",
        "skinless chicken breast": "chicken breast",
        "skinless chicken breasts": "chicken breast",
        "boneless chicken breast": "chicken breast",
        "boneless chicken breasts": "chicken breast",
        "chicken thighs": "chicken thigh",

        "white rice": "white rice",
        "brown rice": "brown rice",
        "jasmine rice": "jasmine rice",
        "basmati rice": "basmati rice",

        "fresh ginger": "ginger",

        "coriander": "cilantro",
        "fresh coriander": "cilantro",

        "soya sauce": "soy sauce",
        "soy": "soy sauce",
    }

    result = canonical_ingredient_identity(
        aliases.get(text, text)
    )

    # Keep the long-running production worker cache bounded.
    if len(_INGREDIENT_ALIAS_CACHE) >= 10000:
        _INGREDIENT_ALIAS_CACHE.clear()

    _INGREDIENT_ALIAS_CACHE[raw_text] = result

    return result


# ---------------------------------------------------------
# MATCH INGREDIENTS
# ---------------------------------------------------------

_INGREDIENT_MATCH_CACHE = {}

_CORE_LOOKUP_CACHE = None


def _get_core_ingredient_lookups(singular_fn):
    global _CORE_LOOKUP_CACHE

    if _CORE_LOOKUP_CACHE is not None:
        return _CORE_LOOKUP_CACHE

    core_exact_lookup = {}
    core_singular_lookup = {}
    core_descriptive_variants = []

    for core_name, variants in CORE_INGREDIENTS.items():
        core_name_clean = clean_word(core_name)
        all_variants = {core_name_clean}

        for variant in variants:
            variant_clean = clean_word(variant)

            if variant_clean:
                all_variants.add(variant_clean)

                variant_alias = ingredient_alias(variant_clean)
                variant_alias = clean_word(variant_alias)

                if variant_alias:
                    all_variants.add(variant_alias)

        for variant in all_variants:
            if variant:
                core_exact_lookup.setdefault(
                    variant,
                    core_name,
                )

                variant_singular = singular_fn(variant)

                core_singular_lookup.setdefault(
                    variant_singular,
                    core_name,
                )

                core_descriptive_variants.append(
                    (
                        variant,
                        variant.split(),
                        core_name,
                    )
                )

    _CORE_LOOKUP_CACHE = (
        core_exact_lookup,
        core_singular_lookup,
        core_descriptive_variants,
    )

    return _CORE_LOOKUP_CACHE

def _ingredient_matches_uncached(recipe_ingredient, user_ingredients, allow_pantry_staple=True):
    canonical_recipe = canonical_ingredient_identity(
        recipe_ingredient
    )

    if not canonical_recipe:
        return False

    recipe_ingredient = canonical_recipe

    canonical_users = []

    for user_item in (user_ingredients or []):
        canonical_user = canonical_ingredient_identity(
            user_item
        )

        if canonical_user:
            canonical_users.append(
                canonical_user
            )

    user_ingredients = canonical_users

    original_recipe_name = clean_word(recipe_ingredient)

    # -----------------------------------------------------
    # UNIVERSAL VEGAN / PLANT-BASED SEPARATION
    # -----------------------------------------------------
    # Vegan and plant-based versions may match each other.
    # They must remain separate from ordinary animal ingredients.
    # Ordinary ingredients with no dietary qualifier are unaffected.
    # -----------------------------------------------------
    recipe_is_plant_based = bool(
        re.search(r"\bvegan\b", original_recipe_name)
        or re.search(r"\bplant\s+based\b", original_recipe_name)
    )

    for raw_user_item in user_ingredients or []:
        raw_user_name = clean_word(raw_user_item)
        if not raw_user_name:
            continue

        user_is_plant_based = bool(
            re.search(r"\bvegan\b", raw_user_name)
            or re.search(r"\bplant\s+based\b", raw_user_name)
        )

        # Only enforce dietary separation when at least one side
        # explicitly identifies itself as vegan/plant-based.
        if recipe_is_plant_based or user_is_plant_based:
            if recipe_is_plant_based != user_is_plant_based:
                continue

        # The compatible pantry item stays in the normal matching flow.
        # Do not remove ordinary pantry ingredients from the list.


    # Preparation-state phrases containing "pasta" are not
    # standalone pasta ingredients.
    pasta_preparation_phrases = {
        "boiling pasta",
        "cooking pasta",
        "cooked pasta",
        "uncooked pasta",
        "prepared pasta",
        "drained pasta",
        "reserved pasta",
    }

    if original_recipe_name in pasta_preparation_phrases:
        return False

    # Preserve butter direction before normalization collapses variants.
    #
    # Generic pantry "butter" can satisfy a specific recipe butter.
    # Specific pantry butter variants cannot satisfy generic recipe
    # "butter" or substitute for another specific butter variant.
    butter_variants = {
        "butter",
        "salted butter",
        "unsalted butter",
        "stick butter",
        "unsalted butter chilled",
    }

    if original_recipe_name in butter_variants:
        for x in (user_ingredients or []):
            user_raw = clean_word(x)

            if user_raw not in butter_variants:
                continue

            # Exact same butter ingredient is valid.
            if user_raw == original_recipe_name:
                return True

            # Generic pantry butter can satisfy a specific recipe butter.
            if original_recipe_name != "butter" and user_raw == "butter":
                return True

            # Specific pantry butter cannot satisfy generic recipe butter
            # or substitute for another specific butter variant.
            return False


    recipe_name = clean_word(recipe_ingredient)
    if not recipe_name:
        return False

    recipe_name = ingredient_alias(recipe_name)
    recipe_name = clean_word(recipe_name)
    if not recipe_name:
        return False

    # Preserve tomato-family direction before broad core matching.
    # Generic tomato may satisfy standard tomato varieties such as
    # Roma, plum, beefsteak, heirloom, and vine-ripened tomatoes.
    # Small tomato varieties are a separate family: generic tomato
    # does not imply grape, cherry, currant, mini, or baby tomatoes.
    tomato_standard_terms = {
        "roma tomato", "roma tomatoes",
        "plum tomato", "plum tomatoes",
        "beefsteak tomato", "beefsteak tomatoes",
        "heirloom tomato", "heirloom tomatoes",
        "vine tomato", "vine tomatoes",
        "vine-ripened tomato", "vine-ripened tomatoes",
        "on the vine tomato", "on the vine tomatoes",
        "slicing tomato", "slicing tomatoes",
    }

    tomato_small_pattern = re.compile(
        r"\b(?:grape|cherry|currant|mini|baby|small|sungold|sun gold)\s+tomatoes?\b"
    )

    def tomato_family(name):
        name = clean_word(name)
        if not name:
            return None

        if tomato_small_pattern.search(name):
            return "small"

        if name in tomato_standard_terms:
            return "standard"

        if name in {"tomato", "tomatoes"}:
            return "generic"

        # Generic descriptive wording still means ordinary tomatoes.
        # Do not include size/type wording here; small varieties are separate.
        if re.fullmatch(
            r"(?:various|different|assorted|fresh|ripe|whole)\s+tomatoes?",
            name,
        ):
            return "generic"

        return None

    recipe_tomato_family = tomato_family(original_recipe_name)

    if recipe_tomato_family:
        for x in (user_ingredients or []):
            original_user_name = clean_word(x)
            user_tomato_family = tomato_family(original_user_name)

            if not user_tomato_family:
                continue

            # Exact same tomato wording is always valid.
            if clean_word(original_recipe_name) == clean_word(original_user_name):
                return True

            # Small tomatoes form their own interchangeable family.
            # Generic or standard tomatoes do not satisfy a small-tomato recipe.
            if recipe_tomato_family == "small":
                if user_tomato_family == "small":
                    return True
                continue

            # Generic pantry tomato can satisfy a standard tomato variety.
            if recipe_tomato_family == "standard":
                if user_tomato_family == "generic":
                    return True
                continue

            # A specific tomato variety does not satisfy a generic recipe tomato.
            if recipe_tomato_family == "generic":
                continue

    # Preserve pepper direction before normalization collapses variants.
    # Generic pantry pepper can satisfy any recognized specific pepper
    # variant, but specific pepper variants cannot satisfy generic pepper
    # or substitute for one another.
    pepper_variants = {
        "pepper",
        "bell pepper", "red pepper", "green pepper",
        "yellow pepper", "orange pepper",
        "black pepper", "white pepper",
    }

    if original_recipe_name in pepper_variants:
        for x in (user_ingredients or []):
            user_raw = clean_word(x)

            if user_raw not in pepper_variants:
                continue

            # Exact same pepper ingredient is valid.
            if user_raw == original_recipe_name:
                return True

            # Generic pantry pepper can satisfy a specific recipe pepper.
            if original_recipe_name != "pepper" and user_raw == "pepper":
                return True

            # Specific pantry pepper cannot satisfy generic recipe pepper
            # or substitute for another specific pepper variant.
            return False

    # Preserve salt direction before broad core matching collapses variants.
    #
    # Generic pantry salt can satisfy a specific recipe salt.
    # Specific pantry salt cannot satisfy generic recipe "salt".
    # Specific salt variants cannot substitute for other specific variants.
    salt_variants = {
        "salt",
        "kosher salt",
        "sea salt",
        "table salt",
        "fine sea salt",
        "coarse salt",
        "fine salt",
        "coarse sea salt",
    }

    if original_recipe_name in salt_variants:
        for x in (user_ingredients or []):
            user_raw = clean_word(x)

            if user_raw not in salt_variants:
                continue

            # Exact same salt ingredient is valid.
            if user_raw == original_recipe_name:
                return True

            # Generic pantry salt can satisfy a specific recipe salt.
            if original_recipe_name != "salt" and user_raw == "salt":
                return True

            # Specific pantry salt cannot satisfy generic recipe salt
            # or substitute for another specific salt variant.
            return False

    # If the pantry contains a salt variant but the recipe is not
    # itself a recognized salt ingredient, do not let broad core
    # matching create a false salt match.
    if any(
        clean_word(x) in salt_variants
        for x in (user_ingredients or [])
    ):
        if original_recipe_name in salt_variants:
            return False

    # Preserve rice direction before normalization collapses variants.
    if original_recipe_name in {"white rice", "brown rice", "basmati rice", "jasmine rice", "long grain rice", "long grain white rice", "extra long grain white rice", "microwave brown rice"}:
        if any(clean_word(x) == "rice" for x in (user_ingredients or [])):
            return True

    if original_recipe_name == "rice":
        for x in (user_ingredients or []):
            if clean_word(x) in {"white rice", "brown rice", "basmati rice", "jasmine rice", "long grain rice", "long grain white rice", "extra long grain white rice", "microwave brown rice"}:
                return False

    # Preserve oil-family direction before broad core matching.
    #
    # Olive-oil variants are one family:
    #   olive oil = virgin olive oil = extra virgin olive oil = light olive oil
    #
    # Generic cooking oils are a separate family:
    #   oil = cooking oil = vegetable oil = canola oil = avocado oil
    #   = coconut oil = sesame oil = peanut oil = grapeseed oil
    #
    # Generic "oil" can satisfy any specific cooking-oil recipe, but
    # olive oil remains distinct from non-olive cooking oils.
    olive_oil_family = {
        "olive oil",
        "virgin olive oil",
        "extra virgin olive oil",
        "light olive oil",
    }

    cooking_oil_family = {
        "oil",
        "cooking oil",
        "vegetable oil",
        "canola oil",
        "avocado oil",
        "coconut oil",
        "sesame oil",
        "peanut oil",
        "grapeseed oil",
    }

    oil_family = olive_oil_family | cooking_oil_family

    if original_recipe_name in oil_family:
        for x in (user_ingredients or []):
            user_raw = clean_word(x)

            if user_raw not in oil_family:
                continue

            # Olive-oil variants match every other olive-oil variant.
            if (
                original_recipe_name in olive_oil_family
                and user_raw in olive_oil_family
            ):
                return True

            # Generic cooking oil matches any member of the cooking-oil
            # family, including a recipe that simply says "oil".
            if (
                original_recipe_name in cooking_oil_family
                and user_raw in cooking_oil_family
            ):
                return True

            # Olive oil and non-olive cooking oils remain distinct.
            return False

    # -----------------------------------------------------
    # EARLY DESCRIPTIVE GROUND-MEAT PROTECTION
    # -----------------------------------------------------
    # Ground-meat matching is directional:
    #
    #   ground beef + ground beef              = TRUE
    #   ground beef + lean ground beef         = FALSE
    #   ground beef + grass fed ground beef    = FALSE
    #
    #   lean ground beef + ground beef         = TRUE
    #   grass fed ground beef + ground beef    = TRUE
    #
    # Descriptive ground meat may NOT substitute
    # for generic ground meat, but generic ground
    # meat MAY satisfy descriptive ground meat.
    # -----------------------------------------------------
    def early_ground_animal(name):
        name = clean_word(name)
        if not name:
            return None

        match = re.search(
            r"\bground\s+(beef|chicken|pork|turkey|lamb)\b",
            name,
        )
        return match.group(1) if match else None

    recipe_ground_animal = early_ground_animal(original_recipe_name)

    if recipe_ground_animal:
        generic_ground_name = f"ground {recipe_ground_animal}"

        exact_recipe_present = False
        generic_ground_present = False
        descriptive_ground_present = False

        for raw_user_item in (user_ingredients or []):
            user_raw = clean_word(raw_user_item)
            if not user_raw:
                continue

            user_ground_animal = early_ground_animal(user_raw)

            if user_ground_animal != recipe_ground_animal:
                continue

            if user_raw == original_recipe_name:
                exact_recipe_present = True

            if user_raw == generic_ground_name:
                generic_ground_present = True
            else:
                descriptive_ground_present = True

        # Exact same ground-meat wording always matches.
        if exact_recipe_present:
            return True

        # Generic ground meat in the pantry can satisfy
        # a descriptive recipe requirement.
        if original_recipe_name != generic_ground_name:
            if generic_ground_present:
                return True

            # Descriptive ground meat cannot substitute for
            # a different descriptive ground-meat requirement.
            if descriptive_ground_present:
                return False

        # Generic recipe ground meat requires the exact
        # generic ground meat; descriptive pantry wording
        # must not satisfy it.
        elif descriptive_ground_present:
            return False

    else:
        # A ground-meat pantry item must never satisfy a
        # non-ground recipe ingredient through broad core
        # matching.
        #
        # Do not return False merely because ANY pantry item
        # is ground; only block when the recipe itself is a
        # recognized meat family and the ground item belongs
        # to that same family. The authoritative meat logic
        # below handles the complete hierarchy.
        pass

    normalized_recipe, _ = normalize_recipe_ingredient(recipe_name)
    if normalized_recipe:
        recipe_name = normalized_recipe

    recipe_name = ingredient_alias(recipe_name)
    recipe_name = clean_word(recipe_name)
    if not recipe_name:
        return False

    # Pasta-related phrases that contain "pasta" but are not
    # actual pasta ingredients.
    pasta_exclusions = {
        "pasta sauce",
        "pasta sauces",
        "pasta water",
        "pasta waters",
        "pasta flour",
        "pasta cooking water",
        "pasta cooking liquid",
        "reserved pasta water",
        "reserved pasta cooking water",
        "reserved pasta cooking liquid",
        "reserve pasta water",
    }

    if recipe_name in pasta_exclusions:
        return False

    # -----------------------------------------------------
    # COMPOUND SALT + PEPPER MATCHING
    # -----------------------------------------------------
    # A compound ingredient requires BOTH portions to be
    # satisfied. Either pantry staple alone is insufficient.
    # -----------------------------------------------------
    if "salt" in recipe_name and "pepper" in recipe_name:
        compound_parts = re.split(
            r"\s+and\s+",
            recipe_name,
            maxsplit=1,
            flags=re.IGNORECASE
        )

        if len(compound_parts) == 2:
            compound_left = clean_word(compound_parts[0])
            compound_right = clean_word(compound_parts[1])

            salt_words = {
                "salt",
                "kosher salt",
                "sea salt",
                "table salt",
                "fine sea salt",
                "coarse salt",
                "fine salt",
                "coarse sea salt",
            }

            pepper_words = {
                "pepper",
                "bell pepper",
                "red pepper",
                "green pepper",
                "yellow pepper",
                "orange pepper",
                "black pepper",
                "white pepper",
                "ground pepper",
                "ground black pepper",
                "freshly ground pepper",
                "freshly ground black pepper",
                "cracked pepper",
                "cracked black pepper",
            }

            salt_variant = next(
                (
                    variant
                    for variant in sorted(salt_words, key=len, reverse=True)
                    if variant in compound_left or variant in compound_right
                ),
                None,
            )

            pepper_variant = next(
                (
                    variant
                    for variant in sorted(pepper_words, key=len, reverse=True)
                    if variant in compound_left or variant in compound_right
                ),
                None,
            )

            salt_ok = False

            if salt_variant is not None:
                salt_ok = any(
                    ingredient_matches(
                        salt_variant,
                        [user_ingredient],
                        allow_pantry_staple=False,
                    )
                    for user_ingredient in (user_ingredients or [])
                )

                # A generic salt component in a compound ingredient
                # may be satisfied by a specific salt product. Standalone
                # "salt" matching remains strict.
                if not salt_ok and salt_variant == "salt":
                    salt_ok = any(
                        clean_word(user_ingredient) in {
                            "kosher salt",
                            "sea salt",
                            "table salt",
                            "fine sea salt",
                            "coarse salt",
                            "fine salt",
                            "coarse sea salt",
                        }
                        for user_ingredient in (user_ingredients or [])
                    )

            pepper_ok = False

            if pepper_variant is not None:
                pepper_ok = any(
                    ingredient_matches(
                        pepper_variant,
                        [user_ingredient],
                        allow_pantry_staple=False,
                    )
                    for user_ingredient in (user_ingredients or [])
                )

                # A generic pepper component in a compound ingredient
                # may be satisfied by a specific black/white pepper
                # product. Standalone "pepper" matching remains strict.
                if not pepper_ok and pepper_variant == "pepper":
                    pepper_ok = any(
                        clean_word(user_ingredient) in {
                            "black pepper",
                            "white pepper",
                            "ground pepper",
                            "ground black pepper",
                            "freshly ground pepper",
                            "freshly ground black pepper",
                            "cracked pepper",
                            "cracked black pepper",
                        }
                        for user_ingredient in (user_ingredients or [])
                    )

            return salt_ok and pepper_ok

        return False

    if allow_pantry_staple and recipe_name in PANTRY_STAPLES:
        return True

    def singular(word):
        word = clean_word(word)
        if word.endswith("ies"):
            return word[:-3] + "y"
        if word.endswith("s") and not word.endswith("ss"):
            return word[:-1]
        return word

    # -------------------------------------------------------------
    # FAST CORE INGREDIENT LOOKUP
    # -------------------------------------------------------------
    # Build the expensive CORE_INGREDIENTS variant index once.
    # This preserves the existing exact, singular, alias, and
    # descriptive matching behavior while avoiding a full scan of
    # every core/variant for every new ingredient string.
    # -------------------------------------------------------------

    (
        _core_exact_lookup,
        _core_singular_lookup,
        _core_descriptive_variants,
    ) = _get_core_ingredient_lookups(singular)

    def find_core(ingredient):
        ingredient = clean_word(ingredient)

        if not ingredient:
            return None

        ingredient = ingredient_alias(ingredient)
        ingredient = clean_word(ingredient)

        if not ingredient:
            return None

        ingredient_singular = singular(ingredient)

        cache_key = ingredient

        if cache_key in _FIND_CORE_CACHE:
            return _FIND_CORE_CACHE[cache_key]

        # Exact variant lookup.
        core_name = _core_exact_lookup.get(ingredient)

        if core_name is not None:
            _FIND_CORE_CACHE[cache_key] = core_name
            return core_name

        # Singular/plural lookup.
        core_name = _core_singular_lookup.get(ingredient_singular)

        if core_name is not None:
            _FIND_CORE_CACHE[cache_key] = core_name
            return core_name

        # Preserve the existing descriptive-word behavior.
        best_descriptive_core = None
        best_descriptive_length = 0
        ingredient_words = ingredient.split()

        for variant, variant_words, core_name in _core_descriptive_variants:
            if (
                not variant_words
                or len(variant_words) > len(ingredient_words)
            ):
                continue

            for i in range(
                len(ingredient_words) - len(variant_words) + 1
            ):
                candidate = ingredient_words[
                    i:i + len(variant_words)
                ]

                if candidate == variant_words:
                    match_length = len(variant_words)

                    if match_length > best_descriptive_length:
                        best_descriptive_core = core_name
                        best_descriptive_length = match_length

                if (
                    len(variant_words) == 1
                    and singular(candidate[0]) == singular(variant)
                ):
                    if best_descriptive_length < 1:
                        best_descriptive_core = core_name
                        best_descriptive_length = 1

        if best_descriptive_core:
            _FIND_CORE_CACHE[cache_key] = best_descriptive_core
            return best_descriptive_core

        _FIND_CORE_CACHE[cache_key] = None
        return None

    # Compound flavored products such as branded dipping oils should not
    # match a pantry ingredient merely because they contain that ingredient
    # name (for example, garlic parmesan dipping oil -> garlic).
    compound_product = bool(re.search(r"\bdipping\s+oil\b", recipe_name))

    recipe_core = None if compound_product else find_core(recipe_name)

    # -----------------------------------------------------
    # COMPOUND INGREDIENT COMPONENT MATCHING
    # -----------------------------------------------------
    # A compound ingredient may contain multiple real pantry
    # components.  find_core() intentionally returns only the
    # single best core, but matching needs to recognize every
    # known component when the recipe wording clearly combines
    # ingredients.
    #
    # Examples:
    #   parmesan garlic sauce -> parmesan + garlic
    #   garlic butter sauce -> garlic + butter
    #   garlic olive oil -> garlic + oil
    #   chili garlic oil -> garlic + oil
    #
    # Do not apply this to branded/product-style dipping oils,
    # which are intentionally treated as a single compound product.
    # -----------------------------------------------------

    compound_component_cores = set()

    # Pepper variants need explicit compound detection because
    # black pepper and white pepper are intentionally not members
    # of the broad CORE_INGREDIENTS "pepper" family.
    compound_pepper_terms = {
        "pepper",
        "black pepper",
        "white pepper",
        "red pepper",
        "green pepper",
        "yellow pepper",
        "orange pepper",
        "bell pepper",
    }

    compound_recipe_peppers = {
        term
        for term in compound_pepper_terms
        if term in recipe_name
    }

    if not compound_product:
        for core_name, variants in CORE_INGREDIENTS.items():
            core_clean = clean_word(core_name)

            if not core_clean:
                continue

            candidate_variants = {core_clean}

            for variant in variants:
                variant_clean = clean_word(variant)
                if variant_clean:
                    candidate_variants.add(variant_clean)

                    variant_alias = ingredient_alias(variant_clean)
                    variant_alias = clean_word(variant_alias)
                    if variant_alias:
                        candidate_variants.add(variant_alias)

            for variant in candidate_variants:
                variant_words = variant.split()
                recipe_words = recipe_name.split()

                if not variant_words or len(variant_words) > len(recipe_words):
                    continue

                for i in range(len(recipe_words) - len(variant_words) + 1):
                    if recipe_words[i:i + len(variant_words)] == variant_words:
                        # Recognized meat is never a compound component.
                        # Meat wording must always be handled by the
                        # authoritative meat hierarchy below so that:
                        #   ground beef -> lean ground beef = TRUE
                        #   lean ground beef -> ground beef = FALSE
                        #   ground beef -> grass fed ground beef = TRUE
                        #   ground beef -> beef = FALSE
                        #   beef -> ground beef = FALSE
                        if core_name in {
                            "beef",
                            "chicken",
                            "pork",
                            "turkey",
                            "lamb",
                        }:
                            continue

                        compound_component_cores.add(core_name)
                        break

                if core_name in compound_component_cores:
                    break

        # Generic oil is only a valid compound component when the recipe
        # ingredient also contains another recognized ingredient component.
        # This prevents specific oils such as "truffle oil" from matching
        # pantry "olive oil" merely because both resolve to the broad "oil" core.
        if compound_component_cores == {"oil"}:
            compound_component_cores.clear()

        if compound_component_cores:
            for user_item in user_ingredients or []:
                user_name = clean_word(user_item)

                if not user_name:
                    continue

                user_name = ingredient_alias(user_name)
                user_name = clean_word(user_name)

                if not user_name:
                    continue

                normalized_user, _ = normalize_recipe_ingredient(user_name)
                if normalized_user:
                    user_name = normalized_user

                user_name = ingredient_alias(user_name)
                user_name = clean_word(user_name)

                if not user_name:
                    continue

                # Pepper matching is authoritative and must not be satisfied
                # by the broad compound-component pepper core.
                compound_pepper_variants = {
                    "pepper",
                    "bell pepper",
                    "red pepper",
                    "green pepper",
                    "yellow pepper",
                    "orange pepper",
                    "black pepper",
                    "white pepper",
                }

                if (
                    "pepper" in compound_component_cores
                    and user_name in compound_pepper_variants
                ):
                    recipe_pepper_variant = next(
                        (
                            variant
                            for variant in sorted(
                                compound_pepper_variants,
                                key=len,
                                reverse=True,
                            )
                            if variant in recipe_name.split()
                        ),
                        None,
                    )

                    # Multi-word pepper variants need phrase matching.
                    recipe_pepper_variant = next(
                        (
                            variant
                            for variant in sorted(
                                compound_pepper_variants,
                                key=len,
                                reverse=True,
                            )
                            if variant in recipe_name
                        ),
                        None,
                    )

                    if recipe_pepper_variant == "pepper":
                        if user_name != "pepper":
                            continue
                    elif recipe_pepper_variant:
                        if user_name == "pepper" or user_name == recipe_pepper_variant:
                            pass
                        else:
                            continue

                user_core = find_core(user_name)

                # Meat matching is authoritative and must not be satisfied
                # by the generic compound-component shortcut.
                #
                # A normalized standalone meat ingredient must continue to
                # the authoritative meat hierarchy below. Only a meat core
                # that is actually being considered as part of a compound
                # ingredient is blocked here.
                if (
                    user_core in {"beef", "chicken", "pork", "turkey", "lamb"}
                    and user_core in compound_component_cores
                ):
                    continue

                if user_core in compound_component_cores or (user_name in compound_pepper_terms and "pepper" in compound_component_cores):
                    # Pepper varieties are authoritative and must not collapse
                    # together through the broad CORE_INGREDIENTS "pepper" core.
                    if user_name in compound_pepper_terms:
                        # Use the longest recognized pepper phrase so that
                        # "black pepper" is not mistaken for generic "pepper".
                        recipe_pepper_variant = next(
                            (
                                variant
                                for variant in sorted(
                                    compound_pepper_variants,
                                    key=len,
                                    reverse=True,
                                )
                                if variant in recipe_name
                            ),
                            None,
                        )

                        if recipe_pepper_variant == "pepper":
                            if user_name == "pepper":
                                return True
                            continue

                        if recipe_pepper_variant:
                            if user_name == "pepper" or user_name == recipe_pepper_variant:
                                return True
                            continue

                    return True

    # -----------------------------------------------------
    # PLAN A: OR-ALTERNATIVE INGREDIENT MATCHING
    # -----------------------------------------------------
    # Each OR alternative is normalized independently before matching.
    # This makes preparation descriptors universal, so examples such as:
    #   broccoli florets or chopped asparagus
    #   chicken breasts or chopped thighs
    #   beef or chopped pork
    # can match either valid alternative.
    # -----------------------------------------------------
    if " or " in original_recipe_name:
        # Normalize the complete OR expression once. The normalizer returns
        # the primary ingredient plus the explicit OR alternatives.
        normalized_primary, normalized_alternatives = normalize_recipe_ingredient(
            original_recipe_name
        )

        or_alternatives = []
        if normalized_primary:
            or_alternatives.append(normalized_primary)
        or_alternatives.extend(
            alternative
            for alternative in normalized_alternatives
            if alternative
        )

        for alternative in or_alternatives:
            alternative_clean = clean_word(alternative)
            alternative_clean = ingredient_alias(alternative_clean)
            alternative_clean = clean_word(alternative_clean)

            if not alternative_clean:
                continue

            for user_item in user_ingredients or []:
                user_clean = clean_word(user_item)
                user_clean = ingredient_alias(user_clean)
                user_clean = clean_word(user_clean)

                if not user_clean:
                    continue

                # Preserve the strict meat direction inside OR expressions:
                # generic pantry meat cannot satisfy a specific meat option.
                generic_meats = {
                    "beef",
                    "chicken",
                    "pork",
                    "turkey",
                    "lamb",
                }
                meat_words = {
                    "beef", "steak", "ribeye", "rib eye", "sirloin",
                    "sirloin steak", "new york strip", "new york strip steak",
                    "ny strip", "ny strip steak", "strip steak", "filet",
                    "filet mignon", "tenderloin", "tenderloin steak", "porterhouse",
                    "porterhouse steak", "t-bone", "t-bone steak", "flat iron steak",
                    "flank steak", "skirt steak",
                    "chicken", "chicken breast", "chicken breasts",
                    "chicken thigh", "chicken thighs", "chicken leg", "chicken legs",
                    "chicken wing", "chicken wings", "chicken drumstick",
                    "chicken drumsticks", "chicken tender", "chicken tenders",
                    "chicken cutlet", "chicken cutlets", "whole chicken",
                    "pork", "pork chop", "pork chops", "pork loin", "pork loins",
                    "pork shoulder", "pork shoulders", "pork tenderloin",
                    "pork tenderloins", "pork belly", "pork rib", "pork ribs",
                    "turkey", "turkey breast", "turkey breasts", "turkey thigh",
                    "turkey thighs", "turkey leg", "turkey legs", "turkey wing",
                    "turkey wings", "turkey tender", "turkey tenders", "whole turkey",
                    "lamb", "lamb shoulder", "lamb leg", "lamb legs", "lamb chop",
                    "lamb chops", "lamb loin", "lamb loins", "lamb shank",
                    "lamb shanks", "lamb rack", "rack of lamb", "lamb rib", "lamb ribs",
                }

                if user_clean in generic_meats and alternative_clean in meat_words:
                    if alternative_clean != user_clean:
                        continue

                # For all other ingredients, reuse the normal matcher so
                # descriptive wording such as "chopped asparagus" and
                # "broccoli florets" follows the universal ingredient rules.
                if ingredient_matches(
                    alternative_clean,
                    [user_item],
                    allow_pantry_staple=False,
                ):
                    return True

        # The recipe explicitly used OR alternatives. If none matched,
        # do not fall through into ordinary single-ingredient matching.
        return False

    # -----------------------------------------------------
    # MEAT LOOKUP
    # -----------------------------------------------------
    # Build the authoritative meat lookup before CORE_INGREDIENTS
    # matching so broad core matching can never override meat rules.
    # -----------------------------------------------------

    meat_parents = {
        "beef": {
            "beef", "beef chuck", "beef chuck roast", "beef brisket", "beef shank",
            "beef steak", "beef roast", "roast beef", "beef stew meat",
            "beef short ribs", "beef tenderloin", "beef sirloin",
            "steak", "ribeye", "ribeyes", "rib eye", "rib eyes",
            "sirloin", "sirloin steak", "sirloin steaks",
            "new york strip", "new york strip steak", "new york strip steaks",
            "ny strip", "ny strip steak", "ny strip steaks",
            "strip steak", "strip steaks", "filet", "filet mignon",
            "filet mignons", "tenderloin", "tenderloin steak",
            "tenderloin steaks", "porterhouse", "porterhouse steak",
            "porterhouse steaks", "t-bone", "t-bone steak", "t-bone steaks",
            "flat iron steak", "flat iron steaks", "flank steak", "flank steaks",
            "skirt steak", "skirt steaks",
        },
        "chicken": {
            "chicken", "chicken breast", "chicken breasts",
            "chicken thigh", "chicken thighs", "chicken leg", "chicken legs",
            "chicken wing", "chicken wings", "chicken drumstick",
            "chicken drumsticks", "chicken tender", "chicken tenders",
            "chicken cutlet", "chicken cutlets", "whole chicken",
            "rotisserie chicken", "boneless skinless chicken breast",
            "boneless skinless chicken breasts", "boneless skinless chicken thigh",
            "boneless skinless chicken thighs",
        },
        "pork": {
            "pork", "pork chop", "pork chops", "pork loin", "pork loins",
            "pork shoulder", "pork shoulders", "pork tenderloin",
            "pork tenderloins", "pork belly", "pork rib", "pork ribs",
            "baby back ribs", "spare ribs",
        },
        "turkey": {
            "turkey", "turkey breast", "turkey breasts",
            "turkey thigh", "turkey thighs", "turkey leg", "turkey legs",
            "turkey wing", "turkey wings", "turkey tender", "turkey tenders",
            "whole turkey", "turkey drumstick", "turkey drumsticks",
        },
        "lamb": {
            "lamb", "lamb shoulder", "lamb leg", "lamb legs",
            "lamb chop", "lamb chops", "lamb loin", "lamb loins",
            "lamb shank", "lamb shanks", "lamb rack", "rack of lamb",
            "lamb rib", "lamb ribs",
        },
    }

    ground_meats = {
        "ground beef",
        "ground chicken",
        "ground pork",
        "ground turkey",
        "ground lamb",
    }

    steak_terms = {
        "steak", "steaks",
        "ribeye", "ribeyes", "rib eye", "rib eyes",
        "sirloin", "sirloin steak", "sirloin steaks",
        "new york strip", "new york strip steak", "new york strip steaks",
        "ny strip", "ny strip steak", "ny strip steaks",
        "strip steak", "strip steaks",
        "filet", "filet mignon", "filet mignons",
        "tenderloin", "beef tenderloin",
        "tenderloin steak", "tenderloin steaks",
        "porterhouse", "porterhouse steak", "porterhouse steaks",
        "t-bone", "t-bone steak", "t-bone steaks",
        "flat iron steak", "flat iron steaks",
        "flank steak", "flank steaks",
        "skirt steak", "skirt steaks",
    }

    def is_ground_meat(name):
        name = clean_word(name)
        if not name:
            return False

        name = ingredient_alias(name)
        name = clean_word(name)
        if not name:
            return False

        if name in ground_meats:
            return True

        # Recognize descriptive ground-meat wording universally.
        # Examples:
        #   lean ground beef
        #   grass fed ground beef
        #   lean ground chicken
        #   seasoned ground pork
        for parent in ground_meats:
            animal = parent.replace("ground ", "", 1)
            if re.search(
                rf"\bground\s+{re.escape(animal)}\b",
                name,
            ):
                return True

        return False

    def is_steak_cut(name):
        name = clean_word(name)
        if not name:
            return False

        excluded_steak_products = {
            "steak sauce",
            "steak seasoning",
            "steak seasoning mix",
            "steak rub",
            "steak marinade",
        }
        if name in excluded_steak_products:
            return False

        if is_ground_meat(name):
            return False

        singular_name = singular(name)

        if name in steak_terms or singular_name in steak_terms:
            return True

        steak_phrases = (
            "steak",
            "ribeye",
            "rib eye",
            "new york strip",
            "ny strip",
            "porterhouse",
            "t-bone",
            "filet mignon",
            "flat iron",
            "flank steak",
            "skirt steak",
        )

        # Recognize descriptive steak wording universally.
        # Examples: lean steaks, NY steaks, breakfast steak.
        if re.search(r"\bsteaks?\b", name):
            return True

        return any(term in name for term in steak_phrases)

    meat_lookup = {}

    for parent, variants in meat_parents.items():
        for variant in variants:
            meat_lookup[variant] = parent

    # Ground meats participate in the authoritative meat lookup.
    # They share the animal parent, while is_ground_meat() keeps
    # them separate from whole/cut meat during hierarchy matching.
    meat_lookup.update({
        "ground beef": "beef",
        "ground chicken": "chicken",
        "ground pork": "pork",
        "ground turkey": "turkey",
        "ground lamb": "lamb",
    })

    def resolve_meat_parent(name):
        """Resolve an exact meat variant or descriptive steak to its animal parent."""
        name = clean_word(name)
        if not name:
            return None

        name = ingredient_alias(name)
        name = clean_word(name)
        if not name:
            return None

        direct = meat_lookup.get(name)
        if direct:
            return direct

        # Descriptive ground-meat wording belongs to its animal parent.
        # Examples: grass fed ground beef, lean ground chicken.
        # This preserves the existing ground-vs-non-ground protection.
        for parent in ground_meats:
            animal = parent.replace("ground ", "", 1)
            if re.search(rf"\bground\s+{re.escape(animal)}\b", name):
                return animal

        # Descriptive steak wording belongs to the beef parent.
        # Ground meat remains excluded by is_steak_cut().
        if is_steak_cut(name):
            return "beef"

        return None

    # -----------------------------------------------------
    # NORMAL CORE INGREDIENT MATCHING
    # -----------------------------------------------------
    # Non-OR recipe ingredients can also contain descriptive
    # wording around a known ingredient core.
    #
    # Examples:
    #   "parmesan cheese topping" -> parmesan
    #   "bulb garlic" -> garlic
    #   "extra virgin olive oil the garlic and finishing" -> oil
    #
    # recipe_core was calculated above, but the OR matching
    # block is skipped for ordinary ingredients. Compare the
    # resolved core here so those ingredients are matched too.
    # -----------------------------------------------------
    if recipe_core:
        for user_item in user_ingredients or []:
            user_name = clean_word(user_item)
            if not user_name:
                continue

            original_user_name = user_name

            user_name = ingredient_alias(user_name)
            user_name = clean_word(user_name)

            if not user_name:
                continue

            normalized_user, _ = normalize_recipe_ingredient(user_name)
            if normalized_user:
                user_name = normalized_user

            user_name = ingredient_alias(user_name)
            user_name = clean_word(user_name)

            if not user_name:
                continue

            user_core = find_core(user_name)

            # UNIVERSAL STANDALONE CORE PROTECTION
            # A standalone recipe ingredient may only match the same
            # resolved core ingredient. Do not allow an unrelated core
            # to satisfy it through broader compound/descriptive logic.
            if (
                recipe_core
                and user_core
                and clean_word(recipe_name) == clean_word(recipe_core)
                and user_core != recipe_core
            ):
                continue

            # -----------------------------------------------------
            # MEAT CORE MATCHING PROTECTION
            # -----------------------------------------------------
            # Meat hierarchy matching is authoritative below.
            # Do not let broad CORE_INGREDIENTS matching create a
            # second meat match before the authoritative meat rules
            # decide the result.
            #
            # Generic -> specific meat matches are handled by the
            # authoritative meat section. All other meat combinations
            # must not fall through to broad core matching.
            # -----------------------------------------------------
            meat_core_names = {
                "beef",
                "chicken",
                "pork",
                "turkey",
                "lamb",
            }

            # Meat hierarchy is authoritative below.
            # Protect all recognized meat wording, including descriptive
            # forms such as "lean ground beef" and "grass fed ground beef",
            # from broad CORE_INGREDIENTS matching.
            if (
                resolve_meat_parent(recipe_name)
                or resolve_meat_parent(user_name)
            ):
                continue

            # Prevent specific oil products from matching through the broad oil core.
            # Olive oil descriptors such as "extra virgin olive oil" remain valid.
            if recipe_core == "oil" and len(compound_component_cores) == 0:
                if "olive oil" not in recipe_name:
                    continue

            # Pepper hierarchy is authoritative below.
            # Do not let broad CORE_INGREDIENTS matching collapse
            # generic pepper, black pepper, and white pepper together.
            if recipe_core == "pepper" and user_core == "pepper":
                continue

            # Plant-Based/Vegan pantry products must not satisfy
            # unqualified animal ingredients through broad core matching.
            # They may only match another explicitly Plant-Based/Vegan
            # recipe ingredient at this stage.
            plant_based_recipe = bool(
                re.search(r"\bvegan\b", recipe_name)
                or re.search(r"\bplant\s+based\b", recipe_name)
            )
            plant_based_user = bool(
                re.search(r"\bvegan\b", user_name)
                or re.search(r"\bplant\s+based\b", user_name)
            )

            animal_core_names = {
                "beef",
                "chicken",
                "pork",
                "turkey",
                "lamb",
            }

            if (
                plant_based_user
                and not plant_based_recipe
                and recipe_core in animal_core_names
            ):
                continue

    # -----------------------------------------------------
    # PASTA MATCHING
    # -----------------------------------------------------
    pasta_variants = {
        "pasta", "spaghetti", "spaghetti pasta", "fettuccine", "linguine",
        "penne", "penne pasta", "penne rigate", "rigatoni", "rigatoni pasta",
        "macaroni", "macaroni pasta", "elbow macaroni", "elbow pasta",
        "cavatappi", "cavatappi pasta", "rotini", "rotini pasta",
        "ziti", "ziti pasta", "farfalle", "bow tie pasta",
        "angel hair", "angel hair pasta", "lasagna noodles", "lasagna pasta",
        "dry pasta", "vermicelli", "noodles", "egg noodles",
    }

    # Generic pantry pasta can satisfy any clearly identified
    # pasta ingredient, including descriptive recipe wording
    # such as "farfalle pasta", "box chickapea pasta", or
    # "linguine fettuccine or pasta choice".
    #
    # Do not treat unrelated ingredients such as "pasta sauce"
    # or "pasta water" as pasta itself.
    pasta_exclusions = {
        "pasta sauce",
        "pasta sauces",
        "pasta water",
        "pasta waters",
        "pasta flour",
        "pasta cooking water",
        "pasta cooking liquid",
        "reserved pasta water",
        "reserved pasta cooking water",
        "reserved pasta cooking liquid",
        "reserve pasta water",
    }

    recipe_contains_pasta = (
        "pasta" in recipe_name.split()
        and recipe_name not in pasta_exclusions
    )

    if recipe_core == "pasta" or recipe_name in pasta_variants or recipe_contains_pasta:
        for user_item in user_ingredients or []:
            user_name = clean_word(user_item)
            if not user_name:
                continue

            user_name = ingredient_alias(user_name)
            user_name = clean_word(user_name)

            # Generic pantry pasta satisfies any clearly identified
            # pasta ingredient.
            if user_name == "pasta":
                return True

            if user_name not in pasta_variants:
                continue

            recipe_pasta = recipe_name.replace(" pasta", "")
            user_pasta = user_name.replace(" pasta", "")

            if user_pasta == "pasta":
                return True

            if recipe_pasta == user_pasta:
                return True

        return False

    # -----------------------------------------------------
    # GENERIC CHEESE MATCHING
    # -----------------------------------------------------
    # Generic pantry "cheese" can satisfy a specific cheese
    # used by a recipe, but a specific cheese does not satisfy
    # generic "cheese" in the reverse direction.
    #
    # Examples:
    #   cheese -> parmesan       TRUE
    #   cheese -> mozzarella     TRUE
    #   cheese -> cheddar        TRUE
    #   cheese -> cream cheese   TRUE
    #   parmesan -> cheese       FALSE
    #
    # Compound ingredients such as "cheese sauce" are excluded.
    # -----------------------------------------------------

    cheese_exclusions = {
        "cheese sauce",
        "cheese sauces",
        "cheese powder",
        "cheese mixture",
    }

    cheese_variants = {
        "cheese",
        "cheddar",
        "cheddar cheese",
        "mozzarella",
        "mozzarella cheese",
        "parmesan",
        "parmesan cheese",
        "cream cheese",
        "cottage cheese",
        "ricotta",
        "ricotta cheese",
        "colby jack",
        "colby jack cheese",
        "monterey jack",
        "monterey jack cheese",
        "swiss cheese",
        "provolone",
        "provolone cheese",
        "gouda",
        "gouda cheese",
        "feta",
        "feta cheese",
    }

    if (
        recipe_name in cheese_variants
        or recipe_name.endswith(" cheese")
    ):
        if recipe_name in cheese_exclusions:
            return False

        for user_item in user_ingredients or []:
            user_name = clean_word(user_item)

            if not user_name:
                continue

            user_name = ingredient_alias(user_name)
            user_name = clean_word(user_name)

            if user_name == "cheese":
                return True

            if user_name in cheese_variants:
                if user_name == recipe_name:
                    return True

                # Treat a specific cheese name and the same name
                # followed by "cheese" as the same ingredient.
                #
                # Examples:
                #   cheddar -> cheddar cheese       TRUE
                #   mozzarella -> mozzarella cheese TRUE
                #   parmesan -> parmesan cheese     TRUE
                #
                # Do not apply this to generic "cheese" or excluded
                # compound ingredients such as cheese sauce/powder.
                user_cheese_base = user_name
                recipe_cheese_base = recipe_name

                if user_cheese_base.endswith(" cheese"):
                    user_cheese_base = user_cheese_base[:-6].strip()

                if recipe_cheese_base.endswith(" cheese"):
                    recipe_cheese_base = recipe_cheese_base[:-6].strip()

                if (
                    user_cheese_base
                    and recipe_cheese_base
                    and user_cheese_base != "cheese"
                    and recipe_cheese_base != "cheese"
                    and singular(user_cheese_base) == singular(recipe_cheese_base)
                ):
                    return True

                if (
                    singular(user_name) == singular(recipe_name)
                    and user_name != "cheese"
                ):
                    return True

        return False

    # -----------------------------------------------------
    # MEAT MATCHING
    # -----------------------------------------------------
    # Generic meat can satisfy a specific cut of the same
    # animal, but ground meat remains separate from whole cuts.
    #
    # Examples:
    #   beef -> steak                  TRUE
    #   beef -> New York strip steak   TRUE
    #   steak -> ribeye                TRUE
    #   ground beef -> steak           FALSE
    #   steak -> ground beef           FALSE
    #   chicken -> pork                FALSE
    # -----------------------------------------------------

    # -----------------------------------------------------
    # MEAT MATCHING
    # -----------------------------------------------------
    # Generic meat can satisfy a specific cut of the same
    # animal, but ground meat remains separate from whole cuts.
    #
    # Examples:
    #   beef -> steak                  TRUE
    #   beef -> New York strip steak   TRUE
    #   steak -> ribeye                TRUE
    #   ground beef -> steak           FALSE
    #   steak -> ground beef           FALSE
    #   chicken -> pork                FALSE
    # -----------------------------------------------------

    # -----------------------------------------------------
    # MEAT MATCHING
    # -----------------------------------------------------
    # Generic meat can satisfy a specific cut of the same
    # animal, but ground meat remains separate from whole cuts.
    # -----------------------------------------------------

    recipe_parent = resolve_meat_parent(recipe_name)

    # -----------------------------------------------------
    # FISH / SEAFOOD HIERARCHY MATCHING
    # -----------------------------------------------------
    # Generic pantry fish can satisfy a specific form of the
    # same species. Specific species/forms cannot substitute
    # for generic fish or another species.
    #
    # salmon -> salmon filet       TRUE
    # salmon -> salmon fillet      TRUE
    # salmon -> salmon filets      TRUE
    # salmon filet -> salmon       FALSE
    # salmon -> cod                FALSE
    # -----------------------------------------------------
    fish_parents = {
        "salmon": {
            "salmon", "salmon filet", "salmon filets",
            "salmon fillet", "salmon fillets",
            "salmon steak", "salmon steaks",
        },
        "cod": {
            "cod", "cod filet", "cod filets",
            "cod fillet", "cod fillets",
        },
        "haddock": {
            "haddock", "haddock filet", "haddock filets",
            "haddock fillet", "haddock fillets",
        },
        "tilapia": {
            "tilapia", "tilapia filet", "tilapia filets",
            "tilapia fillet", "tilapia fillets",
        },
        "tuna": {
            "tuna", "tuna filet", "tuna filets",
            "tuna fillet", "tuna fillets",
            "tuna steak", "tuna steaks",
        },
        "shrimp": {
            "shrimp",
        },
    }

    fish_lookup = {}
    for parent, variants in fish_parents.items():
        for variant in variants:
            fish_lookup[variant] = parent

    recipe_fish_parent = fish_lookup.get(recipe_name)

    if recipe_fish_parent:
        for user_item in user_ingredients or []:
            user_name = clean_word(user_item)
            if not user_name:
                continue

            user_name = ingredient_alias(user_name)
            user_name = clean_word(user_name)
            if not user_name:
                continue

            user_fish_parent = fish_lookup.get(user_name)
            if not user_fish_parent:
                continue

            if user_fish_parent != recipe_fish_parent:
                continue

            # Exact/singular-plural same ingredient is valid.
            if (
                recipe_name == user_name
                or singular(recipe_name) == singular(user_name)
            ):
                return True

            # Generic pantry species can satisfy a specific recipe form.
            if (
                recipe_name != recipe_fish_parent
                and user_name == recipe_fish_parent
            ):
                return True

            # Specific pantry form cannot satisfy generic species
            # or another specific form.
            continue

    # -----------------------------------------------------
    # AUTHORITATIVE MEAT HIERARCHY MATCHING
    # -----------------------------------------------------
    # Direction is intentional:
    #   generic pantry meat -> specific recipe cut = TRUE
    #   specific pantry cut -> generic recipe meat = FALSE
    #   ground meat <-> non-ground meat = FALSE
    #   different animals = FALSE
    #   exact same ingredient = TRUE
    # -----------------------------------------------------
    if recipe_parent:
        for user_item in user_ingredients or []:
            user_name = clean_word(user_item)
            if not user_name:
                continue

            original_user_name = user_name

            user_name = ingredient_alias(user_name)
            user_name = clean_word(user_name)
            if not user_name:
                continue

            user_parent = resolve_meat_parent(user_name)
            if not user_parent:
                continue

            if user_parent != recipe_parent:
                continue

            recipe_is_ground = is_ground_meat(original_recipe_name)
            user_is_ground = is_ground_meat(original_user_name)

            # Ground meat never crosses with whole/cut meat.
            if recipe_is_ground != user_is_ground:
                continue

            # Exact/singular-plural same ingredient is valid.
            if (
                recipe_name == user_name
                or singular(recipe_name) == singular(user_name)
            ):
                return True

            # Generic pantry meat can satisfy a specific same-animal cut.
            if (
                recipe_name != recipe_parent
                and user_name == recipe_parent
            ):
                return True

            # Generic ground meat can satisfy descriptive ground meat
            # of the same animal.
            #
            # Direction is intentional:
            #   ground beef -> grass fed ground beef = TRUE
            #   grass fed ground beef -> ground beef = FALSE
            #   ground chicken -> lean ground chicken = TRUE
            #   lean ground chicken -> ground chicken = FALSE
            if (
                recipe_is_ground
                and user_is_ground
                and recipe_name != user_name
                and user_name == f"ground {recipe_parent}"
            ):
                return True

            # User-facing "beef steak" means any non-ground beef steak cut.
            # Keep the direction intentional: a steak pantry selection can
            # satisfy a specific steak recipe, but a specific pantry cut
            # cannot satisfy a generic "beef steak" recipe.
            if (
                recipe_parent == "beef"
                and user_name == "beef steak"
                and is_steak_cut(recipe_name)
            ):
                return True

            # Generic recipe steak accepts any specific beef steak cut.
            # This is narrower than generic beef -> specific cut matching.
            if recipe_name == "steak" and recipe_parent == "beef":
                if is_steak_cut(user_name):
                    return True

            # Specific pantry cut cannot satisfy generic recipe meat.
            # Specific cuts also cannot substitute for other specific cuts.
            continue

    # Continue with the normal ingredient/core matching rules.
    for user_item in user_ingredients or []:
        user_name = clean_word(user_item)

        if not user_name:
            continue

        original_user_name = user_name

        user_name = ingredient_alias(user_name)
        user_name = clean_word(user_name)

        if not user_name:
            continue

        # -----------------------------------------------------
        # PLANT-BASED EQUIVALENCE
        # -----------------------------------------------------
        # Vegan and plant-based versions of the same product are
        # compatible with each other, but remain completely separate
        # from ordinary animal ingredients.
        # -----------------------------------------------------
        # -----------------------------------------------------
        # UNIVERSAL PLANT-BASED PRODUCT FAMILY MATCHING
        # -----------------------------------------------------
        # Vegan and plant-based versions of the same product may
        # satisfy each other. Do not treat shared animal/product words
        # as a match when the recipe is actually a different product
        # such as broth, stock, seasoning, or sauce.
        # -----------------------------------------------------
        def plant_based_product_key(name):
            name = clean_word(name)
            if not name:
                return None

            is_plant_based = bool(
                re.search(r"\bvegan\b", name)
                or re.search(r"\bplant\s+based\b", name)
            )

            if not is_plant_based:
                return None

            key = re.sub(r"\bvegan\b", " ", name)
            key = re.sub(r"\bplant\s+based\b", " ", key)

            # Product-form words may describe the same plant-based
            # product without changing its identity.
            key = re.sub(
                r"\b(filet|filets|fillet|fillets|patty|patties|burger|burgers)\b",
                " ",
                key,
            )

            key = re.sub(r"\s+", " ", key).strip()
            return key or None

        recipe_plant_key = plant_based_product_key(recipe_name)
        user_plant_key = plant_based_product_key(user_name)

        if recipe_plant_key and user_plant_key:
            if recipe_plant_key == user_plant_key:
                return True

            # Both sides are explicitly Vegan/Plant-Based, but they
            # are different products. Do not let older generic matching
            # rules collapse them together.
            continue


        # -----------------------------------------------------
        # UNIVERSAL MEAT HIERARCHY PROTECTION
        # -----------------------------------------------------
        # Meat matching is authoritative. Once either side is a
        # recognized meat ingredient, do not allow CORE_INGREDIENTS
        # to create a second, broader match.
        #
        # Generic pantry meat -> specific same-animal recipe cut
        #     TRUE
        #
        # Specific pantry cut -> generic recipe meat
        #     FALSE
        #
        # Ground meat <-> whole/cut meat
        #     FALSE
        #
        # Different animals
        #     FALSE
        # -----------------------------------------------------
        recipe_meat_parent = resolve_meat_parent(recipe_name)
        user_meat_parent = resolve_meat_parent(user_name)

        if recipe_meat_parent or user_meat_parent:
            # If only one side is recognized as meat, never allow
            # generic core matching to bridge the two.
            if not recipe_meat_parent or not user_meat_parent:
                continue

            # Different animals never match.
            if recipe_meat_parent != user_meat_parent:
                continue

            recipe_is_ground = is_ground_meat(original_recipe_name)
            user_is_ground = is_ground_meat(original_user_name)

            # Ground meat never crosses with whole/cut meat.
            if recipe_is_ground != user_is_ground:
                continue

            # Exact/singular-plural same ingredient is valid.
            if (
                recipe_name == user_name
                or singular(recipe_name) == singular(user_name)
            ):
                return True

            # Generic pantry meat may satisfy a specific recipe cut.
            if (
                recipe_name != recipe_meat_parent
                and user_name == recipe_meat_parent
            ):
                return True

            # Specific pantry cut must not satisfy generic recipe meat.
            # Specific cuts also cannot substitute for other specific cuts.
            continue

        # -----------------------------------------------------
        # PEPPER VARIANT HIERARCHY
        # -----------------------------------------------------
        # Generic pantry pepper may satisfy a specific pepper
        # recipe, but a specific pepper may not satisfy generic
        # pepper or another specific pepper variety.
        # -----------------------------------------------------
        pepper_variants = {
            "pepper",
            "bell pepper",
            "red pepper",
            "green pepper",
            "yellow pepper",
            "orange pepper",
            "black pepper",
            "white pepper",
        }

        if recipe_name in pepper_variants and user_name in pepper_variants:
            if recipe_name == user_name:
                return True
            if recipe_name == "pepper" and user_name != "pepper":
                continue
            if recipe_name != "pepper" and user_name == "pepper":
                return True
            # Different specific pepper varieties cannot substitute.
            continue

        # Generic pantry salt satisfies common salt varieties/descriptions.
        # A specific salt variety must not satisfy generic "salt".
        salt_variants = {
            "salt",
            "kosher salt",
            "sea salt",
            "table salt",
            "fine sea salt",
            "coarse salt",
            "fine salt",
            "coarse sea salt",
        }

        if recipe_name in salt_variants and user_name in salt_variants:
            if recipe_name == "salt" and user_name != "salt":
                continue
            return True

        # Specific pepper cannot satisfy generic pepper.
        if recipe_core == "pepper" and recipe_name == "pepper" and user_name != "pepper":
            continue

        # Meat hierarchy is authoritative. If either side is a
        # recognized meat ingredient, the generic exact/singular
        # fallback must not override the directional meat rules above.
        #
        # Examples:
        #   ground beef <- lean ground beef = FALSE
        #   ground beef <- grass fed ground beef = FALSE
        #   ground beef -> lean ground beef = TRUE
        #
        # The authoritative meat block above has already handled
        # valid meat matches. Anything reaching this point must not
        # be allowed to become a broader generic match.
        if (
            resolve_meat_parent(recipe_name)
            or resolve_meat_parent(user_name)
        ):
            continue

        if (
            recipe_name == user_name
            or singular(recipe_name) == singular(user_name)
        ):
            # A specific pepper must not satisfy generic pepper.
            if recipe_core == "pepper" and original_user_name != "pepper":
                continue
            return True

        user_core = find_core(user_name)

        # Meat-specific matching must remain authoritative.
        #
        # A generic meat pantry item can satisfy a specific cut,
        # but a specific cut must NOT satisfy generic meat.
        #
        # Examples:
        #   chicken -> chicken breast       TRUE
        #   chicken breast -> chicken       FALSE
        #   whole chicken -> chicken        FALSE
        #   beef -> steak                   TRUE
        #   steak -> beef                   FALSE
        if recipe_core in {"beef", "chicken", "pork", "turkey", "lamb"}:
            if user_core == recipe_core:
                recipe_is_ground = is_ground_meat(recipe_name)
                user_is_ground = is_ground_meat(user_name)

                # Ground meat never matches whole/cut meat.
                if recipe_is_ground != user_is_ground:
                    continue

                # A descriptive ground-meat pantry item must not satisfy
                # a generic ground-meat recipe requirement.
                #
                # Examples:
                #   ground beef <- lean ground beef       FALSE
                #   ground beef <- grass fed ground beef  FALSE
                #   ground chicken <- lean ground chicken FALSE
                #
                # The reverse direction is intentionally allowed by the
                # authoritative hierarchy above:
                #   lean ground beef <- ground beef       TRUE
                #   lean ground chicken <- ground chicken TRUE
                if (
                    recipe_is_ground
                    and user_is_ground
                    and recipe_name in ground_meats
                    and user_name != recipe_name
                    and resolve_meat_parent(user_name) == recipe_core
                ):
                    continue

                # A specific pantry cut must not satisfy generic recipe meat.
                if recipe_name == recipe_core and user_name != recipe_core:
                    continue

                # A generic pantry meat may satisfy a specific same-animal cut.
                if recipe_name != recipe_core and user_name == recipe_core:
                    return True

                # Same-family non-generic cuts must not be collapsed together.
                continue

        # Specific salt does not satisfy generic salt.
        # Generic pantry salt may satisfy a specific salt variety,
        # but a specific pantry salt variety must not satisfy generic salt.
        salt_variants = {
            "salt",
            "kosher salt",
            "sea salt",
            "table salt",
            "fine sea salt",
            "coarse salt",
            "fine salt",
            "coarse sea salt",
        }

        if recipe_core == "salt" and user_core == "salt":
            if recipe_name == "salt" and user_name != "salt":
                continue

        # Specific pepper does not satisfy generic pepper.
        if recipe_core == "pepper" and user_core == "pepper":
            if recipe_name == "pepper" and user_name != "pepper":
                continue

        # Pepper variants are authoritative. Do not let the broad
        # CORE_INGREDIENTS fallback make different pepper varieties match.
        if recipe_core == "pepper" and user_core == "pepper":
            pepper_variants = {"pepper", "black pepper", "white pepper"}
            if recipe_name in pepper_variants and user_name in pepper_variants:
                if recipe_name == user_name:
                    return True
                if recipe_name != "pepper" and user_name == "pepper":
                    return True
                continue

        # Specific oil products must not match each other through the broad oil core.
        # Olive oil descriptors such as "extra virgin olive oil" are valid
        # matches for pantry "olive oil". Compound oils are handled above.
        if recipe_core == "oil" and len(compound_component_cores) == 0:
            if "olive oil" not in recipe_name:
                continue

        # -----------------------------------------------------
        # PLANT-BASED EQUIVALENCE
        # -----------------------------------------------------
        # Plant-based and vegan versions of the same substitute
        # protein/product are interchangeable with each other.
        # They must remain completely separate from the animal
        # ingredient families above.
        # -----------------------------------------------------
        plant_based_pairs = {
            frozenset(("plant-based chicken", "vegan chicken")),
            frozenset(("plant-based beef", "vegan beef")),
            frozenset(("plant-based sausage", "vegan sausage")),
        }

        if frozenset((recipe_name, user_name)) in plant_based_pairs:
            return True

        if recipe_core and user_core and recipe_core == user_core:
            # Meat-specific matching above must remain authoritative:
            # ground meat does not satisfy generic/whole-cut meat.
            if recipe_core in {"beef", "chicken", "pork", "turkey", "lamb"}:
                if is_ground_meat(user_name) != is_ground_meat(recipe_name):
                    continue

            # Generic pantry pepper satisfies specific pepper variants,
            # but a specific pepper does not satisfy generic pepper.
            if recipe_core == "pepper":
                if user_name == "pepper" and recipe_name != "pepper":
                    return True
                continue

            return True

    return False


def ingredient_matches(recipe_ingredient, user_ingredients, allow_pantry_staple=True):
    """
    Cached public wrapper around the existing ingredient matcher.

    The underlying matching logic is intentionally untouched.
    Cache entries are keyed by the exact inputs and the pantry-staple mode.
    """

    try:
        user_key = tuple(user_ingredients or [])
    except TypeError:
        user_key = tuple(user_ingredients)

    cache_key = (
        recipe_ingredient,
        user_key,
        bool(allow_pantry_staple),
    )

    cached = _INGREDIENT_MATCH_CACHE.get(cache_key)

    if cached is not None:
        return cached

    result = _ingredient_matches_uncached(
        recipe_ingredient,
        user_ingredients,
        allow_pantry_staple=allow_pantry_staple,
    )

    # Keep the long-running production worker cache bounded.
    if len(_INGREDIENT_MATCH_CACHE) >= 10000:
        _INGREDIENT_MATCH_CACHE.clear()

    _INGREDIENT_MATCH_CACHE[cache_key] = result

    return result


def get_sensible_substitutions(ingredient):
    name = ingredient.lower().strip()


    # Normalize common descriptive versions so they can
    # use the same substitution rules.
    substitution_key = name

    if "chicken broth" in name or "chicken stock" in name:
        substitution_key = "chicken broth"
    elif "cheddar cheese" in name:
        substitution_key = "cheddar cheese"
    elif "parmesan cheese" in name:
        substitution_key = "parmesan"
    elif "olive oil" in name:
        substitution_key = "olive oil"
    elif "vegetable oil" in name:
        substitution_key = "vegetable oil"
    substitutions = {
        "soy sauce": [
            {
                "replacement": "tamari",
                "type": "direct",
                "note": "Very similar savory flavor."
            },
            {
                "replacement": "coconut aminos",
                "type": "workable",
                "note": "Slightly sweeter and usually less salty."
            }
        ],

        "sriracha sauce": [
            {
                "replacement": "another hot sauce",
                "type": "workable",
                "note": "Use a similar amount and adjust for heat."
            },
            {
                "replacement": "chili garlic sauce",
                "type": "workable",
                "note": "Adds heat and garlic flavor."
            }
        ],

        "garlic powder": [
            {
                "replacement": "fresh garlic",
                "type": "workable",
                "note": "Use about 1 fresh clove for each 1/4 teaspoon garlic powder."
            }
        ],

        "chicken broth": [
            {
                "replacement": "water",
                "type": "workable",
                "note": "Add extra seasoning because water has less flavor."
            },
            {
                "replacement": "vegetable broth",
                "type": "direct",
                "note": "Works well in most savory recipes."
            }
        ],

        "cheddar cheese": [
            {
                "replacement": "Colby or Colby Jack",
                "type": "direct",
                "note": "Very similar flavor and melts well."
            },
            {
                "replacement": "Monterey Jack",
                "type": "direct",
                "note": "Melts smoothly with a mild flavor."
            },
            {
                "replacement": "mozzarella",
                "type": "workable",
                "note": "Melts well but has a milder flavor and less cheddar sharpness."
            }
        ],

        "italian herb blend": [
            {
                "replacement": "dried oregano",
                "type": "workable",
                "note": "Use with basil or thyme when available."
            },
            {
                "replacement": "dried basil",
                "type": "workable",
                "note": "Best when combined with oregano or thyme."
            },
            {
                "replacement": "dried thyme",
                "type": "workable",
                "note": "Adds a similar herbal note."
            }
        ],

        "ginger": [
            {
                "replacement": "ground ginger",
                "type": "direct",
                "note": "Use a smaller amount because ground ginger is more concentrated."
            }
        ],

        "honey": [
            {
                "replacement": "maple syrup",
                "type": "direct",
                "note": "Similar sweetness with a slightly different flavor."
            },
            {
                "replacement": "brown sugar",
                "type": "workable",
                "note": "Adds sweetness but less moisture than honey."
            }
        ],

        "sesame oil": [
            {
                "replacement": "olive oil",
                "type": "workable",
                "note": "Good for cooking, but the finished dish will have less sesame flavor."
            }
        ],

        "scallions": [
            {
                "replacement": "chives",
                "type": "workable",
                "note": "Adds a similar fresh onion flavor."
            }
        ],

        "sesame seeds": [
            {
                "replacement": "sunflower seeds",
                "type": "workable",
                "note": "Adds crunch, though the flavor will be different."
            }
        ]
    }

    return substitutions.get(substitution_key, [])

def match_recipe_to_pantry(recipe, pantry_items):
    if not recipe:
        return None

    pantry = set()

    for item in pantry_items or []:
        normalized, _ = normalize_recipe_ingredient(
            item
        )

        if normalized:
            pantry.add(normalized)

    # -----------------------------------------------------
    # CONTEXTUAL RECIPE MATCHING
    # -----------------------------------------------------
    # If the recipe title clearly identifies the recipe as
    # beef, plain "stew meat" can be treated as beef stew meat.
    #
    # This is intentionally contextual and does NOT change
    # the general ingredient matching rules.
    # -----------------------------------------------------
    recipe_name = clean_word(
        recipe.get("name", "")
    )

    beef_recipe = "beef" in recipe_name

    # -----------------------------------------------------
    # CORE INGREDIENT MATCHING
    # -----------------------------------------------------
    # Use one central ingredient hierarchy instead of
    # maintaining a separate family list inside this function.
    # -----------------------------------------------------

    def matches(recipe_name):
        # Salt and pepper are basic pantry staples.
        if (
            "salt" in recipe_name
            and "pepper" in recipe_name
        ):
            return True

        # Exact ingredient match.
        if recipe_name in pantry:
            return True

        # Use the central ingredient matching engine.
        #
        # This preserves the important rules:
        # - chicken does NOT satisfy chicken breast
        # - chicken breast does NOT satisfy chicken
        # - chicken breast DOES satisfy chicken breasts
        # - beef does NOT satisfy beef steak
        # - beef steak DOES satisfy beef steak
        #
        # ingredient_matches() already handles
        # singular/plural matching and specific/generic rules.
        return ingredient_matches(
            recipe_name,
            list(pantry)
        )

    requirements = {}

    for original in recipe.get(
        "ingredients",
        []
    ):
        # Some recipe websites combine multiple ingredients
        # into one schema line, for example:
        # "diced scallions + toasted sesame seeds"
        # Split combined ingredient lines into separate items.
        # This allows salt and pepper to be treated as separate
        # pantry staples in every recipe.
        parts = re.split(
            r'\s*\+\s*',
            original
        )

        # -----------------------------------------------------
        # UNIVERSAL COMPOUND-INGREDIENT HANDLING
        # -----------------------------------------------------
        # Separate real ingredients from salt/pepper seasoning.
        # Salt and pepper are pantry staples and never become
        # recipe requirements.
        # -----------------------------------------------------
        compound_parts = []

        for part in parts:
            stripped = part.strip()
            if not stripped:
                continue

            # Split comma-separated recipe ingredients normally.
            # OR alternatives are handled separately by the normalizer.
            comma_parts = re.split(r'\s*,\s*', stripped)


            for comma_part in comma_parts:
                text = comma_part.strip()
                if not text:
                    continue

                # Remove complete salt-and-pepper seasoning phrases.
                text = re.sub(
                    r'(?i)\b(?:kosher|sea|table|fine\s+sea|coarse\s+sea|fine|coarse)?\s*salt\s+and\s+(?:(?:(?:freshly\s+ground|ground|cracked)\s+)?(?:black|white)\s+)?pepper\b',
                    '',
                    text,
                )
                text = re.sub(
                    r'(?i)\b(?:black|white)\s+(?:(?:freshly\s+ground|ground|cracked)\s+)?pepper\s+and\s+(?:kosher|sea|table|fine\s+sea|coarse\s+sea|fine|coarse)?\s*salt\b',
                    '',
                    text,
                )

                text = re.sub(r'\s{2,}', ' ', text).strip(' ,')
                text = re.sub(r'\s+(?:and|,)$', '', text, flags=re.IGNORECASE).strip()

                # If salt-and-pepper seasoning was removed and the
                # remaining words contain no known ingredient, the
                # remainder is recipe wording rather than an ingredient.
                if (
                    not extract_known_ingredient(text)
                    and re.search(r'(?i)\bsalt\b|\bpepper\b', comma_part)
                ):
                    continue

                if not text:
                    continue

                # Now split genuine ingredients joined by "and".
                subparts = re.split(r'\s+and\s+', text, flags=re.IGNORECASE)
                compound_parts.extend(
                    subpart.strip()
                    for subpart in subparts
                    if subpart.strip()
                )

        parts = compound_parts

        if re.search(r'\bsweet\s+paprika\b.*\bsalt\b\s+and\s+\bpepper\b', original, re.IGNORECASE):
            parts = ['sweet paprika', 'salt', 'pepper']

        if re.search(r'\beach\s+sweet\s+paprika\b.*\bsalt\b\s+and\s+\bpepper\b', original, re.IGNORECASE):

            parts = ['sweet paprika', 'salt', 'pepper']

        elif re.search(r'\beach\s*:\s*', original, re.IGNORECASE):

            each_text = re.sub(r'^.*?\beach\s*:\s*', '', original, flags=re.IGNORECASE)

            parts = re.split(r'\s*,\s*|\s+and\s+', each_text, flags=re.IGNORECASE)
            parts = [re.sub(r'^and\s+', '', part, flags=re.IGNORECASE).strip() for part in parts]

        for part in parts:
            normalized, alternatives = (
                normalize_recipe_ingredient(
                    part
                )
            )

            if not normalized:
                continue

            # Contextual beef stew matching.
            # A recipe clearly identified as beef can use
            # generic "stew meat" when the pantry contains beef.
            # This does NOT change the general ingredient rules.

            # Salt and pepper are universal pantry staples.
            # They must never become recipe requirements, regardless
            # of how the recipe words them.
            if normalized in {
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
                "salt pepper",
            }:
                continue

            # Other pantry staples continue to be excluded normally.
            if normalized in PANTRY_STAPLES:
                continue

            if normalized not in requirements:
                requirements[normalized] = {
                    "original": part,
                    "alternatives": alternatives
                }
            else:
                requirements[normalized][
                    "alternatives"
                ].extend(alternatives)

    have = []
    missing = []
    substitutions = []

    for name, info in requirements.items():
        # Secure the recipe dictionary layout by handling the jumbled row as missing
        if "sweet paprika" in name and "salt" in name:
            missing.append({"ingredient": name, "original": info["original"], "status": "missing"})
            continue
        contextual_match = (
            beef_recipe
            and name == "stew meat"
            and "beef" in pantry
        )

        # Skip standard pantry staples entirely from having or missing counts
        # Force combined staple and spice strings to separate cleanly from total scores
        if matches(name) or contextual_match or ingredient_matches(name, list(pantry)):
            have.append({"ingredient": name, "original": info["original"], "status": "have"})
            continue

        found_alternative = None

        for alternative in info["alternatives"]:
            alt_name, _ = (
                normalize_recipe_ingredient(
                    alternative
                )
            )

            if alt_name and matches(alt_name):
                found_alternative = alt_name
                break

        if found_alternative:
            substitutions.append({
                "ingredient": name,
                "use_instead": found_alternative,
                "reason": (
                    "The recipe itself lists this "
                    "as an acceptable alternative."
                )
            })
        else:
            missing.append({
                "ingredient": name,
                "original": info["original"],
                "substitutions": get_sensible_substitutions(
                    name
                )
            })

    total = (
        len(have)
        + len(missing)
        + len(substitutions)
    )

    matched = (
        len(have)
        + len(substitutions)
    )

    match_percent = (
        round((matched / total) * 100)
        if total
        else 0
    )

    return {
        "match_percent": match_percent,
        "have": have,
        "missing": missing,
        "substitutions": substitutions,
        "total_requirements": total,
        "matched_requirements": matched
    }

def search_web_recipes(user_ingredients, count=10):
    if not user_ingredients:
        return []

    if not BRAVE_API_KEY:
        print("Brave API key is missing.")
        return []

    ingredients = [
        clean_word(item)
        for item in user_ingredients
        if clean_word(item)
    ]

    if not ingredients:
        return []

    # Full-pantry search plus extra protein-specific queries if multiple proteins.
    queries = [" ".join(ingredients) + " recipe"]

    selected_protein_terms = []
    for item in ingredients:
        for meat_options in MEAT_GROUPS.values():
            if item in meat_options:
                selected_protein_terms.append(item)
                break

    if len(selected_protein_terms) > 1:
        for protein in selected_protein_terms:
            protein_query = protein + " recipe"
            if protein_query not in queries:
                queries.append(protein_query)

    try:
        results = []
        seen_urls = set()

        for query in queries:
            print("BRAVE SEARCH QUERY:", query)
            response = requests.get(
                BRAVE_SEARCH_URL,
                params={
                    "q": query,
                    "count": max(count, 20)
                },
                headers={
                    "X-Subscription-Token": BRAVE_API_KEY,
                    "Accept": "application/json"
                },
                timeout=10
            )

            if response.status_code != 200:
                print("Brave API response:", response.status_code, response.text)
                response.raise_for_status()

            data = response.json()
            web_results = data.get("web", {}).get("results", [])

            candidates = []

            for result in web_results:
                title = result.get("title", "").strip()
                url = result.get("url", "").strip()
                description = result.get("description", "").strip()

                if not title or not url or url in seen_urls:
                    continue

                candidates.append((title, url, description))
                seen_urls.add(url)

            # Fetch recipe pages concurrently instead of waiting for each
            # website to finish before starting the next one.
            def fetch_candidate(candidate):
                title, url, description = candidate
                recipe = extract_web_recipe(url)
                return title, url, description, recipe

            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [
                    executor.submit(fetch_candidate, candidate)
                    for candidate in candidates
                ]

                for future in as_completed(futures):
                    try:
                        title, url, description, recipe = future.result()
                    except Exception as e:
                        print("Recipe extraction error:", e)
                        continue

                    if not recipe:
                        print(
                            "Skipping search result - recipe could not be extracted:",
                            url
                        )
                        continue

                    if not recipe.get("name"):
                        recipe["name"] = title

                    if not recipe.get("ingredients"):
                        print(
                            "Skipping search result - no ingredients found:",
                            url
                        )
                        continue

                    # UNIVERSAL RECIPE INGREDIENT CLEANUP
                    #
                    # Preserve the source ingredient text separately so the
                    # actual recipe amount can be used later for recipe
                    # display, shopping, pricing, or monetization.
                    raw_ingredients = list(
                        recipe.get("ingredients", [])
                    )
                    recipe["raw_ingredients"] = raw_ingredients

                    cleaned_ingredients = []
                    for raw_ingredient in raw_ingredients:
                        if not isinstance(raw_ingredient, str):
                            continue

                        normalized, alternatives = normalize_recipe_ingredient(
                            raw_ingredient,
                            preserve_source=True
                        )

                        if not normalized:
                            continue

                        # Universal final identity extraction. This strips
                        # recipe-site metadata without changing the existing
                        # matching rules.
                        primary_identity = extract_ingredient_identity(
                            normalized
                        )

                        if primary_identity:
                            normalized = primary_identity

                        # UNIVERSAL PANTRY-STAPLE FILTER
                        #
                        # Reuse the existing ingredient matching engine
                        # and PANTRY_STAPLES definition so web-recipe
                        # ingestion follows the same staple rules as
                        # normal recipe matching.
                        #
                        # This removes source variants such as:
                        #   "cooking salt or kosher salt"
                        #   "lukewarm water"
                        #   "freshly ground black pepper"
                        #
                        # The original source line remains untouched in
                        # recipe["raw_ingredients"] for quantities,
                        # measurements, shopping, pricing, and monetization.
                        if ingredient_matches(
                            normalized,
                            list(PANTRY_STAPLES),
                            allow_pantry_staple=True,
                        ):
                            continue

                        # Some recipe sources add a descriptive word to a
                        # pantry staple, for example:
                        #   "cooking salt"
                        #   "lukewarm water"
                        #
                        # These are still pantry staples, but the complete
                        # phrase is not an exact PANTRY_STAPLES entry.
                        #
                        # Only remove the ingredient when the staple itself
                        # is a complete word and removing it leaves only
                        # descriptive/source wording. This deliberately
                        # avoids identities such as "water chestnuts" and
                        # "salted butter".
                        staple_words = {
                            word
                            for staple in PANTRY_STAPLES
                            for word in re.findall(r'[a-z]+', staple.lower())
                        }

                        identity_words = normalized.lower().split()

                        if (
                            identity_words
                            and any(
                                word in staple_words
                                for word in identity_words
                            )
                            and all(
                                word in {
                                    "cooking",
                                    "lukewarm",
                                    "warm",
                                    "cold",
                                    "hot",
                                    "room",
                                    "temperature",
                                    "fresh",
                                    "freshly",
                                    "ground",
                                    "cracked",
                                    "fine",
                                    "coarse",
                                    "kosher",
                                    "sea",
                                    "table",
                                }
                                or word in staple_words
                                for word in identity_words
                            )
                        ):
                            continue

                        # The normalizer may already have incorporated
                        # an OR choice directly into the normalized ingredient.
                        # Do not append the separate alternatives list again
                        # when that would duplicate the OR choices or reintroduce
                        # recipe-site metadata.
                        if alternatives and not re.search(
                            r'\bor\b',
                            normalized,
                            flags=re.IGNORECASE
                        ):
                            cleaned_alternatives = []

                            for alternative in alternatives:
                                alternative = alternative.strip()

                                if not alternative:
                                    continue

                                # Clean each OR alternative with the same universal
                                # ingredient normalizer used by the main ingredient.
                                # Do not require the ingredient to exist in the
                                # current vocabulary: legitimate ingredients such
                                # as paprika and chicken stock may not be listed there.
                                alternative_identity, nested_alternatives = (
                                    normalize_recipe_ingredient(
                                        alternative,
                                        preserve_source=False
                                    )
                                )

                                alternative_identity = alternative_identity.strip()

                                if not alternative_identity:
                                    continue

                                # A normalized alternative that still contains
                                # instruction-style wording is source metadata,
                                # not a second ingredient.
                                metadata_words = {
                                    "omit",
                                    "optional",
                                    "sub",
                                    "substitute",
                                    "between",
                                    "fingers",
                                    "make",
                                    "sure",
                                    "smoke",
                                    "point",
                                }

                                alternative_words = set(
                                    alternative_identity.lower().split()
                                )

                                if alternative_words & metadata_words:
                                    continue

                                # Bare descriptive words are not ingredient identities.
                                if alternative_identity.lower() in {
                                    "smoky",
                                    "more",
                                    "extra",
                                    "additional",
                                    "omit",
                                }:
                                    continue

                                if alternative_identity.lower() == normalized.lower():
                                    continue

                                cleaned_alternatives.append(
                                    alternative_identity
                                )

                            if cleaned_alternatives:
                                normalized = (
                                    normalized
                                    + " or "
                                    + " or ".join(
                                        cleaned_alternatives
                                    )
                                ).strip()

                        cleaned_ingredients.append(normalized)

                    recipe["ingredients"] = cleaned_ingredients

                    if not recipe.get("ingredients"):
                        print(
                            "Skipping search result - no usable ingredients found:",
                            url
                        )
                        continue

                    if not recipe.get("description"):
                        recipe["description"] = description

                    results.append(recipe)

                    if len(results) >= count:
                        # We already have enough usable recipes.
                        # Pending futures are cancelled where possible.
                        for pending in futures:
                            if not pending.done():
                                pending.cancel()
                        break

            if len(results) >= count:
                break

        return results

    except requests.HTTPError as e:
        print("Brave web search HTTP error:", e)
        return []

    except requests.RequestException as e:
        print("Brave web search error:", e)
        return []

def normalize_recipe_ingredient(text, preserve_source=False):
    if not text:
        return '', []

    text = text.lower().strip()

    # Preserve recipe-site slash alternatives without confusing them with
    # fractional quantities such as 1/4.
    #
    # Examples:
    #   "Plain / All Purpose Flour" -> "plain __SLASH_OR__ all purpose flour"
    #   "olive oil / vegetable oil" -> "olive oil __SLASH_OR__ vegetable oil"
    #   "1/4 cup / 40g Plain / All Purpose Flour"
    #       -> preserve 1/4 while separating the ingredient alternatives.
    text = re.sub(
        r'(?<!\d)\s*/\s*(?!\d)',
        ' ZZSLASHALTZZ ',
        text,
        flags=re.IGNORECASE,
    )

    # Salt and pepper are universal pantry staples and never become
    # recipe requirements, regardless of common recipe lead-in wording.
    salt_pepper_only = re.fullmatch(
        r'\s*'
        r'(?:a|an|the|some|any|each|one|two|three|four|five)?\s*'
        r'(?:pinch|dash|little|handful)?\s*'
        r'(?:of\s+)?'
        r'(?:'
        r'(?:kosher|sea|table|fine\s+sea|coarse\s+sea|fine|coarse)?\s*salt'
        r'|'
        r'(?:(?:freshly\s+ground|ground|cracked)\s+)?'
        r'(?:black|white)?\s*pepper'
        r')'
        r'\s*',
        text,
        flags=re.IGNORECASE
    )

    if salt_pepper_only:
        return '', []

    # Salt and pepper are universal pantry staples. When a recipe
    # contains salt-and-pepper wording, remove that seasoning before
    # identifying the actual food ingredient. This handles phrases such
    # as 'salt and pepper' and 'homemade seasoned salt and pepper'.
    if re.search(r'\bsalt\b', text) and re.search(r'\bpepper\b', text):
        seasoning_removed = re.sub(
            r'(?i)\b(?:kosher|sea|table|fine\s+sea|coarse\s+sea|fine|coarse)?\s*salt\b',
            ' ',
                text,
        )
        seasoning_removed = re.sub(
            r'(?i)\b(?:(?:freshly\s+ground|ground|cracked)\s+)?(?:black|white)?\s*pepper\b',
            ' ',
            seasoning_removed,
        )
        seasoning_removed = re.sub(
            r'\b(?:homemade|seasoned|freshly|fresh|ground|cracked|fine|coarse)\b',
            ' ',
            seasoning_removed,
            flags=re.IGNORECASE,
        )

        # Remove recipe measurement/lead-in words left behind after
        # salt and pepper themselves have been removed.
        seasoning_removed = re.sub(
            r'\b(?:tsp|tbsp|tbs|teaspoons?|tablespoons?|each|of)\b',
            ' ',
            seasoning_removed,
            flags=re.IGNORECASE,
        )

        seasoning_removed = re.sub(r'[^a-z\s]', ' ', seasoning_removed.lower())
        seasoning_removed = re.sub(r'\s+', ' ', seasoning_removed).strip()
        seasoning_removed = re.sub(r'^(?:and|or|,)+\s*|\s*(?:and|or|,)+$', '', seasoning_removed).strip()

        if not seasoning_removed:
            return '', []

        known_after_seasoning = extract_known_ingredient(seasoning_removed)
        if known_after_seasoning:
            return known_after_seasoning, []

    # Salt and pepper are universal pantry staples and never become
    # recipe requirements, whether they appear alone or together.
    if re.fullmatch(
        r'\s*(?:'
        r'(?:kosher|sea|table|fine\s+sea|coarse\s+sea|fine|coarse)?\s*salt'
        r'|'
        r'(?:(?:freshly[\s-]+ground|ground|cracked)\s+)?(?:black|white)?\s*pepper'
        r')\s+(?:little|pinch|dash|to\s+taste|as\s+needed)?\s*',
        text,
        flags=re.IGNORECASE
    ):
        return '', []

    # A standalone preparation instruction is not an ingredient.
    # It can appear as a separate comma-delimited fragment after the
    # real ingredient has already been separated.
    if re.match(
        r'^(?:cut|chop|dice|slice|cube|halve|peel|trim|remove|'
        r'grate|shred|mince|crush|mash|blend|whisk|beat|stir|'
        r'toss|drain|rinse|soak|cook|bake|boil|simmer|roast|'
        r'fry|saute|sauté)\b',
        text,
        flags=re.IGNORECASE
    ):
        return '', []

    # Treat common ingredient separators as separate items.
    
    # Surgically separate bundled spices and staples with clean structural commas
    if 'sweet paprika' in text and 'salt and pepper' in text:
        text = text.replace('sweet paprika', 'sweet paprika,').replace('each ', '')
        text = text.replace('salt and pepper', 'salt, pepper')

    # Decode common HTML entities.
    text = re.sub(r'&quot;|&amp;', ' ', text)

    # Find alternatives such as:
    # 'sesame oil (or olive oil)'
    # 'chicken broth (or water)'
    alternatives = re.findall(r'\bor\s+([^()]+)', text)

    # When an alternative follows a comma, keep it in  and
    # remove it from the primary ingredient text before known-ingredient
    # extraction. This prevents duplicate identities such as:
    # "Lucini olive oil, or any high quality olive oil"
    # becoming "lucini olive oil olive oil".
    text = re.sub(
        r'\s*,\s*or\s+.*$',
        '',
        text,
        flags=re.IGNORECASE
    )

    # Preserve comma-separated OR lists with a shared ingredient tail.
    # Example:
    #   "red, green, or orange red peppers"
    # becomes primary "red peppers" with alternatives
    # "green peppers" and "orange red peppers".
    comma_or_match = re.fullmatch(
        r'\s*(.*?)\s*,\s*(.*?)\s*,?\s+or\s+(.+?)\s*',
        text,
        flags=re.IGNORECASE
    )

    if comma_or_match:
        choice1 = comma_or_match.group(1).strip()
        choice2 = comma_or_match.group(2).strip()
        choice3 = comma_or_match.group(3).strip()

        tail_words = choice3.split()

        if len(tail_words) >= 2:
            shared_tail = ' '.join(tail_words[-2:])
            final_head = ' '.join(tail_words[:-2]).strip()

            if final_head:
                options = [
                    choice1 + ' ' + shared_tail,
                    choice2 + ' ' + shared_tail,
                    final_head + ' ' + shared_tail,
                ]
            else:
                options = [
                    choice1 + ' ' + shared_tail,
                    choice2 + ' ' + shared_tail,
                    shared_tail,
                ]

            text = options[0]
            alternatives = options[1:]

    # For an ingredient written as "ingredient or alternative", preserve
    # the shared ingredient context. For example:
    #   "chicken legs or breasts" -> "chicken legs", ["chicken breasts"]
    # while fully specified alternatives remain unchanged.
    or_match = re.search(r'\s+or\s+([^()]+)$', text, flags=re.IGNORECASE)

    if or_match:
        primary_text = text[:or_match.start()].strip()
        alternative_text = or_match.group(1).strip()

        primary_words = primary_text.split()
        alternative_words = alternative_text.split()

        if (
            primary_words
            and alternative_words
            and len(alternative_words) == 1
            and primary_words[-1].lower() not in {
                'and', 'or'
            }
        ):
            shared_prefix = primary_words[:-1]
            if shared_prefix:
                alternatives = [
                    ' '.join(shared_prefix + alternative_words)
                ]

        text = primary_text

    # Preserve ingredient identity when a parenthetical contains the actual ingredient.
    text = re.sub('boneless[ ]*[(]([^)]*)[)]', lambda m: m.group(1), text)

    # Remove remaining parenthetical preparation notes.
    text = re.sub(r'\([^)]*\)', '', text)

    # Remove quantities, including recipe-site forms where the unit
    # is attached directly to the number, such as 2ea, 1mass, 2spoon,
    # or 2~3bowl.
    text = re.sub(
        r'\b\d+(?:[./]\d+)?(?:\s*[~\-]\s*\d+(?:[./]\d+)?)?'
        r'(?=\s*(?:ea|mass|spoon|spoons|bowl|bowls)\b)',
        ' ',
        text,
        flags=re.IGNORECASE
    )

    # Remove ordinary quantities that are separated from their units.
    text = re.sub(
        r'\b\d+(?:[./]\d+)?(?:\s*[~\-]\s*\d+(?:[./]\d+)?)?'
        r'(?:\s*(?:g|gram|grams|kg|kilogram|kilograms|lbs?|pounds?|oz|ounces?|'
        r'ml|milliliter|milliliters|l|liter|liters|cups?|cup|tbsp|tbs|'
        r'tablespoons?|tsp|teaspoons?|cloves?|heads?|ea|mass|spoon|spoons|'
        r'bowl|bowls))?\b',
        ' ',
        text,
        flags=re.IGNORECASE
    )

    # Remove common units and size words, whether attached to the
    # quantity or separated by whitespace.
    text = re.sub(
        r'\b(?:g|gram|grams|kg|kilogram|kilograms|lbs?|pounds?|oz|ounces?|'
        r'ml|milliliter|milliliters|l|liter|liters|cups?|cup|tbsp|tbs|'
        r'tablespoons?|tsp|teaspoons?|cloves?|heads?|ea|mass|spoon|spoons|'
        r'bowl|bowls|large|medium|small|thin|inches?|inch)\b',
        ' ',
        text,
        flags=re.IGNORECASE
    )

    # Web-recipe ingestion only: after quantities and units are removed,
    # re-check standalone salt and pepper. This catches source forms such as
    # "1 tsp kosher salt", "1/2 tsp black pepper", and "1.5 tsp fine sea salt".
    if preserve_source:
        if re.fullmatch(
            r'\s*(?:'
            r'(?:kosher|sea|table|fine\s+sea|coarse\s+sea|fine|coarse)?\s*salt'
            r'|'
            r'(?:(?:freshly[\s-]+ground|ground|cracked)\s+)?'
            r'(?:black|white)?\s*pepper'
            r')\s*',
            text,
            flags=re.IGNORECASE
        ):
            return '', []

    # Web-recipe ingestion only: alternatives were captured before
    # quantity/unit cleanup, so clean their measurement metadata now.
    if preserve_source:
        cleaned_alternatives = []

        for alternative in alternatives:
            alternative = re.sub(
                r'\b\d+(?:[./]\d+)?(?:\s*[~\-]\s*\d+(?:[./]\d+)?)?'
                r'(?:\s*(?:g|gram|grams|kg|kilogram|kilograms|lbs?|pounds?|'
                r'oz|ounces?|ml|milliliter|milliliters|l|liter|liters|'
                r'cups?|cup|tbsp|tbs|tablespoons?|tsp|teaspoons?|cloves?|'
                r'heads?|ea|mass|spoon|spoons|bowl|bowls))?\b',
                ' ',
                alternative,
                flags=re.IGNORECASE
            )

            alternative = re.sub(
                r'\b(?:g|gram|grams|kg|kilogram|kilograms|lbs?|pounds?|'
                r'oz|ounces?|ml|milliliter|milliliters|l|liter|liters|'
                r'cups?|cup|tbsp|tbs|tablespoons?|tsp|teaspoons?|cloves?|'
                r'heads?|ea|mass|spoon|spoons|bowl|bowls)\b',
                ' ',
                alternative,
                flags=re.IGNORECASE
            )

            alternative = re.sub(r'\s+', ' ', alternative).strip()

            if alternative:
                cleaned_alternatives.append(alternative)

        alternatives = cleaned_alternatives

        # Re-check salt and pepper after quantity/unit cleanup.
        # This catches source forms such as:
        # "1/2 tsp each salt and pepper".
        if (
            re.search(r'\\bsalt\\b', text)
            and re.search(r'\\bpepper\\b', text)
        ):
            text = re.sub(
                r'\\b(?:kosher|sea|table|fine\\s+sea|coarse\\s+sea|'
                r'fine|coarse)?\\s*salt\\b',
                ' ',
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r'\\b(?:(?:freshly\\s+ground|ground|cracked)\\s+)?'
                r'(?:black|white)?\\s*pepper\\b',
                ' ',
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(
                r'\\b(?:each|and|or|homemade|seasoned|freshly|fresh|'
                r'ground|cracked|fine|coarse)\\b',
                ' ',
                text,
                flags=re.IGNORECASE
            )
            text = re.sub(r'\\s+', ' ', text).strip()

            if not text:
                return '', []

    # Remove trailing recipe unit/measurement metadata that some
    # recipe sites append after the ingredient identity.
    text = re.sub(
        r'\s+\b(?:ea|each|mass|spoon|spoons)\b\s*$',
        '',
        text,
        flags=re.IGNORECASE
    )

    # Restore slash-written ingredient alternatives after quantity/unit
    # cleanup. The private marker survives until this point so fractional
    # quantities such as 1/4 are never mistaken for alternatives.
    #
    # Examples:
    #   "plain __SLASH_OR__ all purpose flour"
    #       -> primary "plain flour", alternative "all purpose flour"
    #   "olive oil __SLASH_OR__ vegetable oil"
    #       -> primary "olive oil", alternative "vegetable oil"
    #   "chicken broth __SLASH_OR__ water"
    #       -> primary "chicken broth", alternative "water"
    slash_parts = [
        part.strip()
        for part in text.split('ZZSLASHALTZZ')
        if part.strip()
    ]

    if len(slash_parts) >= 2:
        # A quantity can be attached directly to a unit, such as "40g".
        # After the quantity is removed, the unit may remain on the slash
        # side. Clean those residual measurement units before identifying
        # the ingredient alternatives.
        cleaned_slash_parts = []

        for part in slash_parts:
            part = re.sub(
                r'\b(?:g|gram|grams|kg|kilogram|kilograms|lbs?|pounds?|oz|ounces?|'
                r'ml|milliliter|milliliters|l|liter|liters|cups?|cup|tbsp|tbs|'
                r'tablespoons?|tsp|teaspoons?|cloves?|heads?|ea|mass|spoon|spoons|'
                r'bowl|bowls|large|medium|small|thin|inches?|inch)\b',
                ' ',
                part,
                flags=re.IGNORECASE
            )
            part = re.sub(r'\s+', ' ', part).strip()

            if part:
                cleaned_slash_parts.append(part)

        slash_parts = cleaned_slash_parts

        if len(slash_parts) >= 2:
            primary_slash = slash_parts[0]
            slash_alternatives = slash_parts[1:]

            # Recipe sites sometimes abbreviate the first side of an
            # alternative pair, e.g. "Plain / All Purpose Flour".
            # Complete the abbreviated side using the shared final
            # ingredient word. Fully specified alternatives are unchanged.
            first_alternative = slash_alternatives[0]
            primary_words = primary_slash.split()
            alternative_words = first_alternative.split()

            # When an earlier slash side is only measurement metadata,
            # the actual ingredient alternative may be the final slash
            # side. Use the final alternative as the shared-tail source
            # when it gives us a more complete ingredient identity.
            tail_source = slash_alternatives[-1]
            tail_words = tail_source.split()

            if len(tail_words) >= 2:
                alternative_words = tail_words

            if (
                primary_words
                and len(alternative_words) >= 2
                and primary_words[-1].lower() != alternative_words[-1].lower()
            ):
                shared_tail = alternative_words[-1]
                candidate = ' '.join(primary_words + [shared_tail])

                if len(primary_words) == 1:
                    primary_slash = candidate
                elif extract_known_ingredient(candidate):
                    primary_slash = candidate

            text = primary_slash
            alternatives = slash_alternatives

    # Reduce descriptive meat preparation wording to the actual cut.
    text = re.sub(r'\bcenter\s+cut\s+(pork\s+loin)\b.*', r'\1', text)

    # Remove trailing bone/skin preparation wording after the ingredient identity.
    # Examples: "chicken breasts, bone and skin on" -> "chicken breasts"
    #           "chicken breast, skin and bone on" -> "chicken breast"
    text = re.sub(
        r'\s*,?\s*(?:bone|skin)\s+and\s+(?:skin|bone)\s+on\b.*$',
        '',
        text,
        flags=re.IGNORECASE
    )

    # Remove preparation descriptors.
    text = re.sub(r'\bstems?\s+removed\b', ' ', text)

    # "Patted dry" and any preparation wording that follows it
    # are recipe metadata, not ingredient identity.
    text = re.sub(
        r'\s*,?\s*\bpatted\s+dry\b.*$',
        '',
        text,
        flags=re.IGNORECASE
    )

    # Remove a trailing preparation instruction universally.
    # Once the ingredient is named, everything after a preparation
    # phrase such as cut into / cut in / cut up into is recipe metadata.
    text = re.sub(
        r'\s*,?\s+cut\s+(?:up\s+)?(?:into|in)\b.*$',
        '',
        text,
        flags=re.IGNORECASE
    )


    text = re.sub(
        r'\b(?:diced|chopped|minced|cubed|sliced|halved|fresh|freshly|finely|uncooked|cooked|beaten|whisked|grated|shredded|well|low sodium|toasted|dried|peeled|thinly|boneless|skinless|bone[ -]in|skin[ -]on|raw|each|slice|slices|strip|strips|piece|pieces|chunk|chunks|wedge|wedges|stalk|stalks|spear|spears|leaf|leaves|ear|ears|knob|knobs|sprig|sprigs|sheet|sheets|stem|stems|pod|pods|rinsed|rinsed|seeds|seed|veins|vein|packed)\b',
        ' ',
        text,
        flags=re.IGNORECASE
    )

    # Preparation phrases may leave connector words behind after their
    # descriptors are removed.
    text = re.sub(
        r'\b(?:removed|remove)\b',
        ' ',
        text,
        flags=re.IGNORECASE
    )

    # Normalize common recipe wording.
    text = re.sub(r'\b(?:any|some|your favorite|favorite)\s+', '', text)

    # Normalize specific ingredient descriptions.
    # These rules deliberately preserve distinct ingredients such as
    # bell pepper and red pepper flakes.
    text = re.sub(r'\bcracked\s+(?:black\s+)?pepper\b', 'pepper', text)
    text = re.sub(r'\bblack\s+peppercorns\b', 'pepper', text)
    text = re.sub(r'\bspaghetti\s+noodles\b', 'spaghetti', text)
    text = re.sub(r'\ba\s+sprig\s+(?:of\s+)?thyme\b', 'thyme', text)

    # Normalize black pepper to the pantry staple 'pepper'.
    # During web-recipe ingestion, however, pepper is a universal pantry
    # staple and must never become a recipe requirement.
    if preserve_source and re.fullmatch(
        r'\s*(?:freshly[\s-]+ground|ground)\s+black\s+pepper\s*',
        text,
        flags=re.IGNORECASE
    ):
        return '', []

    text = re.sub(
        r'\b(?:freshly[\s-]+ground|ground)\s+black\s+pepper\b',
        'pepper',
        text
    )


    # Remove common recipe wording.
    # Words such as "more" and "serving" commonly appear
    # in phrases like "plus more for serving" and are not
    # separate ingredients.
    text = re.sub(
        r'\b(?:of|to|for|as needed|divided|plus|more|serving|taste|garnish)\b',
        ' ',
        text
    )

    # Normalize standalone black pepper to generic pepper.
    # Keep black pepper intact inside compound ingredients.
    if re.fullmatch(r'\s*black\s+pepper\s*', text):
        text = 'pepper'

    # Remove common quantity and serving words.
    # These describe how much of an ingredient is used, not the ingredient itself.
    text = re.sub(
        r'\b(?:bunch|pinch|dash|handful|package|packages|can|cans|stick|sticks|few|couple|little)\b',
        ' ',
        text
    )

    # Keep letters and spaces.
    text = re.sub(r'[^a-z\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    # Remove stray source-artifact markers that appear as a leading x.
    # Examples: "x chicken breasts" -> "chicken breasts".
    text = re.sub(r'^x\s+', '', text, flags=re.IGNORECASE)

    # Remove trailing recipe-site metadata that is not ingredient identity.
    # Examples:
    #   "olive oil split" -> "olive oil"
    #   "baby bella mushrooms quartered long ways" -> "baby bella mushrooms"
    #   "flour option use a gluten free flour" -> "flour"
    text = re.sub(
        r'\s+\bsplit\b.*$',
        '',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\s+\bquartered\s+long\s+ways?\b.*$',
        '',
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r'\s+\boption\s+use\b.*$',
        '',
        text,
        flags=re.IGNORECASE
    )

    # Remove trailing recipe-site wording such as 'with the tip a'.
    # This is metadata, not part of the ingredient identity.
    text = re.sub(
        r'\s+\bwith\s+the\s+tip\s+a\b.*$',
        '',
        text,
        flags=re.IGNORECASE
    )

    # Preparation/connective words cannot be standalone ingredients.
    if text in {
        'into',
        'in',
        'to',
        'for',
        'of',
        'and',
        'or',
    }:
        return '', []

    # Universal cleanup: remove non-ingredient lead-in wording.
    # Do NOT remove meaningful ingredient descriptors such as
    # ground, boneless, fresh, cracked, etc.
    text = re.sub(
        r'^(?:a|an|the|some|any|each|one|two|three|four|five|six|seven|eight|nine|ten|of)\s+',
        '',
        text,
        flags=re.IGNORECASE
    )

    # Final normalization: standalone black pepper becomes generic pepper.
    # Compound ingredients such as black pepper and salt remain unchanged.
    if re.fullmatch(r'\s*black\s+pepper\s*', text):
        text = 'pepper'

    # PLAN A: identify the actual ingredient and ignore recipe metadata.
    # The known-ingredient vocabulary is authoritative; the longest match
    # wins so specific ingredients are preserved over broad parent terms.
    if not preserve_source:
        known_ingredient = extract_known_ingredient(text)
        if known_ingredient:
            text = known_ingredient

    canonical_text = canonical_ingredient_identity(text)

    canonical_alternatives = []

    for alternative in alternatives:
        canonical_alternative = canonical_ingredient_identity(
            alternative
        )

        if (
            canonical_alternative
            and canonical_alternative != canonical_text
        ):
            canonical_alternatives.append(
                canonical_alternative
            )

    return canonical_text, canonical_alternatives

def normalize_recipe_metadata(value):
    """
    Normalize recipe cuisine or diet metadata from Recipe Schema
    into simple, consistent lowercase values.
    """
    if not value:
        return []

    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = value
    else:
        return []

    normalized = []

    for item in values:
        if not isinstance(item, str):
            continue

        item = item.strip().lower()

        if not item:
            continue

        # Normalize schema.org diet URLs.
        item = re.sub(
            r"^https?://schema\.org/",
            "",
            item
        )

        # Normalize common diet schema names.
        diet_map = {
            "vegandiet": "vegan",
            "vegetariandiet": "vegetarian",
            "halaldiet": "halal",
            "kosherdiet": "kosher",
            "glutenfreediet": "gluten-free",
            "lowcaloriediet": "low-calorie",
            "lowfatdiet": "low-fat",
            "lowcarbdiet": "low-carb",
        }

        item = diet_map.get(item, item)

        # Normalize common cuisine wording.
        if item.endswith("-inspired"):
            item = item[:-9].strip()

        if item and item not in normalized:
            normalized.append(item)

    return normalized

def extract_ingredient_identity(text):
    """
    Universal recipe-source ingredient identity extraction.

    The result is the ingredient itself, with quantities, portions,
    preparation instructions, cooking instructions, editorial notes,
    and source-metadata fragments removed.

    Meaningful ingredient descriptors are preserved:
        ground beef
        lean ground beef
        grass fed ground beef
        yellow onion
        green bell pepper
        russet potatoes
        baby portobello mushrooms
        salmon filets

    Preparation is never allowed to become part of the identity:
        garlic lightly smashed -> garlic
        ground beef browned and drained -> ground beef
        corn cut off the cob -> corn
        russet potatoes peeled and cubed -> russet potatoes
    """
    if not isinstance(text, str):
        return ""

    cleaned = text.lower().strip()
    if not cleaned:
        return ""

    # Decode common HTML entities.
    cleaned = re.sub(r"&(?:quot|amp|apos|lt|gt);", " ", cleaned)

    # Keep letters and whitespace only. Quantities, fractions, punctuation,
    # measurements, and source punctuation are not ingredient identity.
    cleaned = re.sub(r"[^a-z\s]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned:
        return ""

    # These are source/editorial words, not ingredient identity.
    metadata_words = {
        "roughly", "rough", "lightly", "heavily",
        "mixed", "torn", "crushed", "smashed",
        "divided", "optional", "option", "preferred",
        "preferably", "desired", "needed", "required",
        "recommended", "favorite", "favourite",
        "freshly", "approximately", "about",
    }

    # Remove standalone metadata words first.
    words = [
        word for word in cleaned.split()
        if word not in metadata_words
    ]
    cleaned = " ".join(words).strip()

    if not cleaned:
        return ""

    # Preparation/instruction boundaries.
    #
    # Once one of these begins, everything after it is preparation,
    # cooking, handling, or editorial explanation rather than ingredient
    # identity. This deliberately preserves meaningful descriptors before
    # the boundary, including "ground", "lean", "grass fed", "russet",
    # "baby", "portobello", etc.
    preparation_patterns = [
        r"\bcut\s+(?:into|in|off|from|up)\b",
        r"\bcut\b",
        r"\bchop(?:ped|ping)?\b",
        r"\bdice(?:d|ing)?\b",
        r"\bslice(?:d|s|ing)?\b",
        r"\bmince(?:d|ing)?\b",
        r"\bsmash(?:ed|ing)?\b",
        r"\bcrush(?:ed|ing)?\b",
        r"\bpeel(?:ed|ing)?\b",
        r"\btrim(?:med|ming)?\b",
        r"\bhalve(?:d|s|ing)?\b",
        r"\bquarter(?:ed|ing)?\b",
        r"\bshred(?:ded|ding)?\b",
        r"\bgrate(?:d|ing)?\b",
        r"\bchiffonade\b",
        r"\bjulienne\b",
        r"\broughly\b",
        r"\blightly\b",
        r"\bheavily\b",
        r"\bbrown(?:ed|ing)?\b",
        r"\bcook(?:ed|ing)?\b",
        r"\bboil(?:ed|ing)?\b",
        r"\bsimmer(?:ed|ing)?\b",
        r"\broast(?:ed|ing)?\b",
        r"\bbake(?:d|ing)?\b",
        r"\bsaute(?:d|ing)?\b",
        r"\bfry(?:ed|ing)?\b",
        r"\bsear(?:ed|ing)?\b",
        r"\bgrill(?:ed|ing)?\b",
        r"\bdrain(?:ed|ing)?\b",
        r"\bpat(?:ted)?\s+dry\b",
        r"\bremove(?:d|s|ing)?\b",
        r"\bremoved\b",
        r"\bdiscard(?:ed|ing)?\b",
        r"\btear(?:n|ing)?\b",
        r"\bleave(?:s|ing)?\b",
        r"\bskin(?:ned|ning)?\b",
        r"\bseed(?:ed|ing)?\b",
        r"\bcore(?:d|ing)?\b",
        r"\bso\s+(?:dice|chop|slice|cut|cube|halve|peel|trim)\b",
    ]

    prep_boundary = re.compile(
        r"(?:\s+|^)(" + "|".join(preparation_patterns) + r")\b",
        re.IGNORECASE,
    )

    # Source/editorial boundaries. Everything after these is explanatory
    # prose rather than ingredient identity.
    editorial_patterns = [
        r"\s+a\s+substitute\b",
        r"\s+substitute(?:s)?\b",
        r"\s+sub\b",
        r"\s+if\s+you\b",
        r"\s+if\s+they\b",
        r"\s+if\s+it\b",
        r"\s+use\s+(?:a|an|the|your|any|some)\b",
        r"\s+make\s+sure\b",
        r"\s+with\b",
        r"\s+from\b",
        r"\s+so\s+(?:dice|chop|slice|cut|cube|halve|peel|trim)\b",
    ]

    def clean_part(part):
        part = part.strip()
        if not part:
            return ""

        # Reject obvious non-ingredient fragments immediately.
        invalid_starts = {
            "a", "an", "the", "and", "or", "of", "to", "for",
            "with", "from", "use", "so", "if", "as", "in", "into",
            "off", "on", "up", "down",
        }

        if part in invalid_starts:
            return ""

        if any(part.startswith(prefix + " ") for prefix in invalid_starts):
            return ""

        # Remove editorial/source explanations.
        for pattern in editorial_patterns:
            part = re.sub(
                pattern + r".*$",
                "",
                part,
                flags=re.IGNORECASE,
            ).strip()

        if not part:
            return ""

        # Remove preparation instructions from the first preparation
        # boundary onward.
        match = prep_boundary.search(part)
        if match:
            part = part[:match.start()].strip()

        if not part:
            return ""

        # Remove trailing metadata/connective wording.
        part = re.sub(
            r"\s+(?:roughly|rough|lightly|heavily|from|and|with|"
            r"if|so|off|up|down)$",
            "",
            part,
            flags=re.IGNORECASE,
        ).strip()

        # A valid identity cannot end in a connective or instruction word.
        if not part or part in invalid_starts:
            return ""

        # Reject fragments that are clearly source instructions rather than
        # ingredients.
        instruction_only = {
            "dice", "chop", "slice", "cut", "cube", "halve",
            "peel", "trim", "mince", "smash", "crush",
            "browned", "cooked", "drained", "removed",
            "roughly", "rough", "lightly", "heavily",
            "off", "so", "from", "or",
        }

        if part in instruction_only:
            return ""

        # Reject prose-like fragments containing only instruction/editorial
        # vocabulary. This prevents source text such as "if they re you want
        # the mushrooms to be the same size" from becoming an ingredient.
        prose_words = {
            "if", "they", "you", "want", "the", "same", "size",
            "make", "sure", "use", "your", "some", "any",
            "removed", "leaves", "stems", "stem", "roughly",
            "from", "into", "off",
        }

        part_words = part.split()
        if part_words and all(word in prose_words for word in part_words):
            return ""

        return re.sub(r"\s+", " ", part).strip()

    # Clean OR alternatives independently. Invalid alternatives disappear
    # instead of becoming fake ingredients.
    parts = re.split(r"\s+or\s+", cleaned, flags=re.IGNORECASE)
    identities = []

    for part in parts:
        identity = clean_part(part)
        if not identity:
            continue

        if identity not in identities:
            identities.append(identity)

    if not identities:
        return ""

    return canonical_ingredient_identity(
        " or ".join(identities)
    )

def extract_known_ingredient(text):
    # Extract the actual known ingredient while ignoring surrounding
    # recipe metadata. Never extract a shorter ingredient from the
    # middle of a different ingredient name such as "chicken stock".
    if not text:
        return ''

    cleaned = re.sub(r'[^a-z\s]', ' ', text.lower())
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    if not cleaned:
        return ''

    if ' and ' in cleaned or ',' in cleaned:
        return ''

    known = set()

    for variants in CORE_INGREDIENTS.values():
        known.update(variants)

    for category_values in COMMON_INGREDIENTS.values():
        known.update(category_values)

    known = sorted(
        known,
        key=lambda x: (len(x.split()), len(x)),
        reverse=True
    )

    # Exact match is always authoritative.
    if cleaned in known:
        return cleaned

    metadata_words = {
        'a', 'an', 'the', 'some', 'any', 'each',
        'one', 'two', 'three', 'four', 'five',
        'six', 'seven', 'eight', 'nine', 'ten',
        'fresh', 'freshly', 'dried', 'raw', 'cooked',
        'uncooked', 'beaten', 'whisked', 'grated',
        'shredded', 'finely', 'thinly', 'boneless',
        'skinless', 'peeled', 'diced', 'chopped',
        'minced', 'cubed', 'sliced', 'halved',
        'large', 'medium', 'small', 'scant', 'heaping',
        'lightly', 'well', 'seasoned', 'homemade',
        'cut', 'into', 'in', 'pieces', 'piece',
        'chunks', 'chunk', 'cubes', 'cube',
        'strips', 'strip', 'slices', 'slice',
        'wedges', 'wedge', 'stems', 'stem',
        'removed', 'divided', 'plus', 'more',
        'serving', 'taste', 'garnish'
    }

    for ingredient in known:
        pattern = (
            r'(?<![a-z])'
            + re.escape(ingredient.lower())
            + r'(?![a-z])'
        )

        match = re.search(pattern, cleaned)
        if not match:
            continue

        before = cleaned[:match.start()].strip().split()
        after = cleaned[match.end():].strip().split()

        # Anything surrounding the ingredient must be metadata.
        if all(word in metadata_words for word in before + after):
            return ingredient.lower()

    return ''

def extract_web_recipe(url):
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": "Mozilla/5.0"
            },
            timeout=10
        )

        response.raise_for_status()

        html = response.text

        matches = re.findall(
            r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL | re.IGNORECASE
        )

        def is_recipe_type(value):
            if isinstance(value, str):
                return value.lower() == "recipe"
            if isinstance(value, list):
                return any(
                    isinstance(x, str)
                    and x.lower() == "recipe"
                    for x in value
                )
            return False

        def instruction_text(instructions):
            output = []

            if isinstance(instructions, str):
                return [instructions]

            if not isinstance(instructions, list):
                return output

            for item in instructions:
                if isinstance(item, str):
                    output.append(item)

                elif isinstance(item, dict):
                    item_type = item.get("@type")

                    if item_type == "HowToStep":
                        text = item.get("text", "")
                        if text:
                            output.append(text)

                    elif item_type == "HowToSection":
                        steps = item.get(
                            "itemListElement",
                            []
                        )

                        for step in steps:
                            if isinstance(step, dict):
                                text = step.get(
                                    "text",
                                    ""
                                )
                                if text:
                                    output.append(text)

            return output

        def build_recipe(item):
            if not isinstance(item, dict):
                return None

            if not is_recipe_type(
                item.get("@type")
            ):
                return None

            ingredients = item.get(
                "recipeIngredient",
                []
            )

            if not isinstance(
                ingredients,
                list
            ):
                if (
                    isinstance(ingredients, str)
                    and "<li" in ingredients.lower()
                ):
                    ingredients = re.findall(
                        r"<li[^>]*>(.*?)</li>",
                        ingredients,
                        re.DOTALL | re.IGNORECASE
                    )

                    ingredients = [
                        re.sub(r"<[^>]+>", " ", item)
                        for item in ingredients
                    ]

                    ingredients = [
                        html_lib.unescape(
                            re.sub(r"\\s+", " ", item).strip()
                        )
                        for item in ingredients
                        if item.strip()
                    ]
                else:
                    ingredients = [ingredients]

            instructions = instruction_text(
                item.get(
                    "recipeInstructions",
                    []
                )
            )

            return {
                "name": html_lib.unescape(
                    item.get(
                        "name",
                        ""
                    )
                ),
                "url": url,
                "ingredients": ingredients,
                "instructions": instructions,
                "description": item.get(
                    "description",
                    ""
                ),
                "recipeCuisine": normalize_recipe_metadata(
                    item.get(
                        "recipeCuisine",
                        ""
                    )
                ),
                "suitableForDiet": normalize_recipe_metadata(
                    item.get(
                        "suitableForDiet",
                        ""
                    )
                ),
                "nutrition": item.get(
                    "nutrition",
                    {}
                ),
                "recipeYield": item.get(
                    "recipeYield",
                    ""
                ),
                "prepTime": item.get(
                    "prepTime",
                    ""
                ),
                "cookTime": item.get(
                    "cookTime",
                    ""
                ),
                "totalTime": item.get(
                    "totalTime",
                    ""
                ),
                "recipeCategory": item.get(
                    "recipeCategory",
                    ""
                ),
                "keywords": item.get(
                    "keywords",
                    ""
                )
            }

        for raw_json in matches:
            try:
                data = json.loads(
                    raw_json.strip()
                )
            except (
                json.JSONDecodeError,
                ValueError
            ):
                continue

            items = (
                data
                if isinstance(data, list)
                else [data]
            )

            for item in items:
                recipe = build_recipe(item)

                if recipe:
                    return recipe

                if isinstance(item, dict):
                    graph = item.get(
                        "@graph",
                        []
                    )

                    if isinstance(
                        graph,
                        list
                    ):
                        for graph_item in graph:
                            recipe = build_recipe(
                                graph_item
                            )

                            if recipe:
                                return recipe

        print(
            "No Recipe Schema found:",
            url
        )
        return None

    except requests.HTTPError as e:
        print(
            "Recipe page HTTP error:",
            e
        )
        return None

    except requests.RequestException as e:
        print(
            "Recipe page request error:",
            e
        )
        return None

    except Exception as e:
        print(
            "Recipe extraction error:",
            e
        )
        return None

def search_recipe(ingredient):

    try:

        response = requests.get(
            "https://recipe-api.com/api/v1/recipes",
            params={
                "q": ingredient,
                "per_page": 20
            },
            headers={
                "X-API-Key": RECIPE_API_KEY
            },
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        recipes = data.get("data", []) or []

        results = []

        for recipe in recipes:

            results.append({
                "idMeal": recipe.get("id"),
                "strMeal": recipe.get(
                    "name",
                    "Recipe"
                )
            })

        return results

    except requests.RequestException as e:

        print("Recipe API search error:", e)

        return []

# ---------------------------------------------------------
# GET COMPLETE RECIPE - RECIPE API
# ---------------------------------------------------------

def get_recipe(meal_id):

    if meal_id in RECIPE_CACHE:
        return RECIPE_CACHE[meal_id]


    try:

        response = requests.get(
            f"https://recipe-api.com/api/v1/recipes/{meal_id}",
            headers={
                "X-API-Key": RECIPE_API_KEY
            },
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        recipe = data.get("data")

        if not recipe:
            return None

        ingredients = []

        for group in recipe.get(
            "ingredients",
            []
        ):

            for item in group.get(
                "items",
                []
            ):

                ingredients.append({

                    "ingredient": item.get(
                        "name",
                        ""
                    ),

                    "measure": (
                        f"{item.get('quantity', '')} "
                        f"{item.get('unit', '')}"
                    ).strip()

                })

        result =  {

            "idMeal": recipe.get("id"),

            "strMeal": recipe.get(
                "name",
                "Recipe"
            ),

            "strInstructions": "\n".join(
                step.get("text", "")
                for step in recipe.get(
                    "instructions",
                    []
                )
            ),

            "strMealThumb": None,
            "_recipe_ingredients": ingredients

        }

        RECIPE_CACHE[meal_id] = result
        return result

    except requests.RequestException as e:

        print("Recipe API detail error:", e)

        return None

# ---------------------------------------------------------
# GET RECIPE INGREDIENTS
# ---------------------------------------------------------
def format_recipe_time(value):
    """Convert an ISO 8601 recipe duration into readable text."""
    if not value:
        return ""

    text = str(value).strip().upper()
    match = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", text)
    if not match:
        return str(value)

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    parts = []
    if hours:
        parts.append(f"{hours} hour" + ("s" if hours != 1 else ""))
    if minutes:
        parts.append(f"{minutes} minute" + ("s" if minutes != 1 else ""))
    if seconds and not parts:
        parts.append(f"{seconds} second" + ("s" if seconds != 1 else ""))

    return " ".join(parts) if parts else "0 minutes"


def format_recipe_yield(value):
    """Convert recipeYield data into a clean user-facing serving string."""
    if not value:
        return ""

    if isinstance(value, list):
        values = [str(item).strip() for item in value if str(item).strip()]
        if not values:
            return ""

        serving_value = next(
            (item for item in values if re.search(r"\bservings?\b", item, re.IGNORECASE)),
            None,
        )
        value = serving_value or values[-1]

    text = str(value).strip()
    text = re.sub(r"\b(\d+)\s*serving\(s\)", r"\1 servings", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d+)\s+serving\b", r"\1 serving", text, flags=re.IGNORECASE)
    return text


def convert_measurement(measure):
    if not measure:
        return ""

    import re

    text = measure.strip()

    # Weight
    def grams_to_oz(match):
        grams = float(match.group(1))
        ounces = grams / 28.3495
        return f"{ounces:.1f} oz"

    def kg_to_lb(match):
        kg = float(match.group(1))
        pounds = kg * 2.20462
        return f"{pounds:.1f} lb"

    # Volume
    def ml_to_fl_oz(match):
        ml = float(match.group(1))
        ounces = ml / 29.5735
        return f"{ounces:.1f} fl oz"

    def liter_to_cups(match):
        liters = float(match.group(1))
        cups = liters * 4.22675
        return f"{cups:.1f} cups"    

    text = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:g|grams?)\b",
        grams_to_oz,
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:kg|kilograms?)\b",
        kg_to_lb,
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:ml|milliliters?)\b",
        ml_to_fl_oz,
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"(\d+(?:\.\d+)?)\s*(?:l|liters?|litres?)\b",
        liter_to_cups,
        text,
        flags=re.IGNORECASE
    )
    text = re.sub(
        r"\btbs\b",
        "tbsp",
        text,
        flags=re.IGNORECASE
    )

    return text

def get_recipe_ingredients(recipe):

    # Recipe API format
    if recipe.get("_recipe_ingredients") is not None:

        ingredients = []

        for item in recipe.get(
            "_recipe_ingredients",
            []
        ):

            ingredient = item.get(
                "ingredient",
                ""
            )

            if not ingredient:
                continue

            ingredients.append({
                "ingredient": ingredient,
                "measure": convert_measurement(
                    item.get(
                        "measure",
                        ""
                    )
                )
            })

        return ingredients

    # Legacy TheMealDB format
    ingredients = []

    for number in range(1, 21):

        ingredient = recipe.get(
            f"strIngredient{number}"
        )

        measure = recipe.get(
            f"strMeasure{number}"
        )

        if ingredient:

            ingredient = ingredient.strip()

            if ingredient:

                ingredients.append({
                    "ingredient": ingredient,
                    "measure": convert_measurement(
                        measure
                    )
                })

    return ingredients

# ---------------------------------------------------------
# FIND RECIPES
# ---------------------------------------------------------


def format_instructions(text):

    if not text:
        return "Instructions unavailable."

    import re

    # Normalize whitespace
    text = text.replace("\r", " ")
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text).strip()

    # Fix known duplicate step
    text = text.replace(
        "STEP 2 - BOILING THE WHITE RICE",
        "STEP 3 - BOILING THE WHITE RICE"
    )

    # STEP-style instructions
    if re.match(r"^STEP\s*\d+", text, flags=re.IGNORECASE):

        text = re.sub(
            r"\bSTEP\s*(\d+)\s*[-:]?\s*",
            r"\n\nSTEP \1 - ",
            text,
            flags=re.IGNORECASE
        )

    # Numbered instructions that actually start the recipe
    elif re.match(r"^\d+(?:\.|\))?\s+", text):
        text = re.sub(
            r"(?<!\w)(\d+)(?:\.|\))?\s+(?=[A-Z])",
            r"\n\n\1. ",
            text
        )

    # Otherwise split a long paragraph into steps
    else:

        # Treat "To make..." as the beginning of a new instruction
        text = re.sub(
            r"\s+(?=To make\b)",
            "\n\n",
            text
        )

        # Split at sentence endings OR our intentional line breaks
        sentences = re.split(
            r"(?:\n\n|(?<=[.!?])\s+)(?=[A-Z])",
            text
        )

        steps = []

        for sentence in sentences:

            sentence = sentence.strip()

            if sentence:
                steps.append(sentence)

        if steps:

            text = "\n\n".join(
                f"{i}. {step}"
                for i, step in enumerate(steps, 1)
            )

    # Clean spaces around line breaks
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)

    # Convert line breaks to HTML
    text = text.replace("\n\n", "<br><br>")

    return text.strip()
def get_substitutions(missing_ingredients):
    suggestions = {}

    for ingredient in missing_ingredients:

        cleaned = ingredient_alias(ingredient)

        if cleaned in SUBSTITUTIONS:

            suggestions[ingredient] = SUBSTITUTIONS[
                cleaned
            ]

    return suggestions

def get_substitution_notes(missing_ingredients):
    notes = {}

    for ingredient in missing_ingredients:
        cleaned = ingredient_alias(ingredient)

        if cleaned not in SUBSTITUTION_NOTES:
            continue

        note_data = SUBSTITUTION_NOTES[cleaned]

        if "rating" in note_data:
            notes[ingredient] = {
                "general": note_data
            }
        else:
            notes[ingredient] = note_data

    return notes


def fancy_recipe_check(recipe):
    """Return True when recipe metadata strongly suggests an elevated,
    special-occasion, entertaining, or gourmet recipe."""
    parts = []

    for field in (
        "name",
        "description",
        "recipeCategory",
        "keywords",
    ):
        value = recipe.get(field, "")
        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))

    text = " ".join(parts).lower()
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    positive_phrases = {
        "gourmet",
        "elegant",
        "upscale",
        "special occasion",
        "special-occasion",
        "dinner party",
        "entertaining",
        "celebration",
        "holiday",
        "date night",
        "restaurant style",
        "restaurant-style",
        "fine dining",
        "impressive",
        "showstopper",
    }

    negative_phrases = {
        "easy",
        "simple",
        "quick",
        "weeknight",
        "family",
        "15-minute",
        "20-minute",
        "30-minute",
        "one-pot",
        "one pot",
    }

    strong_positive_phrases = {
        "gourmet",
        "elegant",
        "upscale",
        "fine dining",
        "showstopper",
        "restaurant style",
        "restaurant-style",
    }

    positive_hits = sum(1 for phrase in positive_phrases if phrase in text)
    negative_hits = sum(1 for phrase in negative_phrases if phrase in text)
    strong_positive_hits = sum(
        1 for phrase in strong_positive_phrases if phrase in text
    )

    if strong_positive_hits >= 1:
        return True

    return positive_hits >= 1 and positive_hits > negative_hits


def quick_recipe_check(recipe):
    """Return True only when usable total recipe time is 30 minutes or less."""
    total_time = recipe.get("totalTime", "")

    if not total_time:
        return False

    match = re.fullmatch(
        r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?",
        str(total_time).strip().upper()
    )
    if not match:
        return False

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    total_minutes = hours * 60 + minutes + (seconds / 60)
    return total_minutes <= 30


def healthy_recipe_check(recipe):
    """Return True only when usable per-serving nutrition meets
    InThePantry's Healthy screening criteria."""
    nutrition = recipe.get("nutrition", {})

    if not isinstance(nutrition, dict):
        return False

    def number(field):
        value = nutrition.get(field)
        if value is None:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        if not match:
            return None
        try:
            return float(match.group(0))
        except (TypeError, ValueError):
            return None

    calories = number("calories")
    fat = number("fatContent")
    saturated_fat = number("saturatedFatContent")
    sodium = number("sodiumContent")

    if any(value is None for value in (calories, fat, saturated_fat, sodium)):
        return False

    if calories <= 0 or fat < 0 or saturated_fat < 0 or sodium < 0:
        return False

    return (
        calories <= 500
        and fat <= 20
        and saturated_fat <= 8
        and sodium <= 800
    )


def recipe_cuisine_matches(recipe, selected_cuisine):
    """Return True when recipe evidence supports the selected cuisine."""
    if not selected_cuisine:
        return False

    selected = str(selected_cuisine).strip().lower()

    cuisine_aliases = {
        "italian": {"italian", "italian cuisine"},
        "american": {"american", "american cuisine"},
        "middle eastern": {
            "middle eastern",
            "middle-eastern",
            "middle eastern cuisine",
        },
        "mexican": {"mexican", "mexican cuisine"},
    }

    accepted = cuisine_aliases.get(selected, {selected})

    raw_cuisine = recipe.get("recipeCuisine", "")
    cuisine_values = (
        raw_cuisine
        if isinstance(raw_cuisine, list)
        else [raw_cuisine]
    )

    cuisine_values = [
        str(value).strip().lower()
        for value in cuisine_values
        if str(value).strip()
    ]

    # Explicit cuisine metadata is authoritative.
    if cuisine_values:
        return any(
            value in accepted
            or any(
                part.strip() in accepted
                for part in re.split(r"[/,;|]", value)
            )
            for value in cuisine_values
        )

    # When recipeCuisine is absent, use secondary recipe evidence.
    parts = []

    for field in (
        "name",
        "recipeCategory",
        "keywords",
        "description",
    ):
        value = recipe.get(field, "")

        if isinstance(value, list):
            parts.extend(str(item) for item in value)
        elif value:
            parts.append(str(value))

    evidence = " ".join(parts).lower()
    evidence = re.sub(r"[^a-z0-9\s-]", " ", evidence)
    evidence = re.sub(r"\s+", " ", evidence).strip()

    return any(
        re.search(
            r"(?<![a-z])" + re.escape(alias) + r"(?![a-z])",
            evidence,
        )
        for alias in accepted
    )


def find_recipes(
    user_ingredients,
    search_terms=None,
    selected_cuisine=None,
    selected_diet=None,
):
    """
    Search the web for recipes, extract real recipe data,
    compare it with the user's pantry, and provide sensible
    substitutions for missing ingredients.
    """

    if not user_ingredients:
        return []

    # Search Brave using the ingredients the user entered.
    try:
        search_results = search_web_recipes(
            search_terms or user_ingredients,
            count=10
        )
    except Exception as e:
        print("Web recipe search error:", e)
        return []

    if not search_results:
        print("No web recipe search results found.")
        return []

    scored_recipes = []

    # Identify specifically selected proteins so recipes using
    # the user's chosen meat are ranked ahead of recipes that
    # only match side ingredients.
    selected_proteins = []
    for item in user_ingredients or []:
        cleaned_item = clean_word(item)
        for meat_options in MEAT_GROUPS.values():
            if cleaned_item in meat_options:
                selected_proteins.append(cleaned_item)
                break


    for result in search_results:

        url = result.get("url")

        if not url:
            continue

        # search_web_recipes() already extracts the complete
        # recipe before returning it. Reuse that recipe here
        # instead of downloading and extracting the page again.
        recipe = result

        if not recipe:
            continue

        # -----------------------------------------------------
        # UNIVERSAL FINAL RECIPE INGREDIENT CANONICALIZATION
        # -----------------------------------------------------
        # This is the final ingredient-identity boundary for find_recipes().
        #
        # Every ingredient that reaches matching or the webpage must be an
        # ingredient identity only:
        #
        #   no quantities
        #   no portions
        #   no preparation instructions
        #   no editorial/source wording
        #   no stray OR fragments
        #
        # raw_ingredients remains untouched so source amounts/details are
        # still available separately.
        canonical_ingredients = []

        metadata_fragment_words = {
            "a", "an", "the", "and", "or", "of", "to", "for", "as",
            "if", "they", "them", "their", "you", "your", "want",
            "wants", "same", "size", "roughly", "rough", "lightly",
            "heavily", "freshly", "from", "with", "into", "in",
            "on", "off", "so", "use", "used", "using", "make",
            "sure", "removed", "remove", "cut", "cutting", "dice",
            "diced", "chop", "chopped", "slice", "sliced", "cube",
            "cubed", "halve", "halved", "quarter", "quartered",
            "peel", "peeled", "trim", "trimmed", "crush", "crushed",
            "smash", "smashed", "mix", "mixed", "stir", "stirred",
            "toss", "tossed", "drain", "drained", "rinse", "rinsed",
            "cook", "cooked", "bake", "baked", "boil", "boiled",
            "roast", "roasted", "saute", "sauteed", "sauté",
            "sautéed", "serve", "served", "serving", "optional",
            "divided", "plus", "more", "extra", "additional",
            "for", "taste", "garnish", "zest"
        }

        for raw_ingredient in recipe.get("ingredients", []):
            if not isinstance(raw_ingredient, str):
                continue

            normalized, _ = normalize_recipe_ingredient(
                raw_ingredient,
                preserve_source=True
            )

            if not normalized:
                continue

            # A recipe source can contain "or" inside preparation prose.
            # Evaluate each OR side independently and retain only sides that
            # resolve to a real ingredient identity.
            or_parts = [
                part.strip(" ,")
                for part in re.split(
                    r"\s+or\s+",
                    normalized,
                    flags=re.IGNORECASE
                )
                if part.strip(" ,")
            ]

            identities = []

            for part in or_parts:
                identity = extract_ingredient_identity(part)

                if not identity:
                    # Exact vocabulary extraction is a safe fallback for
                    # legitimate ingredients not fully recognized by the
                    # broader identity extractor.
                    identity = extract_known_ingredient(part)

                if not identity:
                    # Preserve legitimate unknown ingredients, but never
                    # preserve a fragment made entirely from recipe-source
                    # preparation/connective wording.
                    words = part.lower().split()

                    if (
                        not words
                        or all(word in metadata_fragment_words for word in words)
                    ):
                        continue

                    identity = part.strip()

                identity = re.sub(r"\s+", " ", identity).strip(" ,")

                if not identity:
                    continue

                # Remove a final source/preparation tail if one survived
                # the vocabulary extraction.
                identity = extract_ingredient_identity(identity) or identity
                identity = re.sub(r"\s+", " ", identity).strip(" ,")

                if not identity:
                    continue

                if identity.lower() not in {
                    existing.lower() for existing in identities
                }:
                    identities.append(identity)

            if not identities:
                continue

            canonical = " or ".join(identities)

            # Pantry staples never become recipe requirements.
            if ingredient_matches(
                canonical,
                list(PANTRY_STAPLES),
                allow_pantry_staple=True
            ):
                continue

            canonical_ingredients.append(canonical)

        recipe["ingredients"] = canonical_ingredients

        if not canonical_ingredients:
            continue

        # -----------------------------------------------------
        # HARD HEALTHY DIET FILTER
        # -----------------------------------------------------
        # Healthy is a true eligibility filter. A recipe must have
        # usable nutrition data and satisfy the application's
        # Healthy screening criteria before it can be returned when
        # Healthy is selected.
        # -----------------------------------------------------
        if selected_diet == "healthy":
            if not healthy_recipe_check(recipe):
                continue

        # -----------------------------------------------------
        # HARD QUICK DIET FILTER
        # -----------------------------------------------------
        # Quick is a true eligibility filter. A recipe must have
        # usable total-time data and require 30 minutes or less.
        # -----------------------------------------------------
        if selected_diet == "quick":
            if not quick_recipe_check(recipe):
                continue

        # -----------------------------------------------------
        # HARD VEGAN DIET FILTER
        # -----------------------------------------------------
        # Vegan is a true eligibility filter. Explicit vegan
        # metadata qualifies the recipe immediately. Otherwise,
        # inspect the recipe ingredients using the application's
        # existing ingredient vocabulary and reject recipes that
        # contain recognized animal-derived ingredients.
        #
        # This keeps Vegan filtering independent from pantry
        # matching while avoiding reliance on incomplete web
        # recipe diet metadata.
        # -----------------------------------------------------
        if selected_diet == "vegan":
            recipe_diets = recipe.get(
                "suitableForDiet",
                []
            )

            if isinstance(recipe_diets, str):
                recipe_diets = [recipe_diets]

            is_explicitly_vegan = any(
                str(diet).strip().lower() == "vegan"
                for diet in recipe_diets
            )

            if not is_explicitly_vegan:
                non_vegan_ingredients = set()

                for raw_ingredient in recipe.get("ingredients", []):
                    ingredient_name = clean_word(raw_ingredient)
                    if not ingredient_name:
                        continue

                    normalized_name, _ = normalize_recipe_ingredient(
                        ingredient_name
                    )
                    normalized_name = ingredient_alias(
                        clean_word(normalized_name)
                    )

                    if not normalized_name:
                        continue

                    # Explicit vegan ingredients are safe.
                    if re.search(r"\bvegan\b", normalized_name):
                        continue

                    # Use the existing application vocabulary for
                    # recognized animal-derived ingredients.
                    animal_ingredients = set()
                    for values in MEAT_GROUPS.values():
                        animal_ingredients.update(values)
                    animal_ingredients.update([
                        "chicken",
                        "beef",
                        "pork",
                        "lamb",
                        "turkey",
                        "fish",
                        "seafood",
                        "eggs",
                        "egg",
                        "milk",
                        "cheese",
                        "butter",
                    ])

                    animal_match = any(
                        normalized_name == animal
                        or normalized_name.startswith(animal + " ")
                        or (" " + animal + " ") in (" " + normalized_name + " ")
                        for animal in animal_ingredients
                    )

                    if animal_match:
                        non_vegan_ingredients.add(normalized_name)

                if non_vegan_ingredients:
                    continue

        recipe_ingredients = canonical_ingredients

        if not recipe_ingredients:
            continue

        # Compare the recipe with the user's pantry.
        #
        # When Vegan is selected, ordinary animal meat/poultry in
        # the pantry is irrelevant to the vegan recipe match. Do not
        # let those incompatible pantry proteins count as missing or
        # otherwise affect the recipe's pantry matching.
        matching_pantry = list(user_ingredients or [])

        # Track whether Vegan filtering removed one of the user's
        # explicitly selected animal proteins. That protein cannot
        # count as a pantry match for a vegan recipe, but it is still
        # the user's intended recipe-search ingredient.
        vegan_incompatible_pantry_removed = False

        if selected_diet == "vegan":
            animal_pantry_items = {
                "chicken",
                "beef",
                "pork",
                "lamb",
                "turkey",
            }

            animal_pantry_items.update(
                item
                for values in MEAT_GROUPS.values()
                for item in values
            )

            # Recognize ordinary plural forms of the established
            # meat vocabulary for Vegan pantry filtering only.
            # This does not change ingredient_matches() or the
            # application's established meat hierarchy.
            for meat_item in list(animal_pantry_items):
                if meat_item.endswith("s"):
                    animal_pantry_items.add(
                        meat_item[:-1]
                    )

            filtered_pantry = []

            for pantry_item in matching_pantry:
                normalized_pantry, _ = normalize_recipe_ingredient(
                    pantry_item
                )
                normalized_pantry = ingredient_alias(
                    clean_word(normalized_pantry)
                )

                if normalized_pantry in animal_pantry_items:
                    vegan_incompatible_pantry_removed = True
                    continue

                filtered_pantry.append(pantry_item)

            matching_pantry = filtered_pantry

        try:
            pantry_result = match_recipe_to_pantry(
                recipe,
                matching_pantry
            )
        except Exception as e:
            print("Pantry matching error:", e)
            continue

        if not pantry_result:
            continue

        # -----------------------------------------------------
        # FINAL UNIVERSAL INGREDIENT-IDENTITY DISPLAY GUARD
        # -----------------------------------------------------
        # Matching is already complete at this point.
        #
        # From here forward, the application must expose ingredient
        # identity only. Never allow recipe-source wording, quantities,
        # preparation instructions, quality descriptors, or other
        # metadata to leak into Have/Need.
        #
        # This is a display/output boundary only. It does NOT alter
        # matching, scoring, the meat hierarchy, OR alternatives,
        # pantry-staple rules, or any other established matching logic.
        # -----------------------------------------------------

        matched = []

        for item in pantry_result.get(
            "have",
            []
        ):
            identity = canonical_ingredient_identity(
                item.get("ingredient", "")
            )

            if identity:
                matched.append(identity)

        missing_items = pantry_result.get(
            "missing",
            []
        )

        missing = []

        for item in missing_items:
            identity = canonical_ingredient_identity(
                item.get("ingredient", "")
            )

            if identity:
                missing.append(identity)

        # Build the substitution display used by
        # the existing webpage.
        substitutions = {}
        substitution_notes = {}

        for item in missing_items:

            ingredient = item["ingredient"]
            options = item.get(
                "substitutions",
                []
            )

            if not options:
                continue

            substitutions[ingredient] = [
                option["replacement"]
                for option in options
                if option.get("replacement")
            ]

            substitution_notes[ingredient] = {}

            for option in options:

                replacement = option.get(
                    "replacement"
                )

                if not replacement:
                    continue

                substitution_notes[ingredient][
                    replacement
                ] = {
                    "rating": (
                        "Good substitute"
                        if option.get("type") == "direct"
                        else "Workable substitute"
                    ),
                    "note": option.get(
                        "note",
                        ""
                    )
                }

        # Avoid displaying recipes that use none
        # of the user's ingredients.
        used_count = len(matched)

        if used_count == 0 and not (
            selected_diet == "vegan"
            and vegan_incompatible_pantry_removed
        ):
            continue

        total_count = (
            used_count
            + len(missing)
        )

        match_percentage = (
            round(
                (used_count / total_count) * 100
            )
            if total_count
            else 0
        )

        instructions = recipe.get(
            "instructions",
            []
        )

        if not instructions:
            instructions = [
                "Instructions unavailable."
            ]

        # Extract an image when the recipe extractor
        # provides one.
        image = recipe.get("image")

        # Some extractors return a list of images.
        if isinstance(image, list):
            image = image[0] if image else None

        scored_recipes.append({
            "name": recipe.get(
                "name",
                result.get(
                    "title",
                    "Recipe"
                )
            ),

            "healthy": healthy_recipe_check(recipe),
            "quick": quick_recipe_check(recipe),
            "fancy": fancy_recipe_check(recipe),
            "prepTime": recipe.get(
                "prepTime",
                ""
            ),
            "cookTime": recipe.get(
                "cookTime",
                ""
            ),
            "totalTime": recipe.get(
                "totalTime",
                ""
            ),
            "nutrition": recipe.get(
                "nutrition",
                {}
            ),
            "recipeYield": recipe.get(
                "recipeYield",
                ""
            ),

            "image": image,

            "ingredients": recipe_ingredients,

            "matched": matched,

            "missing": missing,

            "substitutions": substitutions,

            "substitution_notes": (
                substitution_notes
            ),

            "used_count": used_count,

            "total_count": total_count,

            "missing_count": len(missing),

            "match_percentage": (
                match_percentage
            ),

            "primary_match": 1 if any(
                ingredient_matches(item, selected_proteins)
                for item in matched
            ) else 0,

            "recipeCuisine": recipe.get(
                "recipeCuisine",
                []
            ),

            "cuisine_match": (
                1
                if recipe_cuisine_matches(recipe, selected_cuisine)
                else 0
            ),

            "diet_match": (
                1
                if (
                    (selected_diet == "vegan")
                    or (selected_diet == "healthy" and healthy_recipe_check(recipe))
                    or (selected_diet == "quick" and quick_recipe_check(recipe))
                    or (selected_diet == "fancy" and fancy_recipe_check(recipe))
                )
                else 0
            ),
            "instructions": instructions,

            "source": url
        })

    # When both a cuisine and diet/style are selected, prefer recipes
    # that satisfy both. Otherwise preserve the existing preference order.
    scored_recipes.sort(
        key=lambda x: (
            (
                1
                if x["diet_match"] and x["cuisine_match"]
                else 0
            ),
            x["diet_match"],
            x["cuisine_match"],
            x["primary_match"],
            x["match_percentage"],
            x["used_count"],
            -x["missing_count"]
        ),
        reverse=True
    )

    return scored_recipes[:30]


# ---------------------------------------------------------
# WEB PAGE
# ---------------------------------------------------------

HTML = """
<!DOCTYPE html>

<html>

<head>

    <title>InThePantry</title>

    <meta name="viewport"
          content="width=device-width, initial-scale=1">

    {% if posthog_api_key %}
    <script>
        !function(t,e){var o,n,p,r;e.__SV=1,window.posthog=e,e._i=[],e.init=function(i,s,a){function g(t,e){var o=e.split(".");2==o.length&&(t=t[o[0]],e=o[1]),t[e]=function(){t.push([e].concat(Array.prototype.slice.call(arguments,0)))}}(p=t.createElement("script")).type="text/javascript",p.async=!0,p.src=s.api_host+"/static/array.js",(r=t.getElementsByTagName("script")[0]).parentNode.insertBefore(p,r);var u=e;void 0!==a?u=e[a]=[]:a="posthog",u.people=u.people||[],u.toString=function(t){var e="posthog";return"posthog"!==a&&(e+="."+a),t||(e+=" (stub)"),e},u.people.toString=function(){return u.toString(1)+".people (stub)"};for(n="capture identify alias people.set people.set_once people.unset people.increment people.append people.remove people.group register register_once unregister opt_out_capturing opt_in_capturing has_opted_out_capturing has_opted_in_capturing clear_opt_out_capturing debug reset on onCapture onEvent onFeatureFlags reloadFeatureFlags getFeatureFlag getFeatureFlagPayload isFeatureEnabled getAllFlags getAllFlagsAndPayloads setPersonProperties resetPersonProperties getSessionId getDistinctId getGroupProperties getSessionRecordingProperties get_property".split(" "),o=0;o<n.length;o++)g(u,n[o]);e._i.push([i,s,a])},e.__SV=1}(document,window.posthog||[]);
        posthog.init("{{ posthog_api_key }}", {
            api_host: "https://us.i.posthog.com",
            person_profiles: "identified_only",
            capture_pageview: true,
            capture_pageleave: true,
            autocapture: true,
            session_recording: {
                maskAllInputs: true,
                blockAllMedia: false
            }
        });
    </script>
    {% endif %}

    <style>


.recipe-navigation {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    margin: 10px 0;
    background: transparent;
    border: none;
    box-shadow: none;
    padding: 0;
}

.recipe-navigation button {
    width: auto;
    background: transparent;
    border: none;
    border-radius: 0;
    box-shadow: none;
    padding: 3px 5px;
    margin: 0;
    color: #3568a8;
    font-size: 14px;
    font-weight: bold;
    cursor: pointer;
    outline: none;
    appearance: none;
    -webkit-appearance: none;
    -webkit-tap-highlight-color: transparent;
}

.recipe-navigation button:hover {
    width: auto;
    background: transparent;
    color: #3568a8;
    border: none;
    box-shadow: none;
    text-decoration: underline;
}

.recipe-navigation button:focus,
.recipe-navigation button:focus-visible,
.recipe-navigation button:active {
    width: auto;
    background: transparent;
    border: none;
    border-radius: 0;
    outline: none;
    box-shadow: none;
}

#previous-recipes-top,
#next-recipes-top {
    font-size: 14px;
    padding: 3px 5px;
}
        body {
            font-family: Arial, sans-serif;
            background: #f7f3ed;
            margin: 0;
            padding: 20px;
        }

        .container {
            max-width: 900px;
            margin: auto;
        }

        h1 {
            text-align: center;
            color: #355e3b;
        }

        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 6px;
        }

        .tagline {
            text-align: center;
            color: #355e3b;
            font-size: 18px;
            font-weight: 600;
            margin: 0 0 24px;
        }

        form {
            background: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 25px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }

        input[type="text"] {
            width: 100%;
            padding: 14px;
            font-size: 16px;
            box-sizing: border-box;
            border: 1px solid #ccc;
            border-radius: 8px;
            margin-bottom: 12px;
        }

                .common-ingredients {
            background: #f8f8f8;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 15px;
        }

        .common-ingredients h3 {
            margin-top: 0;
        }
        .ingredient-help {
            margin: 4px 0 12px;
            font-size: 14px;
            line-height: 1.4;
            color: #666;
        }

        .ingredient-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 10px;
    margin-top: 10px;
}
.ingredient-category {
    width: 100%;
    margin: 12px 0 6px;
    padding: 15px 17px;
    border: 1px solid #d8dfd5;
    border-radius: 10px;
    background: #fffdf9;
    color: #355e3b;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 18px;
    font-weight: bold;
    cursor: pointer;
    text-align: left;
    transition: background 0.15s ease, border-color 0.15s ease;
}

.ingredient-category:hover {
    background: #f3f8ee;
    border-color: #b9cdb8;
}

/* Give each top-level ingredient category its own visual identity.
   The colors are intentionally soft so the interface stays clean. */
.ingredient-category.category-color-1 {
    border-left: 6px solid #d96b5f;
    background: #fff7f5;
    color: #8f352c;
}

.ingredient-category.category-color-2 {
    border-left: 6px solid #5b9b6d;
    background: #f5fbf6;
    color: #356a43;
}

.ingredient-category.category-color-3 {
    border-left: 6px solid #d6a64f;
    background: #fffbf2;
    color: #86621e;
}

.ingredient-category.category-color-4 {
    border-left: 6px solid #5c8fc7;
    background: #f5f9fe;
    color: #315f8d;
}

.ingredient-category.category-color-5 {
    border-left: 6px solid #9a75b5;
    background: #faf7fc;
    color: #694681;
}

.ingredient-category.category-color-6 {
    border-left: 6px solid #d17b43;
    background: #fff8f2;
    color: #8a4c25;
}

.ingredient-category.category-color-7 {
    border-left: 6px solid #4e9c9a;
    background: #f3fbfb;
    color: #286967;
}

.ingredient-category.category-color-8 {
    border-left: 6px solid #7d8fbd;
    background: #f6f8fd;
    color: #4d5e8a;
}

.category-arrow {
    color: #333;
    font-size: 14px;
}

.ingredient-category.open .category-arrow {
    transform: rotate(90deg);
}

.category-grid {
    display: none;
}
.ingredient-option {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 10px;
    background: white;
    border: 1px solid #ddd;
    border-radius: 8px;
    cursor: pointer;
}

.ingredient-option:hover {
    background: #f0f7f0;
}

.ingredient-option input {
    width: 18px;
    height: 18px;
    margin: 0;
    flex-shrink: 0;
}

@media (max-width: 600px) {
    body {
        padding: 12px;
    }

    .container {
        max-width: 100%;
    }

    form {
        padding: 16px;
    }

    .ingredient-grid {
        grid-template-columns: 1fr;
    }
}
        button {
            width: 100%;
            padding: 14px;
            background: #333;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            cursor: pointer;
        }

        button:hover {
            background: #555;
        }

        .recipe {
            background: white;
            padding: 25px;
            border-radius: 16px;
            margin: 0 auto 30px;
            max-width: 800px;
            box-shadow: 0 4px 14px rgba(0,0,0,0.10);
            text-align: left;
        }

        .recipe img {
            width: 100%;
            max-width: 500px;
            display: block;
            margin: 0 auto 20px;
            border-radius: 10px;
        }

        .match {
            display: inline-block;
            font-size: 18px;
            font-weight: bold;
            padding: 8px 14px;
            margin: 5px 0 15px;
            border-radius: 20px;
        }

        .match-excellent {
            color: #188038;
            background: #e6f4ea;
        }

        .match-good {
            color: #5f8f29;
            background: #eef6df;
        }

        .match-fair {
            color: #b06000;
            background: #fff4d6;
        }

        .match-low {
            color: #c5221f;
            background: #fce8e6;
        }
        
        .best-match {
            display: inline-block;
            color: #8a5a00;
            background: #fff3cd;
            font-size: 16px;
            font-weight: bold;
            padding: 8px 14px;
            margin: 5px 0 8px;
            border-radius: 20px;
        }

        .have {
            color: #188038;
            font-weight: bold;
        }
        .missing {
            color: #c5221f;
            font-weight: bold;
        }

        .recipe-note {
            margin: 8px 0 12px;
            font-size: 13px;
            line-height: 1.5;
            color: #666;
        }

        .ingredients {
            background: #fafafa;
            padding: 15px;
            border-radius: 8px;
        }

        .ingredients p {
            margin: 6px 0;
        }

        .instructions {
            line-height: 1.8;
            white-space: pre-line;
            text-align: left;
            margin-top: 10px;
            font-size: 16px;
        }
        .source {
            display: inline-block;
            margin-top: 15px;
            padding: 10px 15px;
            background: #333;
            color: white;
            text-decoration: none;
            border-radius: 6px;
        }

        .source:hover {
            background: #555;
        }

        .recipe-details {            display: none;            margin-top: 15px;        }        .recipe-toggle {            margin-top: 12px;            padding: 10px 16px;            border: none;            border-radius: 6px;            background: #333;            color: white;            cursor: pointer;            font-size: 15px;        }        .recipe-toggle:hover {            background: #555;        }        .error {
            background: #ffe6e6;
            padding: 15px;
            border-radius: 8px;
            color: #b00020;
        }

    
    .sound-control {
        display: flex;
        justify-content: center;
        margin: 0 0 18px;
    }

    .sound-toggle {
        width: auto;
        padding: 9px 16px;
        background: #fffdf9;
        color: #355e3b;
        border: 1px solid #d8dfd5;
        border-radius: 999px;
        font-size: 14px;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.15s ease, border-color 0.15s ease;
    }

    .sound-toggle:hover {
        background: #f3f8ee;
        border-color: #b9cdb8;
    }

    .sound-toggle.active {
        background: #355e3b;
        color: white;
        border-color: #355e3b;
    }

    .music-note {
        margin-top: 8px;
        text-align: center;
        font-size: 12px;
        color: #777;
    }

    .music-note a {
        color: #355e3b;
        text-decoration: none;
        font-weight: 600;
    }

    .music-note a:hover {
        text-decoration: underline;
    }

</style>

<script>

function savePantry(event) {
    if (event) {
        event.preventDefault();
    }

    const selected = [];

    document.querySelectorAll(
        'input[name="common_ingredients"]:checked'
    ).forEach(function(checkbox) {
        selected.push(checkbox.value);
    });

    const ingredientInput = document.querySelector(
        'input[name="ingredients"]'
    );

    if (ingredientInput && ingredientInput.value.trim()) {
        selected.push(
            "CUSTOM:" + ingredientInput.value.trim()
        );
    }

    localStorage.setItem(
        "inThePantry",
        JSON.stringify(selected)
    );

    alert("Your pantry has been saved!");
}


function loadPantry(event) {
    if (event) {
        event.preventDefault();
    }

    const saved = localStorage.getItem("inThePantry");

    if (!saved) {
        alert("No saved pantry found.");
        return;
    }

    const selected = JSON.parse(saved);

    document.querySelectorAll(
        'input[name="common_ingredients"]'
    ).forEach(function(checkbox) {
        checkbox.checked = selected.includes(
            checkbox.value
        );
    });

    const ingredientInput = document.querySelector(
        'input[name="ingredients"]'
    );

    if (ingredientInput) {
        const customItems = selected
            .filter(function(item) {
                return item.startsWith("CUSTOM:");
            })
            .map(function(item) {
                return item.substring(7);
            });

        ingredientInput.value = customItems.join(", ");
    }

    alert("Your saved pantry has been loaded!");
}


function clearPantry(event) {
    if (event) {
        event.preventDefault();
    }

    document.querySelectorAll(
        'input[name="common_ingredients"]'
    ).forEach(function(checkbox) {
        checkbox.checked = false;
    });

    const ingredientInput = document.querySelector(
        'input[name="ingredients"]'
    );

    if (ingredientInput) {
        ingredientInput.value = "";
    }

    const dietSelect = document.querySelector(
        'select[name="diet_style"]'
    );

    if (dietSelect) {
        dietSelect.value = "";
    }

    const cuisineSelect = document.querySelector(
        'select[name="cuisine_type"]'
    );

    if (cuisineSelect) {
        cuisineSelect.value = "";
    }

    alert("Your pantry has been cleared!");
}

</script>
<script>

function toggleRecipe(button) {
    const details = button.nextElementSibling;

    if (details.style.display === "block") {
        details.style.display = "none";
        button.textContent = "▶ View Recipe";
    } else {
        details.style.display = "block";
        button.textContent = "▼ Hide Recipe";
    }
}

function toggleIngredientCategory(button) {
    const grid = button.nextElementSibling;

    if (grid.style.display === "grid") {
        grid.style.display = "none";
        button.classList.remove("open");
    } else {
        grid.style.display = "grid";
        button.classList.add("open");
    }
}
let currentRecipePage = 0;

function showRecipePage(page) {
    currentRecipePage = page;

    const recipes = document.querySelectorAll(".recipe");
    const perPage = 5;

    const start = page * perPage;
    const end = start + perPage;

    recipes.forEach((recipe, index) => {
        if (index >= start && index < end) {
            recipe.style.display = "block";
        } else {
            recipe.style.display = "none";
        }
    });

    const previous = document.getElementById("previous-recipes");
const next = document.getElementById("next-recipes");

const previousTop = document.getElementById("previous-recipes-top");
const nextTop = document.getElementById("next-recipes-top");

const previousDisplay =
    page > 0 ? "inline-block" : "none";

const nextDisplay =
    end < recipes.length ? "inline-block" : "none";

if (previous) {
    previous.style.display = previousDisplay;
}

if (next) {
    next.style.display = nextDisplay;
}

if (previousTop) {
    previousTop.style.display = previousDisplay;
}

if (nextTop) {
    nextTop.style.display = nextDisplay;
}

}
document.addEventListener("DOMContentLoaded", function () {
    if (document.querySelectorAll(".recipe").length > 0) {
        showRecipePage(0);
    }
});
</script>

<script>
async function toggleKitchenMusic() {
    const audio = document.getElementById("kitchen-music");
    const button = document.getElementById("sound-toggle");

    if (!audio || !button) {
        return;
    }

    if (audio.paused) {
        audio.volume = 0.15;

        try {
            await audio.play();
        } catch (error) {
            return;
        }

        button.setAttribute("aria-pressed", "true");
        button.classList.add("active");
        button.textContent = "🔊 Kitchen Music";

        localStorage.setItem(
            "inThePantryKitchenSound",
            "on"
        );
    } else {
        audio.pause();

        button.setAttribute("aria-pressed", "false");
        button.classList.remove("active");
        button.textContent = "🔇 Kitchen Music";

        localStorage.setItem(
            "inThePantryKitchenSound",
            "off"
        );
    }
}

function updateKitchenMusicButton() {
    const audio = document.getElementById("kitchen-music");
    const button = document.getElementById("sound-toggle");

    if (!audio || !button) {
        return;
    }

    if (audio.paused) {
        button.setAttribute("aria-pressed", "false");
        button.classList.remove("active");
        button.textContent = "🔇 Kitchen Music";
    } else {
        button.setAttribute("aria-pressed", "true");
        button.classList.add("active");
        button.textContent = "🔊 Kitchen Music";
    }
}

function initializeRecipeSearch() {
    const form = document.querySelector("form");

    if (!form || form.dataset.musicSearchBound === "true") {
        return;
    }

    form.dataset.musicSearchBound = "true";

    form.addEventListener("submit", async function (event) {
        event.preventDefault();

        const button = form.querySelector('button[type="submit"]');

        if (button) {
            button.disabled = true;
            button.textContent = "Finding Your Recipes... 🍳";
        }

        try {
            const response = await fetch(
                form.action || window.location.href,
                {
                    method: "POST",
                    body: new FormData(form),
                    headers: {
                        "X-Requested-With": "XMLHttpRequest"
                    }
                }
            );

            if (!response.ok) {
                throw new Error("Recipe search failed.");
            }

            const html = await response.text();
            const parser = new DOMParser();
            const newDocument = parser.parseFromString(
                html,
                "text/html"
            );

            const newForm = newDocument.querySelector("form");

            if (!newForm) {
                throw new Error("Recipe results could not be loaded.");
            }

            const currentForm = document.querySelector("form");

            if (!currentForm) {
                throw new Error("Current recipe form could not be found.");
            }

            const replacementForm = newForm.cloneNode(true);
            const resultsFragment =
                document.createDocumentFragment();

            let newNode = newForm.nextSibling;

            while (newNode) {
                resultsFragment.appendChild(
                    newNode.cloneNode(true)
                );
                newNode = newNode.nextSibling;
            }

            currentForm.replaceWith(replacementForm);

            let oldNode = replacementForm.nextSibling;

            while (oldNode) {
                const nextNode = oldNode.nextSibling;
                oldNode.remove();
                oldNode = nextNode;
            }

            replacementForm.after(resultsFragment);

            initializeRecipeSearch();

            if (typeof showRecipePage === "function" &&
                document.querySelectorAll(".recipe").length > 0) {
                showRecipePage(0);
            }

            updateKitchenMusicButton();

            window.scrollTo({
                top: 0,
                behavior: "smooth"
            });

        } catch (error) {
            console.error(error);
            alert(
                "Sorry, there was a problem finding your recipes. Please try again."
            );

            const currentButton =
                document.querySelector('form button[type="submit"]');

            if (currentButton) {
                currentButton.disabled = false;
                currentButton.textContent = "Find My Recipes";
            }
        }
    });
}

document.addEventListener("DOMContentLoaded", function () {
    updateKitchenMusicButton();
    initializeRecipeSearch();
});
</script>

</head>

<body>

<div class="container">

    <h1>🍳 InThePantry</h1>

    <p class="subtitle">
        Enter the ingredients you have and find recipes you can make.
    </p>
    <p class="tagline">
        Tell me what you've got. I'll figure out what you can make.
    </p>

    <div class="sound-control">
        <div>
            <button
                type="button"
                id="sound-toggle"
                class="sound-toggle"
                onclick="toggleKitchenMusic()"
                aria-pressed="false"
            >
                🔇 Kitchen Music
            </button>

            <div class="music-note">
                Enjoying the music?
                <a
                    href="https://open.spotify.com/track/4LlzdQEiToxeWtX622DmMP?si=422480aaa9b94c2c"
                    target="_blank"
                    rel="noopener noreferrer"
                >Hear more on Spotify →</a>
            </div>
        </div>
    </div>

    <audio id="kitchen-music" preload="metadata" loop>
        <source
            src="{{ url_for('static', filename='audio/Spirit-of-the-Woods.mp3') }}"
            type="audio/mpeg"
        >
    </audio>

<form method="POST">

    <div class="common-ingredients">

        <h3>What do you already have?</h3>
        <p class="ingredient-help">Quick selections are general categories. For more accurate recipe matches, select the specific ingredient you have when available, or enter it manually. For example, "Cheese" is less specific than "Cheddar Cheese."</p>

        
{% for category, ingredients in common_ingredients.items() %}

    <button
        type="button"
        class="ingredient-category category-color-{{ loop.index }}"
        onclick="toggleIngredientCategory(this)"
    >
        <span>{{ category }}</span>
        <span class="category-arrow">▶</span>
    </button>

    <div class="ingredient-grid category-grid">

        {% if category == "Meat & Seafood" %}

            {% for meat_group, meat_ingredients in meat_groups.items() %}

                <button
                    type="button"
                    class="ingredient-category meat-group"
                    onclick="toggleIngredientCategory(this)"
                >
                    <span>{{ meat_group }}</span>
                    <span class="category-arrow">▶</span>
                </button>

                <div class="ingredient-grid category-grid">

                    {% for ingredient in meat_ingredients %}

                        <label class="ingredient-option">

                            <input
                                type="checkbox"
                                name="common_ingredients"
                                value="{{ ingredient }}"
                                {% if ingredient in selected_common %}checked{% endif %}
                            >

                            {{ ingredient|title }}

                        </label>

                    {% endfor %}

                </div>

            {% endfor %}

        {% elif category == "Pantry" %}

            <button
                type="button"
                class="ingredient-category meat-group"
                onclick="toggleIngredientCategory(this)"
            >
                <span>Pasta</span>
                <span class="category-arrow">▶</span>
            </button>

            <div class="ingredient-grid category-grid">

                {% for ingredient in pasta_group["Pasta"] %}

                    <label class="ingredient-option">

                        <input
                            type="checkbox"
                            name="common_ingredients"
                            value="{{ ingredient }}"
                            {% if ingredient in selected_common %}checked{% endif %}
                        >

                        {{ ingredient|title }}

                    </label>

                {% endfor %}

            </div>

            {% for ingredient in ingredients %}

                {% if ingredient not in pasta_group["Pasta"] %}

                    <label class="ingredient-option">

                        <input
                            type="checkbox"
                            name="common_ingredients"
                            value="{{ ingredient }}"
                            {% if ingredient in selected_common %}checked{% endif %}
                        >

                        {{ ingredient|title }}

                    </label>

                {% endif %}

            {% endfor %}

        {% else %}

            {% for ingredient in ingredients %}

                <label class="ingredient-option">

                    <input
                        type="checkbox"
                        name="common_ingredients"
                        value="{{ ingredient }}"
                        {% if ingredient in selected_common %}checked{% endif %}
                    >

                    {{ ingredient|title }}

                </label>

            {% endfor %}

        {% endif %}

    </div>

{% endfor %}

    <input
        type="text"
        name="ingredients"
        placeholder="Or add other ingredients: chicken, rice, broccoli"
        value="{{ entered }}"
    >
        
        <div style="display: flex; gap: 15px; margin-top: 15px; margin-bottom: 20px;">
            <div style="flex: 1;">
                <label style="display: block; font-weight: bold; margin-bottom: 6px; color: #333; font-size: 14px;">Diet & Style</label>
                <select name="diet_style" style="width: 100%; padding: 12px; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; background: white;">
                    <option value="">Any Diet/Style</option>
                    <option value="healthy" {% if selected_diet == "healthy" %}selected{% endif %}>🥦 Healthy</option>
                    <option value="vegan" {% if selected_diet == "vegan" %}selected{% endif %}>🌱 Vegan</option>
                    <option value="quick" {% if selected_diet == "quick" %}selected{% endif %}>⏱️ Quick</option>
                    <option value="fancy" {% if selected_diet == "fancy" %}selected{% endif %}>✨ Fancy</option>
                </select>
            </div>
            <div style="flex: 1;">
                <label style="display: block; font-weight: bold; margin-bottom: 6px; color: #333; font-size: 14px;">Ethnic Cuisine</label>
                <select name="cuisine_type" style="width: 100%; padding: 12px; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; background: white;">
                    <option value="">Any Cuisine</option>
                    <option value="italian" {% if selected_cuisine == "italian" %}selected{% endif %}>🇮🇹 Italian</option>
                    <option value="american" {% if selected_cuisine == "american" %}selected{% endif %}>🍔 American</option>
                    <option value="middle eastern" {% if selected_cuisine == "middle eastern" %}selected{% endif %}>🥙 Middle Eastern</option>
                    <option value="mexican" {% if selected_cuisine == "mexican" %}selected{% endif %}>🇲🇽 Mexican</option>
                </select>
            </div>
        </div>

    <button type="submit">
        Find My Recipes
</button>

<button
    type="button"
    onclick="clearPantry(event)"
    style="margin-top: 10px; background: #777;"
>
    Clear All
</button>

<button
    type="button"
    onclick="savePantry(event)"
    style="margin-top: 10px; background: #188038;"
>
    💾 Save My Pantry
</button>

<button
    type="button"
    onclick="loadPantry(event)"
    style="margin-top: 10px; background: #3568a8;"
>
    📂 Load My Pantry
</button>

</form>
    {% if searched %}

        {% if recipes %}

            <div class="recipe-navigation">

                <button
                    type="button"
                    id="previous-recipes-top"
                    onclick="showRecipePage(currentRecipePage - 1)"
                    style="display: none;"
                >
                    ◀ Previous 5
                </button>

                <button
                    type="button"
                    id="next-recipes-top"
                    onclick="showRecipePage(currentRecipePage + 1)"
                >
                    Next 5 ▶
                </button>

            </div>

            {% for recipe in recipes %}

                <div class="recipe">
<h2>
    {{ recipe.name }}
</h2>

{% if recipe.healthy %}

    <p class="healthy-badge">
        🥦 Healthy
    </p>

{% endif %}

{% if recipe.quick %}

    <p class="quick-badge">
        ⏱️ Quick
    </p>

{% endif %}

{% if recipe.fancy %}

    <p class="fancy-badge">
        ✨ Fancy
    </p>

{% endif %}


{% if loop.first %}

    <p class="best-match">
        🥇 BEST MATCH
    </p>

{% endif %}

<p class="match match-low">
    🟠 {{ recipe.match_percentage }}% Match
</p>


{% if recipe.image %}

    <img
        src="{{ recipe.image }}"
        alt="{{ recipe.name }}"
        class="recipe-image"
    >

{% endif %}

{% if recipe.matched %}

    <p class="have">
        🟢 You have {{ recipe.used_count }} of {{ recipe.total_count }} ingredients:
        {{ recipe.matched | join(", ") }}
    </p>

{% endif %}

{% if recipe.missing %}

    <p class="missing">
        🛒 You'll need:
        {{ recipe.missing | join(", ") }}
    </p>

    {% if recipe.substitutions %}

        <div class="substitutions">

            <p class="substitution-title">
                💡 Possible substitutions:
            </p>

            {% for ingredient, options in recipe.substitutions.items() %}

                <p class="substitution-item">
                    <strong>{{ ingredient }}:</strong>
                </p>

                {% for option in options %}

                    <p class="substitution-option">
                        • {{ option }}

                        {% if recipe.substitution_notes.get(ingredient) %}

                            {% if recipe.substitution_notes[ingredient].get(option) %}

                                —
                                <strong>
                                    {{ recipe.substitution_notes[ingredient][option].rating }}
                                </strong>

                                {{ recipe.substitution_notes[ingredient][option].note }}

                            {% elif recipe.substitution_notes[ingredient].get("general") %}

                                —
                                <strong>
                                    {{ recipe.substitution_notes[ingredient]["general"].rating }}
                                </strong>

                                {{ recipe.substitution_notes[ingredient]["general"].note }}

                            {% endif %}

                        {% endif %}

                    </p>

                {% endfor %}

            {% endfor %}

        </div>

    {% endif %}

{% else %}

    <p class="have">
        🎉 You have everything!
    </p>

{% endif %}

<button type="button" class="recipe-toggle" onclick="toggleRecipe(this)">
                        ▶ View Recipe
                    </button>

                    <div class="recipe-details" style="display: none;">
                        {% if recipe.nutrition %}
                        <h3>Nutrition per serving</h3>
                        {% if recipe.displayTotalTime %}
                            <p><strong>Total time:</strong> {{ recipe.displayTotalTime }}</p>
                        {% endif %}
                        <div class="nutrition">
                            {% if recipe.displayRecipeYield %}
                                <p><strong>Yield:</strong> {{ recipe.displayRecipeYield }}</p>
                            {% endif %}
                            {% if recipe.nutrition.get("calories") %}
                                <p><strong>Calories:</strong> {{ recipe.nutrition.get("calories") }}</p>
                            {% endif %}
                            {% if recipe.nutrition.get("fatContent") %}
                                <p><strong>Total fat:</strong> {{ recipe.nutrition.get("fatContent") }}</p>
                            {% endif %}
                            {% if recipe.nutrition.get("saturatedFatContent") %}
                                <p><strong>Saturated fat:</strong> {{ recipe.nutrition.get("saturatedFatContent") }}</p>
                            {% endif %}
                            {% if recipe.nutrition.get("sodiumContent") %}
                                <p><strong>Sodium:</strong> {{ recipe.nutrition.get("sodiumContent") }}</p>
                            {% endif %}
                            {% if recipe.nutrition.get("proteinContent") %}
                                <p><strong>Protein:</strong> {{ recipe.nutrition.get("proteinContent") }}</p>
                            {% endif %}
                            {% if recipe.nutrition.get("carbohydrateContent") %}
                                <p><strong>Carbohydrates:</strong> {{ recipe.nutrition.get("carbohydrateContent") }}</p>
                            {% endif %}
                            {% if recipe.nutrition.get("fiberContent") %}
                                <p><strong>Fiber:</strong> {{ recipe.nutrition.get("fiberContent") }}</p>
                            {% endif %}
                            {% if recipe.nutrition.get("sugarContent") %}
                                <p><strong>Sugar:</strong> {{ recipe.nutrition.get("sugarContent") }}</p>
                            {% endif %}
                        </div>
                        {% endif %}

                        <h3>Ingredients</h3>

                        <p class="recipe-note">
                            <strong>Recipe details:</strong>
                            Exact amounts, measurements, preparation details,
                            and cooking instructions are provided by the original
                            recipe. Please check the original recipe for complete
                            details.
                        </p>

<div class="ingredients">
    {% for ingredient in recipe.ingredients %}
        <p>
            {% if ingredient is string %}
                • {{ ingredient }}
            {% else %}
                • {{ ingredient.measure }} {{ ingredient.ingredient }}
            {% endif %}
        </p>
    {% endfor %}
</div>

                        <h3>Instructions</h3>

                        <div class="instructions">
                            {% if recipe.instructions is string %}
                                {{ recipe.instructions | safe }}
                            {% else %}
                                <ol>
                                    {% for step in recipe.instructions %}
                                        <li>{{ step }}</li>
                                    {% endfor %}
                                </ol>
                            {% endif %}
                        </div>

                    </div>
                    
                    {% if recipe.source %}

                        <a
                            class="source"
                            href="{{ recipe.source }}"
                            target="_blank"
                        >
                            View Original Recipe
                        </a>

                    {% endif %}

                </div>

            {% endfor %}

            <div class="recipe-navigation">

                <button
                    type="button"
                    id="previous-recipes"
                    onclick="showRecipePage(currentRecipePage - 1)"
                    style="display: none;"
                >
                    ◀ Previous 5
                </button>

                <button
                    type="button"
                    id="next-recipes"
                    onclick="showRecipePage(currentRecipePage + 1)"
                >
                    Next 5 ▶
                </button>

            </div>

        {% else %}

            <div class="error">

                No matching recipes were found.

                Try entering common ingredients such as:

                chicken, rice, eggs, pasta, tomato, onion

            </div>

        {% endif %}

    {% endif %}

</div>

</body>

</html>
"""


# ---------------------------------------------------------
# HOME PAGE
# ---------------------------------------------------------

@app.route(
    "/",
    methods=["GET", "POST"]
)

def home():
    selected_diet = request.form.get("diet_style", "") if request.method == "POST" else ""
    selected_cuisine = request.form.get("cuisine_type", "") if request.method == "POST" else ""

    recipes = []

    entered = ""

    searched = False

    selected_common = []

    if request.method == "POST":

        entered = request.form.get(
            "ingredients",
            ""
        ).strip()

        selected_common = [
            ingredient.lower()
            for ingredient in request.form.getlist(
                "common_ingredients"
            )
        ]
        if entered or selected_common:

            searched = True

            user_ingredients = [

                ingredient.strip()

                for ingredient in entered.split(",")

                if ingredient.strip()
            ]
 
            user_ingredients.extend(
                selected_common
            )

            user_ingredients = [
                canonical_ingredient_identity(item)
                for item in user_ingredients
            ]

            user_ingredients = [
                item
                for item in user_ingredients
                if item
            ]

            selected_common = [
                canonical_ingredient_identity(item)
                for item in selected_common
            ]

            selected_common = [
                item
                for item in selected_common
                if item
            ]

            # Create a clean payload array incorporating user lifestyle and ethnic choices.
            # Pantry ingredients incompatible with the selected diet must not influence
            # the web search. For Vegan, ordinary animal proteins are ignored.
            search_pantry = list(user_ingredients)

            if selected_diet == "vegan":
                excluded_search_items = {
                    "chicken",
                    "beef",
                    "pork",
                    "lamb",
                    "turkey",
                    "fish",
                    "seafood",
                    "salmon",
                    "cod",
                    "haddock",
                    "tilapia",
                    "tuna",
                    "shrimp",
                    "egg",
                    "eggs",
                    "milk",
                    "cheese",
                    "butter",
                }

                excluded_search_items.update(
                    item
                    for values in MEAT_GROUPS.values()
                    for item in values
                )

                filtered_search_pantry = []

                for pantry_item in search_pantry:
                    normalized_item, _ = normalize_recipe_ingredient(
                        pantry_item
                    )
                    normalized_item = ingredient_alias(
                        clean_word(normalized_item)
                    )

                    if normalized_item in excluded_search_items:
                        continue

                    filtered_search_pantry.append(pantry_item)

                search_pantry = filtered_search_pantry

            search_payload = list(search_pantry)
            print("BROWSER SEARCH PAYLOAD:", search_payload)
            print("BROWSER USER INGREDIENTS:", user_ingredients)
            if selected_diet:
                if selected_diet == "fancy":
                    search_payload.append("gourmet")
                else:
                    search_payload.append(selected_diet)
            if selected_cuisine:
                search_payload.append(selected_cuisine)
            recipes = find_recipes(
                user_ingredients,
                search_terms=search_payload,
                selected_cuisine=selected_cuisine,
                selected_diet=selected_diet
            )


    return render_template_string(
        HTML,
        recipes=recipes,
        entered=entered,
        searched=searched,
        common_ingredients=COMMON_INGREDIENTS,
        meat_groups=MEAT_GROUPS,
        pasta_group=PASTA_GROUP,
        selected_common=selected_common,
        selected_diet=selected_diet,
        selected_cuisine=selected_cuisine,
        posthog_api_key=os.getenv("POSTHOG_API_KEY")
    )

# ---------------------------------------------------------
# START APP
# ---------------------------------------------------------

if __name__ == "__main__":

    app.run(
        debug=False
    )
