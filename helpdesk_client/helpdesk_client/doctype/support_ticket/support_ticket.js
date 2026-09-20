// Copyright (c) 2026, Wahni IT Solutions Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Support Ticket", {
	refresh: function (frm) {
		if (!frm.is_new() && !["Closed", "Resolved"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Reply"), () => reply_to_support(frm)).addClass(
				"btn-primary"
			);
		}
		if (!["Closed", "Resolved"].includes(frm.doc.status) && !frm.doc.close_requested) {
			frm.add_custom_button(__("Close Ticket"), async () => {
				await frappe.call({
					method: "helpdesk_client.helpdesk_client.doctype.support_ticket.support_ticket.request_close",
					args: { ticket: frm.doc.name },
				});
				frappe.show_alert({ indicator: "green", message: __("Close requested — support will confirm shortly.") });
				frm.reload_doc();
			});
		}
		if (frm.doc.close_requested && frm.doc.status !== "Closed") {
			frm.dashboard.set_headline(__("Close requested — awaiting confirmation from support."));
		}
		// Status is pushed here by the Hub over MCP — there is nothing for
		// the client to fetch, so no "Refresh Status" button.
		if (frm.doc.status === "Pending") {
			frm.dashboard.set_headline(
				__("Submitted — support will pick this up shortly.")
			);
		}
		if (frm.doc.status === "Replied") {
			frm.dashboard.set_headline(
				__("Support replied — see the comments below. Use Reply to answer.")
			);
		}
	},
});

function reply_to_support(frm) {
	const d = new frappe.ui.Dialog({
		title: __("Reply to Support"),
		fields: [
			{
				fieldname: "message",
				fieldtype: "Small Text",
				label: __("Your message"),
				reqd: 1,
			},
			{
				fieldname: "file_url",
				fieldtype: "Attach",
				label: __("Screenshot or video (optional)"),
				description: __(
					"Images and screen recordings both work. Support receives it with your reply."
				),
			},
		],
		primary_action_label: __("Send"),
		primary_action({ message, file_url }) {
			d.hide();
			frappe
				.call({
					method: "helpdesk_client.helpdesk_client.doctype.support_ticket.support_ticket.post_reply",
					args: { ticket: frm.doc.name, message, file_url },
				})
				.then(() => {
					frappe.show_alert({
						indicator: "green",
						message: __("Sent — support will see it shortly."),
					});
					frm.reload_doc();
				});
		},
	});
	d.show();
}
