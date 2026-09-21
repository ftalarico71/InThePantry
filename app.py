import difflib

import difflib

def safe_fuzzy_correct(term):
    if not term or not isinstance(term, str):
        return term
    clean = term.strip().lower()
    known = [
        'parsley', 'garlic', 'onion', 'ground beef', 'cheddar cheese',
        'butter', 'milk', 'tomato', 'bell pepper', 'flour', 'rice',
        'olive oil', 'vegetable oil', 'carrot', 'celery', 'oregano',
        'thyme', 'basil', 'tomato paste', 'vegetable stock', 'barley',
        'chicken', 'pork', 'turkey', 'pepper', 'salt', 'spinach',
        'potato', 'potatoes', 'sweet potato', 'sweet potatoes',
        'lemon', 'lime', 'cheese', 'egg', 'eggs', 'bacon', 'heavy cream',
        'mozzarella', 'mozzarella cheese', 'parmesan', 'parmesan cheese',
        'ricotta', 'cream cheese', 'monterey jack', 'swiss cheese'
    ]
    matches = difflib.get_close_matches(clean, known, n=1, cutoff=0.50)
    return matches[0] if matches else clean

