// Copyright (c) 2026, Quark Cyber Systems FZC and contributors
// For license information, please see license.txt

frappe.ui.form.on("HDS Support Settings", {
	refresh(frm) {
		if (frm.doc.client_id) {
			frm.dashboard.add_indicator(
				__("Registered with Hub: {0}", [frm.doc.client_id]),
				"green"
			);
		} else {
			frm.dashboard.add_indicator(__("Not registered"), "orange");

			frm.add_custom_button(__("Connect to Hub"), function () {
				connect_to_hub(frm);
			}).addClass("btn-primary");
		}

		frm.add_custom_button(__("Open support@quarkcs.com User"), function () {
			frappe.set_route("Form", "User", "support@quarkcs.com");
		});
	},
});

function connect_to_hub(frm) {
	if (!frm.doc.qcs_hub_url) {
		frappe.msgprint({
			title: __("Hub URL missing"),
			message: __("Set the Hub URL and save before connecting."),
			indicator: "orange",
		});
		return;
	}

	const d = new frappe.ui.Dialog({
		title: __("Connect to Hub"),
		fields: [
			{
				fieldname: "info",
				fieldtype: "HTML",
				options: `<p>${__(
					"Generates fresh API credentials for support@quarkcs.com and sends them to the Hub. No manual copy-paste needed."
				)}</p>`,
			},
			{
				fieldname: "enrollment_key",
				fieldtype: "Password",
				label: __("Enrollment Key"),
				reqd: 1,
				description: __("From the Hub's HDS Hub Settings."),
			},
		],
		primary_action_label: __("Connect"),
		primary_action({ enrollment_key }) {
			d.hide();
			frappe.dom.freeze(__("Connecting to Hub..."));
			frappe
				.call({
					method: "helpdesk_client.api.enroll_with_hub",
					args: { enrollment_key },
				})
				.then((r) => {
					frappe.dom.unfreeze();
					if (r.message && r.message.client_id) {
						frappe.show_alert({
							message: __("Connected to Hub as {0}", [r.message.client_id]),
							indicator: "green",
						});
						frm.reload_doc();
					}
				})
				.catch(() => frappe.dom.unfreeze());
		},
	});
	d.show();
}
