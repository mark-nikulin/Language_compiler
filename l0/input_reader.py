
from .errors import L0Error, where

MIN_INT = -(1 << 62)
MAX_INT = (1 << 62) - 1


def is_digit(c):
    return "0" <= c <= "9"


def is_space(c):
    return c == " " or c == "\t" or c == "\r" or c == "\n"


class InputQueue:
    def __init__(self, values):
        self.values = values
        self.next_index = 0

    def read(self):
        if self.next_index >= len(self.values):
            raise L0Error("ERROR: input exhausted")
        value = self.values[self.next_index]
        self.next_index += 1
        return value


def parse_input(text):
    if text.strip() == "":
        raise L0Error("ERROR: input not specified")
    n = len(text)
    values = []
    i = 0
    while i < n and is_space(text[i]):
        i += 1
    while True:
        start = i
        negative = False
        if i < n and text[i] == "-":
            negative = True
            i += 1
        if i >= n or not is_digit(text[i]):
            raise L0Error('ERROR: "[" expected at ' + where(text, start))
        value = 0
        while i < n and is_digit(text[i]):
            value = value * 10 + (ord(text[i]) - ord("0"))
            i += 1
        value = -value if negative else value
        if value < MIN_INT or value > MAX_INT:
            raise L0Error('Failure("int_of_string")')
        values.append(value)

        while i < n and is_space(text[i]):
            i += 1
        if i < n and text[i] == ",":
            i += 1
            while i < n and is_space(text[i]):
                i += 1
            continue
        break
    if i < n:
        raise L0Error("ERROR: <EOF> expected at " + where(text, i))
    return InputQueue(values)
