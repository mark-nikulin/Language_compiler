
from .arith import wrap
from .ast_nodes import (ArrayLit, Assign, BinOp, Call, Const, DoWhile, Elem, If, Length,
                        Read, Return, Scope, Seq, SetElem, SexpLit, Skip, StrLit, Switch, Var, While, Write)
from .config import KEEP_OUTPUT_ON_ERROR
from .errors import AstError, L0Error
from .heap import ARR, INT, SEXP, STR, Heap
from .input_reader import parse_input
from .memory import Memory

(EVAL, APPLY, MAKE_ARRAY, MAKE_ELEM, MAKE_LENGTH, MAKE_SEXP,
 EXEC, WHILE_CHECK, DO_CHECK, POP_SCOPE, ASSIGN, SET_ELEM, WRITE, IF_CHECK,
 SWITCH_CHECK, CALL, CALL_END, RETURN_VALUE) = range(18)


class AstInterpreter:
    def __init__(self, inputs):
        self.memory = Memory([])
        self.heap = Heap()
        self.inputs = inputs
        self.output = []

    def execute(self, first_kind, node):
        tasks = [(first_kind, node)]
        values = []
        while tasks:
            kind, e = tasks.pop()
            if kind == APPLY:
                y, x = values.pop(), values.pop()
                values.append(self.heap.binop(e.code, x, y))
            elif kind in (MAKE_ARRAY, MAKE_SEXP):
                count = len(e.items)
                items = values[-count:] if count else []
                if count:
                    del values[-count:]
                if kind == MAKE_ARRAY:
                    values.append(self.heap.new_array(items))
                else:
                    values.append(self.heap.new_sexp(e.tag, items))
            elif kind == MAKE_ELEM:
                index = values.pop()
                values.append(self.heap.elem(values.pop(), index))
            elif kind == MAKE_LENGTH:
                values.append(self.heap.length(values.pop()))
            elif kind == EVAL:
                if isinstance(e, Const):
                    values.append(wrap(e.value))
                elif isinstance(e, Var):
                    values.append(self.memory.load(self.memory.slot_of(e.name)))
                elif isinstance(e, BinOp):
                    tasks.append((APPLY, e))
                    tasks.append((EVAL, e.right))
                    tasks.append((EVAL, e.left))
                elif isinstance(e, StrLit):
                    values.append(self.heap.new_string(e.text.encode("utf-8")))
                elif isinstance(e, (ArrayLit, SexpLit)):
                    action = MAKE_ARRAY if isinstance(e, ArrayLit) else MAKE_SEXP
                    tasks.append((action, e))
                    for item in reversed(e.items):
                        tasks.append((EVAL, item))
                elif isinstance(e, Elem):
                    tasks.append((MAKE_ELEM, e))
                    tasks.append((EVAL, e.index))
                    tasks.append((EVAL, e.array))
                elif isinstance(e, Length):
                    tasks.append((MAKE_LENGTH, e))
                    tasks.append((EVAL, e.array))
                elif isinstance(e, Call):
                    function, parent = self.memory.function_of(e.name)
                    if len(e.args) != len(function.params):
                        raise L0Error('ERROR: function "%s" expects %d arguments, got %d'
                                      % (e.name, len(function.params), len(e.args)))
                    tasks.append((CALL, (function, parent)))
                    for arg in reversed(e.args):
                        tasks.append((EVAL, arg))
                else:
                    raise AstError("unknown expression node")
            elif kind == CALL:
                function, parent = e
                count = len(function.params)
                args = values[-count:] if count else []
                if count:
                    del values[-count:]
                self.memory.push_scope(dict(zip(function.params, args)), parent=parent, call=True)
                tasks.append((CALL_END, (function.name, len(values))))
                tasks.append((EXEC, function.body))
            elif kind == CALL_END:
                self.memory.pop_scope()
                raise L0Error('ERROR: function "%s" finished without return' % e[0])
            elif kind == RETURN_VALUE:
                value = values.pop()
                while tasks:
                    action, saved = tasks.pop()
                    if action == POP_SCOPE:
                        self.memory.pop_scope()
                    elif action == CALL_END:
                        self.memory.pop_scope()
                        del values[saved[1]:]
                        values.append(value)
                        break
                else:
                    raise L0Error("ERROR: return outside function")
            elif kind == POP_SCOPE:
                self.memory.pop_scope()
            elif kind == ASSIGN:
                self.memory.store(e, values.pop())
            elif kind == SET_ELEM:
                value, index, dst = values.pop(), values.pop(), values.pop()
                self.heap.set_elem(dst, index, value)
            elif kind == WRITE:
                self.output.append(self.heap.printable(values.pop()))
            elif kind == IF_CHECK:
                tasks.append((EXEC, e.then if self.heap.as_int(values.pop()) != 0 else e.else_))
            elif kind == WHILE_CHECK:
                if self.heap.as_int(values.pop()) != 0:
                    tasks.append((WHILE_CHECK, e))
                    tasks.append((EVAL, e.cond))
                    tasks.append((EXEC, e.body))
            elif kind == DO_CHECK:
                if self.heap.as_int(values.pop()) != 0:
                    tasks.append((DO_CHECK, e))
                    tasks.append((EVAL, e.cond))
                    tasks.append((EXEC, e.body))
            elif kind == SWITCH_CHECK:
                value = values.pop()
                for pattern, body in e.branches:
                    bindings = self.match(pattern, value)
                    if bindings is not None:
                        self.memory.push_scope(bindings)
                        tasks.append((POP_SCOPE, None))
                        tasks.append((EXEC, body))
                        break
                else:
                    raise L0Error("ERROR: no matching switch branch")
            elif kind == EXEC:
                if isinstance(e, Seq):
                    tasks.append((EXEC, e.second))
                    tasks.append((EXEC, e.first))
                elif isinstance(e, Assign):
                    tasks.append((ASSIGN, self.memory.slot_of(e.name)))
                    tasks.append((EVAL, e.expr))
                elif isinstance(e, SetElem):
                    tasks.append((SET_ELEM, None))
                    tasks.append((EVAL, e.value))
                    tasks.append((EVAL, e.index))
                    tasks.append((EVAL, e.dst))
                elif isinstance(e, Write):
                    tasks.append((WRITE, None))
                    tasks.append((EVAL, e.expr))
                elif isinstance(e, Read):
                    self.memory.store(self.memory.slot_of(e.name), wrap(self.inputs.read()))
                elif isinstance(e, If):
                    tasks.append((IF_CHECK, e))
                    tasks.append((EVAL, e.cond))
                elif isinstance(e, While):
                    tasks.append((WHILE_CHECK, e))
                    tasks.append((EVAL, e.cond))
                elif isinstance(e, DoWhile):
                    tasks.append((DO_CHECK, e))
                    tasks.append((EVAL, e.cond))
                    tasks.append((EXEC, e.body))
                elif isinstance(e, Switch):
                    tasks.append((SWITCH_CHECK, e))
                    tasks.append((EVAL, e.expr))
                elif isinstance(e, Scope):
                    self.memory.push_scope({}, e.variables, e.functions)
                    tasks.append((POP_SCOPE, None))
                    tasks.append((EXEC, e.body))
                elif isinstance(e, Return):
                    if self.memory.function_frame is None:
                        raise L0Error("ERROR: return outside function")
                    tasks.append((RETURN_VALUE, None))
                    tasks.append((EVAL, e.expr))
                elif not isinstance(e, Skip):
                    raise AstError("unknown statement node")
        return values[-1] if first_kind == EVAL else None

    def eval(self, expr):
        return self.execute(EVAL, expr)

    def run(self, program):
        self.execute(EXEC, program)

    def match(self, pattern, value):
        bindings = {}
        todo = [(pattern, value)]
        while todo:
            p, v = todo.pop()
            kind = self.heap.kind(v)
            if p.kind == "wildcard":
                continue
            if p.kind in ("var", "as"):
                if p.value in bindings and not self.heap.equal(bindings[p.value], v):
                    return None
                bindings[p.value] = v
                if p.kind == "as":
                    todo.append((p.items[0], v))
            elif p.kind == "const" or p.kind == "char":
                expected = p.value if p.kind == "const" else p.value.encode("utf-8")[0]
                if kind != INT or v != wrap(expected):
                    return None
            elif p.kind == "string":
                if kind != STR or self.heap.boxes[v.addr] != p.value.encode("utf-8"):
                    return None
            elif p.kind == "type":
                if kind != {"int": INT, "string": STR, "array": ARR, "sexp": SEXP}[p.value]:
                    return None
            elif p.kind == "array":
                if kind != ARR:
                    return None
                items = self.heap.boxes[v.addr]
                if len(items) != len(p.items):
                    return None
                todo.extend(zip(reversed(p.items), reversed(items)))
            else:
                if kind != SEXP:
                    return None
                box = self.heap.boxes[v.addr]
                tag = "cons" if p.kind == "cons" else p.value
                if box.tag != tag or len(box.items) != len(p.items):
                    return None
                todo.extend(zip(reversed(p.items), reversed(box.items)))
        return bindings


def run_ast(program, input_text):
    interp = AstInterpreter(None)
    try:
        interp.inputs = parse_input(input_text)
        interp.run(program)
    except L0Error as err:
        return (interp.output if KEEP_OUTPUT_ON_ERROR else []), err.message
    return interp.output, None
