# Перевод JSON-значений (dict, str, int) в узлы AST без рекурсии.
#
# Явный стек задач двух видов:
#   VISIT - разобрать JSON-узел. Лист сразу превращается в узел AST,
#           составной узел кладёт BUILD и VISIT своих детей.
#   BUILD - дети уже построены и лежат на стеке результатов: снять их и собрать узел.

from .arith import normalize_op, op_code
from .ast_nodes import Assign, BinOp, Const, DoWhile, If, Read, Seq, Skip, Var, While, Write
from .errors import AstError
from .stack import Stack

VISIT, BUILD = 0, 1
EXPR, STMT = 0, 1


def describe(value):
    # Короткое описание JSON-значения для сообщения об ошибке (без обхода вглубь).
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
        results.push(Const(n))
    elif "var" in e:
        results.push(Var(name_field(e, "var", "var")))
    elif "binop" in e:
        op = e["binop"]
        if not isinstance(op, str):
            raise AstError("binop: operation expected, got " + describe(op))
        op = normalize_op(op)
        if op_code(op) < 0:
            raise AstError('unknown binop "%s"' % op)
        # Порядок обратный: сначала разберётся left, потом right, потом сборка.
        tasks.push((BUILD, "binop", op))
        tasks.push((VISIT, EXPR, field(e, "right", "binop")))
        tasks.push((VISIT, EXPR, field(e, "left", "binop")))
    else:
        raise AstError("unknown expression: " + describe(e))


def visit_stmt(s, tasks, results):
    if s == "skip":
        results.push(Skip())
        return
    if not isinstance(s, dict):
        raise AstError("statement expected, got " + describe(s))
    if "read" in s:
        results.push(Read(name_field(s, "read", "read")))
    elif "write" in s:
        tasks.push((BUILD, "write", None))
        tasks.push((VISIT, EXPR, s["write"]))
    elif "assn" in s:
        node = s["assn"]
        tasks.push((BUILD, "assn", name_field(node, "dst", "assn")))
        tasks.push((VISIT, EXPR, field(node, "src", "assn")))
    elif "seq" in s:
        node = s["seq"]
        tasks.push((BUILD, "seq", None))
        tasks.push((VISIT, STMT, field(node, "right", "seq")))
        tasks.push((VISIT, STMT, field(node, "left", "seq")))
    elif "if" in s:
        node = s["if"]
        else_ = node["else"] if isinstance(node, dict) and "else" in node else "skip"
        tasks.push((BUILD, "if", None))
        tasks.push((VISIT, STMT, else_))
        tasks.push((VISIT, STMT, field(node, "then", "if")))
        tasks.push((VISIT, EXPR, field(node, "cond", "if")))
    elif "while" in s:
        node = s["while"]
        tasks.push((BUILD, "while", None))
        tasks.push((VISIT, STMT, field(node, "body", "while")))
        tasks.push((VISIT, EXPR, field(node, "cond", "while")))
    elif "do" in s:
        node = s["do"]
        tasks.push((BUILD, "do", None))
        tasks.push((VISIT, EXPR, field(node, "cond", "do")))
        tasks.push((VISIT, STMT, field(node, "body", "do")))
    else:
        raise AstError("unknown statement: " + describe(s))


def build(kind, arg, results):
    # Дети сняты в порядке, обратном тому, в каком их строили.
    if kind == "binop":
        right = results.pop()
        left = results.pop()
        results.push(BinOp(arg, op_code(arg), left, right))
    elif kind == "write":
        results.push(Write(results.pop()))
    elif kind == "assn":
        results.push(Assign(arg, results.pop()))
    elif kind == "seq":
        second = results.pop()
        first = results.pop()
        results.push(Seq(first, second))
    elif kind == "if":
        else_ = results.pop()
        then = results.pop()
        cond = results.pop()
        results.push(If(cond, then, else_))
    elif kind == "while":
        body = results.pop()
        cond = results.pop()
        results.push(While(cond, body))
    elif kind == "do":
        cond = results.pop()
        body = results.pop()
        results.push(DoWhile(body, cond))


def build_program(value):
    tasks = Stack("builder tasks")
    results = Stack("builder results")
    tasks.push((VISIT, STMT, value))
    while not tasks.is_empty():
        action, kind, arg = tasks.pop()
        if action == VISIT:
            if kind == EXPR:
                visit_expr(arg, tasks, results)
            else:
                visit_stmt(arg, tasks, results)
        else:
            build(kind, arg, results)
    return results.pop()
