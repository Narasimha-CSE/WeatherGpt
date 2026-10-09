/* WeatherGPT — login / register / phone behaviour */
(function () {
    "use strict";
    const body = document.body;
    const card = document.getElementById("card");
    const panes = document.getElementById("panes");
    const forms = {
        login: document.getElementById("loginForm"),
        register: document.getElementById("registerForm"),
        phone: document.getElementById("phoneForm"),
    };
    const EMAIL = /^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$/;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const URLS = {
        login:    { send: "/auth/login",       verify: "/auth/verify",       resend: "/auth/resend",     id: "email" },
        register: { send: "/auth/register",    verify: "/auth/verify",       resend: "/auth/resend",     id: "email" },
        phone:    { send: "/auth/phone/send",  verify: "/auth/phone/verify", resend: "/auth/phone/send", id: "phone" },
    };

    /* ---------- tabs ---------- */
    function sizePanes() {
        const active = forms[body.dataset.mode];
        if (active) panes.style.height = active.scrollHeight + "px";
    }
    function setMode(mode, push) {
        if (!forms[mode]) return;
        body.dataset.mode = mode;
        document.querySelectorAll(".tab").forEach((t) => {
            const on = t.dataset.tab === mode;
            t.classList.toggle("on", on);
            t.setAttribute("aria-selected", on);
        });
        document.title = mode === "login" ? "WeatherGPT — Log in" : mode === "register" ? "WeatherGPT — Create an account" : "WeatherGPT — Continue with phone";
        if (push && (mode === "login" || mode === "register")) history.replaceState(null, "", "/" + mode);
        requestAnimationFrame(sizePanes);
        setTimeout(() => { const f = forms[mode].querySelector("input"); if (f && !reduce && window.innerWidth > 700) f.focus({ preventScroll: true }); }, 450);
    }
    document.querySelectorAll(".tab").forEach((t) => t.addEventListener("click", () => setMode(t.dataset.tab, true)));
    document.querySelectorAll("[data-go]").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); setMode(a.dataset.go, true); }));
    document.getElementById("phoneBtn").addEventListener("click", () => setMode("phone", false));
    window.addEventListener("resize", sizePanes);
    setMode(body.dataset.mode || "login", false);
    setTimeout(sizePanes, 300);

    /* ---------- validation helpers ---------- */
    function fieldOf(form, name) { return form.elements[name].closest(".field"); }
    function setErr(form, name, msg) {
        const f = fieldOf(form, name);
        f.classList.toggle("bad", !!msg);
        f.classList.toggle("good", !msg && !!form.elements[name].value);
        f.querySelector(".err").textContent = msg || "";
    }
    function showMsg(form, msg) {
        const el = form.querySelector(".form-msg");
        el.classList.remove("show"); void el.offsetWidth;
        el.textContent = msg || "";
        el.classList.toggle("show", !!msg);
        sizePanes();
    }
    function validate(form, mode) {
        const e = form.elements;
        let ok = true;
        const check = (name, msg) => { setErr(form, name, msg); if (msg) ok = false; };
        if (form.dataset.step === "otp") {
            check("otp", /^\d{6}$/.test(e.otp.value.trim()) ? "" : "Enter the 6-digit code.");
        } else if (mode === "phone") {
            const digits = e.phone.value.replace(/\D/g, "");
            check("phone", digits.length >= 10 && digits.length <= 15 ? "" : "Enter a valid phone number.");
            const n = e.name.value.trim();
            check("name", n && n.length < 2 ? "Name must be at least 2 characters." : "");
        } else {
            if (mode === "register") check("name", e.name.value.trim().length < 2 ? "Enter your name." : "");
            check("email", EMAIL.test(e.email.value.trim()) ? "" : "Enter a valid email address.");
        }
        sizePanes();
        return ok;
    }
    Object.values(forms).forEach((form) => {
        form.querySelectorAll("input").forEach((inp) => inp.addEventListener("input", () => {
            const f = inp.closest(".field");
            if (f && f.classList.contains("bad")) { f.classList.remove("bad"); sizePanes(); }
            showMsg(form, "");
        }));
    });

    /* ---------- storm / success effects ---------- */
    const rain = document.getElementById("rain");
    for (let i = 0; i < 70; i++) {
        const d = document.createElement("i");
        d.style.left = Math.random() * 100 + "%";
        d.style.animationDuration = 0.5 + Math.random() * 0.5 + "s";
        d.style.animationDelay = -Math.random() + "s";
        d.style.opacity = 0.3 + Math.random() * 0.6;
        rain.appendChild(d);
    }
    function storm() { if (reduce) return; body.classList.add("stormy"); setTimeout(() => body.classList.remove("stormy"), 1500); }

    /* Registration finished: show the done mark, then open the login section with the email filled in. */
    function afterRegister(email) {
        card.classList.remove("done");
        body.classList.remove("burst");
        const reg = forms.register;
        leaveOtpStep(reg, false);
        reg.elements.name.value = ""; reg.elements.email.value = "";
        reg.querySelectorAll(".field").forEach((f) => f.classList.remove("good", "bad"));
        const login = forms.login;
        login.elements.email.value = email;
        login.querySelector(".sub").textContent = "Account created. Tap Send OTP to log in with " + email + ".";
        setMode("login", true);
        setTimeout(() => { login.querySelector(".btn").focus({ preventScroll: true }); sizePanes(); }, 500);
    }
    function success(name, url, mode, email) {
        const first = String(name || "").split(" ")[0] || "there";
        const title = document.getElementById("successTitle");
        const text = document.getElementById("successText");
        if (mode === "register") {
            title.textContent = "Account created, " + first + "!";
            text.textContent = "Opening the login section…";
        } else {
            title.textContent = "Welcome, " + first + "!";
            text.textContent = "Loading your weather…";
        }
        card.classList.add("done");
        body.classList.add("burst");
        if (mode === "register") { setTimeout(() => afterRegister(email), reduce ? 300 : 2200); return; }
        setTimeout(() => { window.location.href = url || "/"; }, reduce ? 200 : 1500);
    }

    /* ---------- OTP step (email and phone) ---------- */
    const timers = new WeakMap();
    const idInput = (form) => form.elements[URLS[form.dataset.pane].id];
    function countdown(form, seconds) {
        const btn = form.querySelector("[data-resend]");
        clearInterval(timers.get(form));
        let left = seconds;
        btn.disabled = true; btn.textContent = "Resend OTP in " + left + "s";
        const t = setInterval(() => {
            left -= 1;
            if (left <= 0) { clearInterval(t); btn.disabled = false; btn.textContent = "Resend OTP"; }
            else btn.textContent = "Resend OTP in " + left + "s";
        }, 1000);
        timers.set(form, t);
    }
    function enterOtpStep(form) {
        const e = form.elements;
        form.dataset.step = "otp";
        form.querySelector("[data-otp-box]").classList.add("show");
        idInput(form).readOnly = true;
        if (e.name) e.name.readOnly = true;
        form.querySelector(".btn-t").textContent = "Verify & log in";
        if (form.dataset.pane === "register") form.querySelector(".btn-t").textContent = "Verify & create account";
        const via = form.dataset.pane === "phone" ? "SMS to " : "email to ";
        form.querySelector(".sub").textContent = "We sent a 6-digit code by " + via + idInput(form).value.trim() + ". It expires in 10 minutes.";
        e.otp.value = "";
        countdown(form, 30);
        sizePanes();
        setTimeout(() => e.otp.focus({ preventScroll: true }), 150);
    }
    function leaveOtpStep(form, focus) {
        const e = form.elements;
        clearInterval(timers.get(form));
        form.dataset.step = "email";
        form.querySelector("[data-otp-box]").classList.remove("show");
        idInput(form).readOnly = false;
        if (e.name) e.name.readOnly = false;
        e.otp.value = "";
        setErr(form, "otp", "");
        const btnT = form.querySelector(".btn-t");
        btnT.textContent = btnT.dataset.label;
        const sub = form.querySelector(".sub");
        sub.textContent = sub.dataset.sub || sub.textContent;
        showMsg(form, "");
        sizePanes();
        if (focus !== false) idInput(form).focus({ preventScroll: true });
    }
    Object.values(forms).forEach((form) => {
        const mode = form.dataset.pane;
        form.dataset.step = "email";
        form.elements.otp.addEventListener("input", (ev) => { ev.target.value = ev.target.value.replace(/\D/g, "").slice(0, 6); });
        form.querySelector("[data-change]").addEventListener("click", () => leaveOtpStep(form));
        form.querySelector("[data-resend]").addEventListener("click", async () => {
            showMsg(form, "");
            const payload = mode === "phone"
                ? { phone: form.elements.phone.value.trim(), name: form.elements.name.value.trim() }
                : { email: form.elements.email.value.trim() };
            try {
                const res = await fetch(URLS[mode].resend, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
                let data = {};
                try { data = await res.json(); } catch (_) { /* non-JSON */ }
                if (!res.ok) { showMsg(form, data.error || "Could not resend the code."); return; }
                countdown(form, 30);
            } catch (err) { showMsg(form, "Can't reach the server. Check your connection and try again."); }
        });
    });

    /* ---------- submit ---------- */
    async function submit(form, mode) {
        if (!validate(form, mode)) { storm(); return; }
        const btn = form.querySelector(".btn");
        const e = form.elements;
        const verifying = form.dataset.step === "otp";
        const remember = e.remember ? e.remember.checked : true;
        let payload;
        if (mode === "phone") {
            payload = verifying
                ? { phone: e.phone.value.trim(), otp: e.otp.value.trim(), remember: remember }
                : { phone: e.phone.value.trim(), name: e.name.value.trim() };
        } else if (verifying) {
            payload = { email: e.email.value.trim(), otp: e.otp.value.trim(), remember: remember };
        } else {
            payload = mode === "login" ? { email: e.email.value.trim() } : { name: e.name.value.trim(), email: e.email.value.trim() };
        }
        btn.classList.add("loading");
        showMsg(form, "");
        try {
            const res = await fetch(verifying ? URLS[mode].verify : URLS[mode].send, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
            let data = {};
            try { data = await res.json(); } catch (_) { /* non-JSON */ }
            if (!res.ok) {
                if (data.fields) Object.entries(data.fields).forEach(([k, v]) => { if (form.elements[k]) setErr(form, k, v); });
                showMsg(form, data.error || "Something went wrong. Please try again.");
                storm();
                return;
            }
            if (!verifying) { enterOtpStep(form); return; }
            success(data.user.name, data.redirect, data.registered ? "register" : mode, data.user.email);
        } catch (err) {
            showMsg(form, "Can't reach the server. Check your connection and try again.");
            storm();
        } finally {
            btn.classList.remove("loading");
        }
    }
    Object.entries(forms).forEach(([mode, form]) => form.addEventListener("submit", (ev) => { ev.preventDefault(); submit(form, mode); }));

    /* ---------- Google / Facebook errors coming back from the server ---------- */
    const SOCIAL = {
        google_not_configured: "Google sign-in isn't set up yet. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env.",
        facebook_not_configured: "Facebook sign-in isn't set up yet. Add FACEBOOK_APP_ID and FACEBOOK_APP_SECRET to .env.",
        denied: "Sign-in was cancelled.",
        unverified: "That account's email isn't verified, so it can't be used to sign in.",
        failed: "Social sign-in failed. Please try again.",
        unknown_provider: "Unknown sign-in provider.",
    };
    const socialErr = new URLSearchParams(location.search).get("social_error");
    if (socialErr) {
        setTimeout(() => { showMsg(forms[body.dataset.mode] || forms.login, SOCIAL[socialErr] || SOCIAL.failed); storm(); }, 500);
        history.replaceState(null, "", location.pathname);
    }

    /* ---------- showcase: parallax + typed chat ---------- */
    const wrap = document.getElementById("floatWrap");
    if (wrap && !reduce) {
        window.addEventListener("pointermove", (ev) => {
            const x = (ev.clientX / window.innerWidth - 0.5) * 2, y = (ev.clientY / window.innerHeight - 0.5) * 2;
            wrap.querySelectorAll(".fcard").forEach((c) => {
                const d = Number(c.dataset.depth || 10);
                c.style.transform = "translate(" + (x * d).toFixed(1) + "px," + (y * d).toFixed(1) + "px)";
            });
        });
    }
    const q = document.getElementById("typedQ"), a = document.getElementById("typedA");
    const script = [
        ["Will it rain today?", "Yes, around 5 PM. Take an umbrella ☔"],
        ["Guntur lo ivala varsham padutunda?", "అవును, సాయంత్రం వర్షం పడే అవకాశం ఉంది."],
        ["Should I spray my chilli crop?", "Spray before 10 AM, winds are calm."],
    ];
    function type(el, text, speed) {
        return new Promise((resolve) => {
            el.textContent = ""; el.classList.add("typing");
            let i = 0;
            const t = setInterval(() => {
                el.textContent = text.slice(0, ++i);
                if (i >= text.length) { clearInterval(t); el.classList.remove("typing"); resolve(); }
            }, speed);
        });
    }
    const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
    (async function loop() {
        if (!q || !a) return;
        if (reduce) { q.textContent = script[0][0]; a.textContent = script[0][1]; return; }
        let i = 0;
        while (document.body) {
            const [qq, aa] = script[i++ % script.length];
            a.textContent = ""; await type(q, qq, 38); await sleep(450); await type(a, aa, 32); await sleep(2600);
        }
    })();
})();
