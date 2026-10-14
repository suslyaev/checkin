import re

# Числовые поля приводятся к числу молча, а не предлагаются к исправлению:
# в Excel-выгрузках тысячи часто разделены пробелом/неразрывным пробелом,
# целые приходят как «1234.0», а отсутствие значения обозначают прочерком.
NUMBER_DASHES = {'-', '–', '—', '−', '--'}
NUMBER_IGNORED_CHARS = re.compile(r"[\s']")
_NUMBER_RE = re.compile(r'^(\d+(?:[.,]\d+)*)(k|к|тыс\.?|m|м|млн\.?)?$', re.IGNORECASE)
_NUMBER_MULTIPLIERS = {'k': 1000, 'к': 1000, 'тыс': 1000, 'm': 1000000, 'м': 1000000, 'млн': 1000000}


def parse_int_like(value):
    """«12 345», «12\u00a0345», «12,345», «1234.0», «1,5к», «2 млн» -> int.
    Пустая строка -> None. Не число -> ValueError. Прочерк здесь не
    обрабатывается — что он означает, решает вызывающий код (0 или пусто)."""
    text = NUMBER_IGNORED_CHARS.sub('', str(value or ''))
    if not text:
        return None
    m = _NUMBER_RE.match(text)
    if not m:
        raise ValueError(value)
    digits, suffix = m.group(1), (m.group(2) or '').lower().rstrip('.')
    separators = re.findall(r'[.,]', digits)
    if separators:
        parts = re.split(r'[.,]', digits)
        if len(separators) == 1 and (suffix or len(parts[1]) != 3):
            # Одиночный разделитель не по три цифры («1,5», «1234.0») или с
            # суффиксом («1,5к») — десятичная дробь.
            number = float('.'.join(parts))
        elif len(set(separators)) == 2:
            # «1,234.5» / «1.234,5» — последний разделитель десятичный.
            number = float(''.join(parts[:-1]) + '.' + parts[-1])
        else:
            # «12,345», «1.234.567» — разделители тысяч.
            if any(len(part) != 3 for part in parts[1:]):
                raise ValueError(value)
            number = float(''.join(parts))
    else:
        number = float(digits)
    return int(round(number * _NUMBER_MULTIPLIERS.get(suffix, 1)))
