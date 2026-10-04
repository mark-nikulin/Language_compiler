# Компилятор AST -> список инструкций SM без рекурсии.
#
# Явный стек задач двух видов:
#   EMIT    - дописать готовую инструкцию в результат;
#   COMPILE - развернуть узел в задачи по его шаблону.
# Стек отдаёт задачи в обратном порядке, поэтому шаблон кладётся задом наперёд.
#
# Шаблоны ([x] - код узла x):
#   Const n          CONST n
#   Var x            LD x
#   BinOp(op, l, r)  [l] [r] BINOP op
#   Read x           READ ; ST x
#   Write e          [e] ; WRITE
#   Assign x = e     [e] ; ST x
#   Seq(a, b)        [a] [b]
#   Skip             -
#   If(c, t, e)      [c] ; JZ else ; [t] ; JMP end ; LABEL else ; [e] ; LABEL end
#   While(c, b)      JMP cond ; LABEL body ; [b] ; LABEL cond ; [c] ; JNZ body
#   DoWhile(b, c)    LABEL body ; [b] ; [c] ; JNZ body

from .ast_nodes import Assign, BinOp, Const, DoWhile, If, Read, Seq, Skip, Var, While, Write
from .errors import AstError
from .opcodes import Instr, Opcode
from .stack import Stack

EMIT, COMPILE = 0, 1


class LabelMaker:
    # Как в sm.cpp: каждая метка получает свой номер из общего счётчика
    # (L_while_body_2, L_while_cond_3), а не один номер на конструкцию.
    def __init__(self):
        self.counter = 0

    def fresh(self, prefix):
        label = "%s_%d" % (prefix, self.counter)
        self.counter += 1
        return label


def compile_program(program):
    code = []
    tasks = Stack("compiler tasks")
    tasks.push((COMPILE, program))
    labels = LabelMaker()

    while not tasks.is_empty():
        kind, x = tasks.pop()
        if kind == EMIT:
            code.append(x)
            continue

        node = x
        if isinstance(node, Const):
            code.append(Instr(Opcode.CONST, node.value))
        elif isinstance(node, Var):
            code.append(Instr(Opcode.LD, node.name))
        elif isinstance(node, BinOp):
            tasks.push((EMIT, Instr(Opcode.BINOP, node.op)))
            tasks.push((COMPILE, node.right))
            tasks.push((COMPILE, node.left))
        elif isinstance(node, Read):
            code.append(Instr(Opcode.READ))
            code.append(Instr(Opcode.ST, node.name))
        elif isinstance(node, Write):
            tasks.push((EMIT, Instr(Opcode.WRITE)))
            tasks.push((COMPILE, node.expr))
        elif isinstance(node, Assign):
            tasks.push((EMIT, Instr(Opcode.ST, node.name)))
            tasks.push((COMPILE, node.expr))
        elif isinstance(node, Seq):
            tasks.push((COMPILE, node.second))
            tasks.push((COMPILE, node.first))
        elif isinstance(node, Skip):
            pass
        elif isinstance(node, If):
            l_else = labels.fresh("L_else")
            l_end = labels.fresh("L_end")
            tasks.push((EMIT, Instr(Opcode.LABEL, l_end)))
            tasks.push((COMPILE, node.else_))
            tasks.push((EMIT, Instr(Opcode.LABEL, l_else)))
            tasks.push((EMIT, Instr(Opcode.JMP, l_end)))
            tasks.push((COMPILE, node.then))
            tasks.push((EMIT, Instr(Opcode.JZ, l_else)))
            tasks.push((COMPILE, node.cond))
        elif isinstance(node, While):
            l_body = labels.fresh("L_while_body")
            l_cond = labels.fresh("L_while_cond")
            # Условие стоит после тела: на итерацию один переход JNZ вместо JZ + JMP.
            tasks.push((EMIT, Instr(Opcode.JNZ, l_body)))
            tasks.push((COMPILE, node.cond))
            tasks.push((EMIT, Instr(Opcode.LABEL, l_cond)))
            tasks.push((COMPILE, node.body))
            tasks.push((EMIT, Instr(Opcode.LABEL, l_body)))
            tasks.push((EMIT, Instr(Opcode.JMP, l_cond)))
        elif isinstance(node, DoWhile):
            l_body = labels.fresh("L_do_body")
            tasks.push((EMIT, Instr(Opcode.JNZ, l_body)))
            tasks.push((COMPILE, node.cond))
            tasks.push((COMPILE, node.body))
            tasks.push((EMIT, Instr(Opcode.LABEL, l_body)))
        else:
            raise AstError("unknown AST node")
    return code
