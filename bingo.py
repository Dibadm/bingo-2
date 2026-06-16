import random
import itertools
from typing import List, Tuple, Set

CARD_COLS = 5
CARD_ROWS = 5
NUMBERS_PER_COL = 5


def generate_card() -> List[int]:
    cols_ranges = [(1, 15), (16, 30), (31, 45), (46, 60), (61, 75)]
    card = []
    for lo, hi in cols_ranges:
        col = random.sample(range(lo, hi + 1), NUMBERS_PER_COL)
        card.extend(col)
    return card


def generate_cards(count: int, exclude: Set[int] = None) -> List[List[int]]:
    exclude = exclude or set()
    cards = []
    seen = set()
    limit = 0
    while len(cards) < count and limit < count * 50:
        limit += 1
        candidate = tuple(generate_card())
        if candidate not in seen and candidate not in exclude:
            seen.add(candidate)
            cards.append(list(candidate))
    return cards


def get_card_grid(card: List[int]) -> List[List[int]]:
    grid = []
    for r in range(CARD_ROWS):
        row = []
        for c in range(CARD_COLS):
            row.append(card[c * CARD_ROWS + r])
        grid.append(row)
    return grid


def get_column(card: List[int], col: int) -> List[int]:
    start = col * CARD_ROWS
    return card[start:start + CARD_ROWS]


def check_line(card: List[int], called: Set[int]) -> Tuple[bool, List[int]]:
    grid = get_card_grid(card)
    for r in range(CARD_ROWS):
        if all(n in called for n in grid[r]):
            return True, grid[r]
    for c in range(CARD_COLS):
        col = get_column(card, c)
        if all(n in called for n in col):
            return True, col
    diag1 = [grid[i][i] for i in range(CARD_ROWS)]
    if all(n in called for n in diag1):
        return True, diag1
    diag2 = [grid[i][CARD_COLS - 1 - i] for i in range(CARD_ROWS)]
    if all(n in called for n in diag2):
        return True, diag2
    return False, []


def check_corners(card: List[int], called: Set[int]) -> bool:
    grid = get_card_grid(card)
    corners = [grid[0][0], grid[0][CARD_COLS - 1], grid[CARD_ROWS - 1][0], grid[CARD_ROWS - 1][CARD_COLS - 1]]
    return all(n in called for n in corners)


def check_card_wins(card: List[int], called: Set[int]) -> Tuple[bool, bool]:
    has_line, _ = check_line(card, called)
    has_corners = check_corners(card, called)
    return has_line, has_corners


def check_all_cards_winners(
    user_cards: List[List[int]], called: Set[int]
) -> List[Tuple[int, bool, bool]]:
    results = []
    for idx, card in enumerate(user_cards):
        hl, hc = check_card_wins(card, called)
        results.append((idx, hl, hc))
    return results


# Amharic number words
AMHARIC_NUMBERS = {
    0: "ዜሮ",
    1: "አንድ",
    2: "ሁለት",
    3: "ሦስት",
    4: "አራት",
    5: "አምስት",
    6: "ስድስት",
    7: "ሰባት",
    8: "ስምንት",
    9: "ዘጠኝ",
    10: "አስር",
    11: "አስራ አንድ",
    12: "አስራ ሁለት",
    13: "አስራ ሦስት",
    14: "አስራ አራት",
    15: "አስራ አምስት",
    16: "አስራ ስድስት",
    17: "አስራ ሰባት",
    18: "አስራ ስምንት",
    19: "አስራ ዘጠኝ",
    20: "ሃያ",
    21: "ሃያ አንድ",
    22: "ሃያ ሁለት",
    23: "ሃያ ሦስት",
    24: "ሃያ አራት",
    25: "ሃያ አምስት",
    26: "ሃያ ስድስት",
    27: "ሃያ ሰባት",
    28: "ሃያ ስምንት",
    29: "ሃያ ዘጠኝ",
    30: "ሠላሳ",
    31: "ሠላሳ አንድ",
    32: "ሠላሳ ሁለት",
    33: "ሠላሳ ሦስት",
    34: "ሠላሳ አራት",
    35: "ሠላሳ አምስት",
    36: "ሠላሳ ስድስት",
    37: "ሠላሳ ሰባት",
    38: "ሠላሳ ስምንት",
    39: "ሠላሳ ዘጠኝ",
    40: "አርባ",
    41: "አርባ አንድ",
    42: "አርባ ሁለት",
    43: "አርባ ሦስት",
    44: "አርባ አራት",
    45: "አርባ አምስት",
    46: "አርባ ስድስት",
    47: "አርባ ሰባት",
    48: "አርባ ስምንት",
    49: "አርባ ዘጠኝ",
    50: "ሃምሳ",
    51: "ሃምሳ አንድ",
    52: "ሃምሳ ሁለት",
    53: "ሃምሳ ሦስት",
    54: "ሃምሳ አራት",
    55: "ሃምሳ አምስት",
    56: "ሃምሳ ስድስት",
    57: "ሃምሳ ሰባት",
    58: "ሃምሳ ስምንት",
    59: "ሃምሳ ዘጠኝ",
    60: "ስልሳ",
    61: "ስልሳ አንድ",
    62: "ስልሳ ሁለት",
    63: "ስልሳ ሦስት",
    64: "ስልሳ አራት",
    65: "ስልሳ አምስት",
    66: "ስልሳ ስድስት",
    67: "ስልሳ ሰባት",
    68: "ስልሳ ስምንት",
    69: "ስልሳ ዘጠኝ",
    70: "ሰባ",
    71: "ሰባ አንድ",
    72: "ሰባ ሁለት",
    73: "ሰባ ሦስት",
    74: "ሰባ አራት",
    75: "ሰባ አምስት",
}


def number_to_amharic(n: int) -> str:
    return AMHARIC_NUMBERS.get(n, str(n))


def generate_number_pool() -> List[int]:
    pool = list(range(1, 76))
    random.shuffle(pool)
    return pool


def render_html_card(card: List[int], called: Set[int], marked: Set[int] = None) -> str:
    marked = marked or set()
    grid = get_card_grid(card)
    rows_html = ""
    for r in range(CARD_ROWS):
        cells = ""
        for c in range(CARD_COLS):
            n = grid[r][c]
            is_called = n in called
            is_marked = n in marked
            bg = ""
            if is_marked:
                bg = ' style="background:#4CAF50;color:#fff"'
            elif is_called:
                bg = ' style="background:#FFD700;color:#000"'
            cells += f'<td{bg}>{n}</td>'
        rows_html += f"<tr>{cells}</tr>"

    return f"""<table style="border-collapse:collapse;font-family:monospace;font-size:14px;margin:4px auto;width:200px">
{rows_html}
</table>"""


def render_number_grid(called: Set[int], max_n: int = 75) -> str:
    cells = ""
    for n in range(1, max_n + 1):
        bg = ' style="background:#4CAF50;color:#fff"' if n in called else ' style="background:#333;color:#aaa"'
        cells += f'<td{bg}>{n}</td>'
        if n % 15 == 0 and n < max_n:
            cells += "</tr><tr>"
    return f"""<table style="border-collapse:collapse;font-family:monospace;font-size:11px;margin:4px auto">
<tr>{cells}</tr></table>"""
