# Компилятор AST -> список инструкций SM без рекурсии.
#
# Задачи: EMIT - дописать инструкцию, EXPR и STMT - развернуть узел, PLACE - поставить метку.
# Шаблон кладётся в список задом наперёд, потому что задачи берутся с конца.
#
# Метка выхода (Exit) - место сразу после оператора. Её ставит тот, кто компилирует оператор,
# и только если на неё были переходы: оператор без выхода раньше конца меток не плодит.
#
# Шаблоны ([x] - код x, X - метка выхода оператора):
#   Const n          CONST n
#   Str s            STRING s
#   [e1, ..., en]    [e1] ... [en] ARRAY n
#   a[i]             [a] [i] ALOAD
#   a.length         [a] ALEN
#   a[i] = e         [a] [i] [e] ASTORE
#   Var x            LD x
#   BinOp(op, l, r)  [l] [r] BINOP op
#   Read x           READ ; ST x
#   Write e          [e] ; WRITE
#   Assign x = e     [e] ; ST x
#   Seq(a, b)        [a с выходом A] ; LABEL A (если нужна) ; [b с выходом X]
#   Skip             -
#   If(c, t, Skip)   [c] ; JZ X ; [t с выходом X]
#   If(c, t, e)      [c] ; JZ else ; [t с выходом X] ; JMP X ; LABEL else ; [e с выходом X]
#   While(c, b)      JMP cond ; LABEL body ; [b с выходом cond] ; LABEL cond ; [c] ; JNZ body
#   DoWhile(b, c)    LABEL body ; [b с выходом B] ; LABEL B (если нужна) ; [c] ; JNZ body

from .ast_nodes import (ArrayLit, Assign, BinOp, Const, DoWhile, Elem, If, Length, Read, Seq, SetElem,
                        Skip, StrLit, Var, While, Write)
from .errors import AstError
from .opcodes import Instr, Opcode

EMIT, EXPR, STMT, PLACE = 0, 1, 2, 3


class LabelMaker:
    # Каждая метка получает свой номер из общего счётчика
    # (L_while_body_2, L_while_cond_3), а не один номер на конструкцию.
    def __init__(self):
        self.counter = 0

    def fresh(self, prefix):
        label = "%s_%d" % (prefix, self.counter)
        self.counter += 1
        return label


class Exit:
    # Метка "после оператора". Имя выдаётся при первом переходе на неё.
    __slots__ = ("labels", "prefix", "name")

    def __init__(self, labels, prefix="L_end"):
        self.labels = labels
        self.prefix = prefix
        self.name = None

    def use(self):
        if self.name is None:
            self.name = self.labels.fresh(self.prefix)
        return self.name

    def used(self):
        return self.name is not None


def compile_expr(node, code, tasks):
    if isinstance(node, Const):
        code.append(Instr(Opcode.CONST, node.value))
    elif isinstance(node, Var):
        code.append(Instr(Opcode.LD, node.name))
    elif isinstance(node, StrLit):
        code.append(Instr(Opcode.STRING, node.text))
    elif isinstance(node, BinOp):
        tasks.append((EMIT, Instr(Opcode.BINOP, node.op), None))
        tasks.append((EXPR, node.right, None))
        tasks.append((EXPR, node.left, None))
    elif isinstance(node, ArrayLit):
        tasks.append((EMIT, Instr(Opcode.ARRAY, len(node.items)), None))
        i = len(node.items) - 1
        while i >= 0:
            tasks.append((EXPR, node.items[i], None))
            i -= 1
    elif isinstance(node, Elem):
        tasks.append((EMIT, Instr(Opcode.ALOAD), None))
        tasks.append((EXPR, node.index, None))
        tasks.append((EXPR, node.array, None))
    elif isinstance(node, Length):
        tasks.append((EMIT, Instr(Opcode.ALEN), None))
        tasks.append((EXPR, node.array, None))
    else:
        raise AstError("unknown expression node")


def compile_stmt(node, exit, code, tasks, labels):
    if isinstance(node, Read):
        code.append(Instr(Opcode.READ))
        code.append(Instr(Opcode.ST, node.name))
    elif isinstance(node, Write):
        tasks.append((EMIT, Instr(Opcode.WRITE), None))
        tasks.append((EXPR, node.expr, None))
    elif isinstance(node, Assign):
        tasks.append((EMIT, Instr(Opcode.ST, node.name), None))
        tasks.append((EXPR, node.expr, None))
    elif isinstance(node, SetElem):
        tasks.append((EMIT, Instr(Opcode.ASTORE), None))
        tasks.append((EXPR, node.value, None))
        tasks.append((EXPR, node.index, None))
        tasks.append((EXPR, node.dst, None))
    elif isinstance(node, Seq):
        between = Exit(labels)
        tasks.append((STMT, node.second, exit))
        tasks.append((PLACE, between, None))
        tasks.append((STMT, node.first, between))
    elif isinstance(node, Skip):
        pass
    elif isinstance(node, If):
        if isinstance(node.else_, Skip):
            # Без else условие ложно - сразу на выход, ни меток, ни JMP больше не нужно.
            tasks.append((STMT, node.then, exit))
            tasks.append((EMIT, Instr(Opcode.JZ, exit.use()), None))
            tasks.append((EXPR, node.cond, None))
        else:
            l_else = labels.fresh("L_else")
            tasks.append((STMT, node.else_, exit))
            tasks.append((EMIT, Instr(Opcode.LABEL, l_else), None))
            tasks.append((EMIT, Instr(Opcode.JMP, exit.use()), None))
            tasks.append((STMT, node.then, exit))
            tasks.append((EMIT, Instr(Opcode.JZ, l_else), None))
            tasks.append((EXPR, node.cond, None))
    elif isinstance(node, While):
        l_body = labels.fresh("L_while_body")
        cond = Exit(labels, "L_while_cond")
        l_cond = cond.use()
        # Условие стоит после тела: на итерацию один переход JNZ вместо JZ + JMP.
        # Метка условия - выход тела, а заодно цель первого перехода, так что нужна всегда.
        code.append(Instr(Opcode.JMP, l_cond))
        code.append(Instr(Opcode.LABEL, l_body))
        tasks.append((EMIT, Instr(Opcode.JNZ, l_body), None))
        tasks.append((EXPR, node.cond, None))
        tasks.append((PLACE, cond, None))
        tasks.append((STMT, node.body, cond))
    elif isinstance(node, DoWhile):
        l_body = labels.fresh("L_do_body")
        after_body = Exit(labels)
        code.append(Instr(Opcode.LABEL, l_body))
        tasks.append((EMIT, Instr(Opcode.JNZ, l_body), None))
        tasks.append((EXPR, node.cond, None))
        tasks.append((PLACE, after_body, None))
        tasks.append((STMT, node.body, after_body))
    else:
        raise AstError("unknown statement node")


def compile_program(program):
    code = []
    labels = LabelMaker()
    end = Exit(labels)
    tasks = [(PLACE, end, None), (STMT, program, end)]
    while tasks:
        kind, x, exit = tasks.pop()
        if kind == EMIT:
            code.append(x)
        elif kind == PLACE:
            if x.used():
                code.append(Instr(Opcode.LABEL, x.name))
        elif kind == EXPR:
            compile_expr(x, code, tasks)
        else:
            compile_stmt(x, exit, code, tasks, labels)
    return code
