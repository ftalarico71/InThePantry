import app


def test_normalize_recipe_ingredient():
    cases = {
        "a salt": "",
        "a pinch of salt": "",
        "pinch of salt": "",
        "a pepper": "",
        "a pinch of black pepper": "",
        "ground pepper": "",
        "ground black pepper": "",
        "boneless chicken": "chicken",
        "a boneless chicken breast": "chicken breast",
        "bone-in chicken": "chicken",
        "a bone-in chicken breast": "chicken breast",
        "fresh garlic": "garlic",
        "a fresh garlic clove": "garlic",
        "the chicken": "chicken",
        "some salt": "",
        "each chicken breast": "chicken breast",
    }

    for raw, expected in cases.items():
        actual, _ = app.normalize_recipe_ingredient(raw)
        assert actual == expected, f"{raw!r}: expected {expected!r}, got {actual!r}"


def test_ingredient_matching():
    cases = [
        ("salt", ["salt"], True),
        ("salt", ["kosher salt"], False),
        ("kosher salt", ["salt"], True),
        ("kosher salt", ["kosher salt"], True),
        ("pepper", ["pepper"], True),
        ("pepper", ["black pepper"], False),
        ("black pepper", ["pepper"], True),
        ("black pepper", ["black pepper"], True),
        ("ground pepper", ["pepper"], True),
        ("boneless chicken breast", ["chicken"], True),
        ("boneless chicken breast", ["boneless chicken breast"], True),
        ("ground chicken", ["chicken"], False),
        ("ground chicken", ["ground chicken"], True),
        ("bone-in chicken breast", ["chicken"], True),
        ("bone-in chicken breast", ["bone-in chicken breast"], True),
        ("bell pepper", ["red bell pepper"], True),
        ("red bell pepper", ["bell pepper"], True),
    ]

    for recipe, pantry, expected in cases:
        actual = app.ingredient_matches(recipe, pantry)
        assert actual == expected, (
            f"{recipe!r} vs {pantry!r}: "
            f"expected {expected}, got {actual}"
        )


def test_recipe_scoring_excludes_salt_and_pepper():
    cases = [
        (
            {"name": "Test", "ingredients": [
                "chicken",
                "a pinch of salt",
                "a pinch of black pepper",
            ]},
            ["chicken"],
            100,
            ["chicken"],
            [],
        ),
        (
            {"name": "Test", "ingredients": [
                "chicken",
                "ground pepper",
                "salt",
            ]},
            ["chicken"],
            100,
            ["chicken"],
            [],
        ),
        (
            {"name": "Test", "ingredients": [
                "chicken",
                "salt and pepper",
            ]},
            ["chicken"],
            100,
            ["chicken"],
            [],
        ),
        (
            {"name": "Test", "ingredients": [
                "chicken",
                "kosher salt",
                "black pepper",
            ]},
            ["chicken"],
            100,
            ["chicken"],
            [],
        ),
    ]

    for recipe, pantry, expected_percent, expected_have, expected_missing in cases:
        result = app.match_recipe_to_pantry(recipe, pantry)

        assert result["match_percent"] == expected_percent
        assert [x["ingredient"] for x in result["have"]] == expected_have
        assert [x["ingredient"] for x in result["missing"]] == expected_missing


def test_real_ingredients_are_not_removed_as_staples():
    cases = [
        (
            {"name": "Test", "ingredients": [
                "boneless chicken breast",
                "a pinch of salt",
            ]},
            ["boneless chicken breast"],
            ["chicken breast"],
        ),
        (
            {"name": "Test", "ingredients": [
                "ground chicken",
                "salt and pepper",
            ]},
            ["ground chicken"],
            ["ground chicken"],
        ),
    ]

    for recipe, pantry, expected_have in cases:
        result = app.match_recipe_to_pantry(recipe, pantry)
        assert [x["ingredient"] for x in result["have"]] == expected_have
        assert result["missing"] == []


def test_find_recipes_pipeline():
    recipes = [
        {
            "name": "Chicken Breast",
            "url": "https://example.com/chicken",
            "ingredients": [
                "boneless chicken breast",
                "a pinch of salt",
                "black pepper",
            ],
            "instructions": ["Cook chicken."],
            "image": None,
        },
        {
            "name": "Chicken with Onion",
            "url": "https://example.com/onion",
            "ingredients": [
                "chicken",
                "onion",
            ],
            "instructions": ["Cook chicken and onion."],
            "image": None,
        },
        {
            "name": "Rice",
            "url": "https://example.com/rice",
            "ingredients": [
                "rice",
            ],
            "instructions": ["Cook rice."],
            "image": None,
        },
    ]

    original_search = app.search_web_recipes
    try:
        app.search_web_recipes = lambda *args, **kwargs: recipes
        results = app.find_recipes(["boneless chicken breast"])
    finally:
        app.search_web_recipes = original_search

    assert len(results) == 1
    assert results[0]["name"] == "Chicken Breast"
    assert results[0]["match_percentage"] == 100
    assert results[0]["matched"] == ["chicken breast"]
    assert results[0]["missing"] == []
    assert results[0]["used_count"] == 1
    assert results[0]["total_count"] == 1



if __name__ == "__main__":
    test_normalize_recipe_ingredient()
    test_ingredient_matching()
    test_recipe_scoring_excludes_salt_and_pepper()
    test_real_ingredients_are_not_removed_as_staples()
    test_find_recipes_pipeline()
    print("ALL MATCHING REGRESSION TESTS PASSED")
