#!/usr/bin/env python3
# Командная строка. Коды возврата: 0 - успех, 1 - ошибка программы L0,
# 2 - битый AST, JSON или SM-код, неверный вызов или файл не читается,
# 3 - check нашёл расхождение.

import sys

from l0.assembler import assemble
from l0.ast_builder import build_program
from l0.ast_interp import run_ast
from l0.compiler import compile_program
from l0.errors import FormatError
from l0.json_reader import parse_json
from l0.opcodes import format_program, parse_sm
from l0.sm import run_sm

USAGE = """usage:
  main.py compile    program.json
  main.py run-sm     program.json [INPUT]
  main.py run-ast    program.json [INPUT]
  main.py check      program.json [INPUT]
  main.py run-smfile code.sm      [INPUT]
Without INPUT the input is read from stdin."""


def read_file(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def load_ast(path):
    return build_program(parse_json(read_file(path)))


def input_text(argv):
    return argv[3] if len(argv) > 3 else sys.stdin.read()


def show(output, message):
    print("; ".join([str(x) for x in output]))
    if message is not None:
        print(message, file=sys.stderr)
        return 1
    return 0


def main(argv):
    if len(argv) < 3:
        print(USAGE, file=sys.stderr)
        return 2
    command = argv[1]
    path = argv[2]
    try:
        if command == "compile":
            print(format_program(compile_program(load_ast(path))))
            return 0
        if command == "run-ast":
            program = load_ast(path)
            return show(*run_ast(program, input_text(argv)))
        if command == "run-sm":
            program = assemble(compile_program(load_ast(path)))
            return show(*run_sm(program, input_text(argv)))
        if command == "run-smfile":
            program = assemble(parse_sm(read_file(path)))
            return show(*run_sm(program, input_text(argv)))
        if command == "check":
            tree = load_ast(path)
            program = assemble(compile_program(tree))
            text = input_text(argv)
            by_ast = run_ast(tree, text)
            by_sm = run_sm(program, text)
            if by_ast == by_sm:
                print("OK")
                return 0
            print("DIFF")
            print("  ast: %s / %s" % ("; ".join([str(x) for x in by_ast[0]]), by_ast[1]))
            print("  sm:  %s / %s" % ("; ".join([str(x) for x in by_sm[0]]), by_sm[1]))
            return 3
    except FormatError as err:
        print("error: %s" % err, file=sys.stderr)
        return 2
    except OSError as err:
        print("error: %s" % err, file=sys.stderr)
        return 2
    print('unknown command "%s"\n%s' % (command, USAGE), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
