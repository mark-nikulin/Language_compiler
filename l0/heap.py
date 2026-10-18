# Куча L0: значение - целое или указатель Ptr на коробку (строку или массив).
#   строка  - bytearray, элементы - байты (числа 0..255);
#   массив  - список значений (целые и указатели).
# Копирование указателя не копирует содержимое: переменные могут делить один массив.

from .arith import EQ, GE, GT, LE, LT, NE, apply_binop
from .errors import L0Error

INT, STR, ARR = 0, 1, 2


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

    def kind(self, value):
        if not is_ptr(value):
            return INT
        return STR if isinstance(self.boxes[value.addr], bytearray) else ARR

    def as_int(self, value):
        if is_ptr(value):
            raise L0Error('ERROR: integer value expected but "%s" given' % self.show(value))
        return value

    def need_box(self, value, wording):
        if not is_ptr(value):
            raise L0Error('ERROR: array/string value expected but "%s" %s' % (self.show(value), wording))
        return self.boxes[value.addr]

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
        # Что попадает в Output: число как есть, остальное - готовым текстом.
        return self.show(value) if is_ptr(value) else value

    def show(self, value):
        # Текст значения: [1; x; [2]]. Строки без кавычек. Вложенность - стеком, без рекурсии.
        out = []
        todo = []
        todo.append((True, value))
        while todo:
            is_value, item = todo.pop()
            if not is_value:
                out.append(item)
            elif not is_ptr(item):
                out.append(str(item))
            else:
                box = self.boxes[item.addr]
                if isinstance(box, bytearray):
                    out.append(bytes(box).decode("utf-8", errors="replace"))
                else:
                    out.append("[")
                    todo.append((False, "]"))
                    i = len(box) - 1
                    while i >= 0:
                        todo.append((True, box[i]))
                        if i > 0:
                            todo.append((False, "; "))
                        i -= 1
        return "".join(out)

    def equal(self, x, y):
        # Сравнение по содержимому. Вложенные значения разного вида не равны.
        pairs = []
        pairs.append((x, y))
        while pairs:
            a, b = pairs.pop()
            if is_ptr(a) != is_ptr(b):
                return False
            if not is_ptr(a):
                if a != b:
                    return False
                continue
            box_a = self.boxes[a.addr]
            box_b = self.boxes[b.addr]
            if type(box_a) is not type(box_b) or len(box_a) != len(box_b):
                return False
            if isinstance(box_a, bytearray):
                if box_a != box_b:
                    return False
            else:
                i = 0
                while i < len(box_a):
                    pairs.append((box_a[i], box_b[i]))
                    i += 1
        return True

    def binop(self, code, x, y):
        if not is_ptr(x) and not is_ptr(y):
            return apply_binop(code, x, y)
        if code == EQ or code == NE:
            if self.kind(x) != self.kind(y):
                name = "=" if code == EQ else "<>"
                raise L0Error('ERROR: binary operator "%s" is applied to %s and %s'
                              % (name, self.show(x), self.show(y)))
            same = self.equal(x, y)
            return 1 if same == (code == EQ) else 0
        if (code == LT or code == LE or code == GT or code == GE) \
                and self.kind(x) == STR and self.kind(y) == STR:
            a = bytes(self.boxes[x.addr])
            b = bytes(self.boxes[y.addr])
            if code == LT:
                return 1 if a < b else 0
            if code == LE:
                return 1 if a <= b else 0
            if code == GT:
                return 1 if a > b else 0
            return 1 if a >= b else 0
        # Правый операнд проверяется первым.
        self.as_int(y)
        self.as_int(x)
