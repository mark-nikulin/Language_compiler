

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


def where(text, pos):
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
