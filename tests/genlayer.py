import types

class GlVM:
    class UserError(Exception):
        pass

class GlPublic:
    @staticmethod
    def view(fn):
        return fn

    @staticmethod
    def write(fn):
        return fn

class GlEqPrinciple:
    @staticmethod
    def strict_eq(fn):
        return fn()

class GlNondet:
    def __init__(self):
        self.prompt_handler = None

    def exec_prompt(self, p, response_format=""):
        if self.prompt_handler:
            return self.prompt_handler(p)
        return ""

class GlMessage:
    class SenderAddress:
        as_hex = "0x1111111111111111111111111111111111111111"
        def __str__(self):
            return self.as_hex
    sender_address = SenderAddress()

class GlMock:
    Contract = object
    vm = GlVM()
    public = GlPublic()
    eq_principle = GlEqPrinciple()
    nondet = GlNondet()
    message = GlMessage()
    get_contract_at = None

gl = GlMock()
TreeMap = dict
Address = str
