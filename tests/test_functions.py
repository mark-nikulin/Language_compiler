import json
import os
import unittest

from test_all import A, B, C, DO, IF, ROOT, V, W, WHILE, cli, run_both, seq
from l0.assembler import assemble
from l0.ast_builder import build_program
from l0.ast_interp import run_ast
from l0.compiler import compile_program
from l0.errors import AsmError, AstError, SmError
from l0.opcodes import format_program, parse_sm
from l0.sm import run_sm
from l0.sm_json import format_program_json, parse_sm_json


def CALL(name, *args): return {"call": {"name": name, "args": list(args)}}
def RET(expr): return {"return": expr}
def FUN(name, params, body): return {"name": name, "params": params, "body": body}
def SCOPE(body, variables=(), functions=()):
    return {"scope": {"vars": list(variables), "functions": list(functions), "body": body}}
def SWITCH(expr, *branches):
    return {"switch": {"expr": expr, "branches": [
        {"pattern": pattern, "body": body} for pattern, body in branches]}}
def SEXP(tag, *items): return {"sexp": {"tag": tag, "args": list(items)}}


class TestFunctions(unittest.TestCase):
    def run_program(self, program):
        return run_ast(build_program(program), "0")

    def test_recursive_factorial_and_multiple_calls(self):
        fact = FUN("fact", ["n"], IF(B("<=", V("n"), C(1)), RET(C(1)),
                      RET(B("*", V("n"), CALL("fact", B("-", V("n"), C(1)))))))
        program = SCOPE(seq(W(CALL("fact", C(5))), W(CALL("fact", C(0)))), functions=[fact])
        self.assertEqual(self.run_program(program), ([120, 1], None))

    def test_deep_recursion_without_python_recursion(self):
        down = FUN("down", ["n"], IF(V("n"), RET(CALL("down", B("-", V("n"), C(1)))), RET(C(42))))
        self.assertEqual(self.run_program(SCOPE(W(CALL("down", C(5000))), functions=[down])), ([42], None))

    def test_mutual_recursion_and_order_independent_declarations(self):
        even = FUN("even", ["n"], IF(V("n"), RET(CALL("odd", B("-", V("n"), C(1)))), RET(C(1))))
        odd = FUN("odd", ["n"], IF(V("n"), RET(CALL("even", B("-", V("n"), C(1)))), RET(C(0))))
        program = SCOPE(seq(W(CALL("even", C(12))), W(CALL("odd", C(5)))), functions=[even, odd])
        self.assertEqual(self.run_program(program), ([1, 1], None))

    def test_lexical_scope_and_shadowing(self):
        get = FUN("get", [], RET(V("x")))
        caller = FUN("caller", ["x"], RET(CALL("get")))
        inner_get = FUN("get", [], RET(C(9)))
        inner = SCOPE(seq(W(CALL("get")), W(V("x"))), variables=["x"], functions=[inner_get])
        program = seq(A("x", C(7)), SCOPE(seq(W(CALL("caller", C(99))),
                          SCOPE(seq(A("x", C(3)), inner), variables=["x"]), W(V("x"))),
                          functions=[get, caller]))
        self.assertEqual(self.run_program(program), ([], 'ERROR: variable "x" is undefined'))
        inner = SCOPE(seq(A("x", C(4)), W(CALL("get")), W(V("x"))),
                      variables=["x"], functions=[inner_get])
        program = seq(A("x", C(7)), SCOPE(seq(W(CALL("caller", C(99))),
                          SCOPE(seq(A("x", C(3)), inner, W(V("x"))), variables=["x"]), W(V("x"))),
                          functions=[get, caller]))
        self.assertEqual(self.run_program(program), ([7, 9, 4, 3, 7], None))

    def test_nested_functions_capture_declaration_scope(self):
        inner = FUN("read_n", [], RET(V("n")))
        outer = FUN("outer", ["n"], SCOPE(RET(CALL("read_n")), functions=[inner]))
        self.assertEqual(self.run_program(SCOPE(W(CALL("outer", C(21))), functions=[outer])), ([21], None))

    def test_nested_functions_modify_captured_variable(self):
        inc = FUN("inc", [], seq(A("n", B("+", V("n"), C(1))), RET(V("n"))))
        outer = FUN("outer", ["n"], SCOPE(RET(B("+", CALL("inc"), CALL("inc"))), functions=[inc]))
        program = seq(A("n", C(100)), SCOPE(seq(W(CALL("outer", C(10))), W(V("n"))), functions=[outer]))
        self.assertEqual(self.run_program(program), ([23, 100], None))

    def test_return_unwinds_switch_loop_and_scope(self):
        branch = SCOPE(seq(RET(B("+", V("x"), C(1))), W(C(999))), variables=["temp"])
        select = SWITCH(V("n"), ({"var": "x"}, branch))
        f = FUN("f", ["n"], seq(WHILE(C(1), select), RET(C(0))))
        program = SCOPE(seq(W(B("+", C(10), CALL("f", C(3)))), W(C(7))), functions=[f])
        self.assertEqual(self.run_program(program), ([14, 7], None))

    def test_arguments_order_and_calls_inside_all_expressions(self):
        mark = FUN("mark", ["v"], seq(W(V("v")), RET(V("v"))))
        subtract = FUN("subtract", ["a", "b"], RET(B("-", V("a"), V("b"))))
        program = SCOPE(W(CALL("subtract", CALL("mark", C(7)), CALL("mark", C(2)))),
                        functions=[mark, subtract])
        self.assertEqual(self.run_program(program), ([7, 2, 5], None))

    def test_locals_are_fresh_and_compound_arguments_are_shared(self):
        f = FUN("f", ["arr"], seq(A("local", V("arr")),
            {"set": {"dst": V("local"), "idx": C(0), "value": C(9)}}, RET(V("local"))))
        program = SCOPE(seq(A("a", {"array": [C(1)]}), W(CALL("f", V("a"))), W(V("a"))), functions=[f])
        self.assertEqual(self.run_program(program), (["[9]", "[9]"], None))
        self.assertEqual(self.run_program(SCOPE(seq(W(CALL("f", {"array": [C(1)]})), W(V("local"))),
                                               functions=[f])),
                         ([], 'ERROR: variable "local" is undefined'))

    def test_scope_variables_and_functions_expire(self):
        program = seq(A("x", C(5)), SCOPE(seq(A("x", C(8)), W(V("x"))), variables=["x"]), W(V("x")))
        self.assertEqual(self.run_program(program), ([8, 5], None))
        f = FUN("f", [], RET(C(1)))
        self.assertEqual(self.run_program(seq(SCOPE("skip", functions=[f]), W(CALL("f")))),
                         ([], 'ERROR: function "f" is undefined'))

    def test_runtime_errors(self):
        f = FUN("f", ["x"], "skip")
        cases = [(RET(C(1)), "ERROR: return outside function"),
                 (W(CALL("missing")), 'ERROR: function "missing" is undefined'),
                 (SCOPE(W(CALL("f")), functions=[f]), 'ERROR: function "f" expects 1 arguments, got 0'),
                 (SCOPE(W(CALL("f", C(1))), functions=[f]), 'ERROR: function "f" finished without return'),
                 (SCOPE(W(V("x")), variables=["x"]), 'ERROR: variable "x" is undefined')]
        for program, error in cases:
            with self.subTest(error=error):
                self.assertEqual(self.run_program(program), ([], error))

    def test_invalid_ast(self):
        bad = [ {"scope": {"vars": ["x", "x"], "body": "skip"}},
                {"scope": {"vars": "x", "body": "skip"}},
                {"scope": {"functions": [FUN("f", ["x", "x"], "skip")], "body": "skip"}},
                {"scope": {"functions": [FUN("f", [], "skip"), FUN("f", [], "skip")], "body": "skip"}},
                {"scope": {"functions": [FUN("f", [], "skip")]}},
                {"write": {"call": {"name": "f", "args": 0}}}, {"return": 1} ]
        for program in bad:
            with self.subTest(program=program), self.assertRaises(AstError):
                build_program(program)

    def test_sm_functions_and_round_trips(self):
        inc = FUN("bar", ["z"], seq(A("y", B("+", V("y"), V("z"))), RET(V("y"))))
        foo = FUN("foo", ["x"], SCOPE(seq(A("y", C(3)),
            RET(B("+", CALL("bar", V("x")), V("y")))), variables=["y"], functions=[inc]))
        program = SCOPE(W(CALL("foo", C(1))), functions=[foo])
        tree = build_program(program)
        code = compile_program(tree)
        self.assertEqual(run_both(program, "0"), (([8], None), ([8], None)))
        for parsed in (parse_sm(format_program(code)), parse_sm_json(format_program_json(code))):
            self.assertEqual(parsed, code)
            self.assertEqual(run_sm(assemble(parsed), "0"), ([8], None))

    def test_invalid_sm_function_instructions(self):
        for text in ('[{"CALL": ["f", -1]}]', '[{"LD": ["ARG", 0, true]}]',
                     '[{"ENTER": {"vars": ["x", "x"], "functions": []}}]',
                     '[{"ENTER": {"vars": [], "functions": [["f", "L", ["x", "x"]]]}}]'):
            with self.subTest(text=text), self.assertRaises(SmError):
                parse_sm_json(text)
        with self.assertRaises(AsmError):
            assemble(parse_sm_json('[{"ENTER": {"vars": [], "functions": [["f", "missing", []]]}}]'))

    def test_sm_recursion_and_function_errors(self):
        fact = FUN("fact", ["n"], IF(B("<=", V("n"), C(1)), RET(C(1)),
                      RET(B("*", V("n"), CALL("fact", B("-", V("n"), C(1)))))))
        down = FUN("down", ["n"], IF(V("n"), RET(CALL("down", B("-", V("n"), C(1)))), RET(C(42))))
        cases = [SCOPE(seq(W(CALL("fact", C(5))), W(CALL("down", C(5000)))), functions=[fact, down]),
                 SCOPE(W(CALL("fact")), functions=[fact]),
                 W(CALL("missing", B("/", C(1), C(0)))),
                 RET(B("/", C(1), C(0))), SCOPE(W(CALL("f")), functions=[FUN("f", [], "skip")])]
        for program in cases:
            with self.subTest(program=program):
                by_ast, by_sm = run_both(program, "0")
                self.assertEqual(by_ast, by_sm)

    def test_sm_resolves_assignment_before_function_call(self):
        read_a = FUN("read_a", [], RET(V("a")))
        f = FUN("f", [], seq(A("a", C(1)), RET(CALL("read_a"))))
        program = SCOPE(seq(A("a", CALL("f")), W(V("a"))), functions=[f, read_a])
        self.assertEqual(run_both(program, "0"), (([1], None), ([1], None)))

    def test_sm_scope_exit_from_if_and_return(self):
        f = FUN("f", ["n"], SCOPE(IF(V("n"), RET(V("n")), RET(C(4))), variables=["x"]))
        program = SCOPE(seq(SCOPE(IF(C(0), W(C(0))), variables=["x"]), W(CALL("f", C(3)))),
                        functions=[f])
        self.assertEqual(run_both(program, "0"), (([3], None), ([3], None)))

    def test_sm_list_elements_keep_left_to_right_effects(self):
        mark = FUN("mark", ["n"], seq(W(V("n")), RET(V("n"))))
        program = SCOPE(W({"list": [CALL("mark", C(1)), CALL("mark", C(2))]}), functions=[mark])
        self.assertEqual(run_both(program, "0"), (([1, 2, "{1, 2}"], None), ([1, 2, "{1, 2}"], None)))

    def test_sm_lexical_scope_and_mutual_recursion(self):
        get = FUN("get", [], RET(V("x")))
        caller = FUN("caller", ["x"], RET(CALL("get")))
        even = FUN("even", ["n"], IF(V("n"), RET(CALL("odd", B("-", V("n"), C(1)))), RET(C(1))))
        odd = FUN("odd", ["n"], IF(V("n"), RET(CALL("even", B("-", V("n"), C(1)))), RET(C(0))))
        program = seq(A("x", C(7)), SCOPE(seq(W(CALL("caller", C(99))), W(CALL("even", C(12)))),
                                              functions=[get, caller, even, odd]))
        self.assertEqual(run_both(program, "0"), (([7, 1], None), ([7, 1], None)))

    def test_recursive_expression_example(self):
        path = os.path.join(ROOT, "examples", "recursive_eval.json")
        result = cli("run-ast", path, "0")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "26\n", ""))
        with open(path, encoding="utf-8") as source:
            program = json.load(source)
        args = program["scope"]["body"]["write"]["call"]["args"]
        args[0] = SEXP("Mul", SEXP("Add", SEXP("Num", C(2)), SEXP("Num", C(3))), SEXP("Num", C(4)))
        self.assertEqual(self.run_program(program), ([20], None))
        args[0] = SEXP("Unknown")
        self.assertEqual(self.run_program(program), ([], "ERROR: no matching switch branch"))


if __name__ == "__main__":
    unittest.main()
