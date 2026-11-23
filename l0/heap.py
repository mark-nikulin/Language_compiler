
from .arith import CONS, EQ, GE, GT, LE, LT, NE, apply_binop
from .errors import L0Error

INT, STR, ARR, SEXP = 0, 1, 2, 3


class Sexp:
    __slots__ = ("tag", "items")

    def __init__(self, tag, items):
        self.tag = tag
        self.items = list(items)


class Ptr:
    __slots__ = ("addr",)

    def __init__(self, addr):
        self.addr = addr


def is_ptr(value):
    return isinstance(value, Ptr)


class Heap:
    def __init__(self):
        self.boxes = []

    def alloc(self, box):
        self.boxes.append(box)
        return Ptr(len(self.boxes) - 1)

    def new_string(self, data):
        return self.alloc(bytearray(data))

    def new_array(self, items):
        return self.alloc(list(items))

    def new_sexp(self, tag, items):
        return self.alloc(Sexp(tag, items))

    def kind(self, value):
        if not is_ptr(value):
            return INT
        box = self.boxes[value.addr]
        if isinstance(box, bytearray):
            return STR
        return SEXP if isinstance(box, Sexp) else ARR

    def as_int(self, value):
        if is_ptr(value):
            raise L0Error('ERROR: integer value expected but "%s" given' % self.show(value))
        return value

    def need_box(self, value, wording):
        if not is_ptr(value):
            raise L0Error('ERROR: array/string value expected but "%s" %s' % (self.show(value), wording))
        box = self.boxes[value.addr]
        return box.items if isinstance(box, Sexp) else box

    def check_index(self, index, size):
        if index < 0 or index >= size:
            raise L0Error("ERROR: index %d is out of bounds [0, %d)" % (index, size))

    def elem(self, array, index):
        box = self.need_box(array, "given")
        index = self.as_int(index)
        self.check_index(index, len(box))
        return box[index]

    def set_elem(self, array, index, value):
        box = self.need_box(array, "is given")
        index = self.as_int(index)
        self.check_index(index, len(box))
        if isinstance(box, bytearray):
            value = self.as_int(value)
            if value < 0 or value > 255:
                raise L0Error('Invalid_argument("Char.chr")')
        box[index] = value

    def length(self, array):
        return len(self.need_box(array, "given"))

    def printable(self, value):
        return self.show(value) if is_ptr(value) else value

    def show(self, value):
        out = []
        todo = [("value", value)]
        active = set()
        while todo:
            action, item = todo.pop()
            if action == "text":
                out.append(item)
            elif action == "leave":
                active.remove(item)
            elif not is_ptr(item):
                out.append(str(item))
            elif item.addr in active:
                out.append("<cycle>")
            else:
                box = self.boxes[item.addr]
                if isinstance(box, bytearray):
                    out.append(bytes(box).decode("utf-8", errors="replace"))
                    continue
                active.add(item.addr)
                todo.append(("leave", item.addr))
                if isinstance(box, Sexp):
                    chain = []
                    seen = set(active)
                    cursor = item
                    while is_ptr(cursor):
                        part = self.boxes[cursor.addr]
                        if not isinstance(part, Sexp):
                            break
                        if part.tag == "nil" and not part.items:
                            break
                        if part.tag != "cons" or len(part.items) != 2:
                            break
                        chain.append(part.items[0])
                        cursor = part.items[1]
                        if is_ptr(cursor) and cursor.addr in seen:
                            break
                        if is_ptr(cursor):
                            seen.add(cursor.addr)
                    part = self.boxes[cursor.addr] if is_ptr(cursor) else None
                    proper = isinstance(part, Sexp) and part.tag == "nil" and not part.items
                    if proper:
                        out.append("{")
                        todo.append(("text", "}"))
                        for i in range(len(chain) - 1, -1, -1):
                            todo.append(("value", chain[i]))
                            if i:
                                todo.append(("text", ", "))
                    else:
                        out.append(box.tag)
                        if box.items:
                            out.append("(")
                            todo.append(("text", ")"))
                            for i in range(len(box.items) - 1, -1, -1):
                                todo.append(("value", box.items[i]))
                                if i:
                                    todo.append(("text", ", "))
                else:
                    out.append("[")
                    todo.append(("text", "]"))
                    for i in range(len(box) - 1, -1, -1):
                        todo.append(("value", box[i]))
                        if i:
                            todo.append(("text", "; "))
        return "".join(out)

    def compare(self, x, y):
        todo = [(x, y)]
        seen = set()
        while todo:
            a, b = todo.pop()
            ka, kb = self.kind(a), self.kind(b)
            if ka != kb:
                return -1 if ka < kb else 1
            if ka == INT:
                if a != b:
                    return -1 if a < b else 1
                continue
            pair = (a.addr, b.addr)
            if pair in seen:
                continue
            seen.add(pair)
            a, b = self.boxes[a.addr], self.boxes[b.addr]
            if ka == STR:
                if a != b:
                    return -1 if a < b else 1
                continue
            if ka == SEXP:
                if a.tag != b.tag:
                    return -1 if a.tag < b.tag else 1
                a, b = a.items, b.items
            todo.append((len(a), len(b)))
            for i in range(min(len(a), len(b)) - 1, -1, -1):
                todo.append((a[i], b[i]))
        return 0

    def equal(self, x, y):
        return self.compare(x, y) == 0

    def binop(self, code, x, y):
        if code == CONS:
            return self.new_sexp("cons", [x, y])
        if code in (EQ, NE, LT, LE, GT, GE):
            order = self.compare(x, y)
            return int((order == 0 if code == EQ else
                        order != 0 if code == NE else
                        order < 0 if code == LT else
                        order <= 0 if code == LE else
                        order > 0 if code == GT else order >= 0))
        if not is_ptr(x) and not is_ptr(y):
            return apply_binop(code, x, y)
        self.as_int(y)
        self.as_int(x)
