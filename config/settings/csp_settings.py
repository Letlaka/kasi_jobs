from __future__ import annotations

from .env import env

_csp_default_src = env.list("CSP_DEFAULT_SRC")
_csp_script_src = env.list("CSP_SCRIPT_SRC")
_csp_style_src = env.list("CSP_STYLE_SRC")
_csp_img_src = env.list("CSP_IMG_SRC")
_csp_font_src = env.list("CSP_FONT_SRC")
_csp_connect_src = env.list("CSP_CONNECT_SRC")
_csp_frame_src = env.list("CSP_FRAME_SRC")
_csp_include_nonce_in = env("CSP_INCLUDE_NONCE_IN")
_csp_report_only = env.bool("CSP_REPORT_ONLY")
_csp_report_uri = env("CSP_REPORT_URI")


_CSP_TEMP_TO_DIRECTIVE = {
    "_csp_default_src": "default-src",
    "_csp_script_src": "script-src",
    "_csp_style_src": "style-src",
    "_csp_img_src": "img-src",
    "_csp_font_src": "font-src",
    "_csp_connect_src": "connect-src",
    "_csp_frame_src": "frame-src",
}

CSP: dict[str, list[str]] = {}
for temp_name, directive in _CSP_TEMP_TO_DIRECTIVE.items():
    temp_val = locals().get(temp_name)
    if temp_val:
        CSP[directive] = list(temp_val)

if _csp_report_uri:
    CSP.setdefault("report-uri", [])
    CSP["report-uri"].append(_csp_report_uri)

_csp_directives = CSP.copy() if isinstance(CSP, dict) else {}

if _csp_report_only:
    CONTENT_SECURITY_POLICY_REPORT_ONLY = {"DIRECTIVES": _csp_directives}
else:
    CONTENT_SECURITY_POLICY = {"DIRECTIVES": _csp_directives}
