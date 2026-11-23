
from .ast_nodes import (ArrayLit, Assign, BinOp, Call, Const, DoWhile, Elem, If, Length,
                        Read, Return, Scope, Seq, SetElem, SexpLit, Skip, StrLit, Switch, Var, While, Write)
from .errors import AstError
from .opcodes import Instr, Opcode

EMIT, EXPR, STMT, PLACE, ENV = 0, 1, 2, 3, 4


class CompileScope:
    def __init__(self, parent, kind, names):
        self.parent = parent
        self.kind = kind
        self.slots = {name: i for i, name in enumerate(names)}

    def location(self, name):
        depth = 0
        scope = self
        while scope is not None:
            if name in scope.slots:
                return (scope.kind, depth, scope.slots[name])
            scope = scope.parent
            depth += 1
        return ("NAME", name)

    def in_function(self):
        scope = self
        while scope is not None:
            if scope.kind == "ARG":
                return True
            scope = scope.parent
        return False


def location(env, name):
    return env.location(name) if env is not None else name


class LabelMaker:
    def __init__(self):
        self.counter = 0

    def fresh(self, prefix):
        label = "%s_%d" % (prefix, self.counter)
        self.counter += 1
        return label


class Exit:
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


def compile_expr(node, code, tasks, env):
    if isinstance(node, Call):
        arg = (node.name, len(node.args))
        code.append(Instr(Opcode.PRECALL, arg))
        tasks.append((EMIT, Instr(Opcode.CALL, arg), None))
        for item in reversed(node.args):
            tasks.append((EXPR, item, None))
    elif isinstance(node, Const):
        code.append(Instr(Opcode.CONST, node.value))
    elif isinstance(node, Var):
        code.append(Instr(Opcode.LD, location(env, node.name)))
    elif isinstance(node, StrLit):
        code.append(Instr(Opcode.STRING, node.text))
    elif isinstance(node, BinOp):
        tasks.append((EMIT, Instr(Opcode.BINOP, node.op), None))
        tasks.append((EXPR, node.right, None))
        tasks.append((EXPR, node.left, None))
    elif isinstance(node, SexpLit):
        tasks.append((EMIT, Instr(Opcode.SEXP, (node.tag, len(node.items))), None))
        for item in reversed(node.items):
            tasks.append((EXPR, item, None))
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


def compile_stmt(node, exit, code, tasks, labels, env, functions):
    if isinstance(node, Scope):
        inner = CompileScope(env, "LOC", node.variables)
        declarations = []
        for function in node.functions:
            label = labels.fresh("L_function")
            declarations.append([function.name, label, function.params])
            functions.append((function, label, inner))
        code.append(Instr(Opcode.ENTER, {"vars": node.variables, "functions": declarations}))
        end_scope = Exit(labels)
        tasks.append((ENV, env, None))
        tasks.append((EMIT, Instr(Opcode.LEAVE), None))
        tasks.append((PLACE, end_scope, None))
        tasks.append((STMT, node.body, end_scope))
        tasks.append((ENV, inner, None))
    elif isinstance(node, Return):
        if env is None or not env.in_function():
            code.append(Instr(Opcode.RETURN))
        else:
            tasks.append((EMIT, Instr(Opcode.RETURN), None))
            tasks.append((EXPR, node.expr, None))
    elif isinstance(node, Switch):
        raise AstError("switch: compilation is not supported")
    elif isinstance(node, Read):
        if env is not None and location(env, node.name)[0] == "NAME":
            code.append(Instr(Opcode.RESOLVE, node.name))
        code.append(Instr(Opcode.READ))
        code.append(Instr(Opcode.ST, location(env, node.name)))
    elif isinstance(node, Write):
        tasks.append((EMIT, Instr(Opcode.WRITE), None))
        tasks.append((EXPR, node.expr, None))
    elif isinstance(node, Assign):
        if env is not None and location(env, node.name)[0] == "NAME":
            code.append(Instr(Opcode.RESOLVE, node.name))
        tasks.append((EMIT, Instr(Opcode.ST, location(env, node.name)), None))
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
    functions = []
    function_index = 0
    env = None
    while True:
        while tasks:
            kind, x, exit = tasks.pop()
            if kind == EMIT:
                code.append(x)
            elif kind == PLACE:
                if x.used():
                    code.append(Instr(Opcode.LABEL, x.name))
            elif kind == ENV:
                env = x
            elif kind == EXPR:
                compile_expr(x, code, tasks, env)
            else:
                compile_stmt(x, exit, code, tasks, labels, env, functions)
        if function_index == len(functions):
            break
        if function_index == 0:
            program_end = labels.fresh("L_program_end")
            code.append(Instr(Opcode.JMP, program_end))
        function, label, parent = functions[function_index]
        function_index += 1
        env = CompileScope(parent, "ARG", function.params)
        code.append(Instr(Opcode.LABEL, label))
        function_end = Exit(labels)
        tasks = [(EMIT, Instr(Opcode.END), None), (PLACE, function_end, None),
                 (STMT, function.body, function_end)]
    if function_index:
        code.append(Instr(Opcode.LABEL, program_end))
    return code
