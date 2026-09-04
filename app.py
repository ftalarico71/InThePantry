from flask import Flask, request, render_template_string
import requests
import re
import os
import json
import html as html_lib
from dotenv import load_dotenv

load_dotenv()

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

    text = re.sub(r"[^a-zA-Z\s]", "", text)

    text = re.sub(r"\s+", " ", text).strip()

    return text


# ---------------------------------------------------------
# INGREDIENT ALIASES
# ---------------------------------------------------------

def ingredient_alias(text):
    text = text.strip().lower()
    if text == 'lean ground beef':
        return 'ground beef'
    text = clean_word(text)

    # Correct obvious misspellings before applying aliases.
    # Only very close matches to known ingredients are corrected.
    from difflib import get_close_matches

    known_ingredients = set()

    for family_values in CORE_INGREDIENTS.values():
        known_ingredients.update(family_values)

    # Also include the broader common-ingredient vocabulary.
    # This gives typo correction access to ingredients such
    # as tomato that are not part of CORE_INGREDIENTS.
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
        "spring onions": "onion",
        "spring onion": "onion",
        "green onions": "onion",
        "green onion": "onion",
        "scallions": "onion",
        "scallion": "onion",
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

    return aliases.get(text, text)


# ---------------------------------------------------------
# MATCH INGREDIENTS
# ---------------------------------------------------------

def ingredient_matches(recipe_ingredient, user_ingredients, allow_pantry_staple=True):
    original_recipe_name = clean_word(recipe_ingredient)

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

    def find_core(ingredient):
        ingredient = clean_word(ingredient)
        if not ingredient:
            return None
        ingredient = ingredient_alias(ingredient)
        ingredient = clean_word(ingredient)
        ingredient_singular = singular(ingredient)

        best_descriptive_core = None
        best_descriptive_length = 0

        for core_name, variants in CORE_INGREDIENTS.items():
            core_name_clean = clean_word(core_name)
            all_variants = {core_name_clean}

            for variant in variants:
                variant_clean = clean_word(variant)
                if variant_clean:
                    all_variants.add(variant_clean)

                    # Also include the canonical alias form of the
                    # variant. For example:
                    #   "parmesan cheese" -> "parmesan"
                    variant_alias = ingredient_alias(variant_clean)
                    variant_alias = clean_word(variant_alias)
                    if variant_alias:
                        all_variants.add(variant_alias)
            if ingredient in all_variants:
                return core_name

            for variant in all_variants:
                if ingredient_singular == singular(variant):
                    return core_name

            # Descriptive recipe wording may contain a known ingredient
            # variant without being an exact match.
            #
            # Examples:
            #   "bulb garlic" -> garlic
            #   "parmesan cheese topping" -> parmesan
            #   "extra virgin olive oil the garlic and finishing" -> oil
            #
            # Use complete word boundaries so short cores such as "oil"
            # cannot match inside unrelated words.
            for variant in all_variants:
                variant_words = variant.split()
                ingredient_words = ingredient.split()

                if not variant_words or len(variant_words) > len(ingredient_words):
                    continue

                for i in range(len(ingredient_words) - len(variant_words) + 1):
                    candidate = ingredient_words[i:i + len(variant_words)]

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
            return best_descriptive_core

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
    if " or " in recipe_name:
        alternatives = [
            part.strip()
            for part in recipe_name.split(" or ")
            if part.strip()
        ]

        if len(alternatives) > 1:
            first_words = alternatives[0].split()
            expanded = [alternatives[0]]

            # Expand abbreviated alternatives such as
            # "chicken breasts or thighs" ->
            # "chicken breasts" / "chicken thighs".
            expanded = [alternatives[0]]

            if len(first_words) >= 2:
                shared_prefix = " ".join(first_words[:-1])

                for alternative in alternatives[1:]:
                    alternative_words = alternative.split()

                    if len(alternative_words) == 1:
                        # Keep BOTH interpretations.
                        #
                        # Independent alternative:
                        #   broccoli florets or asparagus
                        #       -> asparagus
                        #
                        # Abbreviated shared-prefix alternative:
                        #   chicken breasts or thighs
                        #       -> chicken thighs
                        #
                        # This makes OR matching universal instead of
                        # assuming every one-word alternative belongs
                        # to the first ingredient.
                        expanded.append(alternative)
                        expanded.append(
                            shared_prefix + " " + alternative
                        )
                    else:
                        expanded.append(alternative)
            else:
                expanded.extend(alternatives[1:])

            for alternative in expanded:
                alternative_clean = clean_word(alternative)
                alternative_clean = ingredient_alias(alternative_clean)
                alternative_clean = clean_word(alternative_clean)

                if not alternative_clean:
                    continue

                # Normalize each alternative independently. This removes
                # universal preparation descriptors such as chopped, diced,
                # sliced, bone-in, boneless, florets, etc.
                normalized_alternative, _ = normalize_recipe_ingredient(
                    alternative_clean
                )
                if normalized_alternative:
                    alternative_clean = normalized_alternative

                alternative_clean = ingredient_alias(alternative_clean)
                alternative_clean = clean_word(alternative_clean)

                if not alternative_clean:
                    continue

                alternative_core = find_core(alternative_clean)

                # Meat alternatives must not bypass the authoritative meat
                # hierarchy below through direct/core OR matching.
                alternative_is_meat = alternative_clean in {
                    "beef", "ground beef", "steak", "ribeye", "rib eye",
                    "sirloin", "sirloin steak", "new york strip",
                    "new york strip steak", "ny strip", "ny strip steak",
                    "strip steak", "filet", "filet mignon",
                    "tenderloin", "tenderloin steak", "porterhouse",
                    "porterhouse steak", "t-bone", "t-bone steak",
                    "flat iron steak", "flank steak", "skirt steak",
                    "chicken", "chicken breast", "chicken breasts",
                    "chicken thigh", "chicken thighs", "chicken leg",
                    "chicken legs", "chicken wing", "chicken wings",
                    "chicken drumstick", "chicken drumsticks",
                    "chicken tender", "chicken tenders", "chicken cutlet",
                    "chicken cutlets", "whole chicken", "ground chicken",
                    "pork", "pork chop", "pork chops", "pork loin",
                    "pork shoulder", "pork tenderloin", "pork belly",
                    "pork rib", "pork ribs", "baby back ribs", "spare ribs",
                    "ground pork", "turkey", "turkey breast", "turkey breasts",
                    "turkey thigh", "turkey thighs", "turkey leg", "turkey legs",
                    "turkey wing", "turkey wings", "turkey tender",
                    "turkey tenders", "whole turkey", "ground turkey",
                    "lamb", "lamb shoulder", "lamb leg", "lamb legs",
                    "lamb chop", "lamb chops", "lamb loin", "lamb loins",
                    "lamb shank", "lamb shanks", "lamb rack", "rack of lamb",
                    "lamb rib", "lamb ribs", "ground lamb"
                }

                for user_item in user_ingredients or []:
                    user_name = clean_word(user_item)
                    if not user_name:
                        continue

                    user_name = ingredient_alias(user_name)
                    user_name = clean_word(user_name)

                    # Normalize pantry wording too. This allows a pantry item
                    # such as "bone-in chicken" or "boneless chicken" to
                    # satisfy a generic recipe alternative such as "chicken".
                    normalized_user, _ = normalize_recipe_ingredient(user_name)
                    if normalized_user:
                        user_name = normalized_user

                    user_name = ingredient_alias(user_name)
                    user_name = clean_word(user_name)

                    if not user_name:
                        continue

                    # Resolve the pantry core before any direct/core shortcut.
                    user_core = find_core(user_name)

                    # OR meat alternatives must obey the authoritative meat
                    # hierarchy instead of falling through to broad core matching.
                    # Generic recipe meat may NOT be satisfied by a specific
                    # pantry cut; a generic pantry meat MAY satisfy a specific
                    # recipe cut. Ground meat remains separate from whole/cut meat.
                    or_meat_cores = {"beef", "chicken", "pork", "turkey", "lamb"}

                    if alternative_core in or_meat_cores or user_core in or_meat_cores:
                        if alternative_core != user_core:
                            continue

                        recipe_is_ground = (
                            alternative_clean in {
                                "ground beef", "ground chicken", "ground pork",
                                "ground turkey", "ground lamb"
                            }
                            or alternative_clean.startswith("ground ")
                        )
                        user_is_ground = (
                            user_name in {
                                "ground beef", "ground chicken", "ground pork",
                                "ground turkey", "ground lamb"
                            }
                            or user_name.startswith("ground ")
                        )

                        if recipe_is_ground != user_is_ground:
                            continue

                        # Generic recipe meat cannot accept a specific pantry cut.
                        if alternative_clean == alternative_core and user_name != user_core:
                            continue

                        # Generic pantry meat can satisfy a specific recipe cut.
                        if alternative_clean != alternative_core and user_name == user_core:
                            return True

                        # Exact same meat item is valid.
                        if alternative_clean == user_name:
                            return True

                        # Same-family specific cuts cannot substitute for one another.
                        continue

                    # Direct or singular/plural match.
                    if (
                        alternative_clean == user_name
                        or singular(alternative_clean) == singular(user_name)
                    ):
                        return True

                    # Core ingredient match.
                    if (
                        alternative_core
                        and user_core
                        and alternative_core == user_core
                    ):
                        return True

                    # Universal parent/core fallback for descriptive variants.
                    # This deliberately requires both sides to resolve to the
                    # same known core ingredient, preventing cross-meat matches.
                    if alternative_core and user_core:
                        if alternative_core == user_core:
                            return True

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
        return name in ground_meats or "ground beef" in name

    def is_steak_cut(name):
        name = clean_word(name)
        if not name:
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

            if recipe_name in meat_lookup or user_name in meat_lookup:
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

            if user_core and recipe_core == user_core:
                return True

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

    recipe_parent = meat_lookup.get(recipe_name)

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

            user_parent = meat_lookup.get(user_name)
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
        recipe_meat_parent = meat_lookup.get(recipe_name)
        user_meat_parent = meat_lookup.get(user_name)

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

    query = " ".join(ingredients) + " recipe"

    try:
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
            print(
                "Brave API response:",
                response.status_code,
                response.text
            )
            response.raise_for_status()

        data = response.json()

        results = data.get(
            "web",
            {}
        ).get(
            "results",
            []
        )

        recipes = []

        for result in results:

            title = result.get(
                "title",
                ""
            ).strip()

            url = result.get(
                "url",
                ""
            ).strip()

            description = result.get(
                "description",
                ""
            ).strip()

            if not title or not url:
                continue

            # Try to extract the actual recipe from the page.
            # Some websites may block the request or may not
            # contain Recipe Schema. Those results are skipped
            # rather than being returned as empty recipes.

            recipe = extract_web_recipe(url)

            if not recipe:
                print(
                    "Skipping search result - "
                    "recipe could not be extracted:",
                    url
                )
                continue

            # Make sure the extracted recipe has the
            # information our matching engine needs.

            if not recipe.get("name"):
                recipe["name"] = title

            if not recipe.get("ingredients"):
                print(
                    "Skipping search result - "
                    "no ingredients found:",
                    url
                )
                continue

            # UNIVERSAL RECIPE INGREDIENT CLEANUP
            # Normalize the ingredient identity as soon as recipe data
            # comes off the internet. Measurements, sizes, preparation
            # wording, and recipe-site metadata are not pantry identity.
            cleaned_ingredients = []

            for raw_ingredient in recipe.get("ingredients", []):
                if not isinstance(raw_ingredient, str):
                    continue

                normalized, alternatives = normalize_recipe_ingredient(
                    raw_ingredient
                )

                if not normalized:
                    continue

                if alternatives:
                    normalized = (
                        normalized
                        + " or "
                        + " or ".join(
                            alt.strip()
                            for alt in alternatives
                            if alt.strip()
                        )
                    ).strip()

                cleaned_ingredients.append(normalized)

            recipe["ingredients"] = cleaned_ingredients

            if not recipe.get("ingredients"):
                print(
                    "Skipping search result - "
                    "no usable ingredients found:",
                    url
                )
                continue

            if not recipe.get("description"):
                recipe["description"] = description

            recipes.append(recipe)

            if len(recipes) >= count:
                break

        return recipes

    except requests.HTTPError as e:
        print(
            "Brave web search HTTP error:",
            e
        )
        return []

    except requests.RequestException as e:
        print(
            "Brave web search error:",
            e
        )
        return []

    except ValueError as e:
        print(
            "Brave web search JSON error:",
            e
        )
        return []

# ---------------------------------------------------------
# EXTRACT RECIPE FROM WEB PAGE
# Reads standard Recipe Schema data from recipe websites.
# ---------------------------------------------------------

# ---------------------------------------------------------
# EXTRACT RECIPE FROM WEB PAGE
# Reads standard Recipe Schema data from recipe websites.
# ---------------------------------------------------------

# ---------------------------------------------------------
# NORMALIZE RECIPE INGREDIENT
# Converts recipe ingredient text into a simpler ingredient
# name while preserving alternatives separately.
# ---------------------------------------------------------

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
    

def normalize_recipe_ingredient(text):
    if not text:
        return '', []

    text = text.lower().strip()

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
        r'(?:(?:freshly\s+ground|ground|cracked)\s+)?(?:black|white)?\s*pepper'
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
        r'\b\d+(?:[./]\d+)?(?:\s*[~\-]\s*\d+(?:[./]\d+)?)?\b',
        ' ',
        text
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

    # Remove trailing recipe unit/measurement metadata that some
    # recipe sites append after the ingredient identity.
    text = re.sub(
        r'\s+\b(?:ea|each|mass|spoon|spoons)\b\s*$',
        '',
        text,
        flags=re.IGNORECASE
    )

    # Reduce descriptive meat preparation wording to the actual cut.
    text = re.sub(r'\bcenter\s+cut\s+(pork\s+loin)\b.*', r'\1', text)

    # Remove preparation descriptors.
    text = re.sub(r'\bstems?\s+removed\b', ' ', text)

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
        r'\b(?:diced|chopped|minced|cubed|sliced|halved|fresh|freshly|finely|uncooked|cooked|beaten|whisked|grated|shredded|well|low sodium|toasted|dried|peeled|thinly|boneless|skinless|bone[ -]in|skin[ -]on|raw|each|slice|slices|strip|strips|piece|pieces|chunk|chunks|wedge|wedges|stalk|stalks|spear|spears|leaf|leaves|ear|ears|knob|knobs|sprig|sprigs|sheet|sheets|stem|stems|pod|pods|rinsed|rinsed|seeds|seed|veins|vein)\b',
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
    text = re.sub(r'\b(?:freshly\s+ground|ground)\s+black\s+pepper\b', 'pepper', text)


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
    known_ingredient = extract_known_ingredient(text)
    if known_ingredient:
        text = known_ingredient

    return text, alternatives

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

def find_recipes(user_ingredients, search_terms=None):
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

        recipe_ingredients = recipe.get(
            "ingredients",
            []
        )

        if not recipe_ingredients:
            continue

        # Compare the recipe with the user's pantry.
        try:
            pantry_result = match_recipe_to_pantry(
                recipe,
                user_ingredients
            )
        except Exception as e:
            print("Pantry matching error:", e)
            continue

        if not pantry_result:
            continue

        matched = [
            item["ingredient"]
            for item in pantry_result.get(
                "have",
                []
            )
        ]

        missing_items = pantry_result.get(
            "missing",
            []
        )

        missing = [
            item["ingredient"]
            for item in missing_items
        ]

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

        if used_count == 0:
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

            "instructions": instructions,

            "source": url
        })

    # Highest pantry match first.
    # If tied, prefer the recipe using more
    # ingredients the user already has.
    scored_recipes.sort(
        key=lambda x: (
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
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
        }

        .container {
            max-width: 900px;
            margin: auto;
        }

        h1 {
            text-align: center;
            color: #333;
        }

        .subtitle {
            text-align: center;
            color: #666;
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
    padding: 14px 16px;
    border: 1px solid #ddd;
    border-radius: 10px;
    background: #f5f5f5;
    color: #333;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 18px;
    font-weight: bold;
    cursor: pointer;
    text-align: left;
}

.ingredient-category:hover {
    background: #eef6df;
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
</head>

<body>

<div class="container">

    <h1>🍳 InThePantry</h1>

    <p class="subtitle">
        Enter the ingredients you have and find recipes you can make.
    </p>
<form method="POST">

    <div class="common-ingredients">

        <h3>What do you already have?</h3>
        <p class="ingredient-help">Quick selections are general categories. For more accurate recipe matches, select the specific ingredient you have when available, or enter it manually. For example, "Cheese" is less specific than "Cheddar Cheese."</p>

        
    <button
        type="button"
        class="ingredient-category"
        onclick="toggleIngredientCategory(this)"

{% for category, ingredients in common_ingredients.items() %}

    <button
        type="button"
        class="ingredient-category"
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
                        <h3>Ingredients</h3>

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

            # Create a clean payload array incorporating user lifestyle and ethnic choices
            search_payload = list(user_ingredients)
            if selected_diet:
                search_payload.append(selected_diet)
            if selected_cuisine:
                search_payload.append(selected_cuisine)
            recipes = find_recipes(
                user_ingredients,
                search_terms=search_payload
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
        selected_cuisine=selected_cuisine
    )

# ---------------------------------------------------------
# START APP
# ---------------------------------------------------------

if __name__ == "__main__":

    app.run(
        debug=True
    )
