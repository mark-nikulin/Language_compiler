# Ассемблер: символьный SM-код -> собранная программа с числовыми аргументами.
#   проход 1: метка -> адрес (индекс инструкции LABEL);
#   проход 2: переменная -> номер ячейки, метка -> адрес, текст операции -> её номер.
# Словари здесь - таблицы символов времени сборки. При выполнении их уже нет.

from .arith import op_code
from .errors import AsmError
from .opcodes import Instr, Opcode


class Program:
    def __init__(self, code, names):
        self.code = code  # список Instr с числовыми аргументами
        self.names = names  # номер ячейки -> имя переменной (для текста ошибок)
        self.memory_size = len(names)


def assemble(instrs):
    labels = {}
    addr = 0
    while addr < len(instrs):
        instr = instrs[addr]
        if instr.op == Opcode.LABEL:
            if instr.arg in labels:
                raise AsmError('duplicate label "%s"' % instr.arg)
            labels[instr.arg] = addr  # LABEL остаётся в коде как пустая инструкция
        addr += 1

    slots = {}
    names = []
    code = []
    for instr in instrs:
        op = instr.op
        if op == Opcode.LD or op == Opcode.ST:
            if instr.arg not in slots:
                slots[instr.arg] = len(names)
                names.append(instr.arg)
            code.append(Instr(op, slots[instr.arg]))
        elif op == Opcode.JMP or op == Opcode.JZ or op == Opcode.JNZ:
            if instr.arg not in labels:
                raise AsmError('unknown label "%s"' % instr.arg)
            code.append(Instr(op, labels[instr.arg]))
        elif op == Opcode.BINOP:
            code.append(Instr(op, op_code(instr.arg)))
        elif op == Opcode.LABEL:
            code.append(Instr(op))
        else:
            code.append(Instr(op, instr.arg))
    return Program(code, names)
