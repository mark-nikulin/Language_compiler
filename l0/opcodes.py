import json

from .arith import op_code
from .errors import JsonError, SmError, where
from .json_reader import parse_json


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
    STRING = 10
    ARRAY = 11
    ALOAD = 12
    ASTORE = 13
    ALEN = 14
    SEXP = 15
    ENTER = 16
    LEAVE = 17
    CALL = 18
    RETURN = 19
    END = 20
    PRECALL = 21
    RESOLVE = 22

    NAMES = ["READ", "WRITE", "LD", "ST", "CONST", "BINOP", "LABEL", "JMP", "JZ", "JNZ", "STRING", "ARRAY", "ALOAD", "ASTORE",
             "ALEN", "SEXP", "ENTER", "LEAVE", "CALL", "RETURN", "END", "PRECALL", "RESOLVE"]


def has_arg(op):
    return op not in (Opcode.READ, Opcode.WRITE, Opcode.ALOAD, Opcode.ASTORE, Opcode.ALEN,
                      Opcode.LEAVE, Opcode.RETURN, Opcode.END)


def opcode_by_name(name):
    i = 0
    while i < len(Opcode.NAMES):
        if Opcode.NAMES[i] == name:
            return i
        i += 1
    return -1


class Instr:
    __slots__ = ("op", "arg")

    def __init__(self, op, arg=None):
        self.op = op
        self.arg = arg

    def __eq__(self, other):
        return isinstance(other, Instr) and self.op == other.op and self.arg == other.arg

    def __repr__(self):
        return format_instr(self)


def quote_string(text):
    chars = ['"']
    for c in text:
        if c == '"':
            chars.append('\\"')
        elif c == "\\":
            chars.append("\\\\")
        elif c == "\n":
            chars.append("\\n")
        elif c == "\r":
            chars.append("\\r")
        elif c == "\t":
            chars.append("\\t")
        elif ord(c) < 32:
            chars.append("\\u%04x" % ord(c))
        else:
            chars.append(c)
    chars.append('"')
    return "".join(chars)


def format_instr(instr):
    name = Opcode.NAMES[instr.op]
    if instr.op in (Opcode.ENTER, Opcode.CALL, Opcode.PRECALL) or (instr.op in (Opcode.LD, Opcode.ST)
                                                  and isinstance(instr.arg, (tuple, list))):
        return "%s %s" % (name, json.dumps(instr.arg, ensure_ascii=False))
    if instr.op == Opcode.SEXP:
        return "%s %s %d" % (name, quote_string(instr.arg[0]), instr.arg[1])
    if instr.op in (Opcode.STRING, Opcode.RESOLVE):
        return "%s %s" % (name, quote_string(instr.arg))
    if has_arg(instr.op):
        return "%s %s" % (name, instr.arg)
    return name


def format_program(instrs):
    lines = []
    for instr in instrs:
        lines.append(format_instr(instr))
    return "\n".join(lines)


def parse_int(word):
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


def strip_comment(line):
    in_string = False
    i = 0
    while i < len(line):
        c = line[i]
        if in_string:
            if c == "\\":
                i += 1
            elif c == '"':
                in_string = False
        elif c == '"':
            in_string = True
        elif c == "#":
            return line[:i]
        i += 1
    return line


def validate_structured_arg(op, arg, at):
    def name(value):
        return isinstance(value, str) and bool(value)

    def names(value):
        return (isinstance(value, list) and all(name(item) for item in value)
                and len(set(value)) == len(value))

    def number(value):
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0

    if op in (Opcode.LD, Opcode.ST):
        if (isinstance(arg, list) and len(arg) == 2 and arg[0] == "NAME" and name(arg[1])):
            return tuple(arg)
        if (isinstance(arg, list) and len(arg) == 3 and arg[0] in ("ARG", "LOC")
                and number(arg[1]) and number(arg[2])):
            return tuple(arg)
    elif op in (Opcode.CALL, Opcode.PRECALL):
        if isinstance(arg, list) and len(arg) == 2 and name(arg[0]) and number(arg[1]):
            return tuple(arg)
    elif op == Opcode.ENTER and isinstance(arg, dict):
        variables = arg.get("vars")
        functions = arg.get("functions")
        if names(variables) and isinstance(functions, list):
            seen = set()
            for function in functions:
                if (not isinstance(function, list) or len(function) != 3 or not name(function[0])
                        or not name(function[1]) or not names(function[2]) or function[0] in seen):
                    break
                seen.add(function[0])
            else:
                return {"vars": variables, "functions": functions}
    raise SmError("%s: invalid argument for %s" % (at, Opcode.NAMES[op]))


def parse_sm(text):
    instrs = []
    line_start = 0
    while line_start <= len(text):
        line_end = line_start
        while line_end < len(text) and text[line_end] != "\n":
            line_end += 1
        line = text[line_start:line_end]
        line = strip_comment(line)
        words = split_words(line)
        at = where(text, line_start)

        if words:
            op = opcode_by_name(words[0])
            if op < 0:
                raise SmError('SM: unknown instruction "%s" at %s' % (words[0], at))
            if op in (Opcode.ENTER, Opcode.CALL, Opcode.PRECALL) or (op in (Opcode.LD, Opcode.ST)
                                                    and line[line.index(words[0]) + len(words[0]):].lstrip().startswith("[")):
                rest = line[line.index(words[0]) + len(words[0]):].strip()
                try:
                    arg = parse_json(rest)
                except JsonError:
                    raise SmError("SM: invalid argument after %s at %s" % (words[0], at))
                instrs.append(Instr(op, validate_structured_arg(op, arg, "SM at %s" % at)))
            elif op == Opcode.SEXP:
                rest = line[line.index(words[0]) + len(words[0]):].strip()
                end = 1
                while end < len(rest):
                    if rest[end] == "\\":
                        end += 2
                    elif rest[end] == '"':
                        break
                    else:
                        end += 1
                try:
                    tag = parse_json(rest[:end + 1])
                except JsonError:
                    tag = None
                count = parse_int(rest[end + 1:].strip())
                if not isinstance(tag, str) or not tag or count is None or count < 0:
                    raise SmError("SM: quoted tag and nonnegative arity expected after SEXP at %s" % at)
                instrs.append(Instr(op, (tag, count)))
            elif op in (Opcode.STRING, Opcode.RESOLVE):
                rest = line[line.index(words[0]) + len(words[0]):].strip()
                try:
                    arg = parse_json(rest)
                except JsonError:
                    arg = None
                if not isinstance(arg, str):
                    raise SmError("SM: quoted string expected after %s at %s" % (words[0], at))
                instrs.append(Instr(op, arg))
            elif not has_arg(op):
                if len(words) != 1:
                    raise SmError("SM: %s takes no argument at %s" % (words[0], at))
                instrs.append(Instr(op))
            else:
                if len(words) != 2:
                    raise SmError("SM: %s takes one argument at %s" % (words[0], at))
                arg = words[1]
                if op == Opcode.CONST or op == Opcode.ARRAY:
                    arg = parse_int(arg)
                    if arg is None or (op == Opcode.ARRAY and arg < 0):
                        raise SmError("SM: integer expected after %s at %s" % (words[0], at))
                elif op == Opcode.BINOP and op_code(arg) < 0:
                    raise SmError('SM: unknown binop "%s" at %s' % (arg, at))
                instrs.append(Instr(op, arg))
        line_start = line_end + 1
    return instrs
