from flask import Flask, request, render_template_string
import requests
import re
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

THEMEALDB_URL = "https://www.themealdb.com/api/json/v1/1"
RECIPE_API_KEY = os.getenv("RECIPE_API_KEY")
# ---------------------------------------------------------
# PANTRY STAPLES
# These don't count as ingredients the user needs to buy.
# ---------------------------------------------------------

PANTRY_STAPLES = {
    "salt",
    "pepper",
    "black pepper",
    "white pepper",
    "water",
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
        "chicken",
        "chicken breast",
        "chicken thigh",
        "chicken drumstick",
        "chicken wing",
        "whole chicken",

        "beef",
        "ground beef",
        "beef chuck",
        "beef brisket",
        "beef steak",
        "beef roast",
        "beef stew meat",

        "pork",
        "ground pork",
        "pork chop",
        "pork loin",
        "pork shoulder",
        "pork tenderloin",
        "bacon",
        "ham",

        "lamb",
        "ground lamb",
        "lamb shoulder",
        "lamb leg",
        "lamb chops",

        "turkey",
        "ground turkey",
        "turkey breast",
        "turkey thigh",

        "fish",
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
        "pasta",
        "beans",
        "bread",
        "tomato sauce",
        "olive oil",
        "vegetable oil",
    ],
}

MEAT_GROUPS = {
    "Beef": [
        "beef",
        "ground beef",
        "beef chuck",
        "beef brisket",
        "beef steak",
        "beef roast",
        "beef stew meat",
    ],

    "Chicken": [
        "chicken",
        "chicken breast",
        "chicken thigh",
        "chicken drumstick",
        "chicken wing",
        "whole chicken",
    ],

    "Pork": [
        "pork",
        "ground pork",
        "pork chop",
        "pork loin",
        "pork shoulder",
        "pork tenderloin",
        "bacon",
        "ham",
    ],

    "Lamb": [
        "lamb",
        "ground lamb",
        "lamb shoulder",
        "lamb leg",
        "lamb chops",
    ],

    "Turkey": [
        "turkey",
        "ground turkey",
        "turkey breast",
        "turkey thigh",
    ],

    "Fish": [
        "fish",
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

        "olive oil": "oil",
        "vegetable oil": "oil",
        "ground nut oil": "oil",
        "groundnut oil": "oil",

        "chicken breast": "chicken",
        "chicken breasts": "chicken",
        "chicken thigh": "chicken",
        "chicken thighs": "chicken",

        "white rice": "rice",
        "brown rice": "rice",

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

def ingredient_matches(
    recipe_ingredient,
    user_ingredients
):

    recipe_name = clean_word(
        recipe_ingredient
    )

    if recipe_name in PANTRY_STAPLES:
        return True

    excluded_combinations = {
        'rice': [
            'rice vinegar',
            'rice wine',
            'rice wine vinegar',
            'rice noodle',
            'wide rice noodle'
        ],
        'chicken': [
            'chicken broth',
            'chicken stock',
            'chicken bouillon'
        ],
        'broccoli': [
            'chinese broccoli',
            'broccoli soup',
            'broccoli cheese soup'
        ],
        'beef': [
            'beef broth',
            'beef stock',
            'beef bouillon'
        ]
    }

    for user_item in user_ingredients:

        user_name = clean_word(
            user_item
        )

        if not user_name:
            continue

        blocked = excluded_combinations.get(
            user_name,
            []
        )

        if recipe_name in blocked:
            continue

        # Exact match.
        if recipe_name == user_name:
            return True

        # Simple singular/plural matching.
        if (
            recipe_name.endswith('s')
            and recipe_name[:-1] == user_name
        ):
            return True

        if (
            user_name.endswith('s')
            and user_name[:-1] == recipe_name
        ):
            return True
        
        # Allow a more specific recipe ingredient
        # to match a general pantry ingredient only
        # for selected food categories.
        allowed_general_matches = {
            'beef': [
                'ground beef',
                'beef chuck',
                'beef brisket',
                'beef shank',
                'beef steak',
                'beef roast',
                'beef stew meat',
                'beef short ribs',
                'beef tenderloin',
                'beef sirloin'
            ],
            'chicken': [
                'chicken breast',
                'chicken thigh',
                'chicken leg',
                'chicken drumstick',
                'chicken wing'
            ],
            'potatoes': [
                'small potatoes',
                'baby potatoes',
                'new potatoes',
                'red potatoes',
                'yukon gold potatoes',
                'russet potatoes'
            ],
            'pork': [
                'ground pork',
                'pork chop',
                'pork loin',
                'pork shoulder',
                'pork tenderloin'
            ],
            'lamb': [
                'ground lamb',
                'lamb shoulder',
                'lamb leg',
                'lamb chops'
            ],
            'turkey': [
                'ground turkey',
                'turkey breast',
                'turkey thigh'
            ],
            'onion': [
                'onions',
                'yellow onion',
                'white onion',
                'red onion'
            ],
            'garlic': [
                'fresh garlic',
                'garlic cloves'
            ],
            'carrots': [
                'carrot',
                'baby carrots'
            ],
            'bell pepper': [
                'bell peppers',
                'red bell pepper',
                'green bell pepper',
                'yellow bell pepper',
                'orange bell pepper'
            ] 
        }

        if recipe_name in allowed_general_matches.get(
            user_name,
            []
        ):
            return True

    return False

# ---------------------------------------------------------
# SEARCH RECIPES
# ---------------------------------------------------------

def search_recipe(ingredient):

    try:

        response = requests.get(
            f"{THEMEALDB_URL}/filter.php",
            params={"i": ingredient},
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        return data.get(
            "meals",
            []
        ) or []

    except requests.RequestException:

        return []


# ---------------------------------------------------------
# GET COMPLETE RECIPE
# ---------------------------------------------------------

def get_recipe(meal_id):

    try:

        response = requests.get(
            f"{THEMEALDB_URL}/lookup.php",
            params={"i": meal_id},
            timeout=10
        )

        response.raise_for_status()

        data = response.json()

        meals = data.get(
            "meals",
            []
        ) or []

        if meals:
            return meals[0]

    except requests.RequestException:

        pass

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
    
    primary_ingredient = None

    primary_ingredients = {
        "chicken",
        "chicken breast",
        "chicken thigh",
        "chicken drumstick",
        "chicken wing",
        "whole chicken",
        "beef",
        "ground beef",
        "beef chuck",
        "beef brisket",
        "beef steak",
        "beef roast",
        "beef stew meat",
        "pork",
        "ground pork",
        "pork chop",
        "pork loin",
        "pork shoulder",
        "pork tenderloin",
        "bacon",
        "ham",
        "lamb",
        "ground lamb",
        "lamb shoulder",
        "lamb leg",
        "lamb chops",
        "turkey",
        "ground turkey",
        "turkey breast",
        "turkey thigh",
        "fish",
        "salmon",
        "cod",
        "haddock",
        "tilapia",
        "tuna",
        "shrimp"
    }

    for ingredient in user_ingredients:
        cleaned = clean_word(ingredient)

        if cleaned in primary_ingredients:
            primary_ingredient = cleaned
            break
    # Find candidate recipes using each ingredient.
    # We use TheMealDB temporarily while RecipeAPI is unavailable.
    candidate_ids = {}

    for ingredient in user_ingredients:

        ingredient = clean_word(ingredient)

        if not ingredient:
            continue

        meals = search_recipe(ingredient)

        for meal in meals:

            meal_id = meal.get("idMeal")

            if meal_id:
                candidate_ids[meal_id] = meal.get(
                    "strMeal",
                    "Recipe"
                )

    if not candidate_ids:
        return []

    scored_recipes = []

    # Get the complete recipe only once for each unique recipe.
    for meal_id, meal_name in candidate_ids.items():

        recipe = get_recipe(meal_id)

        if not recipe:
            continue

        recipe_ingredients = get_recipe_ingredients(recipe)

        if not recipe_ingredients:
            continue

        matched = []
        missing = []

        for item in recipe_ingredients:

            ingredient = item["ingredient"]

            if ingredient_matches(
                ingredient,
                user_ingredients
            ):

                if ingredient_alias(
                    ingredient
                ) not in PANTRY_STAPLES:

                    matched.append(
                        ingredient
                    )

            else:

                normalized_ingredient = ingredient_alias(
                    ingredient
                )

                if normalized_ingredient not in PANTRY_STAPLES:

                    user_normalized = [
                        ingredient_alias(item)
                        for item in user_ingredients
                    ]

                    if normalized_ingredient not in user_normalized:

                        missing.append(
                            ingredient
                        )

        matched = list(
            dict.fromkeys(matched)
        )

        missing = list(
            dict.fromkeys(missing)
        )


        used_count = len(matched)

        if used_count == 0:
            continue

        total = used_count + len(missing)

        match_percentage = int(
            (used_count / total) * 100
        ) if total else 0

        instructions = recipe.get(
            "strInstructions"
        ) or "Instructions unavailable."

        instructions = re.sub(
            r"<[^>]+>",
            "",
            instructions
        )

        instructions = format_instructions(
            instructions
        )

        primary_match = 0

        if primary_ingredient:
            for item in recipe_ingredients:
                if clean_word(item["ingredient"]) == primary_ingredient:
                    primary_match = 1
                    break

        
        scored_recipes.append({

            "name": recipe.get(
                "strMeal",
                meal_name
            ),

            "image": recipe.get(
                "strMealThumb"
            ),

            "ingredients": recipe_ingredients,

            "matched": matched,

            "missing": missing,

            "substitutions": get_substitutions(missing),

            "substitution_notes": get_substitution_notes(missing),

            "used_count": used_count,

            "total_count": total,

            "missing_count": len(missing),

            "match_percentage": match_percentage,

            "primary_match": primary_match,
              
            "instructions": instructions, 
            
            "source": None
        })

    scored_recipes.sort(
        key=lambda x: (
            x["primary_match"],
            x["match_percentage"],
            x["used_count"],
            -len(x["missing"])
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

        .have {
            color: #188038;

        .match-excellent {
            color: #188038;
        }

        .match-good {
            color: #5f8f29;
        }

        .match-fair {
            color: #b06000;
        }

        .match-low {
            color: #c5221f;
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

{% if recipe.match_percentage >= 80 %}

    <p class="match match-excellent">
        🟢 {{ recipe.match_percentage }}% Excellent Match
    </p>

{% elif recipe.match_percentage >= 60 %}

    <p class="match match-good">
        🟢 {{ recipe.match_percentage }}% Great Match
    </p>

{% elif recipe.match_percentage >= 40 %}

    <p class="match match-fair">
        🟡 {{ recipe.match_percentage }}% Good Match
    </p>

{% else %}

    <p class="match match-low">
        🟠 {{ recipe.match_percentage }}% More Ingredients Needed
    </p>

{% endif %}
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
            • {{ ingredient.measure }} {{ ingredient.ingredient }}
        </p>

    {% endfor %}

</div>

                        <h3>Instructions</h3>

                        <div class="instructions">{{ recipe.instructions | safe }}</div>

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
        selected_common=selected_common
    )


# ---------------------------------------------------------
# START APP
# ---------------------------------------------------------

if __name__ == "__main__":

    app.run(
        debug=True
    )
