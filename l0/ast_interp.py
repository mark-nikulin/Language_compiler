# Интерпретатор AST без рекурсии.
# Исполняет дерево напрямую, без компиляции. Нужен для сверки с результатом SM.

from .arith import wrap
from .ast_nodes import (ArrayLit, Assign, BinOp, Const, DoWhile, Elem, If, Length, Read, Seq, SetElem,
                        Skip, StrLit, Var, While, Write)
from .config import KEEP_OUTPUT_ON_ERROR
from .errors import AstError, L0Error
from .heap import Heap
from .input_reader import parse_input
from .memory import Memory

EVAL, APPLY, MAKE_ARRAY, MAKE_ELEM, MAKE_LENGTH = 0, 1, 2, 3, 4
EXEC, WHILE_CHECK, DO_CHECK = 0, 1, 2


class AstInterpreter:
    def __init__(self, inputs):
        self.memory = Memory([])
        self.heap = Heap()
        self.inputs = inputs
        self.output = []

    def eval(self, expr):
        # Обход в обратной польской записи: значения копятся на своём стеке,
        # составной узел откладывает задачу сборки, пока не вычислятся его части.
        tasks = []
        values = []
        tasks.append((EVAL, expr))
        while tasks:
            kind, e = tasks.pop()
            if kind == APPLY:
                y = values.pop()
                x = values.pop()
                values.append(self.heap.binop(e.code, x, y))
            elif kind == MAKE_ARRAY:
                items = []
                i = 0
                while i < len(e.items):
                    items.append(values.pop())
                    i += 1
                items.reverse()
                values.append(self.heap.new_array(items))
            elif kind == MAKE_ELEM:
                index = values.pop()
                values.append(self.heap.elem(values.pop(), index))
            elif kind == MAKE_LENGTH:
                values.append(self.heap.length(values.pop()))
            elif isinstance(e, Const):
                values.append(wrap(e.value))
            elif isinstance(e, Var):
                values.append(self.memory.load(self.memory.slot_of(e.name)))
            elif isinstance(e, BinOp):
                tasks.append((APPLY, e))
                tasks.append((EVAL, e.right))
                tasks.append((EVAL, e.left))
            elif isinstance(e, StrLit):
                values.append(self.heap.new_string(e.text.encode("utf-8")))
            elif isinstance(e, ArrayLit):
                tasks.append((MAKE_ARRAY, e))
                i = len(e.items) - 1
                while i >= 0:
                    tasks.append((EVAL, e.items[i]))
                    i -= 1
            elif isinstance(e, Elem):
                tasks.append((MAKE_ELEM, e))
                tasks.append((EVAL, e.index))
                tasks.append((EVAL, e.array))
            elif isinstance(e, Length):
                tasks.append((MAKE_LENGTH, e))
                tasks.append((EVAL, e.array))
            else:
                raise AstError("unknown expression node")
        return values.pop()

    def holds(self, expr):
        return self.heap.as_int(self.eval(expr)) != 0

    def run(self, program):
        # Стек. Циклы кладут на него задачу
        # повторной проверки условия после тела.
        tasks = []
        tasks.append((EXEC, program))
        while tasks:
            kind, s = tasks.pop()
            if kind == WHILE_CHECK:
                if self.holds(s.cond):
                    tasks.append((WHILE_CHECK, s))
                    tasks.append((EXEC, s.body))
            elif kind == DO_CHECK:
                if self.holds(s.cond):
                    tasks.append((DO_CHECK, s))
                    tasks.append((EXEC, s.body))
            elif isinstance(s, Seq):
                tasks.append((EXEC, s.second))
                tasks.append((EXEC, s.first))
            elif isinstance(s, Assign):
                self.memory.store(self.memory.slot_of(s.name), self.eval(s.expr))
            elif isinstance(s, SetElem):
                dst = self.eval(s.dst)
                index = self.eval(s.index)
                self.heap.set_elem(dst, index, self.eval(s.value))
            elif isinstance(s, Write):
                self.output.append(self.heap.printable(self.eval(s.expr)))
            elif isinstance(s, Read):
                self.memory.store(self.memory.slot_of(s.name), wrap(self.inputs.read()))
            elif isinstance(s, If):
                if self.holds(s.cond):
                    tasks.append((EXEC, s.then))
                else:
                    tasks.append((EXEC, s.else_))
            elif isinstance(s, While):
                tasks.append((WHILE_CHECK, s))
            elif isinstance(s, DoWhile):
                tasks.append((DO_CHECK, s))
                tasks.append((EXEC, s.body))
            elif isinstance(s, Skip):
                pass
            else:
                raise AstError("unknown statement node")


def run_ast(program, input_text):
    # Возвращает (выведенные значения, сообщение об ошибке или None).
    interp = AstInterpreter(None)
    try:
        interp.inputs = parse_input(input_text)
        interp.run(program)
    except L0Error as err:
        return (interp.output if KEEP_OUTPUT_ON_ERROR else []), err.message
    return interp.output, None
