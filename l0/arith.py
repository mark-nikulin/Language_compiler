# Арифметика L0: коды бинарных операций и их вычисление.

from .errors import L0Error

# Разрядность целых. None - неограниченные целые Python.
# 63 - как native int в OCaml, 32 - как int32. При переполнении значение "заворачивается".
INT_BITS = None

# Номера операций. Текст операции -> номер ищется по OP_NAMES.
OR, AND, EQ, NE, LE, LT, GE, GT, ADD, SUB, MUL, DIV, MOD = 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12
OP_NAMES = ["!!", "&&", "==", "!=", "<=", "<", ">=", ">", "+", "-", "*", "/", "%"]


def normalize_op(op):
    # Минус может прийти как U+2212 или U+2013 - приводим к обычному "-".
    chars = []
    for c in op:
        if c == "−" or c == "–":
            chars.append("-")
        else:
            chars.append(c)
    return "".join(chars)


def op_code(name):
    # Номер операции по тексту или -1, если такой операции нет.
    i = 0
    while i < len(OP_NAMES):
        if OP_NAMES[i] == name:
            return i
        i += 1
    return -1


def wrap(n):
    if INT_BITS is None:
        return n
    m = 1 << INT_BITS
    n &= m - 1
    return n - m if n >= (m >> 1) else n


def div(a, b):
    # Деление с округлением к нулю, как в OCaml и C. В Python // округляет вниз.
    if b == 0:
        raise L0Error("Division_by_zero")
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def mod(a, b):
    # Остаток со знаком делимого: a = b * div(a, b) + mod(a, b).
    return a - b * div(a, b)


def apply_binop(code, x, y):
    # x - левый операнд, y - правый. Оба уже вычислены: короткого замыкания нет.
    if code == ADD:
        return wrap(x + y)
    elif code == SUB:
        return wrap(x - y)
    elif code == MUL:
        return wrap(x * y)
    elif code == DIV:
        return wrap(div(x, y))
    elif code == MOD:
        return wrap(mod(x, y))
    elif code == LT:
        return 1 if x < y else 0
    elif code == LE:
        return 1 if x <= y else 0
    elif code == GT:
        return 1 if x > y else 0
    elif code == GE:
        return 1 if x >= y else 0
    elif code == EQ:
        return 1 if x == y else 0
    elif code == NE:
        return 1 if x != y else 0
    elif code == AND:
        return 1 if x != 0 and y != 0 else 0
    elif code == OR:
        return 1 if x != 0 or y != 0 else 0
    raise ValueError("unknown binop code %d" % code)
