
from .arith import normalize_op, op_code
from .ast_nodes import (ArrayLit, Assign, BinOp, Call, Const, DoWhile, Elem, Function, If, Length,
                        Pattern, Read, Return, Scope, Seq, SetElem, SexpLit, Skip, StrLit,
                        Switch, Var, While, Write)
from .errors import AstError

VISIT, BUILD = 0, 1
STRING_KEY = "string"
EXPR, STMT, PATTERN = 0, 1, 2


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


def names_list(value, what):
    if not isinstance(value, list):
        raise AstError("%s: list of names expected" % what)
    seen = set()
    for name in value:
        if not isinstance(name, str) or not name:
            raise AstError("%s: nonempty name expected" % what)
        if name in seen:
            raise AstError('%s: duplicate name "%s"' % (what, name))
        seen.add(name)
    return value


def visit_expr(e, tasks, results):
    if not isinstance(e, dict):
        raise AstError("expression expected, got " + describe(e))
    if "const" in e:
        n = e["const"]
        if not isinstance(n, int) or isinstance(n, bool):
            raise AstError("const: integer expected, got " + describe(n))
        results.append(Const(n))
    elif "char" in e:
        char = e["char"]
        if not isinstance(char, str) or len(char.encode("utf-8")) != 1:
            raise AstError("char: single-byte character expected")
        results.append(Const(char.encode("utf-8")[0]))
    elif "var" in e:
        results.append(Var(name_field(e, "var", "var")))
    elif "binop" in e:
        op = e["binop"]
        if not isinstance(op, str):
            raise AstError("binop: operation expected, got " + describe(op))
        op = normalize_op(op)
        if op_code(op) < 0:
            raise AstError('unknown binop "%s"' % op)
        tasks.append((BUILD, "binop", op))
        tasks.append((VISIT, EXPR, field(e, "right", "binop")))
        tasks.append((VISIT, EXPR, field(e, "left", "binop")))
    elif "call" in e:
        node = e["call"]
        name = name_field(node, "name", "call")
        args = field(node, "args", "call")
        if not isinstance(args, list):
            raise AstError("call: list of arguments expected")
        tasks.append((BUILD, "call", (name, len(args))))
        for item in reversed(args):
            tasks.append((VISIT, EXPR, item))
    elif "sexp" in e or "list" in e:
        if "sexp" in e:
            node = e["sexp"]
            tag = name_field(node, "tag", "sexp")
            items = field(node, "args", "sexp")
            kind = "sexp"
        else:
            tag = None
            items = e["list"]
            kind = "list"
        if not isinstance(items, list):
            raise AstError("%s: list of expressions expected" % kind)
        tasks.append((BUILD, kind, (tag, len(items))))
        for item in reversed(items):
            tasks.append((VISIT, EXPR, item))
    elif "array" in e:
        items = e["array"]
        if not isinstance(items, list):
            raise AstError("array: list of expressions expected, got " + describe(items))
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
    elif "return" in s:
        tasks.append((BUILD, "return", None))
        tasks.append((VISIT, EXPR, s["return"]))
    elif "scope" in s:
        node = s["scope"]
        if not isinstance(node, dict):
            raise AstError("scope: object expected")
        variables = names_list(node.get("vars", []), "scope vars")
        functions = node.get("functions", [])
        if not isinstance(functions, list):
            raise AstError("scope: list of functions expected")
        declarations = []
        seen = set()
        for function in functions:
            name = name_field(function, "name", "function")
            if name in seen:
                raise AstError('scope: duplicate function "%s"' % name)
            seen.add(name)
            params = names_list(field(function, "params", "function"), "function params")
            declarations.append((name, params, field(function, "body", "function")))
        tasks.append((BUILD, "scope", (variables, [(name, params) for name, params, _ in declarations])))
        tasks.append((VISIT, STMT, field(node, "body", "scope")))
        for _, _, body in reversed(declarations):
            tasks.append((VISIT, STMT, body))
    elif "switch" in s:
        node = s["switch"]
        branches = field(node, "branches", "switch")
        if not isinstance(branches, list) or not branches:
            raise AstError("switch: nonempty list of branches expected")
        tasks.append((BUILD, "switch", len(branches)))
        for branch in reversed(branches):
            tasks.append((VISIT, STMT, field(branch, "body", "branch")))
            tasks.append((VISIT, PATTERN, field(branch, "pattern", "branch")))
        tasks.append((VISIT, EXPR, field(node, "expr", "switch")))
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


def visit_pattern(p, tasks, results):
    if p == "_":
        results.append(Pattern("wildcard"))
        return
    if not isinstance(p, dict) or len(p) != 1:
        raise AstError("pattern expected, got " + describe(p))
    kind, value = next(iter(p.items()))
    if kind == "var":
        results.append(Pattern("var", name_field(p, "var", "pattern")))
    elif kind == "const":
        if not isinstance(value, int) or isinstance(value, bool):
            raise AstError("pattern: integer expected")
        results.append(Pattern("const", value))
    elif kind in ("string", "char"):
        if not isinstance(value, str) or (kind == "char" and len(value.encode("utf-8")) != 1):
            raise AstError("pattern: invalid %s" % kind)
        results.append(Pattern(kind, value))
    elif kind == "type":
        if value not in ("int", "string", "array", "sexp"):
            raise AstError("pattern: unknown type")
        results.append(Pattern(kind, value))
    elif kind == "as":
        name = name_field(value, "name", "pattern as")
        tasks.append((BUILD, "pattern", (kind, name, 1)))
        tasks.append((VISIT, PATTERN, field(value, "pattern", "pattern as")))
    elif kind in ("array", "list", "sexp", "cons"):
        tag = None
        if kind == "sexp":
            tag = name_field(value, "tag", "pattern sexp")
            items = field(value, "args", "pattern sexp")
        else:
            items = value
        if not isinstance(items, list) or (kind == "cons" and len(items) != 2):
            raise AstError("pattern %s: invalid items" % kind)
        tasks.append((BUILD, "pattern", (kind, tag, len(items))))
        for item in reversed(items):
            tasks.append((VISIT, PATTERN, item))
    else:
        raise AstError("unknown pattern: " + kind)


def build(kind, arg, results):
    if kind == "call":
        name, count = arg
        args = results[-count:] if count else []
        if count:
            del results[-count:]
        results.append(Call(name, args))
    elif kind == "scope":
        variables, declarations = arg
        body = results.pop()
        count = len(declarations)
        bodies = results[-count:] if count else []
        if count:
            del results[-count:]
        functions = [Function(name, params, fn_body)
                     for (name, params), fn_body in zip(declarations, bodies)]
        results.append(Scope(variables, functions, body))
    elif kind == "return":
        results.append(Return(results.pop()))
    elif kind in ("sexp", "list"):
        tag, count = arg
        items = results[-count:] if count else []
        if count:
            del results[-count:]
        if kind == "sexp":
            results.append(SexpLit(tag, items))
        else:
            result = SexpLit("nil", [])
            for item in reversed(items):
                result = SexpLit("cons", [item, result])
            results.append(result)
    elif kind == "pattern":
        pattern_kind, value, count = arg
        items = results[-count:] if count else []
        if count:
            del results[-count:]
        if pattern_kind == "list":
            result = Pattern("sexp", "nil")
            for item in reversed(items):
                result = Pattern("cons", items=[item, result])
            results.append(result)
        else:
            results.append(Pattern(pattern_kind, value, items))
    elif kind == "switch":
        branches = []
        for i in range(arg):
            body = results.pop()
            pattern = results.pop()
            branches.append((pattern, body))
        branches.reverse()
        results.append(Switch(results.pop(), branches))
    elif kind == "binop":
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
            elif kind == STMT:
                visit_stmt(arg, tasks, results)
            else:
                visit_pattern(arg, tasks, results)
        else:
            build(kind, arg, results)
    return results.pop()
