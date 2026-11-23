import unittest

from test_all import A, ARR, B, C, ELEM, LEN, ROOT, SET, STR, V, W, WHILE, cli, seq, run_both
import os
from l0.assembler import assemble
from l0.ast_builder import build_program
from l0.ast_interp import run_ast
from l0.compiler import compile_program
from l0.errors import AstError, SmError
from l0.opcodes import format_program, parse_sm
from l0.sm import run_sm
from l0.sm_json import format_program_json, parse_sm_json


def S(tag, *items): return {"sexp": {"tag": tag, "args": list(items)}}
def L(*items): return {"list": list(items)}
def P(tag, *items): return {"sexp": {"tag": tag, "args": list(items)}}
def SWITCH(expr, *branches):
    return {"switch": {"expr": expr, "branches": [
        {"pattern": pattern, "body": body} for pattern, body in branches]}}


class TestSexp(unittest.TestCase):
    def test_construct_print_index_and_alias(self):
        program = seq(A("x", S("Pair", C(1), S("Node", C(2)))), A("y", V("x")),
                      W(V("x")), W(ELEM(V("x"), C(0))), W(LEN(V("x"))),
                      SET(V("y"), C(0), C(9)), W(V("x")), W(S("Nothing")))
        expected = (["Pair(1, Node(2))", 1, 2, "Pair(9, Node(2))", "Nothing"], None)
        self.assertEqual(run_both(program, "0"), (expected, expected))

    def test_lists_and_cons(self):
        program = seq(W(L()), W(L(C(1), C(2), L(C(3)))),
                      W(B(":", C(1), B(":", C(2), S("nil")))),
                      W(S("cons", C(1), C(2))), W({"char": "A"}))
        expected = (["{}", "{1, 2, {3}}", "{1, 2}", "cons(1, 2)", 65], None)
        self.assertEqual(run_both(program, "0"), (expected, expected))

    def test_list_literals_compile_as_sexpressions(self):
        list_code = compile_program(build_program(W(L(C(1), C(2)))))
        sexp_code = compile_program(build_program(W(S("cons", C(1), S("cons", C(2), S("nil"))))))
        self.assertEqual(list_code, sexp_code)
        deep = L(*(C(i) for i in range(5000)))
        expected = ([0], None)
        self.assertEqual(run_both(W(ELEM(deep, C(0))), "0"), (expected, expected))

    def test_sm_serialization_and_validation(self):
        code = compile_program(build_program(W(S('A "# B', C(2), L(C(1))))))
        self.assertEqual(parse_sm(format_program(code)), code)
        self.assertEqual(parse_sm_json(format_program_json(code)), code)
        self.assertEqual(run_sm(assemble(code), "0"), (['A "# B(2, {1})'], None))
        self.assertEqual(run_sm(assemble(parse_sm('SEXP "Empty" 0\nWRITE')), "0"), (["Empty"], None))
        for bad in ('SEXP "x" -1', 'SEXP "x"', 'SEXP "x" 2 extra', 'SEXP x 1'):
            with self.subTest(bad=bad), self.assertRaises(SmError):
                parse_sm(bad)
        for bad in ('[{"SEXP": ["x", -1]}]', '[{"SEXP": ["x", true]}]', '[{"SEXP": "x"}]'):
            with self.subTest(bad=bad), self.assertRaises(SmError):
                parse_sm_json(bad)
        with self.assertRaises(SmError):
            run_sm(assemble(parse_sm('SEXP "Pair" 2')), "0")

    def test_cycles_and_comparison(self):
        program = seq(A("a", ARR(C(0), C(1))), SET(V("a"), C(0), V("a")),
                      A("b", ARR(C(0), C(1))), SET(V("b"), C(0), V("b")),
                      A("c", ARR(C(0), C(2))), SET(V("c"), C(0), V("c")),
                      W(V("a")), W(B("==", V("a"), V("b"))), W(B("<", V("a"), V("c"))),
                      W(B("!=", V("a"), V("c"))), W(B("<", C(9), STR("a"))),
                      W(B("<", ARR(C(1)), ARR(C(1), C(0)))),
                      W(B(">", S("Z"), S("A"))))
        expected = (["[<cycle>; 1]", 1, 1, 1, 1, 1, 1], None)
        self.assertEqual(run_both(program, "0"), (expected, expected))

    def test_sexp_cycles(self):
        program = seq(A("a", S("Loop", C(0))), SET(V("a"), C(0), V("a")),
                      A("b", S("Loop", C(0))), SET(V("b"), C(0), V("b")),
                      W(V("a")), W(B("==", V("a"), V("b"))))
        expected = (["Loop(<cycle>)", 1], None)
        self.assertEqual(run_both(program, "0"), (expected, expected))

    def test_cyclic_list(self):
        program = seq(A("xs", L(C(1))), SET(V("xs"), C(1), V("xs")), W(V("xs")))
        expected = (["cons(1, <cycle>)"], None)
        self.assertEqual(run_both(program, "0"), (expected, expected))

    def test_deep_structures(self):
        a, b = C(0), C(0)
        for i in range(3000):
            a, b = S("N", a), S("N", b)
        expected = ([1], None)
        self.assertEqual(run_both(W(B("==", a, b)), "0"), (expected, expected))


class TestPatterns(unittest.TestCase):
    def run_program(self, program):
        return run_ast(build_program(program), "0")

    def test_list_loop_and_branch_scope(self):
        empty = {"list": []}
        pair = {"cons": [{"var": "x"}, {"var": "ys"}]}
        switch = SWITCH(V("xs"), (empty, A("cont", C(0))),
                        (pair, seq(W(V("x")), A("xs", V("ys")), A("x", C(99)))))
        program = seq(A("x", C(42)), A("xs", L(C(1), C(2), C(3))), A("cont", C(1)),
                      WHILE(V("cont"), switch), W(V("x")), W(V("xs")))
        self.assertEqual(self.run_program(program), ([1, 2, 3, 42, "{}"], None))

    def test_new_global_and_reused_local_slots(self):
        body = seq(A("new", V("x")), A("i", B("+", V("i"), C(1))))
        switch = SWITCH(V("i"), ({"var": "x"}, body))
        program = seq(A("i", C(0)), WHILE(B("<", V("i"), C(3)), switch), W(V("new")))
        self.assertEqual(self.run_program(program), ([2], None))

    def test_exercise_examples(self):
        expected = "cons (; 1; , ; cons (; 2; , ; cons (; 3; , ; cons (; 4; , ; cons (; 5; , ; nil; ); ); ); ); )\n"
        for name in ("list_switch.json", "sexp_switch.json"):
            result = cli("run-ast", os.path.join(ROOT, "examples", name), "0")
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, expected, ""))

    def test_nested_scopes_and_failed_bindings(self):
        inner = SWITCH(S("Box", C(8)), (P("Box", {"var": "x"}), seq(W(V("x")), A("x", C(9)))),)
        outer = SWITCH(S("Pair", C(1), C(2)),
                       (P("Pair", {"var": "leaked"}, {"const": 9}), W(C(0))),
                       (P("Pair", {"var": "x"}, "_"), seq(W(V("x")), inner, W(V("x")))))
        self.assertEqual(self.run_program(seq(A("x", C(42)), outer, W(V("x")))), ([1, 8, 1, 42], None))
        self.assertEqual(self.run_program(seq(outer, W(V("leaked")))),
                         ([], 'ERROR: variable "leaked" is undefined'))

    def test_patterns(self):
        patterns = [
            (S("Pair", C(7), ARR(C(65), STR("hi"))),
             {"as": {"name": "whole", "pattern": P("Pair", {"var": "x"},
                         {"array": [{"char": "A"}, {"string": "hi"}]})}}, W(V("x")), 7),
            (L(C(1), C(2)), {"list": [{"const": 1}, {"var": "x"}]}, W(V("x")), 2),
            (STR("abc"), {"type": "string"}, W(C(3)), 3),
            (S("One"), {"type": "sexp"}, W(C(4)), 4),
            (ARR(), {"type": "array"}, W(C(5)), 5),
            (C(1), {"type": "int"}, W(C(6)), 6),
            (S("Pair", C(1), C(2)), P("Pair", {"var": "x"}, {"var": "x"}), W(C(7)), 8),
        ]
        for value, pattern, body, expected in patterns:
            with self.subTest(pattern=pattern):
                self.assertEqual(self.run_program(SWITCH(value, (pattern, body), ("_", W(C(8))))),
                                 ([expected], None))

    def test_no_match_and_invalid_pattern(self):
        self.assertEqual(self.run_program(SWITCH(C(1), ({"const": 2}, "skip"))),
                         ([], "ERROR: no matching switch branch"))
        for pattern in ({"cons": ["_"]}, {"type": "other"}, {"char": "aa"}, {"bad": 1}):
            with self.subTest(pattern=pattern), self.assertRaises(AstError):
                build_program(SWITCH(C(1), (pattern, "skip")))
        with self.assertRaises(AstError):
            compile_program(build_program(SWITCH(C(1), ("_", "skip"))))


if __name__ == "__main__":
    unittest.main()
