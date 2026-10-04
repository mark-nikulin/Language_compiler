# Тесты: каждая программа идёт двумя путями (AST-интерпретатор и SM),
# результаты должны совпасть между собой и с ожидаемым.
# Запуск: python3 -m unittest discover tests   (или python3 tests/test_all.py)

import os
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from l0.assembler import assemble  # noqa: E402
from l0.ast_builder import build_program  # noqa: E402
from l0.ast_interp import run_ast  # noqa: E402
from l0.compiler import compile_program  # noqa: E402
from l0.errors import AsmError, JsonError  # noqa: E402
from l0.json_reader import parse_json  # noqa: E402
from l0.opcodes import Opcode, format_instr, format_program, parse_sm  # noqa: E402
from l0.sm import run_sm  # noqa: E402

MAIN = os.path.join(ROOT, "main.py")


# AST в формате "мордочки" (JSON-значения как dict/str/int)

def C(n): return {"const": n}
def V(x): return {"var": x}
def B(op, l, r): return {"binop": op, "left": l, "right": r}
def W(e): return {"write": e}
def R(x): return {"read": x}
def A(d, s): return {"assn": {"dst": d, "src": s}}
def IF(c, t, e="skip"): return {"if": {"cond": c, "then": t, "else": e}}
def WHILE(c, b): return {"while": {"cond": c, "body": b}}
def DO(b, c): return {"do": {"body": b, "cond": c}}


def seq(*stmts):
    s = stmts[-1]
    for x in reversed(stmts[:-1]):
        s = {"seq": {"left": x, "right": s}}
    return s


def run_both(ast_json, text):
    tree = build_program(ast_json)
    by_ast = run_ast(tree, text)
    by_sm = run_sm(assemble(compile_program(tree)), text)
    return by_ast, by_sm


def normalize_labels(lines):
    # Метки переименовываются в L0, L1, ... по порядку первого появления.
    names = []
    result = []
    for line in lines:
        words = line.split(" ")
        if words[0] in ("LABEL", "JMP", "JZ", "JNZ"):
            if words[1] not in names:
                names.append(words[1])
            line = "%s L%d" % (words[0], names.index(words[1]))
        result.append(line)
    return result


SUM = seq(R("a"), R("b"), W(B("+", V("a"), V("b"))))
NEG = seq(R("n"), IF(B("<", V("n"), C(0)), W(B("-", C(0), C(1)))))
ELIF = seq(R("a"), IF(B("==", V("a"), C(1)), W(C(10)),
                      IF(B("==", V("a"), C(2)), W(C(20)), W(C(30)))))

CASES = [
    # (имя, AST, ввод, ожидаемый вывод, ожидаемое сообщение)
    ("sum 1, 3", SUM, "1, 3", [4], None),
    ("sum 1,3", SUM, "1,3", [4], None),
    ("sum 1,      3", SUM, "1,      3", [4], None),
    ("sum newline", SUM, "1,\n3", [4], None),
    ("sum extra number", SUM, "1, 3, 5", [4], None),
    ("sum negative", SUM, "-10, 3", [-7], None),
    ("sum one number", SUM, "0", [], "L0.Stmt.No_input"),
    ("input trailing comma", SUM, "4,", [], 'Input error: "decimal constant" expected at (1:3)'),
    ("input empty", SUM, "", [], 'Input error: "decimal constant" expected at (1:1)'),
    ("input space sep", SUM, "1 3", [], "Input error: <EOF> expected at (1:3)"),
    ("input newline sep", SUM, "1\n3", [], "Input error: <EOF> expected at (2:1)"),
    ("input <end of line>", SUM, "1 <end of line> 3", [], "Input error: <EOF> expected at (1:3)"),
    ("write(10)", W(C(10)), "0", [10], None),
    ("if without else, 0", NEG, "0", [], None),
    ("if without else, -10", NEG, "-10", [-1], None),
    ("while", seq(A("x", C(0)), WHILE(B("<", V("x"), C(3)), A("x", B("+", V("x"), C(1)))),
                  W(V("x"))), "1", [3], None),
    ("do-while", seq(A("x", C(0)), DO(A("x", B("+", V("x"), C(1))), B("<", V("x"), C(3))),
                     W(V("x"))), "1", [3], None),
    ("for", seq(A("i", C(0)), WHILE(B("<", V("i"), C(3)),
                                    seq(W(V("i")), A("i", B("+", V("i"), C(1)))))),
     "1", [0, 1, 2], None),
    ("x += 1", seq(A("x", C(5)), A("x", B("+", V("x"), C(1))), W(V("x"))), "1", [6], None),
    ("precedence", seq(W(B("+", C(1), B("*", C(2), C(3)))),
                       W(B("-", B("-", C(10), C(3)), C(2))),
                       W(B("+", B("*", C(2), C(3)), C(1)))), "1", [7, 5, 7], None),
    ("div/mod", seq(W(B("/", B("-", C(0), C(7)), C(2))),
                    W(B("%", B("-", C(0), C(7)), C(3))),
                    W(B("/", C(7), C(2)))), "0", [-3, -1, 3], None),
    ("logic", seq(W(B("<", C(1), C(2))), W(B("<", C(2), C(1))), W(B("!!", C(0), C(5))),
                  W(B("&&", C(3), C(0))), W(B("&&", C(3), C(4))), W(B("!=", C(5), C(5)))),
     "0", [1, 0, 1, 0, 1, 0], None),
    ("undefined variable", W(V("y")), "0", [], 'L0.State.Undefined_variable("y")'),
    ("division by zero", W(B("/", C(1), C(0))), "0", [], "Division_by_zero"),
    ("mod by zero", W(B("%", C(1), C(0))), "0", [], "Division_by_zero"),
    ("skip", {"seq": {"left": "skip", "right": {"write": {"const": 1}}}}, "0", [1], None),
    ("elif 1", ELIF, "1", [10], None),
    ("elif 2", ELIF, "2", [20], None),
    ("elif else", ELIF, "5", [30], None),
    ("unicode minus", W(B("−", C(5), C(2))), "0", [3], None),
    ("en dash minus", W(B("–", C(5), C(2))), "0", [3], None),
    ("no short circuit", W(B("&&", C(0), V("y"))), "0", [], 'L0.State.Undefined_variable("y")'),
]

SM_WHILE = seq(A("x", C(0)), WHILE(B("<", V("x"), C(10)),
                                   seq(W(V("x")), A("x", B("+", V("x"), C(1))))))
SM_WHILE_CODE = ["CONST 0", "ST x", "JMP L0", "LABEL L1", "LD x", "WRITE", "LD x", "CONST 1",
                 "BINOP +", "ST x", "LABEL L0", "LD x", "CONST 10", "BINOP <", "JNZ L1"]


class TestPrograms(unittest.TestCase):
    def test_cases(self):
        for name, ast_json, text, want_out, want_msg in CASES:
            with self.subTest(name):
                by_ast, by_sm = run_both(ast_json, text)
                self.assertEqual(by_ast, (want_out, want_msg))
                self.assertEqual(by_sm, (want_out, want_msg))

    def test_while_code_from_sm_cpp(self):
        code = compile_program(build_program(SM_WHILE))
        lines = [format_instr(i) for i in code]
        self.assertEqual(normalize_labels(lines), SM_WHILE_CODE)
        by_ast, by_sm = run_both(SM_WHILE, "0")
        self.assertEqual(by_sm, (list(range(10)), None))
        self.assertEqual(by_ast, by_sm)

    def test_while_label_names(self):
        # Как в sm.cpp: у тела и условия одного while разные номера.
        code = compile_program(build_program(SM_WHILE))
        lines = [format_instr(i) for i in code]
        self.assertEqual(lines[2:4], ["JMP L_while_cond_1", "LABEL L_while_body_0"])
        self.assertEqual(lines[-1], "JNZ L_while_body_0")

    def test_program_from_sm_cpp_main(self):
        # Дословно инструкции из main() в sm.cpp, вместе с опечаткой "cody".
        text = """CONST 0
ST x
JMP L_while_cond_3
LABEL L_while_cody_2
LD x
WRITE
LD x
CONST 1
BINOP +
ST x
LABEL L_while_cond_3
LD x
CONST 10
BINOP <
JNZ L_while_cody_2
"""
        self.assertEqual(run_sm(assemble(parse_sm(text)), "0"), (list(range(10)), None))

    def test_if_code(self):
        code = compile_program(build_program(NEG))
        lines = normalize_labels([format_instr(i) for i in code])
        self.assertEqual(lines, ["READ", "ST n", "LD n", "CONST 0", "BINOP <", "JZ L0",
                                 "CONST 0", "CONST 1", "BINOP -", "WRITE", "JMP L1",
                                 "LABEL L0", "LABEL L1"])

    def test_do_code(self):
        code = compile_program(build_program(DO(W(C(1)), C(0))))
        lines = normalize_labels([format_instr(i) for i in code])
        self.assertEqual(lines, ["LABEL L0", "CONST 1", "WRITE", "CONST 0", "JNZ L0"])

    def test_sm_text_round_trip(self):
        for name, ast_json, text, _, _ in CASES:
            with self.subTest(name):
                code = compile_program(build_program(ast_json))
                again = parse_sm(format_program(code))
                self.assertEqual(again, code)
                self.assertEqual(run_sm(assemble(again), text), run_sm(assemble(code), text))


class TestJson(unittest.TestCase):
    def test_values(self):
        self.assertEqual(parse_json(' { "a" : [1, -2, "x\\"\\\\\\n"], "b": {} } '),
                         {"a": [1, -2, 'x"\\\n'], "b": {}})
        self.assertEqual(parse_json('"\\u2212"'), "−")
        self.assertEqual(parse_json("[]"), [])

    def test_errors(self):
        for bad in ["", "{", '{"a" 1}', '{"a": 1,}', "[1 2]", '"abc', "1.5", "{} x", '{"a": }']:
            with self.subTest(bad):
                with self.assertRaises(JsonError):
                    parse_json(bad)


class TestAssembler(unittest.TestCase):
    def test_slots_and_addresses(self):
        program = assemble(parse_sm("CONST 1\nST b\nLABEL top\nLD a\nST b\nJMP top\n"))
        self.assertEqual(program.names, ["b", "a"])
        self.assertEqual(program.code[5].op, Opcode.JMP)
        self.assertEqual(program.code[5].arg, 2)

    def test_duplicate_label(self):
        with self.assertRaises(AsmError):
            assemble(parse_sm("LABEL a\nLABEL a\n"))

    def test_unknown_label(self):
        with self.assertRaises(AsmError):
            assemble(parse_sm("JMP nowhere\n"))


N = 100000


def deep_seq_text(n):
    # {"seq":{"left":W,"right":{"seq":...}}} - текст собирается повторением строк, без рекурсии
    write = '{"write":{"const":1}}'
    return '{"seq":{"left":%s,"right":' % write * n + write + "}}" * n


def deep_left_sum_text(n):
    # ((1+1)+1)+...
    return '{"binop":"+","left":' * n + '{"const":1}' + ',"right":{"const":1}}' * n


def deep_right_sum_text(n):
    # 1+(1+(1+...))
    return '{"binop":"+","left":{"const":1},"right":' * n + '{"const":1}' + "}" * n


class TestStress(unittest.TestCase):
    def test_long_seq(self):
        tree = build_program(parse_json(deep_seq_text(N)))
        out_sm = run_sm(assemble(compile_program(tree)), "0")
        self.assertEqual(out_sm, ([1] * (N + 1), None))
        self.assertEqual(run_ast(tree, "0"), out_sm)

    def test_deep_left_expression(self):
        tree = build_program(parse_json('{"write":' + deep_left_sum_text(N) + "}"))
        self.assertEqual(run_sm(assemble(compile_program(tree)), "0"), ([N + 1], None))
        self.assertEqual(run_ast(tree, "0"), ([N + 1], None))

    def test_deep_right_expression(self):
        tree = build_program(parse_json('{"write":' + deep_right_sum_text(N) + "}"))
        self.assertEqual(run_sm(assemble(compile_program(tree)), "0"), ([N + 1], None))
        self.assertEqual(run_ast(tree, "0"), ([N + 1], None))

    def test_million_iterations(self):
        loop = seq(A("x", C(0)), WHILE(B("<", V("x"), C(1000000)),
                                      A("x", B("+", V("x"), C(1)))), W(V("x")))
        by_ast, by_sm = run_both(loop, "0")
        self.assertEqual(by_sm, ([1000000], None))
        self.assertEqual(by_ast, by_sm)


def cli(*args, stdin=None):
    return subprocess.run([sys.executable, MAIN] + list(args), input=stdin,
                          capture_output=True, text=True)


class TestCli(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.dir.cleanup()

    def write(self, name, text):
        path = os.path.join(self.dir.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_commands(self):
        path = self.write("sum.json", '{"seq":{"left":{"read":"a"},"right":{"seq":{"left":'
                                      '{"read":"b"},"right":{"write":{"binop":"+","left":'
                                      '{"var":"a"},"right":{"var":"b"}}}}}}}')
        for command in ("run-sm", "run-ast"):
            p = cli(command, path, "1, 3")
            self.assertEqual((p.returncode, p.stdout, p.stderr), (0, "4\n", ""))
        p = cli("run-sm", path, stdin="1,\n3\n")
        self.assertEqual((p.returncode, p.stdout), (0, "4\n"))
        p = cli("run-sm", path, "1")
        self.assertEqual((p.returncode, p.stderr), (1, "L0.Stmt.No_input\n"))
        p = cli("check", path, "1, 3")
        self.assertEqual((p.returncode, p.stdout), (0, "OK\n"))

    def test_compile_then_run_smfile(self):
        path = self.write("loop.json", '{"seq":{"left":{"assn":{"dst":"x","src":{"const":0}}},'
                                       '"right":{"while":{"cond":{"binop":"<","left":{"var":"x"},'
                                       '"right":{"const":3}},"body":{"seq":{"left":{"write":'
                                       '{"var":"x"}},"right":{"assn":{"dst":"x","src":{"binop":'
                                       '"+","left":{"var":"x"},"right":{"const":1}}}}}}}}}}')
        p = cli("compile", path)
        self.assertEqual(p.returncode, 0)
        sm_path = self.write("loop.sm", p.stdout)
        by_file = cli("run-smfile", sm_path, "0")
        by_sm = cli("run-sm", path, "0")
        self.assertEqual((by_file.returncode, by_file.stdout), (0, "0; 1; 2\n"))
        self.assertEqual(by_file.stdout, by_sm.stdout)

    def test_format_errors_exit_2(self):
        bad_json = self.write("bad.json", '{"write": ')
        bad_ast = self.write("bad_ast.json", '{"print": 1}')
        dup = self.write("dup.sm", "LABEL a\nLABEL a\n")
        missing = self.write("missing.sm", "JMP b\n")
        bad_sm = self.write("bad.sm", "PUSH 1\n")
        underflow = self.write("underflow.sm", "WRITE\n")
        for args in (("run-sm", bad_json), ("run-ast", bad_ast), ("compile", bad_json),
                     ("run-smfile", dup), ("run-smfile", missing), ("run-smfile", bad_sm),
                     ("run-smfile", underflow)):
            with self.subTest(args):
                p = cli(args[0], args[1], "0")
                self.assertEqual(p.returncode, 2, p.stderr)


if __name__ == "__main__":
    unittest.main()
