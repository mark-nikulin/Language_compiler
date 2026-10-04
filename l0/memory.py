# Память переменных: массив значений и параллельный массив флагов "инициализирована".
# Ячейка адресуется номером. Имена нужны только для текста ошибки.

from .errors import L0Error


class Memory:
    def __init__(self, names):
        self.names = list(names)  # номер ячейки -> имя переменной
        self.values = [0] * len(names)
        self.defined = [False] * len(names)

    def load(self, slot):
        if not self.defined[slot]:
            raise L0Error('L0.State.Undefined_variable("%s")' % self.names[slot])
        return self.values[slot]

    def store(self, slot, value):
        self.values[slot] = value
        self.defined[slot] = True

    def slot_of(self, name):
        # Номер ячейки по имени линейным поиском; новое имя получает новую ячейку.
        # Нужно только AST-интерпретатору: в SM номера раздаёт ассемблер.
        i = 0
        while i < len(self.names):
            if self.names[i] == name:
                return i
            i += 1
        self.names.append(name)
        self.values.append(0)
        self.defined.append(False)
        return i
