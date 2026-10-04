# Эталонный интерпретатор AST без рекурсии.
# Исполняет дерево напрямую, без компиляции. Нужен для сверки с результатом SM.

from .arith import apply_binop, wrap
from .ast_nodes import Assign, BinOp, Const, DoWhile, If, Read, Seq, Skip, Var, While, Write
from .config import KEEP_OUTPUT_ON_ERROR
from .errors import AstError, L0Error
from .input_reader import parse_input
from .memory import Memory
from .stack import Stack

# Задачи вычисления выражения
EVAL, APPLY = 0, 1
# Задачи исполнения операторов
EXEC, WHILE_CHECK, DO_CHECK = 0, 1, 2


class AstInterpreter:
    def __init__(self, inputs):
        self.memory = Memory([])
        self.inputs = inputs
        self.output = []

    def eval(self, expr):
        # Обход в обратной польской записи: значения копятся на своём стеке,
        # BinOp откладывает задачу APPLY, пока не вычислятся оба операнда.
        tasks = Stack("eval tasks")
        values = Stack("eval values")
        tasks.push((EVAL, expr))
        while not tasks.is_empty():
            kind, e = tasks.pop()
            if kind == APPLY:
                y = values.pop()
                x = values.pop()
                values.push(apply_binop(e.code, x, y))
            elif isinstance(e, Const):
                values.push(wrap(e.value))
            elif isinstance(e, Var):
                values.push(self.memory.load(self.memory.slot_of(e.name)))
            elif isinstance(e, BinOp):
                tasks.push((APPLY, e))
                tasks.push((EVAL, e.right))
                tasks.push((EVAL, e.left))
            else:
                raise AstError("unknown expression node")
        return values.pop()

    def run(self, program):
        # Стек - это "что осталось сделать". Циклы кладут на него задачу
        # повторной проверки условия после тела.
        tasks = Stack("exec tasks")
        tasks.push((EXEC, program))
        while not tasks.is_empty():
            kind, s = tasks.pop()
            if kind == WHILE_CHECK:
                if self.eval(s.cond) != 0:
                    tasks.push((WHILE_CHECK, s))
                    tasks.push((EXEC, s.body))
            elif kind == DO_CHECK:
                if self.eval(s.cond) != 0:
                    tasks.push((DO_CHECK, s))
                    tasks.push((EXEC, s.body))
            elif isinstance(s, Seq):
                tasks.push((EXEC, s.second))
                tasks.push((EXEC, s.first))
            elif isinstance(s, Assign):
                self.memory.store(self.memory.slot_of(s.name), self.eval(s.expr))
            elif isinstance(s, Write):
                self.output.append(self.eval(s.expr))
            elif isinstance(s, Read):
                self.memory.store(self.memory.slot_of(s.name), wrap(self.inputs.read()))
            elif isinstance(s, If):
                if self.eval(s.cond) != 0:
                    tasks.push((EXEC, s.then))
                else:
                    tasks.push((EXEC, s.else_))
            elif isinstance(s, While):
                tasks.push((WHILE_CHECK, s))
            elif isinstance(s, DoWhile):
                tasks.push((DO_CHECK, s))
                tasks.push((EXEC, s.body))
            elif isinstance(s, Skip):
                pass
            else:
                raise AstError("unknown statement node")


def run_ast(program, input_text):
    # Возвращает (выведенные числа, сообщение об ошибке или None).
    interp = AstInterpreter(None)
    try:
        interp.inputs = parse_input(input_text)
        interp.run(program)
    except L0Error as err:
        return (interp.output if KEEP_OUTPUT_ON_ERROR else []), err.message
    return interp.output, None
