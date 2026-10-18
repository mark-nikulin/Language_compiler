# Стековая машина: цикл fetch-execute по собранной программе.
# Метки уже заменены адресами, переменные лежат в ячейках по номеру, строки и массивы - в куче
# (на стеке и в переменных хранятся указатели).

from .arith import wrap
from .config import KEEP_OUTPUT_ON_ERROR
from .errors import L0Error, SmError
from .heap import Heap
from .input_reader import parse_input
from .memory import Memory
from .opcodes import Opcode


class SM:
    def __init__(self, program, inputs):
        self.insts = program.code
        self.ip = 0
        self.stack = []
        self.memory = Memory(program.names)
        self.heap = Heap()
        self.inputs = inputs
        self.output = []

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
                    stack.append(memory.load(instr.arg))
                elif op == Opcode.ST:
                    memory.store(instr.arg, stack.pop())
                elif op == Opcode.CONST:
                    stack.append(wrap(instr.arg))
                elif op == Opcode.BINOP:
                    y = stack.pop()  # правый операнд лежит сверху
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
                else:
                    raise SmError("unknown opcode %d at address %d" % (op, self.ip - 1))
        except IndexError:
            raise SmError("stack underflow at address %d" % (self.ip - 1))


def run_sm(program, input_text):
    # Возвращает (выведенные значения, сообщение об ошибке или None).
    machine = SM(program, None)
    try:
        machine.inputs = parse_input(input_text)
        machine.exec()
    except L0Error as err:
        return (machine.output if KEEP_OUTPUT_ON_ERROR else []), err.message
    return machine.output, None
