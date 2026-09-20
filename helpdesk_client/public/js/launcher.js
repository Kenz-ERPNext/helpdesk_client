// Copyright (c) 2026, Quark Cyber Systems FZC and Contributors
// Adds a persistent "Raise a Ticket" launcher to the desk so users can open
// the support-ticket dialog without the console. Only shows when ticket
// raising is enabled in HDS Support Settings (frappe.boot.genie_support_enabled).

frappe.provide("genie");

$(document).on("app_ready", function () {
	genie.setup_ticket_launcher();
});

genie.setup_ticket_launcher = function () {
	if (!frappe.boot.genie_support_enabled) return;
	if (document.getElementById("genie-support-fab")) return;

	const mk = (id, label, bottom, onclick) => {
		const b = document.createElement("button");
		b.id = id;
		b.type = "button";
		b.className = "btn btn-default btn-sm";
		b.textContent = label;
		Object.assign(b.style, {
			position: "fixed",
			right: "24px",
			bottom: bottom,
			zIndex: "1030",
			borderRadius: "20px",
			padding: "6px 14px",
			boxShadow: "0 2px 10px rgba(0, 0, 0, 0.2)",
			display: "none",
			transition: "opacity 0.15s",
		});
		b.addEventListener("click", () => {
			toggle(false);
			onclick();
		});
		document.body.appendChild(b);
		return b;
	};

	const actions = [
		mk("genie-raise-ticket-btn", __("Raise a Ticket"), "76px", () => new genie.SupportTicket()),
		mk("genie-my-tickets-btn", __("My Tickets"), "116px", () => frappe.set_route("List", "Support Ticket")),
	];

	const fab = document.createElement("button");
	fab.id = "genie-support-fab";
	fab.type = "button";
	fab.className = "btn btn-primary btn-sm";
	fab.title = __("Support");
	fab.innerHTML = `<svg class="icon icon-sm" style="vertical-align: middle;"><use href="#icon-message"></use></svg>`;
	Object.assign(fab.style, {
		position: "fixed",
		right: "24px",
		bottom: "24px",
		zIndex: "1030",
		borderRadius: "50%",
		width: "44px",
		height: "44px",
		boxShadow: "0 2px 10px rgba(0, 0, 0, 0.25)",
	});
	let open = false;
	const toggle = (state) => {
		open = state === undefined ? !open : state;
		actions.forEach((a) => (a.style.display = open ? "block" : "none"));
		fab.style.transform = open ? "rotate(90deg)" : "";
	};
	fab.addEventListener("click", () => toggle());
	document.body.appendChild(fab);
};
