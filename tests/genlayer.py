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


class GlWebResponse:
    def __init__(self, status=200, body=b""):
        self.status = status
        self.body = body


class GlWeb:
    def __init__(self):
        self.pages = {}
        self.render_handler = None
        self.get_handler = None

    def render(self, url, mode="text"):
        if self.render_handler:
            return self.render_handler(url, mode)
        if url in self.pages:
            return self.pages[url]
        return ""

    def get(self, url):
        if self.get_handler:
            return self.get_handler(url)
        if url in self.pages:
            return GlWebResponse(status=200, body=self.pages[url].encode("utf-8"))
        return GlWebResponse(status=404, body=b"Not found")


class GlNondet:
    def __init__(self):
        self.prompt_handler = None
        self.web = GlWeb()

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
    message_raw = {"datetime": "2026-10-10T12:00:00Z"}
    get_contract_at = None


gl = GlMock()
TreeMap = dict
Address = str
