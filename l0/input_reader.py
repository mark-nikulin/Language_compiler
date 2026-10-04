# Разбор поля Input: число ("," число)*, вокруг запятых любые пробельные символы.
# Число - необязательный "-" и десятичные цифры. Минимум одно число.

from .errors import L0Error, where


def is_digit(c):
    return "0" <= c <= "9"


def is_space(c):
    return c == " " or c == "\t" or c == "\r" or c == "\n"


class InputQueue:
    # Очередь чисел ввода: массив и индекс следующего непрочитанного.
    def __init__(self, values):
        self.values = values
        self.next_index = 0

    def read(self):
        if self.next_index >= len(self.values):
            raise L0Error("L0.Stmt.No_input")
        value = self.values[self.next_index]
        self.next_index += 1
        return value


def parse_input(text):
    n = len(text)
    values = []
    i = 0
    while i < n and is_space(text[i]):
        i += 1
    while True:
        # Число: [-] цифры
        start = i
        negative = False
        if i < n and text[i] == "-":
            negative = True
            i += 1
        if i >= n or not is_digit(text[i]):
            raise L0Error('Input error: "decimal constant" expected at ' + where(text, start))
        value = 0
        while i < n and is_digit(text[i]):
            value = value * 10 + (ord(text[i]) - ord("0"))
            i += 1
        values.append(-value if negative else value)

        while i < n and is_space(text[i]):
            i += 1
        if i < n and text[i] == ",":
            i += 1
            while i < n and is_space(text[i]):
                i += 1
            continue
        break
    if i < n:
        raise L0Error("Input error: <EOF> expected at " + where(text, i))
    return InputQueue(values)
