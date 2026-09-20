// Copyright (c) 2023, Wahni IT Solutions Pvt. Ltd. and Contributors
// MIT License. See license.txt
// Recording part referrenced from https://github.com/TylerPottsDev/yt-js-screen-recorder

frappe.provide("genie");

genie.chunks = [];
genie.blob = null;
genie.blobURL = null;

genie.SupportTicket = class SupportTicket {
	constructor() {
		if (!frappe.boot.genie_support_enabled) {
			frappe.msgprint(__("Ticket raising is not enabled for this site."));
			return;
		}
		this.init_config();
		this.setup_dialog();
		this.dialog.show();
		this.maybe_start_tour();
	}

	setup_dialog() {
		this.dialog = new frappe.ui.Dialog({
			title: __("Support Ticket"),
			size: "large",
			minimizable: true,
			static: true,
			fields: [
				{
					fieldname: "ticket_title",
					label: __("Title"),
					fieldtype: "Data",
					reqd: 1
				},
				{
					fieldname: "ticket_description",
					label: __("Description"),
					fieldtype: "Text Editor",
					reqd: 1
				},
				{
					fieldtype: "Section Break",
					label: __("Screen Recording")
				},
				{
					fieldname: "record_screen",
					label: __("Start Recording"),
					fieldtype: "Button",
					click: () => {
						if (this.recorder && this.recorder.state == "recording") {
							this.stopRecording();
						} else {
							this.startRecording();
						}
					}
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "view_recording",
					label: __("View Recording"),
					fieldtype: "Button",
					hidden: 1,
					click: () => {
						window.open(genie.blobURL, "_blank");
					}
				},
				{
					fieldname: "clear_recording",
					label: __("Clear Recording"),
					fieldtype: "Button",
					hidden: 1,
					click: () => {
						if (this.recorder && this.recorder.state == "recording") {
							frappe.show_alert({
								indicator: "red",
								message: __("Please stop the recording before clearing.")
							});
							return;
						}

						genie.chunks = [];
						genie.blob = null;
						genie.blobURL = null;

						this.dialog.set_df_property("record_screen", "label", "Start Recording")
						this.dialog.set_df_property("view_recording", "hidden", 1);
						this.dialog.set_df_property("clear_recording", "hidden", 1);

						frappe.show_alert({
							indicator: "green",
							message: __("Screen recording have been cleared.")
						});
					}
				},
				{
					fieldtype: "Section Break",
					label: __("Screenshots")
				},
				{
					fieldname: "capture_screenshot",
					label: __("Capture Screenshot"),
					fieldtype: "Button",
					click: () => this.captureScreenshot()
				},
				{ fieldtype: "Column Break" },
				{
					fieldname: "add_images",
					label: __("Add Images"),
					fieldtype: "Button",
					click: () => this.pickImages()
				},
				{ fieldtype: "Section Break" },
				{
					fieldname: "screenshot_list",
					fieldtype: "HTML"
				}
			],
			primary_action_label: __("Raise Ticket"),
			primary_action: (values) => {
				if (this.recorder && this.recorder.state == "recording") {
					frappe.show_alert({
						indicator: "red",
						message: __("Please stop the recording before raising the ticket.")
					});
					return;
				}
				this.raise_ticket(values);
			},
			secondary_action_label: __("Cancel"),
			secondary_action: () => {
				if (this.recorder && this.recorder.state == "recording") {
					frappe.show_alert({
						indicator: "red",
						message: __("Please stop the recording before cancelling.")
					});
					return;
				}
				this.end_tour();
				this.dialog.hide();
			}
		});

		this.dialog.$wrapper.find(".modal-dialog").css("z-index", 1);

		// Make "minimize" discoverable: a labelled chip instead of a bare icon.
		this.dialog
			.get_minimize_btn()
			.attr("title", __("Minimize — the ticket stays open while you work"))
			.css({
				border: "1px solid var(--border-color)",
				"border-radius": "6px",
				padding: "2px 8px",
				"margin-right": "8px",
				display: "inline-flex",
				"align-items": "center",
				gap: "4px",
			})
			.prepend(`<span style="font-size: var(--text-xs);">${__("Minimize")}</span>`);

		// A "?" that replays the how-to tour on demand.
		const help = document.createElement("button");
		help.type = "button";
		help.className = "btn btn-default btn-sm";
		help.textContent = "?";
		help.title = __("How does this work?");
		Object.assign(help.style, { borderRadius: "50%", marginLeft: "8px", padding: "2px 9px" });
		help.addEventListener("click", () => this.start_tour());
		this.dialog.header.find(".modal-title").after(help);
	}

	setIndicator(indicator) {
		this.dialog.header
			.find(".indicator")
			.css({ width: "1rem", height: '1rem'})
			.removeClass()
			.addClass("indicator " + (indicator || "hidden"));
	}

	async raise_ticket(values) {
		if (this.inUpload) return;

		this.inUpload = true;
		let screen_recording = null;
		if (genie.blob) {
			frappe.show_alert({
				indicator: "yellow",
				message: __("Raising ticket. Please wait..."),
			})
			screen_recording = await genie.UploadFile(genie.blob).catch(() => null);
			if (!screen_recording) {
				frappe.show_alert({
					indicator: "red",
					message: __("Error raising ticket. Please try again."),
				})
				this.inUpload = false;
				return;
			}
		}

		const screenshot_urls = [];
		for (const shot of this.screenshots) {
			const url = await genie.UploadFile(shot.blob, shot.name).catch(() => null);
			if (!url) {
				frappe.show_alert({
					indicator: "red",
					message: __("Error uploading screenshot {0}. Please try again.", [shot.name]),
				});
				this.inUpload = false;
				return;
			}
			screenshot_urls.push(url);
		}

		this.inUpload = false;
		frappe.call({
			method: "helpdesk_client.utils.support.create_ticket",
			type: "POST",
			args: {
				"title": values.ticket_title,
				"description": values.ticket_description,
				"screen_recording": screen_recording,
				"screenshots": JSON.stringify(screenshot_urls)
			},
			freeze: true,
			freeze_message: __("Creating ticket..."),
			callback: (r) => {
				if (!r.exc && r.message) {
					frappe.show_alert({
						indicator: "green",
						message: __("Ticket submitted"),
					});
					this.end_tour();
					this.dialog.hide();
					// No Helpdesk ID yet — support picks the ticket up on its
					// next cycle and the ID lands on the local record.
					frappe.msgprint(
						__("Your ticket {0} has been submitted and will be picked up by support shortly. You will be notified as it progresses.",
							[`<a href="/app/support-ticket/${encodeURIComponent(r.message)}">${r.message}</a>`])
					)
				}
			}
		});
	}

	init_config() {
		this.stream = null;
		this.audio = null;
		this.mixedStream = null;
		this.recorder = null;
		this.recordedVideo = null;
		this.inUpload = false;

		genie.chunks = [];
		genie.blob = null;
		genie.blobURL = null;
		this.screenshots = [];

		// Fall back to 50MB when the setting is 0/unset — otherwise the cap
		// is 0 bytes and recording stops on the first chunk.
		const maxFileSizeMB = frappe.boot.genie_max_file_size || 50;
		this.maxFileSizeInBytes = maxFileSizeMB * 1024 * 1024;
		this.sizeWarning = (maxFileSizeMB / 4) * 1024 * 1024;
		this.nextWarningSize = this.sizeWarning;
	}

	maybe_start_tour() {
		// Auto-run until the user unticks "Show this tour next time".
		try {
			if (localStorage.getItem("genie_ticket_tour_hidden")) return;
		} catch (err) {
			return;
		}
		setTimeout(() => this.start_tour(), 400);
	}

	start_tour() {
		const d = this.dialog;
		const steps = [
			{
				el: () => d.get_field("ticket_title").$wrapper[0],
				title: __("1. Title"),
				text: __("A short summary of the problem — e.g. “Printer offline”."),
			},
			{
				el: () => d.get_field("ticket_description").$wrapper[0],
				title: __("2. Description"),
				text: __("What happened, what you expected, and any error message you saw."),
			},
			{
				el: () => d.get_field("record_screen").$wrapper[0],
				title: __("3. Screen Recording (optional)"),
				text: __("Record your screen while you reproduce the issue — support sees exactly what you see."),
			},
			{
				el: () => d.get_field("capture_screenshot").$wrapper[0],
				title: __("4. Screenshots (optional)"),
				text: __("Capture your screen as images, or attach existing ones. Add as many as you need."),
			},
			{
				el: () => d.get_primary_btn()[0],
				title: __("5. Raise Ticket"),
				text: __("Submit! Support picks it up within minutes — you'll get a notification as it progresses."),
			},
		].filter((step) => {
			try {
				return !!step.el();
			} catch (err) {
				return false;
			}
		});
		if (!steps.length) return;

		this.end_tour(); // clear any previous run
		let idx = 0;
		let highlighted = null;

		const pop = document.createElement("div");
		pop.id = "genie-tour-popover";
		Object.assign(pop.style, {
			position: "fixed",
			zIndex: "3000",
			maxWidth: "300px",
			background: "var(--bg-color, #fff)",
			border: "1px solid var(--border-color, #ddd)",
			borderRadius: "8px",
			boxShadow: "0 6px 24px rgba(0,0,0,0.25)",
			padding: "12px 14px",
			fontSize: "var(--text-md)",
		});
		document.body.appendChild(pop);

		const unhighlight = () => {
			if (highlighted) {
				highlighted.style.boxShadow = "";
				highlighted.style.borderRadius = "";
				highlighted = null;
			}
		};

		const show = (i) => {
			idx = i;
			const step = steps[i];
			const el = step.el();
			unhighlight();
			el.scrollIntoView({ block: "center", behavior: "smooth" });
			el.style.boxShadow = "0 0 0 3px var(--primary, #171717)";
			el.style.borderRadius = "6px";
			highlighted = el;

			const last = i === steps.length - 1;
			pop.innerHTML = `
				<div style="font-weight:600; margin-bottom:4px;">${step.title}</div>
				<div style="margin-bottom:10px;">${step.text}</div>
				${last ? `<label style="display:flex; gap:6px; align-items:center; margin-bottom:10px; font-size: var(--text-sm);">
					<input type="checkbox" id="genie-tour-again" checked> ${__("Show this tour next time")}
				</label>` : ""}
				<div style="display:flex; justify-content:space-between; align-items:center;">
					<span style="color:var(--text-muted); font-size:var(--text-sm);">${i + 1}/${steps.length}</span>
					<span>
						${i > 0 ? `<button type="button" class="btn btn-default btn-xs" data-act="back">${__("Back")}</button>` : ""}
						<button type="button" class="btn btn-primary btn-xs" data-act="next">${last ? __("Done") : __("Next")}</button>
						${last ? "" : `<button type="button" class="btn btn-default btn-xs" data-act="skip">${__("Skip")}</button>`}
					</span>
				</div>`;

			// place near the element (below if room, else above)
			const r = el.getBoundingClientRect();
			const below = r.bottom + 12 + 160 < window.innerHeight;
			pop.style.top = below ? `${r.bottom + 10}px` : "";
			pop.style.bottom = below ? "" : `${window.innerHeight - r.top + 10}px`;
			pop.style.left = `${Math.max(16, Math.min(r.left, window.innerWidth - 320))}px`;

			pop.querySelectorAll("button[data-act]").forEach((btn) => {
				btn.addEventListener("click", () => {
					const act = btn.dataset.act;
					if (act === "back") return show(idx - 1);
					if (act === "skip") return this.end_tour();
					if (idx === steps.length - 1) {
						const again = pop.querySelector("#genie-tour-again");
						try {
							if (again && !again.checked) {
								localStorage.setItem("genie_ticket_tour_hidden", "1");
							} else {
								localStorage.removeItem("genie_ticket_tour_hidden");
							}
						} catch (err) {
							// private mode — just skip persisting
						}
						return this.end_tour();
					}
					show(idx + 1);
				});
			});
		};

		this._tour_cleanup = () => {
			unhighlight();
			pop.remove();
		};
		show(0);
	}

	end_tour() {
		if (this._tour_cleanup) {
			this._tour_cleanup();
			this._tour_cleanup = null;
		}
	}

	async captureScreenshot() {
		// One still frame via the same permission flow as recording.
		try {
			const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
			const video = document.createElement("video");
			video.srcObject = stream;
			await video.play();
			const canvas = document.createElement("canvas");
			canvas.width = video.videoWidth;
			canvas.height = video.videoHeight;
			canvas.getContext("2d").drawImage(video, 0, 0);
			stream.getTracks().forEach((t) => t.stop());
			canvas.toBlob((blob) => {
				if (!blob) return;
				this.screenshots.push({ blob: blob, name: `screenshot-${Date.now()}.png` });
				this.renderScreenshots();
			}, "image/png");
		} catch (err) {
			// user cancelled the picker — not an error
			console.warn(err);
		}
	}

	pickImages() {
		const input = document.createElement("input");
		input.type = "file";
		input.accept = "image/*";
		input.multiple = true;
		input.onchange = () => {
			for (const f of input.files) {
				this.screenshots.push({ blob: f, name: f.name });
			}
			this.renderScreenshots();
		};
		input.click();
	}

	renderScreenshots() {
		const wrapper = this.dialog.get_field("screenshot_list").$wrapper;
		wrapper.empty();
		this.screenshots.forEach((shot, i) => {
			const url = URL.createObjectURL(shot.blob);
			const $thumb = $(`
				<div style="display:inline-block; position:relative; margin:4px;">
					<img src="${url}" style="height:64px; border-radius:4px; border:1px solid var(--border-color);">
					<span data-idx="${i}" title="${__("Remove")}" style="position:absolute; top:-6px; right:-6px; cursor:pointer; background:var(--bg-color); border:1px solid var(--border-color); border-radius:50%; width:18px; height:18px; line-height:16px; text-align:center; font-size:11px;">&times;</span>
				</div>`);
			$thumb.find("span").on("click", () => {
				this.screenshots.splice(i, 1);
				this.renderScreenshots();
			});
			wrapper.append($thumb);
		});
	}

	async setupStream() {
		try {
			this.stream = await navigator.mediaDevices.getDisplayMedia({
				video: true
			});

			this.audio = await navigator.mediaDevices.getUserMedia({
				audio: {
					echoCancellation: true,
					noiseSuppression: true,
					sampleRate: 44100,
				},
			});
		} catch (err) {
			console.error(err)
		}
	}

	async startRecording() {
		await this.setupStream();

		if (this.stream && this.audio) {
			genie.chunks = [];
			this.mixedStream = new MediaStream([...this.stream.getTracks(), ...this.audio.getTracks()]);
			this.recorder = new MediaRecorder(this.mixedStream);
			this.recorder.ondataavailable = (e) => {
				genie.chunks.push(e.data);
				this.checkFileSize();
			};
			this.recorder.onstop = this.handleStop.bind(this);
			this.recorder.start(1000);

			this.setIndicator("spinner-grow text-danger align-self-center mr-2");
			this.dialog.set_df_property("record_screen", "label", "Stop Recording");
			this.dialog.set_df_property("view_recording", "hidden", 1);
			this.dialog.set_df_property("clear_recording", "hidden", 1);

			// Stop cleanly when the user ends it from the browser's own
			// "Stop sharing" bar instead of our button.
			const track = this.stream.getVideoTracks()[0];
			track && track.addEventListener("ended", () => {
				if (this.recorder && this.recorder.state === "recording") {
					this.stopRecording();
				}
			});

			// Get out of the user's way: minimize the dialog so they can
			// reproduce the issue anywhere in the app while recording.
			this.end_tour();
			if (!this.dialog.is_minimized) {
				this.dialog.toggle_minimize();
			}
			this.show_recording_pill();
		} else {
			console.warn('No stream available.');
			frappe.show_alert({
				indicator: "red",
				message: __("Error starting screen recording. Please try again.")
			});
		}
	}

	stopRecording() {
		this.recorder.stop();
		this.hide_recording_pill();
		this.setIndicator();
		this.dialog.set_df_property("record_screen", "label", "Start Recording")
		this.dialog.set_df_property("view_recording", "hidden", 0);
		this.dialog.set_df_property("clear_recording", "hidden", 0);

		// Bring the ticket back so the user can review and submit.
		if (this.dialog.is_minimized) {
			this.dialog.toggle_minimize();
		}
		frappe.show_alert({
			indicator: "green",
			message: __(`Recording captured. Review it with "View Recording", then raise the ticket.`)
		})
	}

	show_recording_pill() {
		this.hide_recording_pill();

		if (!document.getElementById("genie-rec-style")) {
			const style = document.createElement("style");
			style.id = "genie-rec-style";
			style.textContent = `
				@keyframes genie-rec-pulse {
					0% { box-shadow: 0 0 0 0 rgba(224, 49, 49, 0.55); }
					70% { box-shadow: 0 0 0 8px rgba(224, 49, 49, 0); }
					100% { box-shadow: 0 0 0 0 rgba(224, 49, 49, 0); }
				}`;
			document.head.appendChild(style);
		}

		const pill = document.createElement("div");
		pill.id = "genie-rec-pill";
		Object.assign(pill.style, {
			position: "fixed",
			// top-centre: Chrome parks its own "sharing your screen" bar at
			// the bottom-centre, and the two must never overlap.
			top: "70px",
			left: "50%",
			transform: "translateX(-50%)",
			zIndex: "2000",
			display: "flex",
			alignItems: "center",
			gap: "12px",
			background: "rgba(20, 20, 20, 0.92)",
			color: "#fff",
			padding: "10px 12px 10px 18px",
			borderRadius: "999px",
			boxShadow: "0 8px 30px rgba(0, 0, 0, 0.35)",
			backdropFilter: "blur(6px)",
			fontSize: "13px",
		});

		const dot = document.createElement("span");
		Object.assign(dot.style, {
			width: "10px",
			height: "10px",
			borderRadius: "50%",
			background: "#e03131",
			animation: "genie-rec-pulse 1.6s ease-out infinite",
		});

		const label = document.createElement("span");
		label.textContent = __("Recording");

		const timer = document.createElement("span");
		timer.textContent = "00:00";
		Object.assign(timer.style, { fontVariantNumeric: "tabular-nums", opacity: "0.8" });
		const started = Date.now();
		this._rec_timer = setInterval(() => {
			const secs = Math.floor((Date.now() - started) / 1000);
			const mm = String(Math.floor(secs / 60)).padStart(2, "0");
			const ss = String(secs % 60).padStart(2, "0");
			timer.textContent = `${mm}:${ss}`;
		}, 1000);

		const stop = document.createElement("button");
		stop.type = "button";
		stop.textContent = __("Stop Recording");
		Object.assign(stop.style, {
			border: "none",
			borderRadius: "999px",
			padding: "6px 14px",
			background: "#e03131",
			color: "#fff",
			fontWeight: "600",
			cursor: "pointer",
		});
		stop.addEventListener("click", () => {
			if (this.recorder && this.recorder.state === "recording") {
				this.stopRecording();
			}
		});

		pill.append(dot, label, timer, stop);
		document.body.appendChild(pill);

		// Draggable: if the pill ever covers something the user needs,
		// they just move it. Grab anywhere except the Stop button.
		pill.style.cursor = "grab";
		pill.addEventListener("mousedown", (e) => {
			if (e.target === stop) return;
			e.preventDefault();
			pill.style.cursor = "grabbing";
			const rect = pill.getBoundingClientRect();
			const dx = e.clientX - rect.left;
			const dy = e.clientY - rect.top;
			pill.style.transform = "none";
			const move = (ev) => {
				pill.style.left = `${Math.max(8, Math.min(ev.clientX - dx, window.innerWidth - rect.width - 8))}px`;
				pill.style.top = `${Math.max(8, Math.min(ev.clientY - dy, window.innerHeight - rect.height - 8))}px`;
			};
			const up = () => {
				pill.style.cursor = "grab";
				document.removeEventListener("mousemove", move);
				document.removeEventListener("mouseup", up);
			};
			document.addEventListener("mousemove", move);
			document.addEventListener("mouseup", up);
		});
	}

	hide_recording_pill() {
		if (this._rec_timer) {
			clearInterval(this._rec_timer);
			this._rec_timer = null;
		}
		const pill = document.getElementById("genie-rec-pill");
		pill && pill.remove();
	}

	checkFileSize() {
		// Ignore the final chunk that flushes after we've already stopped,
		// so the "exceeded" alert doesn't fire twice.
		if (!this.recorder || this.recorder.state !== "recording") return;

		const totalSize = genie.chunks.reduce((acc, chunk) => acc + chunk.size, 0);

		if (totalSize >= this.maxFileSizeInBytes) {
			frappe.show_alert({
				indicator: "red",
				message: __("Screen recording size has exceeded the maximum allowed size. Recording has been stopped.")
			});
			this.stopRecording();
			return;
		}


		if (totalSize >= this.nextWarningSize) {
			frappe.show_alert({
				indicator: "yellow",
				message: __(`Screen recording size has exceeded ${(totalSize / (1024 * 1024)).toFixed(1)}MB.`)
			});
			this.nextWarningSize += this.sizeWarning;
		}
	}

	handleStop(e) {
		// MediaRecorder emits WebM — label it honestly so players don't choke.
		genie.blob = new Blob(genie.chunks, { 'type': 'video/webm' });
		genie.blobURL = URL.createObjectURL(genie.blob);

		this.stream.getTracks().forEach((track) => track.stop());
		this.audio && this.audio.getTracks().forEach((track) => track.stop());
	}
}
