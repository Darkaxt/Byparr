"""
Keep Byparr bindings out of frames and honor main-document CSP bypass.

The installed Gecko adapter applies bypassCSP after a document's policy may
already exist. Clear that policy through Gecko's privileged API before trusted
evaluation, only when bypass was explicitly requested for the main document.
No website JavaScript receives this privileged API. Exact source anchors make
an incompatible browser update fail the image build for review.
"""

from pathlib import Path


def patch_source(source: str) -> str:
    """Patch only the bundled adapter; retain its original MPL-2.0 header."""
    changes = [
        (
            "  addBinding(name, script) {\n    Cu.exportFunction",
            """  addBinding(name, script) {
    // Custom Byparr: the request helper belongs only to the main document.
    if (name === '__playwright__binding__' &&
        (!this._domWindow || this._domWindow !== this._domWindow.top))
      return;
    Cu.exportFunction""",
        ),
        (
            "  async evaluateFunction(functionText, args, exceptionDetails = {}) {",
            """  _applyByparrCSPBypass() {
    if (this._domWindow && this._domWindow === this._domWindow.top &&
        this._domWindow.docShell.bypassCSPEnabled)
      this._domWindow.document.policyContainer?.initFromCSP(null);
  }

  async evaluateFunction(functionText, args, exceptionDetails = {}) {
    this._applyByparrCSPBypass();""",
        ),
        (
            "  evaluateScriptSafely(script) {",
            """  evaluateScriptSafely(script) {
    // The driver installs its binding controller through an initialization script.
    if ((script.includes('__byparr_main_') ||
         script.includes('__playwright__binding__controller__')) &&
        this._domWindow && this._domWindow !== this._domWindow.top)
      return;
    this._applyByparrCSPBypass();""",
        ),
    ]
    for before, after in changes:
        if source.count(before) != 1:
            message = "Bundled Firefox adapter changed; review the scripting patch before building"
            raise RuntimeError(message)
        source = source.replace(before, after)
    return source


def main() -> None:
    """Apply the reviewed adapter change during an offline image build."""
    roots = list(
        Path("/cache/invisible-playwright").glob(
            "firefox-*/chrome/juggler/content/content/Runtime.js"
        )
    )
    if len(roots) != 1:
        message = "Expected exactly one bundled Firefox runtime adapter"
        raise RuntimeError(message)
    target = roots[0]
    target.write_text(patch_source(target.read_text()))
    print("Applied custom Byparr main-document scripting fix")  # noqa: T201


if __name__ == "__main__":
    main()
