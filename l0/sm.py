
from .arith import wrap
from .config import KEEP_OUTPUT_ON_ERROR
from .errors import L0Error, SmError
from .heap import Heap
from .input_reader import parse_input
from .memory import Memory
from .opcodes import Opcode


class CompiledFunction:
    def __init__(self, name, address, params):
        self.name = name
        self.address = address
        self.params = params


class SM:
    def __init__(self, program, inputs):
        self.insts = program.code
        self.ip = 0
        self.stack = []
        self.memory = Memory(program.names)
        self.memory.global_frame.variables = {}
        self.heap = Heap()
        self.inputs = inputs
        self.output = []
        self.calls = []

    def slot_of(self, operand):
        if not isinstance(operand, tuple):
            name = self.memory.names[operand]
            frame = self.memory.global_frame
            if name not in frame.variables:
                frame.variables[name] = operand
            return frame.variables[name]
        if operand[0] == "NAME":
            return self.memory.slot_of(operand[1])
        frame = self.memory.current
        for _ in range(operand[1]):
            frame = frame.parent if frame is not None else None
        if frame is None or frame.kind != operand[0] or operand[2] >= len(frame.slots):
            raise SmError("invalid variable location at address %d" % (self.ip - 1))
        return frame.slots[operand[2]]

    def function_of(self, operand):
        name, count = operand
        function, parent = self.memory.function_of(name)
        if len(function.params) != count:
            raise L0Error('ERROR: function "%s" expects %d arguments, got %d'
                          % (name, len(function.params), count))
        return function, parent

    def exec(self):
        insts = self.insts
        stack = self.stack
        memory = self.memory
        heap = self.heap
        try:
            while self.ip < len(insts):
                instr = insts[self.ip]
                self.ip += 1
                op = instr.op
                if op == Opcode.LD:
                    stack.append(memory.load(self.slot_of(instr.arg)))
                elif op == Opcode.ST:
                    memory.store(self.slot_of(instr.arg), stack.pop())
                elif op == Opcode.CONST:
                    stack.append(wrap(instr.arg))
                elif op == Opcode.BINOP:
                    y = stack.pop()
                    x = stack.pop()
                    stack.append(heap.binop(instr.arg, x, y))
                elif op == Opcode.JNZ:
                    if heap.as_int(stack.pop()) != 0:
                        self.ip = instr.arg
                elif op == Opcode.JZ:
                    if heap.as_int(stack.pop()) == 0:
                        self.ip = instr.arg
                elif op == Opcode.JMP:
                    self.ip = instr.arg
                elif op == Opcode.LABEL:
                    pass
                elif op == Opcode.READ:
                    stack.append(wrap(self.inputs.read()))
                elif op == Opcode.WRITE:
                    self.output.append(heap.printable(stack.pop()))
                elif op == Opcode.STRING:
                    stack.append(heap.new_string(instr.arg.encode("utf-8")))
                elif op == Opcode.SEXP:
                    tag, count = instr.arg
                    items = []
                    for i in range(count):
                        items.append(stack.pop())
                    items.reverse()
                    stack.append(heap.new_sexp(tag, items))
                elif op == Opcode.ARRAY:
                    items = []
                    i = 0
                    while i < instr.arg:
                        items.append(stack.pop())
                        i += 1
                    items.reverse()
                    stack.append(heap.new_array(items))
                elif op == Opcode.ALOAD:
                    index = stack.pop()
                    stack.append(heap.elem(stack.pop(), index))
                elif op == Opcode.ASTORE:
                    value = stack.pop()
                    index = stack.pop()
                    heap.set_elem(stack.pop(), index, value)
                elif op == Opcode.ALEN:
                    stack.append(heap.length(stack.pop()))
                elif op == Opcode.ENTER:
                    functions = [CompiledFunction(name, address, params)
                                 for name, address, params in instr.arg["functions"]]
                    memory.push_scope({}, instr.arg["vars"], functions)
                elif op == Opcode.LEAVE:
                    if not memory.scopes or (self.calls and len(memory.scopes) <= self.calls[-1][2] + 1):
                        raise SmError("invalid scope exit at address %d" % (self.ip - 1))
                    memory.pop_scope()
                elif op == Opcode.PRECALL:
                    self.function_of(instr.arg)
                elif op == Opcode.RESOLVE:
                    memory.slot_of(instr.arg)
                elif op == Opcode.CALL:
                    function, parent = self.function_of(instr.arg)
                    count = len(function.params)
                    if len(stack) < count:
                        raise IndexError
                    args = stack[-count:] if count else []
                    if count:
                        del stack[-count:]
                    self.calls.append((self.ip, len(stack), len(memory.scopes), function.name))
                    memory.push_scope(dict(zip(function.params, args)), parent=parent, call=True)
                    self.ip = function.address
                elif op == Opcode.RETURN:
                    if not self.calls:
                        raise L0Error("ERROR: return outside function")
                    value = stack.pop()
                    address, base, depth, _ = self.calls.pop()
                    while len(memory.scopes) > depth:
                        memory.pop_scope()
                    del stack[base:]
                    stack.append(value)
                    self.ip = address
                elif op == Opcode.END:
                    if not self.calls:
                        raise SmError("function end outside call at address %d" % (self.ip - 1))
                    raise L0Error('ERROR: function "%s" finished without return' % self.calls[-1][3])
                else:
                    raise SmError("unknown opcode %d at address %d" % (op, self.ip - 1))
        except IndexError:
            raise SmError("stack underflow at address %d" % (self.ip - 1))


def run_sm(program, input_text):
    machine = SM(program, None)
    try:
        machine.inputs = parse_input(input_text)
        machine.exec()
    except L0Error as err:
        return (machine.output if KEEP_OUTPUT_ON_ERROR else []), err.message
    return machine.output, None
