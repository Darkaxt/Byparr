// Caller-owned recipe; the Byparr implementation has no Uptodown-specific code.
// Pass {fileId: "1220892131"} as scriptArgs for the documented Showly example.
async args => {
    // The button exists before the async site bundle has installed its handler.
    // Wait for the actual load event, not a delay or network-idle heuristic.
    if (document.readyState !== "complete") {
        await new Promise(resolve => window.addEventListener("load", resolve, {once: true}));
    }
    if (typeof window.turnstile?.execute !== "function") {
        throw new Error("Website challenge SDK did not initialize");
    }
    const button = document.querySelector("#detail-download-button");
    if (!button) throw new Error("Download button missing");
    const appId = button.getAttribute("data-app-id");
    const fileId = button.getAttribute("data-file-id");
    const onlyXapk = button.getAttribute("data-only-xapk") ?? "0";
    if (!/^\d+$/.test(appId ?? "") || !/^\d+$/.test(fileId ?? "")) {
        throw new Error("Invalid build identifiers");
    }
    if (fileId !== args.fileId || button.getAttribute("data-download-version") !== args.fileId) {
        throw new Error("Requested build changed");
    }
    if (!location.pathname.endsWith(`/download/${args.fileId}-x`)) {
        throw new Error("Requested build page changed");
    }
    // Derive identifiers/options from the live DOM; let the site submit its token.
    // Do not build, extract or replay a token-bearing POST in the caller.
    const resolutionUrl = `${location.origin}/ajax/app/${appId}/file/${fileId}/download-url`;
    await byparr.watchResponse("resolution", {method: "POST", url: resolutionUrl});
    await byparr.watchRequest("attachment", {
        method: "GET", urlPrefix: "https://dw.uptodown.com/dwn/", abort: true
    });
    await byparr.finishWith("attachment");
    await byparr.click("#detail-download-button");
    const response = await byparr.waitFor("resolution");
    if (response.status !== 200 || response.body?.success !== 1 || !response.body?.data?.downloadURL) {
        throw new Error("Website rejected link resolution");
    }
    // onlyXapk is a page option, not a promise about the returned archive format.
    void onlyXapk;
    return await byparr.waitFor("attachment");
}
