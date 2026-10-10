# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

import json
from genlayer import *


class Probe(gl.Contract):
    probe_results: str

    def __init__(self):
        info = {}
        info["gl_dir"] = [x for x in dir(gl) if not x.startswith("__")]
        info["has_message_raw"] = hasattr(gl, "message_raw")
        if hasattr(gl, "message_raw"):
            mr = getattr(gl, "message_raw")
            info["message_raw_type"] = type(mr).__name__
            if isinstance(mr, dict):
                info["message_raw_keys"] = list(mr.keys())
                info["message_raw_repr"] = str(mr)
            else:
                info["message_raw_dir"] = [x for x in dir(mr) if not x.startswith("__")]

        info["gl_message_dir"] = [x for x in dir(gl.message) if not x.startswith("__")]
        for k in ["datetime", "timestamp", "time", "date"]:
            info[f"gl_message_has_{k}"] = hasattr(gl.message, k)
            if hasattr(gl.message, k):
                val = getattr(gl.message, k)
                info[f"gl_message_{k}_val"] = str(val)
                info[f"gl_message_{k}_type"] = type(val).__name__

        info["has_nondet"] = hasattr(gl, "nondet")
        if hasattr(gl, "nondet"):
            info["nondet_dir"] = [x for x in dir(gl.nondet) if not x.startswith("__")]
            info["has_web"] = hasattr(gl.nondet, "web")
            if hasattr(gl.nondet, "web"):
                info["web_dir"] = [x for x in dir(gl.nondet.web) if not x.startswith("__")]

        self.probe_results = json.dumps(info)

    @gl.public.view
    def get_results(self) -> str:
        return self.probe_results

    @gl.public.write
    def probe_consensus(self) -> None:
        info = json.loads(self.probe_results)
        write_info = {}
        write_info["has_message_raw"] = hasattr(gl, "message_raw")
        if hasattr(gl, "message_raw"):
            mr = getattr(gl, "message_raw")
            write_info["message_raw_type"] = type(mr).__name__
            if isinstance(mr, dict):
                write_info["message_raw_keys"] = list(mr.keys())
                write_info["message_raw_repr"] = str(mr)
            else:
                write_info["message_raw_dir"] = [x for x in dir(mr) if not x.startswith("__")]

        write_info["gl_message_dir"] = [x for x in dir(gl.message) if not x.startswith("__")]
        for k in ["datetime", "timestamp", "time", "date"]:
            write_info[f"gl_message_has_{k}"] = hasattr(gl.message, k)
            if hasattr(gl.message, k):
                val = getattr(gl.message, k)
                write_info[f"gl_message_{k}_val"] = str(val)
                write_info[f"gl_message_{k}_type"] = type(val).__name__

        import urllib.parse
        split_res = urllib.parse.urlsplit("https://example.com/test")
        write_info["urllib_hostname"] = split_res.hostname

        def probe_web() -> str:
            web_features = []
            if hasattr(gl.nondet, "web"):
                web_dir = [x for x in dir(gl.nondet.web) if not x.startswith("__")]
                web_features.append(f"web_dir:{','.join(web_dir)}")
                if hasattr(gl.nondet.web, "render"):
                    try:
                        render_res = gl.nondet.web.render("https://en.wikipedia.org/wiki/Apollo_11", mode="text")
                        web_features.append(f"render_type:{type(render_res).__name__}:len:{len(str(render_res))}")
                    except Exception as e:
                        web_features.append(f"render_err:{str(e)[:50]}")
                if hasattr(gl.nondet.web, "get"):
                    try:
                        get_res = gl.nondet.web.get("https://en.wikipedia.org/wiki/Apollo_11")
                        web_features.append(f"get_type:{type(get_res).__name__}:status:{get_res.status}")
                    except Exception as e:
                        web_features.append(f"get_err:{str(e)[:50]}")
            return "|".join(web_features)

        try:
            eq_val = gl.eq_principle.strict_eq(probe_web)
            write_info["probe_web_result"] = eq_val
        except Exception as e:
            write_info["probe_web_err"] = str(e)

        info["write_call"] = write_info
        self.probe_results = json.dumps(info)
