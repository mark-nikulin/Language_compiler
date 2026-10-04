# Ошибки делятся на два вида:
#   L0Error     - ошибка самой программы L0 (ввод, выполнение). Текст дословно как у эталона.
#   FormatError - битые входные данные (JSON, AST, SM-код). Это ошибка инструмента, код возврата 2.


class L0Error(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


class FormatError(Exception):
    pass


class JsonError(FormatError):
    pass


class AstError(FormatError):
    pass


class SmError(FormatError):
    pass


class AsmError(FormatError):
    pass


class StackError(FormatError):
    pass


def where(text, pos):
    # Позиция в тексте в виде "(строка:столбец)", обе с единицы.
    line = 1
    col = 1
    i = 0
    while i < pos:
        if text[i] == "\n":
            line += 1
            col = 1
        else:
            col += 1
        i += 1
    return "(%d:%d)" % (line, col)
