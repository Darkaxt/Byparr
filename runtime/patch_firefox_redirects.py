"""
Fix overridden POST upload streams across Gecko 307/308 redirects.

The bundled Juggler observer stores method/header overrides, but discards the
body after the initial intercepted channel. Gecko then redirects a GET-derived
POST channel without an upload stream. Preserve that body only on HTTP redirects
which preserve the method. This changes our image, never the production image.

The modified browser source retains its original MPL-2.0 header. Exact anchors
make incompatible upstream browser revisions fail at build time for review.
"""

from pathlib import Path


def patch_source(source: str) -> str:
    """Apply the narrow observer change, requiring every expected anchor."""
    changes = [
        (
            "    this._overriddenHeadersForRedirect = redirectedFrom?._overriddenHeadersForRedirect;",
            """    this._overriddenHeadersForRedirect = redirectedFrom?._overriddenHeadersForRedirect;
    // Custom Byparr: retain an overridden upload only while the method survives.
    this._overriddenPostData = redirectedFrom &&
      httpChannel.requestMethod === redirectedFrom.httpChannel.requestMethod
      ? redirectedFrom._overriddenPostData : undefined;
    if (redirectedFrom && this._overriddenHeadersForRedirect) {
      const crossOrigin = httpChannel.URI.prePath !== redirectedFrom.httpChannel.URI.prePath;
      const dropsBody = httpChannel.requestMethod !== redirectedFrom.httpChannel.requestMethod &&
        ["GET", "HEAD"].includes(httpChannel.requestMethod);
      this._overriddenHeadersForRedirect = this._overriddenHeadersForRedirect.filter(header => {
        const name = header.name.toLowerCase();
        return !(crossOrigin && name === "authorization") &&
          !(dropsBody && ["content-type", "content-length"].includes(name));
      });
    }""",
        ),
        (
            "    if (postData !== undefined)\n      setPostData(this.httpChannel, postData, headers);",
            """    if (postData !== undefined) {
      this._overriddenPostData = postData;
      setPostData(this.httpChannel, postData, headers);
    }""",
        ),
        (
            "    if (this._overriddenHeadersForRedirect)\n      overrideRequestHeaders(httpChannel, this._overriddenHeadersForRedirect);\n    else if (this._pageNetwork)\n      appendExtraHTTPHeaders(httpChannel, this._pageNetwork.combinedExtraHTTPHeaders());",
            """    if (this._overriddenHeadersForRedirect)
      overrideRequestHeaders(httpChannel, this._overriddenHeadersForRedirect);
    else if (this._pageNetwork)
      appendExtraHTTPHeaders(httpChannel, this._pageNetwork.combinedExtraHTTPHeaders());
    // Custom Byparr: restore the overridden upload at http-on-modify-request,
    // after Gecko has finished initializing the redirect channel's method.
    if (redirectedFrom && this._overriddenPostData !== undefined &&
        [307, 308].includes(redirectedFrom.httpChannel.responseStatus))
      setPostData(httpChannel, this._overriddenPostData,
                  this._overriddenHeadersForRedirect);""",
        ),
    ]
    for before, after in changes:
        if source.count(before) != 1:
            message = "Bundled Firefox observer changed; review the POST redirect patch before building"
            raise RuntimeError(message)
        source = source.replace(before, after)
    return source


def main() -> None:
    """Patch the one bundled engine during an image build."""
    roots = list(
        Path("/cache/invisible-playwright").glob(
            "firefox-*/chrome/juggler/content/NetworkObserver.js"
        )
    )
    if len(roots) != 1:
        message = "Expected exactly one bundled Firefox observer"
        raise RuntimeError(message)
    target = roots[0]
    target.write_text(patch_source(target.read_text()))
    print("Applied custom Byparr POST redirect upload fix")  # noqa: T201 - build evidence


if __name__ == "__main__":
    main()
