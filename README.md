# L0: компилятор AST → стековая машина

```
Текст ──«мордочка»──► AST (JSON) ──компилятор──► SM-код ──ассемблер──► программа SM ──► Output
                          │
                          └──────────── эталонный AST-интерпретатор ───────────────► Output
```

Оба пути обязаны давать одинаковый вывод и одинаковые ошибки. Внешних библиотек нет, рекурсии нет:
везде явный стек (`l0/stack.py`) и циклы `while`.

## Запуск

```
python3 main.py compile    program.json           # напечатать SM-код
python3 main.py run-sm     program.json "1, 3"    # AST → SM → выполнение
python3 main.py run-ast    program.json "1, 3"    # эталонный интерпретатор AST
python3 main.py check      program.json "1, 3"    # оба пути, OK / DIFF
python3 main.py run-smfile code.sm      "1, 3"    # выполнить SM-код из текстового файла
python3 -m unittest discover tests                # тесты
```

Без аргумента ввода он читается из stdin. Коды возврата: 0 — успех, 1 — ошибка L0
(сообщение в stderr), 2 — битый JSON, AST или SM-код, неверный вызов или файл не читается,
3 — `check` нашёл расхождение.

## Модули

| Файл | Что делает |
|---|---|
| `l0/stack.py` | `Stack`: массив + `sp` |
| `l0/json_reader.py` | разбор JSON, открытые контейнеры на стеке |
| `l0/ast_nodes.py`, `l0/ast_builder.py` | классы узлов и JSON → узлы |
| `l0/input_reader.py` | разбор поля Input, очередь ввода |
| `l0/arith.py` | коды операций, `/` и `%` как в OCaml, `INT_BITS` |
| `l0/memory.py` | память переменных: массив значений + массив флагов |
| `l0/opcodes.py` | `Opcode`, `Instr`, печать и разбор текста SM |
| `l0/compiler.py` | AST → `Instr` (стек задач `COMPILE` / `EMIT`) |
| `l0/assembler.py` | метки → адреса, переменные → номера ячеек |
| `l0/sm.py` | стековая машина, цикл fetch–execute |
| `l0/ast_interp.py` | эталонный интерпретатор AST |
| `l0/errors.py` | `L0Error` (ошибки программы) и `FormatError` (битые входные данные) |
| `l0/config.py` | `KEEP_OUTPUT_ON_ERROR`: оставлять ли вывод при ошибке |

## Схема компиляции

```
Const n            CONST n
Var x              LD x
BinOp(op, l, r)    [l] [r] BINOP op
Read x             READ ; ST x
Write e            [e] ; WRITE
Assign x = e       [e] ; ST x
Seq(a, b)          [a] [b]
Skip               —
If(c, t, e)        [c] ; JZ L_else_N ; [t] ; JMP L_end_M ; LABEL L_else_N ; [e] ; LABEL L_end_M
While(c, b)        JMP L_while_cond_M ; LABEL L_while_body_N ; [b] ;
                   LABEL L_while_cond_M ; [c] ; JNZ L_while_body_N
DoWhile(b, c)      LABEL L_do_body_N ; [b] ; [c] ; JNZ L_do_body_N
```

Как в `sm.cpp`, каждая метка получает свой номер из общего счётчика: у одного `while`
это, например, `L_while_body_0` и `L_while_cond_1`.

## Отличия SM от `sm.cpp`

- Метки разрешаются ассемблером до запуска, а не через `resolve_label()` на каждом переходе.
- Переменные хранятся в ячейках по номеру, а не в `unordered_map` по имени.
- `LD` неинициализированной переменной — ошибка `L0.State.Undefined_variable`; в `sm.cpp` получится 0.
- Деление на 0 — ошибка `Division_by_zero`; в C++ это неопределённое поведение.
- Повтор метки — ошибка ассемблера; в `sm.cpp` молча побеждает последняя.

## Формат SM-кода

Одна инструкция на строку, аргумент через пробел, `#` — комментарий:

```
CONST 0
ST x
JMP L_while_cond_0
LABEL L_while_body_0
...
```

Формат совпадает с `sm.cpp`: SM-код этого компилятора исполняется эталонной машиной без изменений.
