# Выражения

class Const:
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class Var:
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name


class BinOp:
    # op - текст операции ("+"), code - её номер из arith.py
    __slots__ = ("op", "code", "left", "right")

    def __init__(self, op, code, left, right):
        self.op = op
        self.code = code
        self.left = left
        self.right = right


class ArrayLit:
    __slots__ = ("items",)

    def __init__(self, items):
        self.items = items


class Elem:
    __slots__ = ("array", "index")

    def __init__(self, array, index):
        self.array = array
        self.index = index


class Length:
    __slots__ = ("array",)

    def __init__(self, array):
        self.array = array


class StrLit:
    __slots__ = ("text",)

    def __init__(self, text):
        self.text = text


# Операторы

class Skip:
    __slots__ = ()


class Read:
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name


class Write:
    __slots__ = ("expr",)

    def __init__(self, expr):
        self.expr = expr


class Assign:
    __slots__ = ("name", "expr")

    def __init__(self, name, expr):
        self.name = name
        self.expr = expr


class Seq:
    __slots__ = ("first", "second")

    def __init__(self, first, second):
        self.first = first
        self.second = second


class If:
    __slots__ = ("cond", "then", "else_")

    def __init__(self, cond, then, else_):
        self.cond = cond
        self.then = then
        self.else_ = else_


class SetElem:
    # dst[index] = value
    __slots__ = ("dst", "index", "value")

    def __init__(self, dst, index, value):
        self.dst = dst
        self.index = index
        self.value = value


class While:
    __slots__ = ("cond", "body")

    def __init__(self, cond, body):
        self.cond = cond
        self.body = body


class DoWhile:
    __slots__ = ("body", "cond")

    def __init__(self, body, cond):
        self.body = body
        self.cond = cond
