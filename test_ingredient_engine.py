import ingredient_engine as ie


IDENTITY_CASES = [
    ("all-purpose flour", "flour"),
    ("extra-virgin olive oil", "olive oil"),
    ("freshly chopped garlic", "garlic"),
    ("grated Parmesan cheese", "parmesan cheese"),
    ("diced tomatoes", "tomato"),
    ("large eggs", "egg"),
    ("lean ground beef", "ground beef"),
    ("wild-caught salmon fillets", "salmon"),
    ("peeled and deveined shrimp", "shrimp"),
    ("bone-in, skin-on chicken thighs, trimmed", "chicken thigh"),
    ("garlic powder", "garlic powder"),
    ("red pepper flakes", "red pepper flakes"),
    ("beef chuck", "chuck roast"),
    ("beef chuck roast", "chuck roast"),
    ("chuck roast", "chuck roast"),
    ("beef brisket", "brisket"),
    ("freshly ground black pepper", ""),
    ("salt and pepper", ""),
]


MATCH_CASES = [
    ("flour", ["all-purpose flour"], True),
    ("potato", ["tomato"], False),
    ("tomato", ["potato"], False),
    ("garlic", ["garlic powder"], False),
    ("garlic powder", ["garlic"], False),
    ("mozzarella", ["mozzarella"], True),
    ("mozzarella", ["mozzarella cheese"], True),
    ("mozzarella cheese", ["mozzarella"], True),
    ("ricotta", ["ricotta"], True),
    ("ricotta", ["ricotta cheese"], True),
    ("ricotta", ["mozzarella"], False),
    ("beef chuck", ["chuck roast"], True),
    ("chuck roast", ["beef chuck"], True),
    ("beef chuck roast", ["chuck roast"], True),
    ("beef chuck roast", ["beef brisket"], False),
    ("beef", ["chuck roast"], False),
    ("chuck roast", ["beef"], True),
    ("ground beef", ["beef"], False),
    ("ground beef", ["ground beef"], True),
]


def run():
    for raw, expected in IDENTITY_CASES:
        actual = ie.identify_ingredient(raw)
        assert actual == expected, (
            f"IDENTITY: {raw!r}: expected {expected!r}, got {actual!r}"
        )
        print(f"PASS identity: {raw!r} -> {actual!r}")

    for recipe, pantry, expected in MATCH_CASES:
        actual = ie.ingredients_match(recipe, pantry)
        assert actual == expected, (
            f"MATCH: {recipe!r} vs {pantry!r}: "
            f"expected {expected}, got {actual}"
        )
        print(f"PASS match: {recipe!r} vs {pantry!r} -> {actual}")

    result = ie.match_recipe(
        [
            "ricotta",
            "tomato",
            "garlic",
            "olive oil",
            "salt",
        ],
        ["ricotta", "garlic", "olive oil"],
    )

    assert result["have"] == ["ricotta", "garlic", "olive oil"], result
    assert result["need"] == ["tomato"], result

    result = ie.match_recipe(
        [
            "pasta",
            "tomato",
            "garlic",
            "mozzarella cheese",
        ],
        ["mozzarella", "garlic"],
    )

    assert result["have"] == ["garlic", "mozzarella"], result
    assert result["need"] == ["pasta", "tomato"], result

    print("PASS recipe HAVE/NEED test: ricotta")
    print("PASS recipe HAVE/NEED test: mozzarella")
    print("ALL STANDALONE INGREDIENT ENGINE TESTS PASSED")


if __name__ == "__main__":
    run()
