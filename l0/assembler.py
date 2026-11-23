
from .arith import op_code
from .errors import AsmError
from .opcodes import Instr, Opcode


class Program:
    def __init__(self, code, names):
        self.code = code
        self.names = names
        self.memory_size = len(names)


def assemble(instrs):
    labels = {}
    addr = 0
    while addr < len(instrs):
        instr = instrs[addr]
        if instr.op == Opcode.LABEL:
            if instr.arg in labels:
                raise AsmError('duplicate label "%s"' % instr.arg)
            labels[instr.arg] = addr
        addr += 1

    slots = {}
    names = []
    code = []
    for instr in instrs:
        op = instr.op
        if op == Opcode.LD or op == Opcode.ST:
            if isinstance(instr.arg, tuple):
                code.append(Instr(op, instr.arg))
            else:
                if instr.arg not in slots:
                    slots[instr.arg] = len(names)
                    names.append(instr.arg)
                code.append(Instr(op, slots[instr.arg]))
        elif op == Opcode.ENTER:
            functions = []
            for name, label, params in instr.arg["functions"]:
                if label not in labels:
                    raise AsmError('unknown label "%s"' % label)
                functions.append((name, labels[label], params))
            code.append(Instr(op, {"vars": instr.arg["vars"], "functions": functions}))
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
