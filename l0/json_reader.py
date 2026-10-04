# Разбор JSON без рекурсии.
# Открытые, ещё не закрытые объекты и массивы лежат на явном стеке.
# Числа поддерживаются только целые: в AST языка L0 других нет.

from .errors import JsonError, where
from .stack import Stack


def is_digit(c):
    return len(c) == 1 and "0" <= c <= "9"


def is_space(c):
    return c == " " or c == "\t" or c == "\r" or c == "\n"


def hex_value(c):
    if "0" <= c <= "9":
        return ord(c) - ord("0")
    if "a" <= c <= "f":
        return ord(c) - ord("a") + 10
    if "A" <= c <= "F":
        return ord(c) - ord("A") + 10
    return -1


class Frame:
    # Открытый контейнер: сам объект или массив и ключ, под который ляжет следующее значение.
    __slots__ = ("value", "is_object", "key")

    def __init__(self, value, is_object):
        self.value = value
        self.is_object = is_object
        self.key = None


class Reader:
    def __init__(self, text):
        self.text = text
        self.pos = 0

    def error(self, what):
        raise JsonError("JSON: %s at %s" % (what, where(self.text, self.pos)))

    def peek(self):
        # Текущий символ или "" в конце текста.
        if self.pos < len(self.text):
            return self.text[self.pos]
        return ""

    def skip_spaces(self):
        while self.pos < len(self.text) and is_space(self.text[self.pos]):
            self.pos += 1

    def expect(self, c):
        if self.peek() != c:
            self.error("'%s' expected" % c)
        self.pos += 1

    def read_string(self):
        self.expect('"')
        chars = []
        while True:
            c = self.peek()
            if c == "":
                self.error("unterminated string")
            self.pos += 1
            if c == '"':
                return "".join(chars)
            if c != "\\":
                chars.append(c)
                continue
            e = self.peek()
            self.pos += 1
            if e == '"' or e == "\\" or e == "/":
                chars.append(e)
            elif e == "n":
                chars.append("\n")
            elif e == "t":
                chars.append("\t")
            elif e == "r":
                chars.append("\r")
            elif e == "b":
                chars.append("\b")
            elif e == "f":
                chars.append("\f")
            elif e == "u":
                code = 0
                k = 0
                while k < 4:
                    h = hex_value(self.peek())
                    if h < 0:
                        self.error("bad \\u escape")
                    code = code * 16 + h
                    self.pos += 1
                    k += 1
                chars.append(chr(code))
            else:
                self.pos -= 1
                self.error("bad escape")

    def read_int(self):
        negative = False
        if self.peek() == "-":
            negative = True
            self.pos += 1
        if not is_digit(self.peek()):
            self.error("digit expected")
        value = 0
        while is_digit(self.peek()):
            value = value * 10 + (ord(self.peek()) - ord("0"))
            self.pos += 1
        c = self.peek()
        if c == "." or c == "e" or c == "E":
            self.error("only integer numbers are supported")
        return -value if negative else value

    def read_key(self):
        # Ключ объекта вместе с двоеточием: "key" :
        if self.peek() != '"':
            self.error("object key expected")
        key = self.read_string()
        self.skip_spaces()
        self.expect(":")
        self.skip_spaces()
        return key

    def read_word(self, word):
        if self.text.startswith(word, self.pos):
            self.pos += len(word)
            return True
        return False


def parse_json(text):
    r = Reader(text)
    open_frames = Stack("JSON stack")
    r.skip_spaces()
    while True:
        # Шаг 1: начать очередное значение.
        # Контейнер кладём на стек и сразу идём читать его первый элемент.
        c = r.peek()
        if c == "{":
            r.pos += 1
            r.skip_spaces()
            if r.peek() == "}":
                r.pos += 1
                value = {}
            else:
                frame = Frame({}, True)
                frame.key = r.read_key()
                open_frames.push(frame)
                continue
        elif c == "[":
            r.pos += 1
            r.skip_spaces()
            if r.peek() == "]":
                r.pos += 1
                value = []
            else:
                open_frames.push(Frame([], False))
                continue
        elif c == '"':
            value = r.read_string()
        elif c == "-" or is_digit(c):
            value = r.read_int()
        elif r.read_word("true"):
            value = True
        elif r.read_word("false"):
            value = False
        elif r.read_word("null"):
            value = None
        else:
            r.error("value expected")

        # Шаг 2: значение готово. Кладём его в родителя и закрываем
        # все контейнеры, которые на этом закончились.
        while True:
            if open_frames.is_empty():
                r.skip_spaces()
                if r.pos != len(text):
                    r.error("end of input expected")
                return value
            frame = open_frames.peek()
            if frame.is_object:
                frame.value[frame.key] = value
            else:
                frame.value.append(value)
            r.skip_spaces()
            c = r.peek()
            if c == ",":
                r.pos += 1
                r.skip_spaces()
                if frame.is_object:
                    frame.key = r.read_key()
                break  # читаем следующий элемент того же контейнера
            closer = "}" if frame.is_object else "]"
            if c != closer:
                r.error("',' or '%s' expected" % closer)
            r.pos += 1
            open_frames.pop()
            value = frame.value  # закрытый контейнер сам стал готовым значением
