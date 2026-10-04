# Стековая машина: цикл fetch-execute по собранной программе.
# Повторяет структуру SM из sm.cpp: insts, ip, stack, exec() со switch по опкоду.
# Отличия от sm.cpp:
#   - init() и resolve_label() вынесены в ассемблер: метки превращаются в адреса
#     до запуска, поэтому JMP/JZ/JNZ не ищут метку на каждом переходе;
#   - environment - не словарь по имени, а Memory с ячейками по номеру;
#   - LD неинициализированной переменной - ошибка (в sm.cpp получится 0),
#     деление на 0 - ошибка Division_by_zero (в C++ это неопределённое поведение).

from .arith import apply_binop, wrap
from .config import KEEP_OUTPUT_ON_ERROR
from .errors import L0Error, SmError
from .input_reader import parse_input
from .memory import Memory
from .opcodes import Opcode
from .stack import Stack


class SM:
    def __init__(self, program, inputs):
        self.insts = program.code
        self.ip = 0  # адрес следующей инструкции
        self.stack = Stack("SM stack")
        self.memory = Memory(program.names)
        self.inputs = inputs
        self.output = []

    def exec(self):
        insts = self.insts
        stack = self.stack
        memory = self.memory
        while self.ip < len(insts):
            instr = insts[self.ip]
            self.ip += 1
            op = instr.op
            if op == Opcode.LD:
                stack.push(memory.load(instr.arg))
            elif op == Opcode.ST:
                memory.store(instr.arg, stack.pop())
            elif op == Opcode.CONST:
                stack.push(wrap(instr.arg))
            elif op == Opcode.BINOP:
                y = stack.pop()  # правый операнд лежит сверху
                x = stack.pop()
                stack.push(apply_binop(instr.arg, x, y))
            elif op == Opcode.JNZ:
                if stack.pop() != 0:
                    self.ip = instr.arg
            elif op == Opcode.JZ:
                if stack.pop() == 0:
                    self.ip = instr.arg
            elif op == Opcode.JMP:
                self.ip = instr.arg
            elif op == Opcode.LABEL:
                pass
            elif op == Opcode.READ:
                stack.push(wrap(self.inputs.read()))
            elif op == Opcode.WRITE:
                self.output.append(stack.pop())
            else:
                raise SmError("unknown opcode %d at address %d" % (op, self.ip - 1))


def run_sm(program, input_text):
    # Возвращает (выведенные числа, сообщение об ошибке или None).
    machine = SM(program, None)
    try:
        machine.inputs = parse_input(input_text)
        machine.exec()
    except L0Error as err:
        return (machine.output if KEEP_OUTPUT_ON_ERROR else []), err.message
    return machine.output, None
