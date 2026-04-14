// Copyright (c) 2024, Your Company and contributors
// For license information, please see license.txt

const APP = "stridenex_app";

// ─────────────────────────────────────────────────────────────────────────────
// Slot Calendar Styles
// ─────────────────────────────────────────────────────────────────────────────

function _inject_styles() {
    if (document.getElementById("msb-slot-styles")) return;

    const css = `
#msb-slot-overlay {
    position: fixed; inset: 0; z-index: 9999;
    background: rgba(15, 17, 26, 0.72);
    backdrop-filter: blur(4px);
    display: flex; align-items: center; justify-content: center;
    animation: msb-fade-in 0.18s ease;
}
@keyframes msb-fade-in { from { opacity: 0 } to { opacity: 1 } }

#msb-slot-panel {
    background: #fff;
    border-radius: 16px;
    width: min(96vw, 860px);
    max-height: 88vh;
    display: flex; flex-direction: column;
    box-shadow: 0 32px 80px rgba(0,0,0,0.28);
    overflow: hidden;
    font-family: 'DM Sans', 'Segoe UI', sans-serif;
    animation: msb-slide-up 0.22s cubic-bezier(.22,.68,0,1.2);
}
@keyframes msb-slide-up {
    from { transform: translateY(32px); opacity: 0 }
    to   { transform: translateY(0);    opacity: 1 }
}
.msb-header {
    background: linear-gradient(135deg, #1e2a4a 0%, #2e3f6f 100%);
    color: #fff;
    padding: 20px 24px 16px;
    display: flex; align-items: flex-start; justify-content: space-between;
    flex-shrink: 0;
}
.msb-header h2 { margin: 0 0 4px; font-size: 18px; font-weight: 700; letter-spacing: -0.3px; }
.msb-header p  { margin: 0; font-size: 13px; opacity: .75; }
.msb-close-btn {
    background: rgba(255,255,255,0.15); border: none; cursor: pointer;
    color: #fff; border-radius: 8px; width: 32px; height: 32px;
    font-size: 18px; line-height: 1; display: flex; align-items: center;
    justify-content: center; transition: background .15s; flex-shrink: 0;
}
.msb-close-btn:hover { background: rgba(255,255,255,0.28); }
.msb-week-nav {
    display: flex; align-items: center; gap: 10px;
    padding: 14px 24px 10px;
    border-bottom: 1px solid #f0f0f4;
    flex-shrink: 0; background: #fafbfd;
}
.msb-week-label { flex: 1; text-align: center; font-size: 14px; font-weight: 600; color: #1e2a4a; }
.msb-nav-btn {
    background: #fff; border: 1.5px solid #e3e7f0;
    border-radius: 8px; width: 34px; height: 34px; cursor: pointer;
    font-size: 16px; color: #4a5568; display: flex;
    align-items: center; justify-content: center; transition: all .15s;
}
.msb-nav-btn:hover { background: #1e2a4a; color: #fff; border-color: #1e2a4a; }
.msb-nav-btn:disabled { opacity: .35; cursor: not-allowed; }
.msb-legend {
    display: flex; gap: 16px; align-items: center;
    padding: 8px 24px 10px; flex-shrink: 0; flex-wrap: wrap;
}
.msb-legend-item { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #6b7280; }
.msb-legend-dot  { width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0; }
.msb-legend-dot.available { background: #22c55e; }
.msb-legend-dot.booked    { background: #f59e0b; }
.msb-legend-dot.blocked   { background: #ef4444; }
.msb-calendar-scroll { flex: 1; overflow-y: auto; overflow-x: auto; padding: 0 24px 20px; }
.msb-days-grid {
    display: grid;
    grid-template-columns: repeat(7, minmax(96px, 1fr));
    gap: 10px; min-width: 640px; padding-top: 16px;
}
.msb-day-col { display: flex; flex-direction: column; gap: 6px; }
.msb-day-header {
    text-align: center; padding: 6px 4px; border-radius: 8px;
    font-size: 11px; font-weight: 700; letter-spacing: .5px;
    text-transform: uppercase; color: #6b7280; margin-bottom: 2px;
}
.msb-day-header.today { background: #1e2a4a; color: #fff; }
.msb-day-header span  { display: block; font-size: 18px; font-weight: 800; margin-bottom: 1px; color: inherit; }
.msb-day-header.today span { color: #fff; }
.msb-day-empty { font-size: 11px; color: #c0c4cc; text-align: center; padding: 14px 0; font-style: italic; }
.msb-slot {
    border-radius: 8px; padding: 8px 8px 7px;
    font-size: 11.5px; line-height: 1.3;
    border: 1.5px solid transparent;
    transition: transform .12s, box-shadow .12s, opacity .12s;
    position: relative; overflow: hidden;
}
.msb-slot-time  { font-weight: 700; display: block; font-size: 12px; }
.msb-slot-label { font-size: 10.5px; opacity: .75; display: block; margin-top: 1px; }
.msb-slot.available { background: #f0fdf4; border-color: #86efac; color: #166534; cursor: pointer; }
.msb-slot.available:hover {
    background: #22c55e; color: #fff; border-color: #16a34a;
    transform: translateY(-2px); box-shadow: 0 6px 16px rgba(34,197,94,.28);
}
.msb-slot.available:hover .msb-slot-label { opacity: .9; }
.msb-slot.booked {
    background: #fffbeb; border-color: #fcd34d; color: #92400e; cursor: default;
}
.msb-slot.booked::after {
    content: ''; position: absolute; inset: 0;
    background: repeating-linear-gradient(
        -45deg, transparent, transparent 4px,
        rgba(245,158,11,.10) 4px, rgba(245,158,11,.10) 8px
    );
}
.msb-slot.blocked { background: #fef2f2; border-color: #fca5a5; color: #991b1b; cursor: not-allowed; opacity: .85; }
.msb-slot.blocked::before { content: '🔒'; position: absolute; right: 5px; top: 4px; font-size: 10px; opacity: .6; }
.msb-confirm-bar {
    background: #f0fdf4; border-top: 1.5px solid #86efac;
    padding: 14px 24px;
    display: flex; align-items: center; gap: 14px;
    flex-shrink: 0; flex-wrap: wrap;
}
.msb-confirm-bar.hidden { display: none; }
.msb-confirm-info { flex: 1; }
.msb-confirm-info strong { display: block; font-size: 13.5px; color: #166534; }
.msb-confirm-info span   { font-size: 12px; color: #6b7280; }
.msb-topic-input {
    flex: 1; min-width: 180px; border: 1.5px solid #86efac;
    border-radius: 8px; padding: 8px 12px; font-size: 13px;
    outline: none; transition: border-color .15s;
}
.msb-topic-input:focus { border-color: #22c55e; }
.msb-confirm-btn {
    background: #22c55e; color: #fff; border: none; border-radius: 8px;
    padding: 9px 20px; font-size: 13px; font-weight: 700;
    cursor: pointer; transition: all .15s; white-space: nowrap;
}
.msb-confirm-btn:hover    { background: #16a34a; transform: translateY(-1px); }
.msb-confirm-btn:disabled { background: #9ca3af; cursor: not-allowed; transform: none; }
.msb-cancel-sel {
    background: none; border: 1.5px solid #e3e7f0; border-radius: 8px;
    padding: 8px 14px; font-size: 13px; cursor: pointer; color: #6b7280;
    transition: all .15s;
}
.msb-cancel-sel:hover { background: #f3f4f6; }
.msb-loading {
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; padding: 60px 0; gap: 14px;
    color: #6b7280; font-size: 14px;
}
.msb-spinner {
    width: 36px; height: 36px; border-radius: 50%;
    border: 3px solid #e3e7f0; border-top-color: #1e2a4a;
    animation: msb-spin .7s linear infinite;
}
@keyframes msb-spin { to { transform: rotate(360deg) } }
.msb-tooltip {
    position: absolute; bottom: calc(100% + 6px); left: 50%;
    transform: translateX(-50%);
    background: #1e2a4a; color: #fff;
    font-size: 11px; padding: 5px 9px; border-radius: 6px;
    white-space: nowrap; pointer-events: none; z-index: 10;
    opacity: 0; transition: opacity .15s;
    max-width: 180px; white-space: normal; text-align: center;
}
.msb-slot:hover .msb-tooltip { opacity: 1; }
`;
    const el = document.createElement("style");
    el.id = "msb-slot-styles";
    el.textContent = css;
    document.head.appendChild(el);
}


// ─────────────────────────────────────────────────────────────────────────────
// Slot Calendar Class
// ─────────────────────────────────────────────────────────────────────────────

class SlotCalendar {
    constructor(opts) {
        this.isReschedule = opts.isReschedule || false;
        this.mentor       = opts.mentor;
        this.student      = opts.student;
        this.offering     = opts.offering || null;   // ← new
        this.onBooked     = opts.onBooked || (() => {});
        this.weekOffset   = 0;
        this.calendarData = {};
        this.selectedSlot = null;
        this.$overlay     = null;
    }

    open() {
        _inject_styles();
        this._buildOverlay();
        document.body.appendChild(this.$overlay);
        this._loadWeek();
    }

    close() {
        this.$overlay && this.$overlay.remove();
        this.$overlay = null;
    }

    _weekDates(offset) {
        const today  = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - today.getDay() + 1 + offset * 7);
        const days = [];
        for (let i = 0; i < 7; i++) {
            const d = new Date(monday);
            d.setDate(monday.getDate() + i);
            days.push(d);
        }
        return days;
    }

    _fmt(date) { return date.toISOString().slice(0, 10); }

    _buildOverlay() {
        const div = document.createElement("div");
        div.id = "msb-slot-overlay";
        div.innerHTML = `
<div id="msb-slot-panel">
    <div class="msb-header">
        <div>
            <h2>📅 Book a Session</h2>
            <p>Select an available slot to book with <strong id="msb-mentor-name">${this.mentor}</strong></p>
        </div>
        <button class="msb-close-btn" id="msb-close-btn">✕</button>
    </div>
    <div class="msb-week-nav">
        <button class="msb-nav-btn" id="msb-prev-week" title="Previous week">‹</button>
        <div class="msb-week-label" id="msb-week-label">Loading…</div>
        <button class="msb-nav-btn" id="msb-next-week" title="Next week">›</button>
    </div>
    <div class="msb-legend">
        <div class="msb-legend-item"><div class="msb-legend-dot available"></div>Available – click to book</div>
        <div class="msb-legend-item"><div class="msb-legend-dot booked"></div>Already booked</div>
        <div class="msb-legend-item"><div class="msb-legend-dot blocked"></div>Blocked by mentor</div>
    </div>
    <div class="msb-calendar-scroll">
        <div class="msb-days-grid" id="msb-days-grid">
            <div class="msb-loading"><div class="msb-spinner"></div>Fetching availability…</div>
        </div>
    </div>
    <div class="msb-confirm-bar hidden" id="msb-confirm-bar">
        <div class="msb-confirm-info">
            <strong id="msb-sel-label">—</strong>
            <span>Click Confirm to book this slot</span>
        </div>
        <input class="msb-topic-input" id="msb-topic-input" placeholder="Session topic / notes…" />
        <button class="msb-cancel-sel" id="msb-cancel-sel">✕ Clear</button>
        <button class="msb-confirm-btn" id="msb-confirm-btn">✓ Confirm Booking</button>
    </div>
</div>`;
        this.$overlay = div;
        this._bindEvents();
    }

    _bindEvents() {
        const $ = (id) => this.$overlay.querySelector(`#${id}`);
        $("msb-close-btn").addEventListener("click", () => this.close());
        this.$overlay.addEventListener("click", (e) => { if (e.target === this.$overlay) this.close(); });
        $("msb-prev-week").addEventListener("click", () => { if (this.weekOffset <= 0) return; this.weekOffset--; this._loadWeek(); });
        $("msb-next-week").addEventListener("click", () => { this.weekOffset++; this._loadWeek(); });
        $("msb-cancel-sel").addEventListener("click", () => this._clearSelection());
        $("msb-confirm-btn").addEventListener("click", () => this._confirmBooking());
    }

    _updateNavState() {
        this.$overlay.querySelector("#msb-prev-week").disabled = this.weekOffset <= 0;
    }

    _loadWeek() {
        this._updateNavState();
        const days      = this._weekDates(this.weekOffset);
        const from_date = this._fmt(days[0]);
        const to_date   = this._fmt(days[6]);

        this.$overlay.querySelector("#msb-week-label").textContent =
            `${days[0].toLocaleDateString("en-IN", { day: "numeric", month: "short" })} – ` +
            `${days[6].toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}`;

        this.$overlay.querySelector("#msb-days-grid").innerHTML =
            `<div class="msb-loading"><div class="msb-spinner"></div>Fetching availability…</div>`;

        this._clearSelection();

        frappe.call({
            method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.get_slot_calendar`,
            args: { mentor: this.mentor, from_date, to_date, offering: this.offering || null },
            callback: ({ message: data }) => {
                this.calendarData = data || {};
                this._renderGrid(days);
            },
            error: () => {
                this.$overlay.querySelector("#msb-days-grid").innerHTML =
                    `<div class="msb-loading" style="color:#ef4444">⚠ Failed to load slots.</div>`;
            },
        });
    }

    _renderGrid(days) {
        const todayStr = this._fmt(new Date());
        const grid     = this.$overlay.querySelector("#msb-days-grid");
        grid.innerHTML = "";

        days.forEach((date) => {
            const dateStr = this._fmt(date);
            const isPast  = dateStr < todayStr;
            const isToday = dateStr === todayStr;
            const slots   = this.calendarData[dateStr] || [];

            const col = document.createElement("div");
            col.className = "msb-day-col";

            const hdr = document.createElement("div");
            hdr.className = "msb-day-header" + (isToday ? " today" : "");
            hdr.innerHTML = `<span>${date.getDate()}</span>${date.toLocaleDateString("en-IN", { weekday: "short" })}`;
            col.appendChild(hdr);

            if (!slots.length) {
                const empty = document.createElement("div");
                empty.className = "msb-day-empty";
                empty.textContent = "No slots";
                col.appendChild(empty);
            } else {
                slots.forEach((slot) => {
                    const effectiveStatus = (isPast && slot.status === "available") ? "past" : slot.status;
                    col.appendChild(this._buildSlotChip(dateStr, slot, effectiveStatus));
                });
            }
            grid.appendChild(col);
        });
    }

    _buildSlotChip(dateStr, slot, effectiveStatus) {
        const chip        = document.createElement("div");
        const now         = new Date();
        const slotDT      = new Date(dateStr + "T" + slot.from_time);
        const isPastTime  = dateStr === this._fmt(new Date()) && slotDT <= now;
        const finalStatus = isPastTime ? "past" : effectiveStatus;
        const displayClass = finalStatus === "past" ? "booked" : finalStatus;

        chip.className    = `msb-slot ${displayClass}`;
        chip.dataset.date = dateStr;
        chip.dataset.from = slot.from_time;
        chip.dataset.to   = slot.to_time;

        const fromFmt = slot.from_time.slice(0, 5);
        const toFmt   = slot.to_time.slice(0, 5);

        let label = "", tooltip = "";
        if (finalStatus === "past") {
            label = "Past"; tooltip = "Slot time has passed";
        } else if (effectiveStatus === "available" && !isPastTime) {
            label = "Click to book"; tooltip = `Available ${fromFmt}–${toFmt}`;
        } else if (slot.status === "booked") {
            label   = slot.student ? slot.student.split("@")[0] : "Booked";
            tooltip = slot.topic ? `Topic: ${slot.topic}` : "Session booked";
        } else if (slot.status === "blocked") {
            label   = "Blocked";
            tooltip = slot.reason ? `Reason: ${slot.reason}` : "Mentor unavailable";
        } else {
            label = "Past"; tooltip = "Slot has passed";
        }

        chip.innerHTML = `
            <span class="msb-slot-time">${fromFmt}–${toFmt}</span>
            <span class="msb-slot-label">${label}</span>
            <div class="msb-tooltip">${tooltip}</div>`;

        if (effectiveStatus === "available" && !isPastTime) {
            chip.addEventListener("click", () => this._selectSlot(dateStr, slot, chip));
        }
        return chip;
    }

    _selectSlot(dateStr, slot, chipEl) {
        this.$overlay.querySelectorAll(".msb-slot.selected-slot").forEach((el) => {
            el.classList.remove("selected-slot");
            el.style.cssText = "";
        });
        chipEl.style.background  = "#1e2a4a";
        chipEl.style.color       = "#fff";
        chipEl.style.borderColor = "#1e2a4a";
        chipEl.style.boxShadow   = "0 6px 20px rgba(30,42,74,.35)";
        chipEl.classList.add("selected-slot");
        this.selectedSlot = { date: dateStr, slot };

        const date    = new Date(dateStr + "T00:00:00");
        const formatted = date.toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" });
        this.$overlay.querySelector("#msb-sel-label").textContent =
            `${formatted}  ·  ${slot.from_time.slice(0,5)} – ${slot.to_time.slice(0,5)}`;
        this.$overlay.querySelector("#msb-confirm-bar").classList.remove("hidden");
        this.$overlay.querySelector("#msb-topic-input").focus();
    }

    _clearSelection() {
        this.selectedSlot = null;
        this.$overlay.querySelectorAll(".msb-slot.selected-slot").forEach((el) => {
            el.classList.remove("selected-slot");
            el.style.cssText = "";
        });
        this.$overlay.querySelector("#msb-confirm-bar").classList.add("hidden");
        this.$overlay.querySelector("#msb-topic-input").value = "";
    }

    _confirmBooking() {
        if (!this.selectedSlot) return;
        const { date, slot } = this.selectedSlot;

        // Reschedule path — no topic needed
        if (this.isReschedule) {
            this.onBooked(null, date, slot);
            return;
        }

        const input = this.$overlay.querySelector("#msb-topic-input");
        const topic = input ? input.value.trim() : "";

        if (!topic) {
            if (input) { input.style.borderColor = "#ef4444"; input.focus(); }
            frappe.show_alert({ message: __("Please enter a session topic."), indicator: "orange" });
            return;
        }
        input.style.borderColor = "#86efac";

        const btn = this.$overlay.querySelector("#msb-confirm-btn");
        btn.disabled    = true;
        btn.textContent = "Booking…";

        frappe.call({
            method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.book_slot`,
            args: {
                mentor:       this.mentor,
                student:      this.student,
                session_date: date,
                from_time:    slot.from_time,
                to_time:      slot.to_time,
                topic,
                offering:     this.offering,   // ← passed through
            },
            callback: ({ message }) => {
                frappe.show_alert({ message: __("Session booked! ID: {0}", [message.session_name]), indicator: "green" });
                this.onBooked(message.session_name, date, slot);
                this.close();
            },
            error: () => {
                btn.disabled    = false;
                btn.textContent = "✓ Confirm Booking";
            },
        });
    }
}


// ─────────────────────────────────────────────────────────────────────────────
// Frappe Form Controller
// ─────────────────────────────────────────────────────────────────────────────

frappe.ui.form.on("Mentor Session Booking", {

    setup(frm) {
        frm.set_query("mentor",  () => ({}));
        frm.set_query("student", () => ({}));
    },

// ── Inside frappe.ui.form.on("Mentor Session Booking" → refresh(frm) ────────
// Replace the existing refresh function with this:

    refresh(frm) {
        // ── existing code stays ───────────────────────────────────────
        _inject_styles();
        _set_status_indicator(frm);
        _render_action_buttons(frm);   // ← updated below
        _toggle_meeting_link(frm);

        frm.set_df_property("mentor", "read_only", !!frm.doc.offering);
        frm.set_df_property("priority", "read_only", 1);

        // ── Request stage indicator ───────────────────────────────────
        const reqStatus = frm.doc.mentor_request_status;
        if (reqStatus) {
            const colors = {
                "Pending":           "orange",
                "Accepted":          "green",
                "Declined":          "red",
                "Suggested Alt Time":"blue",
            };
            frm.page.set_indicator(
                __("Request: {0}", [reqStatus]),
                colors[reqStatus] || "grey"
            );
        }

        // ── 1:1 slot calendar ─────────────────────────────────────────
        const offeringType = frm.doc.offering_type;
        const is1on1 = !offeringType || offeringType === "1:1 Mentor Session";
        const isGroup = offeringType === "Group Session";

        if (is1on1 && (frm.is_new() || frm.doc.status === "Scheduled")
            && frm.doc.mentor_request_status !== "Pending") {
            frm.add_custom_button(__("📅 Browse & Book Slots"), () => {
                const mentor  = frm.doc.mentor;
                const student = frm.doc.student || frappe.session.user;
                if (!mentor) { frappe.msgprint(__("Please select a Mentor first.")); return; }
                new SlotCalendar({
                    mentor, student,
                    offering: frm.doc.offering || null,
                    onBooked(sessionName, date, slot) {
                        if (frm.is_new()) {
                            frm.set_value("session_date", date);
                            frm.set_value("from_time",    slot.from_time);
                            frm.set_value("to_time",      slot.to_time);
                            frappe.set_route("Form", "Mentor Session Booking", sessionName);
                        } else {
                            frm.reload_doc();
                        }
                    },
                }).open();
            });
        }

        if (isGroup && frm.doc.offering && frm.is_new()) {
            frm.add_custom_button(__("🗓 View Group Slots"), () => {
                _open_group_slot_picker(frm);
            });
        }

        // ── Review button ─────────────────────────────────────────────
        if (frm.doc.offering_type === "Offering" &&
            frm.doc.status        === "Completed" &&
            frm.doc.docstatus     === 1 &&
            !frm.doc.rating) {
            frm.add_custom_button(__("⭐ Submit Review"), () => {
                _submit_review_dialog(frm);
            });
        }
    },

    // ── offering field handler — also triggers button re-render ──────
    offering(frm) {
        if (frm.doc.offering) {
            frappe.db.get_value(
                "Mentor Offering",
                frm.doc.offering,
                ["price_per_session", "mentor", "offering_type"],
                (r) => {
                    if (r) {
                        frm.set_value("amount_paid",    r.price_per_session);
                        frm.set_value("mentor",         r.mentor);
                        frm.set_value("offering_type",  r.offering_type);
                        frm.set_df_property("mentor",   "read_only", 1);
                        // Re-render so correct buttons appear
                        frm.refresh();
                    }
                }
            );
        } else {
            frm.set_df_property("mentor", "read_only", 0);
            frm.refresh();
        }
    },

    mentor(frm) {
        frm.set_value("from_time", null);
        frm.set_value("to_time", null);
        if (frm.doc.mentor && frm.doc.session_date) open_slot_calendar(frm);
    },

    session_date(frm) {
        const today = frappe.datetime.get_today();
        if (frm.doc.session_date && frm.doc.session_date < today) {
            frappe.show_alert({ message: __("Session date cannot be in the past."), indicator: "red" });
            frm.set_value("session_date", null);
            return;
        }
        if (frm.doc.mentor && frm.doc.session_date) open_slot_calendar(frm);
    },

    from_time(frm) { _validate_time_range(frm); _auto_duration(frm); },
    to_time(frm)   { _validate_time_range(frm); _auto_duration(frm); },
    status(frm)    { _set_status_indicator(frm); },
});


// ─────────────────────────────────────────────────────────────────────────────
// Private Helpers
// ─────────────────────────────────────────────────────────────────────────────

function _validate_time_range(frm) {
    const { from_time, to_time } = frm.doc;
    if (from_time && to_time && from_time >= to_time) {
        frappe.show_alert({ message: __("From Time must be earlier than To Time."), indicator: "red" });
    }
}

function _auto_duration(frm) {
    const { from_time, to_time } = frm.doc;
    if (!from_time || !to_time) return;
    const mins = (t) => { const [h, m] = t.split(":").map(Number); return h * 60 + m; };
    const diff = mins(to_time) - mins(from_time);
    if (diff > 0) frm.set_value("duration", diff);
}

function _set_status_indicator(frm) {
    const map = { Scheduled: "blue", Completed: "green", Cancelled: "red" };
    frm.page && frm.page.set_indicator(frm.doc.status, map[frm.doc.status] || "grey");
}

function _toggle_meeting_link(frm) {
    frm.set_df_property("meeting_link", "hidden", !frm.doc.meeting_link);
}

function _render_action_buttons(frm) {
    // Clear all custom action buttons first
    [
        "Reschedule", "Cancel Session", "Mark as Completed",
        "Cancel Booking", "Accept Request", "Decline Request", "Suggest Alt Time",
        "Confirm Alt Time"
    ].forEach((b) => frm.remove_custom_button(__(b)));

    if (frm.is_new()) return;

    const reqStatus = frm.doc.mentor_request_status;
    const isMentor  = frappe.session.user === frm.doc.mentor;
    const isStudent = frappe.session.user === frm.doc.student;

    // ── Request stage actions ─────────────────────────────────────────
    if (reqStatus === "Pending" && isMentor) {
        // Mentor sees: Accept (opens slot calendar), Decline, Suggest Alt Time
        frm.add_custom_button(__("✅ Accept Request"), () => {
            _open_accept_calendar(frm);
        }, __("Request"));

        frm.add_custom_button(__("❌ Decline Request"), () => {
            _decline_request_dialog(frm);
        }, __("Request"));

        frm.add_custom_button(__("🕐 Suggest Alt Time"), () => {
            _suggest_alt_time_dialog(frm);
        }, __("Request"));
    }

    if (reqStatus === "Suggested Alt Time" && isStudent) {
        // Student sees: Confirm alt time or Cancel
        frm.add_custom_button(__("✅ Confirm Alt Time"), () => {
            frappe.confirm(
                __("Confirm the mentor's suggested time: {0} at {1}?", [
                    frm.doc.alt_date, frm.doc.alt_time
                ]),
                () => {
                    frappe.call({
                        method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.student_confirm_alt_time`,
                        args: { booking_name: frm.doc.name },
                        callback() {
                            frappe.show_alert({ message: __("Alt time confirmed. Waiting for mentor to schedule."), indicator: "green" });
                            frm.reload_doc();
                        }
                    });
                }
            );
        }, __("Request"));

        frm.add_custom_button(__("❌ Cancel Request"), () => {
            _decline_request_dialog(frm);
        }, __("Request"));
    }

    // ── Confirmed booking actions (request accepted or direct booking) ─
    if (frm.doc.status === "Scheduled" && !reqStatus || reqStatus === "Accepted") {
        frm.add_custom_button(__("Reschedule"),        () => open_reschedule_calendar(frm), __("Actions"));
        frm.add_custom_button(__("Cancel Session"),    () => _cancel_session(frm),           __("Actions"));
        frm.add_custom_button(__("Mark as Completed"), () => _mark_completed(frm),           __("Actions"));
    }

    // ── Submitted offering booking ────────────────────────────────────
    if (frm.doc.docstatus === 1 && frm.doc.offering_type === "Offering") {
        if (frm.doc.status !== "Completed") {
            frm.add_custom_button(__("Mark as Completed"), () => {
                _update_booking_status(frm, "Completed");
            }, __("Actions"));
        }
        if (frm.doc.status !== "Cancelled") {
            frm.add_custom_button(__("Cancel Booking"), () => {
                _update_booking_status(frm, "Cancelled");
            }, __("Actions"));
        }
    }
}

// ── Review dialog (Offering bookings only) ─────────────────────────────────

function _submit_review_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Submit Review"),
        fields: [
            { fieldtype: "Float",      fieldname: "rating",      label: __("Rating (1–5)"), reqd: 1 },
            { fieldtype: "Small Text", fieldname: "review_text", label: __("Review"),       reqd: 1 },
        ],
        primary_action_label: __("Submit"),
        primary_action(values) {
            frappe.call({
                method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.submit_review`,
                args: {
                    booking_name: frm.doc.name,
                    rating:       values.rating,
                    review_text:  values.review_text,
                },
                callback(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({ message: __("Review submitted!"), indicator: "green" });
                        frm.reload_doc();
                        d.hide();
                    }
                },
            });
        },
    });
    d.show();
}

function _update_booking_status(frm, status) {
    frappe.call({
        method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.update_status`,
        args: { booking_name: frm.doc.name, status },
        callback(r) {
            if (r.message) {
                frappe.show_alert({ message: __("Status updated to " + status), indicator: "green" });
                frm.reload_doc();
            }
        },
    });
}

// ── Slot calendar helpers ──────────────────────────────────────────────────

function open_slot_calendar(frm) {
    const mentor  = frm.doc.mentor;
    const student = frm.doc.student || frappe.session.user;
    if (!mentor) { frappe.msgprint(__("Please select a Mentor first.")); return; }

    new SlotCalendar({
        mentor,
        student,
        offering: frm.doc.offering || null,
        onBooked(sessionName, date, slot) {
            if (frm.is_new()) {
                frm.set_value("session_date", date);
                frm.set_value("from_time", slot.from_time);
                frm.set_value("to_time", slot.to_time);
                frappe.set_route("Form", "Mentor Session Booking", sessionName);
            } else {
                frm.reload_doc();
            }
        },
    }).open();
}

function open_reschedule_calendar(frm) {
    new SlotCalendar({
        mentor:      frm.doc.mentor,
        student:     frm.doc.student,
        offering:    frm.doc.offering || null,
        isReschedule: true,
        onBooked(sessionName, date, slot) {
            frappe.call({
                method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.reschedule_session`,
                args: {
                    session_name:  frm.doc.name,
                    new_date:      date,
                    new_from_time: slot.from_time,
                    new_to_time:   slot.to_time,
                },
                callback: () => {
                    frappe.show_alert({ message: "Session Rescheduled", indicator: "green" });
                    frm.reload_doc();
                },
            });
        },
    }).open();
}

function _cancel_session(frm) {
    frappe.confirm(__("Cancel session {0}?", [frm.doc.name]), () => {
        frappe.call({
            method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.cancel_session`,
            args: { session_name: frm.doc.name },
            callback({ message }) {
                frappe.show_alert({ message, indicator: "green" });
                frm.reload_doc();
            },
        });
    });
}

// ── Replace _mark_completed function ─────────────────────────────────────────

function _mark_completed(frm) {
    frappe.confirm(__("Mark {0} as Completed?", [frm.doc.name]), () => {
        frappe.call({
            method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.mark_session_completed`,
            args: { session_name: frm.doc.name },
            callback({ message }) {
                frappe.show_alert({ message, indicator: "green" });
                frm.reload_doc();

                // ── Show updated mentor stats as a toast ──────────────
                // Fetch fresh stats and display them
                frappe.db.get_value(
                    "Mentor",   // ← change to your mentor doctype
                    frm.doc.mentor,
                    ["total_sessions", "total_hours", "total_earnings", "avg_rating"],
                    (r) => {
                        if (r && r.total_sessions !== undefined) {
                            frappe.show_alert({
                                message: __(
                                    "📊 Mentor Stats Updated — Sessions: {0} | Hours: {1} | Earnings: ₹{2} | Rating: {3}⭐",
                                    [r.total_sessions, r.total_hours, r.total_earnings, r.avg_rating]
                                ),
                                indicator: "blue",
                            });
                        }
                    }
                );
            },
        });
    });
}

// ── Replace _open_group_slot_picker ──────────────────────────────────────────

// ─────────────────────────────────────────────────────────────────────────────
// Group Session — Batch Picker
// ─────────────────────────────────────────────────────────────────────────────

function _open_group_slot_picker(frm) {
    if (!frm.doc.offering) {
        frappe.msgprint(__("Please select an Offering first."));
        return;
    }

    frappe.call({
        method: `${APP}.${APP}.doctype.mentor_offering.mentor_offering.get_open_batches_for_offering`,
        args:   { offering: frm.doc.offering },
        freeze: true,
        freeze_message: __("Loading available batches…"),
        callback({ message: batches }) {
            if (!batches || !batches.length) {
                frappe.msgprint(__("No open batches available. Ask your mentor to publish a batch first."));
                return;
            }
            _show_batch_picker_dialog(frm, batches);
        },
        error(err) {
            // Show the server-side frappe.throw message clearly
            frappe.msgprint({
                title:     __("Cannot Load Batches"),
                message:   err.message || __("Failed to load batch list."),
                indicator: "orange"
            });
        }
    });
}


function _show_batch_picker_dialog(frm, batches) {
    const d = new frappe.ui.Dialog({
        title: __("Join a Group Session Batch"),
        size:  "large",
    });

    const cards = batches.map((b, idx) => {
        const isFull  = b.is_full;
        const start   = b.start_date ? frappe.datetime.str_to_user(b.start_date) : "TBD";
        const end     = b.end_date   ? frappe.datetime.str_to_user(b.end_date)   : "TBD";
        const seatTxt = b.seat_count
            ? `${b.seats_left} seat(s) left  (${b.current_count}/${b.seat_count})`
            : `${b.current_count} enrolled  (unlimited seats)`;

        return `
        <div style="
            border: 1.5px solid ${isFull ? "#fca5a5" : "#86efac"};
            border-radius: 10px; padding: 16px 18px; margin-bottom: 12px;
            background: ${isFull ? "#fef2f2" : "#f0fdf4"};
            display: flex; align-items: center; justify-content: space-between; gap: 12px;
        ">
            <div style="flex:1">
                <strong style="font-size:14px; color:#1e2a4a">${b.title || b.name}</strong><br>
                <span style="font-size:12px; color:#6b7280">📅 ${start} → ${end}</span><br>
                <span style="font-size:12px; color:${isFull ? "#ef4444" : "#16a34a"}; font-weight:600">
                    ${isFull ? "🔴 Full" : "🟢 " + seatTxt}
                </span>
                ${b.description
                    ? `<br><span style="font-size:11px;color:#9ca3af;margin-top:4px;display:block">${b.description}</span>`
                    : ""}
            </div>
            <button
                data-idx="${idx}"
                class="msb-join-btn"
                ${isFull ? "disabled" : ""}
                style="
                    background: ${isFull ? "#e5e7eb" : "#1e2a4a"};
                    color: ${isFull ? "#9ca3af" : "#fff"};
                    border: none; border-radius: 8px;
                    padding: 10px 22px; font-size: 13px; font-weight: 700;
                    cursor: ${isFull ? "not-allowed" : "pointer"};
                    white-space: nowrap; flex-shrink: 0;
                "
            >
                ${isFull ? "Full" : "Join Batch"}
            </button>
        </div>`;
    }).join("");

    d.$body.html(`<div style="padding: 8px 4px">${cards}</div>`);

    d.$body.find(".msb-join-btn:not([disabled])").on("click", function () {
        const batch = batches[parseInt($(this).data("idx"))];
        d.hide();
        _confirm_join_batch(frm, batch);
    });

    d.show();
}


function _confirm_join_batch(frm, batch) {
    const startLabel = batch.start_date
        ? frappe.datetime.str_to_user(batch.start_date)
        : batch.name;

    frappe.confirm(
        __('Join batch "{0}" starting {1}?', [batch.title || batch.name, startLabel]),
        () => {
            const student = frm.doc.student || frappe.session.user;

            // ── Step 1: LMS enrollment (add to Batch Student + LMS Enrollment) ──
            frappe.call({
                method: `${APP}.${APP}.doctype.mentor_offering.mentor_offering.enroll_student_in_batch`,
                args: {
                    offering:   frm.doc.offering,
                    batch_name: batch.name,
                    student,
                },
                freeze:         true,
                freeze_message: __("Enrolling in batch…"),
                callback({ message: lms_result }) {

                    // ── Step 2: Create Mentor Session Booking record ──────────
                    frappe.call({
                        method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.create_group_session_booking`,
                        args: {
                            offering:   frm.doc.offering,
                            batch_name: batch.name,
                            student,
                        },
                        callback({ message: booking_result }) {
                            frappe.show_alert({
                                message: __(
                                    "✅ Enrolled! Booking: {0}  |  {1} seat(s) left",
                                    [booking_result.session_name, lms_result.seats_left]
                                ),
                                indicator: "green",
                            });
                            frappe.set_route(
                                "Form", "Mentor Session Booking",
                                booking_result.session_name
                            );
                        },
                        error(err) {
                            frappe.msgprint({
                                title:     __("Booking Error"),
                                message:   err.message || __("Could not create booking record."),
                                indicator: "red"
                            });
                        }
                    });
                },
                error(err) {
                    frappe.msgprint({
                        title:     __("Enrollment Error"),
                        message:   err.message || __("Could not enroll in batch."),
                        indicator: "red"
                    });
                }
            });
        }
    );
}

// ─────────────────────────────────────────────────────────────────────────────
// Request Flow Dialogs
// ────────────────────────────────────────────────────────────────────────────────

function _open_accept_calendar(frm) {
    // Reuse SlotCalendar — mentor picks a confirmed slot to accept with
    const cal = new SlotCalendar({
        mentor:      frm.doc.mentor,
        student:     frm.doc.student,
        offering:    frm.doc.offering || null,
        isReschedule: true,   // no topic input needed
        onBooked(sessionName, date, slot) {
            // sessionName is null in reschedule mode — call accept_request directly
            frappe.call({
                method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.accept_request`,
                args: {
                    booking_name: frm.doc.name,
                    session_date: date,
                    from_time:    slot.from_time,
                    to_time:      slot.to_time,
                },
                callback({ message }) {
                    frappe.show_alert({
                        message:   __("✅ Request accepted! Booking: {0}", [message.booking_name]),
                        indicator: "green",
                    });
                    frm.reload_doc();
                },
            });
            cal.close();
        },
    });
    cal.open();
}


function _decline_request_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Decline Request"),
        fields: [{
            fieldtype:  "Small Text",
            fieldname:  "notes",
            label:      __("Reason (optional)"),
        }],
        primary_action_label: __("Decline"),
        primary_action(values) {
            frappe.call({
                method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.decline_request`,
                args: {
                    booking_name: frm.doc.name,
                    notes:        values.notes || "",
                },
                callback() {
                    frappe.show_alert({ message: __("Request declined."), indicator: "orange" });
                    frm.reload_doc();
                    d.hide();
                },
            });
        },
    });
    d.show();
}


function _suggest_alt_time_dialog(frm) {
    const d = new frappe.ui.Dialog({
        title: __("Suggest Alternate Time"),
        fields: [
            {
                fieldtype: "Date",
                fieldname: "alt_date",
                label:     __("Suggested Date"),
                reqd:      1,
                default:   frm.doc.requested_date,
            },
            {
                fieldtype: "Time",
                fieldname: "alt_time",
                label:     __("Suggested Time"),
                reqd:      1,
                default:   frm.doc.requested_time,
            },
            {
                fieldtype: "Small Text",
                fieldname: "notes",
                label:     __("Message to student (optional)"),
            },
        ],
        primary_action_label: __("Send Suggestion"),
        primary_action(values) {
            frappe.call({
                method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.suggest_alt_time`,
                args: {
                    booking_name: frm.doc.name,
                    alt_date:     values.alt_date,
                    alt_time:     values.alt_time,
                    notes:        values.notes || "",
                },
                callback() {
                    frappe.show_alert({
                        message:   __("Alternate time suggested to student."),
                        indicator: "blue",
                    });
                    frm.reload_doc();
                    d.hide();
                },
            });
        },
    });
    d.show();
}


// ── Student-facing: create a new request from an offering ─────────────────────
// Call this from the student portal / offering page JS

function _open_request_dialog(mentor, offering, student) {
    const d = new frappe.ui.Dialog({
        title: __("Request a Session"),
        fields: [
            {
                fieldtype: "Date",
                fieldname: "requested_date",
                label:     __("Preferred Date"),
                reqd:      1,
            },
            {
                fieldtype: "Time",
                fieldname: "requested_time",
                label:     __("Preferred Time"),
            },
            {
                fieldtype: "Data",
                fieldname: "topic",
                label:     __("Topic"),
                reqd:      1,
            },
            {
                fieldtype: "Small Text",
                fieldname: "student_message",
                label:     __("Message to Mentor (optional)"),
            },
        ],
        primary_action_label: __("Send Request"),
        primary_action(values) {
            frappe.call({
                method: `${APP}.${APP}.doctype.mentor_session_booking.mentor_session_booking.create_session_request`,
                args: {
                    mentor,
                    student:          student || frappe.session.user,
                    offering,
                    topic:            values.topic,
                    requested_date:   values.requested_date,
                    requested_time:   values.requested_time || null,
                    student_message:  values.student_message || null,
                },
                callback({ message }) {
                    frappe.show_alert({
                        message:   __("✅ Request sent! ID: {0}", [message.booking_name]),
                        indicator: "green",
                    });
                    d.hide();
                },
                error(err) {
                    frappe.msgprint({
                        title:     __("Error"),
                        message:   err.message,
                        indicator: "red",
                    });
                },
            });
        },
    });
    d.show();
}

