from .errors import StackError


class Stack:
    # Стек на массиве. items - память стека, sp - число элементов,
    # то есть индекс первой свободной ячейки.

    def __init__(self, name="stack"):
        self.items = []
        self.sp = 0
        self.name = name

    def push(self, value):
        if self.sp == len(self.items):
            self.items.append(value)
        else:
            self.items[self.sp] = value
        self.sp += 1

    def pop(self):
        if self.sp == 0:
            raise StackError("pop from empty " + self.name)
        self.sp -= 1
        value = self.items[self.sp]
        self.items[self.sp] = None  # не держим ссылку на снятый элемент
        return value

    def peek(self):
        if self.sp == 0:
            raise StackError("peek into empty " + self.name)
        return self.items[self.sp - 1]

    def is_empty(self):
        return self.sp == 0

    def size(self):
        return self.sp
