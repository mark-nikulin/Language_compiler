# Узлы AST языка L0.


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
