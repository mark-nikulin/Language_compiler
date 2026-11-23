
import json

from .arith import normalize_op, op_code
from .errors import SmError
from .json_reader import parse_json
from .opcodes import Instr, Opcode, has_arg, opcode_by_name, parse_sm, quote_string, validate_structured_arg


def format_json_instr(instr):
    name = Opcode.NAMES[instr.op]
    if not has_arg(instr.op):
        return quote_string(name)
    if instr.op in (Opcode.ENTER, Opcode.CALL, Opcode.PRECALL) or (instr.op in (Opcode.LD, Opcode.ST)
                                                  and isinstance(instr.arg, (tuple, list))):
        return '{ "%s": %s }' % (name, json.dumps(instr.arg, ensure_ascii=False))
    if instr.op == Opcode.SEXP:
        return '{ "%s": [%s, %d] }' % (name, quote_string(instr.arg[0]), instr.arg[1])
    if instr.op == Opcode.CONST or instr.op == Opcode.ARRAY:
        return '{ "%s": %d }' % (name, instr.arg)
    return '{ "%s": %s }' % (name, quote_string(instr.arg))


def format_program_json(instrs):
    lines = []
    for instr in instrs:
        lines.append("  " + format_json_instr(instr))
    if not lines:
        return "[]"
    return "[\n" + ",\n".join(lines) + "\n]"


def instr_from_json(item, index):
    at = "SM JSON: instruction %d" % index
    if isinstance(item, str):
        op = opcode_by_name(item)
        if op < 0:
            raise SmError('%s: unknown instruction "%s"' % (at, item))
        if has_arg(op):
            raise SmError("%s: %s needs an argument" % (at, item))
        return Instr(op)
    if not isinstance(item, dict) or len(item) != 1:
        raise SmError("%s: string or object with one key expected" % at)
    name = list(item.keys())[0]
    arg = item[name]
    op = opcode_by_name(name)
    if op < 0:
        raise SmError('%s: unknown instruction "%s"' % (at, name))
    if not has_arg(op):
        raise SmError("%s: %s takes no argument" % (at, name))
    if op in (Opcode.ENTER, Opcode.CALL, Opcode.PRECALL) or (op in (Opcode.LD, Opcode.ST) and isinstance(arg, list)):
        arg = validate_structured_arg(op, arg, at)
    elif op == Opcode.SEXP:
        if (not isinstance(arg, list) or len(arg) != 2 or not isinstance(arg[0], str)
                or not arg[0] or not isinstance(arg[1], int) or isinstance(arg[1], bool) or arg[1] < 0):
            raise SmError("%s: [tag, nonnegative arity] expected after SEXP" % at)
        arg = (arg[0], arg[1])
    elif op == Opcode.CONST or op == Opcode.ARRAY:
        if not isinstance(arg, int) or isinstance(arg, bool) or (op == Opcode.ARRAY and arg < 0):
            raise SmError("%s: integer expected after %s" % (at, name))
    else:
        if not isinstance(arg, str):
            raise SmError("%s: string expected after %s" % (at, name))
        if op == Opcode.BINOP:
            arg = normalize_op(arg)
            if op_code(arg) < 0:
                raise SmError('%s: unknown binop "%s"' % (at, arg))
    return Instr(op, arg)


def parse_sm_json(text):
    items = parse_json(text)
    if not isinstance(items, list):
        raise SmError("SM JSON: array of instructions expected")
    instrs = []
    i = 0
    while i < len(items):
        instrs.append(instr_from_json(items[i], i))
        i += 1
    return instrs


def parse_sm_any(text):
    i = 0
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    if i < len(text) and text[i] == "[":
        return parse_sm_json(text)
    return parse_sm(text)
