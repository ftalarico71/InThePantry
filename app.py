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
        "chicken breast",
        "chicken breasts",
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
        "beef brisket",
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

def ingredient_matches(recipe_ingredient, user_ingredients):
    recipe_name = clean_word(recipe_ingredient)
    if not recipe_name:
        return False

    recipe_name = ingredient_alias(recipe_name)
    recipe_name = clean_word(recipe_name)
    if not recipe_name:
        return False

    normalized_recipe, _ = normalize_recipe_ingredient(recipe_name)
    if normalized_recipe:
        recipe_name = normalized_recipe

    recipe_name = ingredient_alias(recipe_name)
    recipe_name = clean_word(recipe_name)
    if not recipe_name:
        return False

    if recipe_name in PANTRY_STAPLES:
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

        for core_name, variants in CORE_INGREDIENTS.items():
            core_name_clean = clean_word(core_name)
            all_variants = {core_name_clean}
            for variant in variants:
                variant_clean = clean_word(variant)
                if variant_clean:
                    all_variants.add(variant_clean)
            if ingredient in all_variants:
                return core_name
            for variant in all_variants:
                if ingredient_singular == singular(variant):
                    return core_name
        return None

    recipe_core = find_core(recipe_name)

    pasta_variants = {
        "pasta", "spaghetti", "fettuccine", "linguine", "penne", "penne pasta",
        "penne rigate", "rigatoni", "rigatoni pasta", "macaroni", "macaroni pasta",
        "elbow macaroni", "elbow pasta", "cavatappi", "cavatappi pasta", "rotini",
        "rotini pasta", "ziti", "ziti pasta", "farfalle", "bow tie pasta",
        "angel hair", "angel hair pasta", "lasagna noodles", "lasagna pasta",
        "dry pasta", "vermicelli", "noodles", "egg noodles",
    }

    if recipe_core == "pasta" or recipe_name in pasta_variants:
        for user_item in user_ingredients or []:
            user_name = clean_word(user_item)
            if not user_name:
                continue
            user_name = ingredient_alias(user_name)
            user_name = clean_word(user_name)
            if user_name in pasta_variants:
                if recipe_name == user_name:
                    return True
        return False

    meat_variants = {
        "beef", "ground beef", "lean ground beef", "beef chuck", "beef brisket",
        "beef shank", "beef steak", "beef roast", "beef stew meat", "beef short ribs",
        "beef tenderloin", "beef sirloin", "chicken", "chicken breast", "chicken breasts",
        "chicken thigh", "chicken thighs", "chicken leg", "chicken legs", "chicken wing",
        "chicken wings", "chicken drumstick", "chicken drumsticks",
        "boneless skinless chicken breast", "boneless skinless chicken thighs", "pork",
        "ground pork", "pork chop", "pork chops", "pork loin", "pork shoulder",
        "pork tenderloin", "turkey", "ground turkey", "turkey breast", "turkey thigh",
        "lamb", "ground lamb", "lamb shoulder", "lamb leg", "lamb chops",
    }

    if recipe_name in meat_variants:
        recipe_parent = find_core(recipe_name)
        for user_item in user_ingredients or []:
            user_name = clean_word(user_item)
            if not user_name:
                continue
            user_name = ingredient_alias(user_name)
            user_name = clean_word(user_name)
            if user_name not in meat_variants:
                continue
            if recipe_name == user_name or singular(recipe_name) == singular(user_name):
                return True
            if recipe_parent and recipe_parent == user_name:
                return True
        return False

    for user_item in user_ingredients or []:
        user_name = clean_word(user_item)
        if not user_name:
            continue
        user_name = ingredient_alias(user_name)
        user_name = clean_word(user_name)
        if not user_name:
            continue
        if recipe_name == user_name or singular(recipe_name) == singular(user_name):
            return True
        user_core = find_core(user_name)
        if recipe_core and user_core and recipe_core == user_core:
            if recipe_core == 'pepper':
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
        if re.search(
            r'\bsalt\b\s+and\s+(?:(?:freshly\s+ground|ground)\s+)?\bpepper\b',
            original,
            re.IGNORECASE
        ):
            parts = re.split(
                r'\s+and\s+',
                original,
                maxsplit=1,
                flags=re.IGNORECASE
            )

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

            # Assumed pantry staples are not tracked.
            # Some recipes write "salt and pepper" as one
            # ingredient line. After normalization, this can
            # become "salt pepper". Treat both as pantry staples.
            if normalized == "salt pepper":
                continue

            if normalized in PANTRY_STAPLES:
                continue
            # Treat bell pepper varieties as one ingredient
            # for recipe scoring.
            pepper_variants = {
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
                "bell peppers",
                "green peppers",
                "red peppers",
                "yellow peppers",
                "orange peppers",
            }
            if normalized in pepper_variants:
                normalized = "bell pepper"

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
        contextual_match = (
            beef_recipe
            and name == "stew meat"
            and "beef" in pantry
        )

        if matches(name) or contextual_match:
            have.append({
                "ingredient": name,
                "original": info["original"],
                "status": "have"
            })
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
                "count": count
            },
            headers={
                "X-Subscription-Token": BRAVE_API_KEY,
                "Accept": "application/json"
            },
            timeout=10
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

def normalize_recipe_ingredient(text):
    if not text:
        return '', []

    text = text.lower().strip()

    # Treat common ingredient separators as separate items.
    text = re.sub(r'\s+\+\s+', ',', text)

    # Decode common HTML entities.
    text = re.sub(r'&quot;|&amp;', ' ', text)

    # Find alternatives such as:
    # 'sesame oil (or olive oil)'
    # 'chicken broth (or water)'
    alternatives = re.findall(r'\bor\s+([^()]+)', text)

    # Remove parenthetical preparation notes.
    text = re.sub(r'\([^)]*\)', '', text)

    # Remove quantities.
    text = re.sub(r'\b\d+(?:[./]\d+)?\b', ' ', text)

    # Remove common units and size words.
    text = re.sub(r'\b(?:lbs?|pounds?|oz|ounces?|cups?|cup|tbsp|tbs|tablespoons?|tsp|teaspoons?|cloves?|heads?|large|medium|small|thin)\b', ' ', text)

    # Remove preparation descriptors.
    text = re.sub(r'\b(?:diced|chopped|minced|cubed|sliced|halved|fresh|freshly|finely|uncooked|cooked|beaten|whisked|grated|shredded|well|low sodium|toasted|dried)\b', ' ', text)

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
    text = re.sub(r'\bblack\s+pepper\b', 'pepper', text)

    # Normalize salt-and-pepper combinations to salt.
    text = re.sub(r'\b(?:kosher|sea|table)?\s*salt\s+(?:and|&)\s+(?:freshly\s+ground\s+|ground\s+)?(?:black\s+)?pepper\b', 'salt', text)

    # Remove common recipe wording.
    text = re.sub(r'\b(?:of|to|for|as needed|divided|plus|taste)\b', ' ', text)

    # Remove common quantity words.
    text = re.sub(r'\b(?:bunch|pinch|dash|handful|package|packages|can|cans|stick|sticks)\b', ' ', text)

    # Keep letters and spaces.
    text = re.sub(r'[^a-z\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()

    return text, alternatives

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

def find_recipes(user_ingredients):
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
            user_ingredients,
            count=10
        )
    except Exception as e:
        print("Web recipe search error:", e)
        return []

    if not search_results:
        print("No web recipe search results found.")
        return []

    scored_recipes = []

    for result in search_results:

        url = result.get("url")

        if not url:
            continue

        # Extract the actual recipe from the webpage.
        try:
            recipe = extract_web_recipe(url)
        except Exception as e:
            print("Recipe extraction error:", e)
            continue

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

            "primary_match": 1,

            "instructions": instructions,

            "source": url
        })

    # Highest pantry match first.
    # If tied, prefer the recipe using more
    # ingredients the user already has.
    scored_recipes.sort(
        key=lambda x: (
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

            recipes = find_recipes(
                user_ingredients
            )


    return render_template_string(
        HTML,
        recipes=recipes,
        entered=entered,
        searched=searched,
        common_ingredients=COMMON_INGREDIENTS,
        meat_groups=MEAT_GROUPS,
        pasta_group=PASTA_GROUP,
        selected_common=selected_common
    )

# ---------------------------------------------------------
# START APP
# ---------------------------------------------------------

if __name__ == "__main__":

    app.run(
        debug=True
    )
