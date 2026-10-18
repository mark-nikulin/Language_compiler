# Перевод JSON-значений (dict, str, int) в узлы AST без рекурсии.
#
# Явный стек задач двух видов:
#   VISIT - разобрать JSON-узел. Лист сразу превращается в узел AST,
#           составной узел кладёт BUILD и VISIT своих детей.
#   BUILD - дети уже построены и лежат на стеке результатов: снять их и собрать узел.

from .arith import normalize_op, op_code
from .ast_nodes import (ArrayLit, Assign, BinOp, Const, DoWhile, Elem, If, Length, Read, Seq, SetElem,
                        Skip, StrLit, Var, While, Write)
from .errors import AstError

VISIT, BUILD = 0, 1
STRING_KEY = "string"
EXPR, STMT = 0, 1


def describe(value):
    if isinstance(value, dict):
        return "object with keys [%s]" % ", ".join(value.keys())
    if isinstance(value, str):
        return 'string "%s"' % value
    return type(value).__name__


def field(obj, key, what):
    if not isinstance(obj, dict) or key not in obj:
        raise AstError('%s: field "%s" expected in %s' % (what, key, describe(obj)))
    return obj[key]


def name_field(obj, key, what):
    name = field(obj, key, what)
    if not isinstance(name, str) or name == "":
        raise AstError("%s: variable name expected, got %s" % (what, describe(name)))
    return name


def visit_expr(e, tasks, results):
    if not isinstance(e, dict):
        raise AstError("expression expected, got " + describe(e))
    if "const" in e:
        n = e["const"]
        if not isinstance(n, int) or isinstance(n, bool):
            raise AstError("const: integer expected, got " + describe(n))
        results.append(Const(n))
    elif "var" in e:
        results.append(Var(name_field(e, "var", "var")))
    elif "binop" in e:
        op = e["binop"]
        if not isinstance(op, str):
            raise AstError("binop: operation expected, got " + describe(op))
        op = normalize_op(op)
        if op_code(op) < 0:
            raise AstError('unknown binop "%s"' % op)
        # Порядок обратный: сначала разберётся left, потом right, потом сборка.
        tasks.append((BUILD, "binop", op))
        tasks.append((VISIT, EXPR, field(e, "right", "binop")))
        tasks.append((VISIT, EXPR, field(e, "left", "binop")))
    elif "array" in e:
        items = e["array"]
        if not isinstance(items, list):
            raise AstError("array: list of expressions expected, got " + describe(items))
        # Порядок обратный: первый элемент снимется со стека задач первым.
        tasks.append((BUILD, "array", len(items)))
        i = len(items) - 1
        while i >= 0:
            tasks.append((VISIT, EXPR, items[i]))
            i -= 1
    elif "elem" in e:
        tasks.append((BUILD, "elem", None))
        tasks.append((VISIT, EXPR, field(e, "index", "elem")))
        tasks.append((VISIT, EXPR, e["elem"]))
    elif STRING_KEY in e:
        text = e[STRING_KEY]
        if not isinstance(text, str):
            raise AstError("string: text expected, got " + describe(text))
        results.append(StrLit(text))
    elif "length" in e:
        tasks.append((BUILD, "length", None))
        tasks.append((VISIT, EXPR, e["length"]))
    else:
        raise AstError("unknown expression: " + describe(e))


def visit_stmt(s, tasks, results):
    if s == "skip":
        results.append(Skip())
        return
    if not isinstance(s, dict):
        raise AstError("statement expected, got " + describe(s))
    if "read" in s:
        results.append(Read(name_field(s, "read", "read")))
    elif "write" in s:
        tasks.append((BUILD, "write", None))
        tasks.append((VISIT, EXPR, s["write"]))
    elif "assn" in s:
        node = s["assn"]
        tasks.append((BUILD, "assn", name_field(node, "dst", "assn")))
        tasks.append((VISIT, EXPR, field(node, "src", "assn")))
    elif "seq" in s:
        node = s["seq"]
        tasks.append((BUILD, "seq", None))
        tasks.append((VISIT, STMT, field(node, "right", "seq")))
        tasks.append((VISIT, STMT, field(node, "left", "seq")))
    elif "if" in s:
        node = s["if"]
        else_ = node["else"] if isinstance(node, dict) and "else" in node else "skip"
        tasks.append((BUILD, "if", None))
        tasks.append((VISIT, STMT, else_))
        tasks.append((VISIT, STMT, field(node, "then", "if")))
        tasks.append((VISIT, EXPR, field(node, "cond", "if")))
    elif "set" in s:
        node = s["set"]
        tasks.append((BUILD, "set", None))
        tasks.append((VISIT, EXPR, field(node, "value", "set")))
        tasks.append((VISIT, EXPR, field(node, "idx", "set")))
        tasks.append((VISIT, EXPR, field(node, "dst", "set")))
    elif "while" in s:
        node = s["while"]
        tasks.append((BUILD, "while", None))
        tasks.append((VISIT, STMT, field(node, "body", "while")))
        tasks.append((VISIT, EXPR, field(node, "cond", "while")))
    elif "do" in s:
        node = s["do"]
        tasks.append((BUILD, "do", None))
        tasks.append((VISIT, EXPR, field(node, "cond", "do")))
        tasks.append((VISIT, STMT, field(node, "body", "do")))
    else:
        raise AstError("unknown statement: " + describe(s))


def build(kind, arg, results):
    # Дети сняты в порядке, обратном тому, в каком их строили.
    if kind == "binop":
        right = results.pop()
        left = results.pop()
        results.append(BinOp(arg, op_code(arg), left, right))
    elif kind == "array":
        items = []
        i = 0
        while i < arg:
            items.append(results.pop())
            i += 1
        items.reverse()
        results.append(ArrayLit(items))
    elif kind == "elem":
        index = results.pop()
        results.append(Elem(results.pop(), index))
    elif kind == "length":
        results.append(Length(results.pop()))
    elif kind == "set":
        value = results.pop()
        index = results.pop()
        results.append(SetElem(results.pop(), index, value))
    elif kind == "write":
        results.append(Write(results.pop()))
    elif kind == "assn":
        results.append(Assign(arg, results.pop()))
    elif kind == "seq":
        second = results.pop()
        first = results.pop()
        results.append(Seq(first, second))
    elif kind == "if":
        else_ = results.pop()
        then = results.pop()
        cond = results.pop()
        results.append(If(cond, then, else_))
    elif kind == "while":
        body = results.pop()
        cond = results.pop()
        results.append(While(cond, body))
    elif kind == "do":
        cond = results.pop()
        body = results.pop()
        results.append(DoWhile(body, cond))


def build_program(value):
    tasks = []
    results = []
    tasks.append((VISIT, STMT, value))
    while tasks:
        action, kind, arg = tasks.pop()
        if action == VISIT:
            if kind == EXPR:
                visit_expr(arg, tasks, results)
            else:
                visit_stmt(arg, tasks, results)
        else:
            build(kind, arg, results)
    return results.pop()
