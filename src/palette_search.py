"""Pure search ranking for the CreatorStudios desktop command palette.

A command is a mapping with title, description, and optional keywords.
Keeping filtering independent of Qt lets it be tested without a GUI.
"""


def match_commands(commands, query):
    """Return matching commands in a predictable, relevance-first order."""
    terms = query.casefold().split()
    if not terms:
        return list(commands)

    phrase = " ".join(terms)
    matches = []
    for index, command in enumerate(commands):
        title = command["title"].casefold()
        details = command.get("description", "").casefold()
        keywords = command.get("keywords", "").casefold()
        haystack = " ".join((title, details, keywords))
        if not all(term in haystack for term in terms):
            continue
        if title.startswith(phrase):
            rank = 0
        elif any(word.startswith(phrase) for word in title.split()):
            rank = 1
        elif phrase in title:
            rank = 2
        else:
            rank = 3
        matches.append((rank, index, command))

    return [command for _, _, command in sorted(matches, key=lambda item: item[:2])]
