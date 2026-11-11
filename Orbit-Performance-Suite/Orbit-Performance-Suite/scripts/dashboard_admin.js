module.exports = async function (context, commands) {
    const isPreprod = process.env.PERF_ENV === "preprod";
    const baseUrl = isPreprod ? "https://preprod.orbit.pieq.ai" : "https://orbit.pieq.ai";
    const email = "kesav.r@pieq.ai";
    const password = "Ab@12345";
    const log = context.log;

    const date = new Date();
    date.setDate(date.getDate() - 1);

    const formattedDate = [
        date.getFullYear(),
        String(date.getMonth() + 1).padStart(2, "0"),
        String(date.getDate()).padStart(2, "0")
    ].join("-");

    async function fillInput(id, value) {
        await commands.wait.byId(id, 60000);
        await commands.click.byId(id);
        await commands.wait.byTime(300);
        await commands.addText.byId(value, id);

        let actual = await commands.js.run(
            `return document.getElementById(${JSON.stringify(id)})?.value || "";`
        );

        if (actual !== value) {
            log.info(`Selenium fill missed for #${id}, using JS fallback`);
            actual = await commands.js.run(`
                return (function () {
                    const el = document.getElementById(${JSON.stringify(id)});
                    if (!el) throw new Error("Element not found: ${id}");
                    el.focus();
                    const proto = window.HTMLInputElement.prototype;
                    const setter = Object.getOwnPropertyDescriptor(proto, "value").set;
                    setter.call(el, ${JSON.stringify(value)});
                    el.dispatchEvent(new Event("input", { bubbles: true }));
                    el.dispatchEvent(new Event("change", { bubbles: true }));
                    return el.value;
                })();
            `);
        }

        if (actual !== value) {
            throw new Error(`Failed to fill #${id}. Expected "${value}", got "${actual}"`);
        }
        log.info(`Filled #${id}`);
    }

    await commands.navigate(baseUrl + "/");

    // Orbit Keycloak (pieq-theme-v4): email and password are on the same page
    await commands.wait.byId("username", 60000);
    await commands.wait.byId("password", 60000);
    await fillInput("username", email);
    await fillInput("password", password);
    await commands.wait.byTime(500);
    await commands.click.byIdAndWait("kc-login");

    const pages = [
        { name: "Airport Monitor", url: `${baseUrl}/airport-monitor?date=${formattedDate}` },
        { name: "JFK Airport Monitor Operational", url: `${baseUrl}/airport-monitor/airport/JFK?date=${formattedDate}` },
        { name: "JFK Airport Monitor Live Arrivals", url: `${baseUrl}/airport-monitor/live-arrivals/JFK?date=${formattedDate}` },
        { name: "Region Master", url: `${baseUrl}/region-master` },
        { name: "POE Master", url: `${baseUrl}/poe-master` },
        { name: "Campaign Master", url: `${baseUrl}/campaigns` },
        { name: "User Management", url: `${baseUrl}/user-management` }
    ];

    for (const page of pages) {
        await commands.measure.start(page.name);
        await commands.navigate(page.url);
        await commands.wait.byTime(5000);
        await commands.measure.stop();
    }
};
