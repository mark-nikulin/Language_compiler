# Инструкции стековой машины, их печать и разбор текстового SM-кода.

from .arith import op_code
from .errors import SmError, where


class Opcode:
    READ = 0
    WRITE = 1
    LD = 2
    ST = 3
    CONST = 4
    BINOP = 5
    LABEL = 6
    JMP = 7
    JZ = 8
    JNZ = 9

    NAMES = ["READ", "WRITE", "LD", "ST", "CONST", "BINOP", "LABEL", "JMP", "JZ", "JNZ"]


def has_arg(op):
    return op != Opcode.READ and op != Opcode.WRITE


def opcode_by_name(name):
    i = 0
    while i < len(Opcode.NAMES):
        if Opcode.NAMES[i] == name:
            return i
        i += 1
    return -1


class Instr:
    # До ассемблера arg - имя переменной, метка, число или текст операции.
    # После ассемблера arg - номер ячейки, адрес или номер операции;
    # у CONST число не меняется, у LABEL arg становится None.
    __slots__ = ("op", "arg")

    def __init__(self, op, arg=None):
        self.op = op
        self.arg = arg

    def __eq__(self, other):
        return isinstance(other, Instr) and self.op == other.op and self.arg == other.arg

    def __repr__(self):
        return format_instr(self)


def format_instr(instr):
    name = Opcode.NAMES[instr.op]
    if has_arg(instr.op):
        return "%s %s" % (name, instr.arg)
    return name


def format_program(instrs):
    lines = []
    for instr in instrs:
        lines.append(format_instr(instr))
    return "\n".join(lines)


def parse_int(word):
    # Целое из строки: [-] цифры. None, если это не число.
    i = 0
    negative = False
    if i < len(word) and word[i] == "-":
        negative = True
        i += 1
    if i >= len(word):
        return None
    value = 0
    while i < len(word):
        c = word[i]
        if not ("0" <= c <= "9"):
            return None
        value = value * 10 + (ord(c) - ord("0"))
        i += 1
    return -value if negative else value


def split_words(line):
    # Разбить строку на слова по пробелам, табам и \r (строки с CRLF).
    words = []
    current = []
    for c in line:
        if c == " " or c == "\t" or c == "\r":
            if current:
                words.append("".join(current))
                current = []
        else:
            current.append(c)
    if current:
        words.append("".join(current))
    return words


def parse_sm(text):
    # Текст SM: одна инструкция на строку, "#" - комментарий до конца строки.
    instrs = []
    line_start = 0
    while line_start <= len(text):
        line_end = line_start
        while line_end < len(text) and text[line_end] != "\n":
            line_end += 1
        line = text[line_start:line_end]
        comment = 0
        while comment < len(line) and line[comment] != "#":
            comment += 1
        words = split_words(line[:comment])
        at = where(text, line_start)

        if words:
            op = opcode_by_name(words[0])
            if op < 0:
                raise SmError('SM: unknown instruction "%s" at %s' % (words[0], at))
            if not has_arg(op):
                if len(words) != 1:
                    raise SmError("SM: %s takes no argument at %s" % (words[0], at))
                instrs.append(Instr(op))
            else:
                if len(words) != 2:
                    raise SmError("SM: %s takes one argument at %s" % (words[0], at))
                arg = words[1]
                if op == Opcode.CONST:
                    arg = parse_int(arg)
                    if arg is None:
                        raise SmError("SM: integer expected after CONST at %s" % at)
                elif op == Opcode.BINOP and op_code(arg) < 0:
                    raise SmError('SM: unknown binop "%s" at %s' % (arg, at))
                instrs.append(Instr(op, arg))
        line_start = line_end + 1
    return instrs
